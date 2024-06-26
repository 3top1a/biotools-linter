use axum::{
    extract::{Path, Query, State},
    http::{HeaderMap, StatusCode},
    response::Html,
    Json,
};
use chrono::{DateTime, Utc};
use db::DatabaseEntry;

use pulldown_cmark::{CowStr, Event, Tag};
use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

use axum::response::IntoResponse;
use std::{
    fs,
    io::Write,
    path::{Component, PathBuf},
    process::{Command, Stdio},
    str::FromStr,
    time::{Duration, UNIX_EPOCH},
};
use tera::{Context, Tera};
use tokio::join;

use tracing::{error, info};

use axum::http::header;
use utoipa::{IntoParams, ToSchema};

use serde_repr::{Deserialize_repr, Serialize_repr};
use sitewriter::{ChangeFreq, UrlEntry};

use crate::db;
use crate::ServerState;

/// Macro to log important information on a http method
/// Needs `headers: HeaderMap` in argument
macro_rules! info_statement {
    ($headers:tt, $name:tt, $($arg:tt)*) => {
        // Get sender IP, prioritize X-Real-IP because of nginx
        let ip: String = match $headers.contains_key("X-Real-IP") {
            true => $headers
                .get("X-Real-IP")
                .unwrap()
                .to_str()
                .unwrap()
                .to_string(),
            false => String::from("?"),
        };

        let ua: String = match $headers.contains_key("User-Agent") {
            true => $headers
                .get("User-Agent")
                .unwrap()
                .to_str()
                .unwrap()
                .to_string(),
            false => String::from("?"),
        };

        let custom_message = format!($($arg)*);

        info!("HTTP {} ({custom_message}) FROM IP `{ip}` UA `{ua}`", $name);
    };
}

static ERROR_CODES: [&str; 25] = [
    "URL_INVALID",
    "URL_PERMANENT_REDIRECT",
    "URL_BAD_STATUS",
    "URL_NO_SSL",
    "URL_UNUSED_SSL",
    "URL_TIMEOUT",
    "URL_SSL_ERROR",
    "URL_CONN_ERROR",
    "URL_LINTER_ERROR",
    "EDAM_OBSOLETE",
    "EDAM_NOT_RECOMMENDED",
    "EDAM_INVALID",
    "DOI_BUT_NOT_PMID",
    "DOI_BUT_NOT_PMCID",
    "PMID_BUT_NOT_DOI",
    "PMCID_BUT_NOT_DOI",
    "PMCID_BUT_NOT_PMID",
    "URL_TOO_MANY_REDIRECTS",
    "EDAM_TOPIC_DISCREPANCY",
    "EDAM_INPUT_DISCREPANCY",
    "EDAM_OUTPUT_DISCREPANCY",
    "PMID_DISCREPANCY",
    "PMCID_DISCREPANCY",
    "DOI_DISCREPANCY",
    "EDAM_FORMAT_DISCREPANCY",
];

// Initialize and cache templates and regex
lazy_static! {
    pub static ref TEMPLATES: Tera = {
        match Tera::new("templates/*.html") {
            Ok(t) => t,
            Err(e) => {
                panic!("Parsing error(s): {e}");
            }
        }
    };
    pub static ref LINK_REGEX: Regex = {
        Regex::new(
            r"(http[s]?|ftp)://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+(?:(?:\#[^\s]*)?[^)\s'])",
        )
        .unwrap()
    };
}

#[derive(Debug, Serialize_repr, Deserialize_repr, ToSchema, Clone, Copy)]
#[repr(u8)]
/// Enumerable severity score
/// - Error (1) -> Obsolete, no longer used
/// - LinterError (2) -> Uncaught linter error
/// - ReportCritical (4) -> Indicates a critical error reserved for security vulnerabilities.
/// - ReportHigh (5) -> Represents a high-severity error.
/// - ReportMedium (6) -> Represents a medium-severity error.
/// - ReportLow (7) -> Represents a low-severity error.
pub enum Severity {
    /// Obsolete, now used as an API error
    #[serde(rename = "Error")]
    Error = 1,
    /// Uncaught linter error
    #[serde(rename = "LinterError")]
    LinterError = 2,
    /// Indicates a critical error reserved for security vulnerabilities.
    #[serde(rename = "ReportCritical")]
    ReportCritical = 8,
    /// Represents a high-severity error.
    #[serde(rename = "ReportHigh")]
    ReportHigh = 5,
    /// Represents a medium-severity error.
    #[serde(rename = "ReportMedium")]
    ReportMedium = 6,
    /// Represents a low-severity error.
    #[serde(rename = "ReportLow")]
    ReportLow = 7,
}

impl From<i32> for Severity {
    fn from(value: i32) -> Self {
        match value {
            2 => Self::LinterError,
            8 => Self::ReportCritical,
            5 => Self::ReportHigh,
            6 => Self::ReportMedium,
            7 => Self::ReportLow,
            _ => Self::Error,
        }
    }
}
impl From<Severity> for i32 {
    fn from(value: Severity) -> Self {
        match value {
            Severity::LinterError => 2,
            Severity::ReportCritical => 8,
            Severity::ReportHigh => 5,
            Severity::ReportMedium => 6,
            Severity::ReportLow => 7,
            Severity::Error => 1,
        }
    }
}

/// Represents the query parameters needed by the API.
#[derive(Deserialize, IntoParams)]
pub struct APIQuery {
    /// A search string used to filter messages (optional).
    ///
    /// If provided, the API will return errors where the tool or error code matches the query (Case insensitive)
    query: Option<String>,

    /// The page number for pagination (optional).
    ///
    /// Each page contains up to 100 messages. Use this field to specify the
    /// desired page number when retrieving results.
    #[param(style = Simple, minimum = 0)]
    page: Option<i64>,

    /// Optional severity filter
    severity: Option<Severity>,

    /// Optional error code filter
    code: Option<String>,
}

#[derive(Deserialize, IntoParams)]
pub struct DownloadParams {
    /// A search string used to filter messages (optional).
    query: Option<String>,
}

/// Represents a single result in the API response.
#[derive(Debug, Serialize, Deserialize, ToSchema)]
pub struct Message {
    /// Unix timestamp when the error was found
    time: i64,
    /// A human-readable timestamp formatted as `%Y-%m-%d %H:%M`.
    timestamp: String,
    /// The ID of the tool to which the error belongs (valid biotools ID).
    tool: String,
    /// Error code
    code: String,
    /// Human readable error
    text: String,
    /// The severity level of the error.
    ///
    /// - `4` indicates a critical error reserved for security vulnerabilities.
    /// - `5` represents a high-severity error.
    /// - `6` represents a medium-severity error.
    /// - `7` represents a low-severity error.
    severity: Severity,
}

/// Convert a database entry into the api message
impl From<DatabaseEntry> for Message {
    fn from(value: DatabaseEntry) -> Self {
        let mut v = value;

        // Escape
        v.tool = html_escape::encode_text(&v.tool).to_string();
        v.code = html_escape::encode_text(&v.code).to_string();
        v.location = html_escape::encode_text(&v.location).to_string();

        // Autolink
        let processed_text = LINK_REGEX
            .replace_all(&v.text, |caps: &regex::Captures| {
                let url = caps.get(0).unwrap().as_str();
                format!("<a href=\"{url}\" rel=\"nofollow\" >{url}</a>")
            })
            .to_string();

        // Timestamp
        let d = UNIX_EPOCH + Duration::from_secs(v.time.try_into().unwrap());
        let datetime = DateTime::<Utc>::from(d);
        let timestamp = datetime.format("%Y-%m-%d %H:%M").to_string();

        Self {
            code: v.code,
            tool: v.tool,
            text: processed_text,
            timestamp,
            time: v.time,
            #[allow(clippy::cast_possible_truncation)]
            severity: Severity::from(v.level),
        }
    }
}

/// Statistics data sent from the API
#[derive(Serialize, Deserialize, ToSchema)]
pub struct Statistics {
    pub data: Vec<StatisticsEntry>,
}

/// A single statistics entry
#[derive(Serialize, Deserialize, ToSchema)]
pub struct StatisticsEntry {
    pub time: u64,
    pub total_count_on_biotools: u64,
    pub total_errors: u64,
    pub unique_tools: u64,
    pub error_types: Map<String, Value>,
    pub severity: Option<Map<String, Value>>,
}

/// Represents the response sent to web clients.
#[derive(Debug, Serialize, Deserialize, ToSchema)]
pub struct ApiResponse {
    /// The number of results returned by the query.
    pub count: i64,
    /// `null` if there is no next page, otherwise returns `?page={page + 1}`
    pub next: Option<String>,
    /// `null` if there is no previous page, otherwise returns `?page={page - 1}`
    pub previous: Option<String>,
    /// A list of results matching the query.
    pub results: Vec<Message>,
}

/// Relint parameters
#[derive(Deserialize, IntoParams)]
pub struct RelintParams {
    tool: String,
}

/// JSON parameters
#[derive(Deserialize, IntoParams)]
pub struct JSONParams {
    biotools_format: Option<bool>,
}

/// Serve the main page
pub async fn serve_index_page(
    headers: HeaderMap,
    State(state): State<ServerState>,
) -> Html<String> {
    info_statement!(headers, "WWW-INDEX", "");

    // Simple statistics, multiple futures executing at once
    let (error_count, oldest_entry_unix, tool_count, critical_count) = tokio::join!(
        db::count_total_messages(&state.pool),
        db::get_oldest_entry_unix(&state.pool),
        db::count_total_unique_tools(&state.pool),
        db::count_critical_messages(&state.pool),
    );

    // Timestamp
    let d = UNIX_EPOCH + Duration::from_secs(oldest_entry_unix.try_into().unwrap());
    let datetime = DateTime::<Utc>::from(d);
    let timestamp = datetime.format("%Y-%m-%d %H:%M").to_string();

    let mut c = Context::new();
    c.insert("critical_count", &critical_count);
    c.insert("error_count", &error_count);
    c.insert("tool_count", &tool_count);
    c.insert("last_time", &timestamp);
    c.insert("search_value", "");

    Html(TEMPLATES.render("index.html", &c).unwrap())
}

/// Serve the stats page
pub async fn serve_statistics_page(headers: HeaderMap) -> Html<String> {
    info_statement!(headers, "WWW-STATISTICS", "");

    let c = Context::new();
    Html(TEMPLATES.render("statistics.html", &c).unwrap())
}

fn parse_markdown(md: &String) -> String {
    let parser = pulldown_cmark::Parser::new(md);

    // https://github.com/raphlinus/pulldown-cmark/issues/407
    // This adds anchors to headers
    let mut heading_level = 0;
    let parser = parser.filter_map(|event| match event {
        Event::Start(Tag::Heading(level, _, _)) => {
            heading_level = level as usize;
            None
        }
        Event::Text(text) => {
            if heading_level != 0 {
                let anchor = text.clone().into_string().trim().replace(' ', "_");
                let tmp = Event::Html(CowStr::from(format!(
                    "<h{} id=\"{}\">{}",
                    heading_level, anchor, text
                )))
                .into();
                heading_level = 0;
                return tmp;
            }
            Some(Event::Text(text))
        }
        _ => Some(event),
    });

    let mut html_output = String::new();
    pulldown_cmark::html::push_html(&mut html_output, parser);
    html_output
}

pub async fn serve_documentation_page(
    headers: HeaderMap,
    Path(query_title): Path<String>,
) -> Html<String> {
    info_statement!(headers, "WWW-DOCUMENTATION", "{query_title}");

    // https://stackoverflow.com/questions/56366947/how-does-a-rust-pathbuf-prevent-directory-traversal-attacks
    let mut p = PathBuf::from_str(&query_title).unwrap();
    if p.components().any(|x| x == Component::ParentDir) {
        let c = Context::new();
        return Html(TEMPLATES.render("error.html", &c).unwrap());
    }

    if p.to_str() == Some("") {
        p = PathBuf::from_str("index.md").unwrap();
    }

    let p = p.with_extension("md");

    let markdown_path = PathBuf::from_str("documentation/").unwrap().join(p);
    let markdown_string = fs::read_to_string(markdown_path).unwrap();

    let html = parse_markdown(&markdown_string);

    let mut c = Context::new();
    c.insert("content", &html);
    Html(TEMPLATES.render("documentation.html", &c).unwrap())
}

pub async fn serve_documentation_index(headers: HeaderMap) -> Html<String> {
    info_statement!(headers, "WWW-DOCUMENTATION", "");

    let markdown_path = PathBuf::from_str("documentation/index.md").unwrap();
    let markdown_string = fs::read_to_string(markdown_path).unwrap();

    let html = parse_markdown(&markdown_string);

    let mut c = Context::new();
    c.insert("content", &html);
    Html(TEMPLATES.render("documentation.html", &c).unwrap())
}

/// Serve statistics JSON data
#[utoipa::path(
    get,
    path = "/api/statistics",
    responses(
         (status = 200, description = "Request successful", body = Statistics,
         ),
    ),
    params(
 ),
 )]
pub async fn serve_statistics_api(
    headers: HeaderMap,
    State(state): State<ServerState>,
) -> Json<Statistics> {
    info_statement!(headers, "API-STATISTICS", "");

    let json_str =
        fs::read_to_string(state.stats_file_path).expect("Should have been able to read json file");

    let mut json: Statistics = serde_json::from_str(&json_str).expect("Could not parse JSON");

    // Make entries have all error types even if they will be null
    for entry in &mut json.data {
        for code in ERROR_CODES {
            if !entry.error_types.contains_key(code) {
                entry.error_types.insert(code.to_owned(), Value::Null);
            }
        }
    }

    Json(json)
}

/// List every error or search for a specific one
#[utoipa::path(
   get,
   path = "/api/search",
   responses(
        (status = 200, description = "Search successful", body = ApiResponse,
        ),
   ),
   params(
    APIQuery
),
)]
pub async fn serve_search_api(
    headers: HeaderMap,
    State(state): State<ServerState>,
    Query(params): Query<APIQuery>,
) -> Json<ApiResponse> {
    // Get parameters
    let query = params.query;
    let page = params.page.unwrap_or(0);
    let severity = params.severity;
    let code = params.code;

    info_statement!(
        headers,
        "API-SEARCH",
        "{:?}, {}, {:?}",
        query,
        page,
        severity
    );

    let code = match code {
        None => "%%".to_owned(),
        Some(x) => x,
    };

    let (messages, total_count) = match query.clone() {
        None => {
            join!(
                db::get_messages_paginated(&state.pool, page, severity, code.clone()),
                db::count_messages_paginated(&state.pool, severity, code)
            )
        }
        Some(query) => {
            join!(
                db::get_messages_paginated_search(
                    &state.pool,
                    page,
                    &query,
                    severity,
                    code.clone()
                ),
                db::count_messages_paginated_search(&state.pool, &query, severity, code)
            )
        }
    };

    Json(ApiResponse {
        count: total_count,
        next: if (page * 100) + 100 < total_count {
            Some(format!("?page={}", page + 1))
        } else {
            None
        },
        previous: if page > 0 {
            Some(format!("?page={}", page - 1))
        } else {
            None
        },
        results: messages,
    })
}

/// Relint a specific tool. Rate limited to 1 request every 2 seconds.
#[utoipa::path(post, path = "/api/lint", params(RelintParams))]
pub async fn relint_api(headers: HeaderMap, Query(params): Query<RelintParams>) -> StatusCode {
    let input = params.tool.trim();
    info_statement!(headers, "API-RELINT", "{}", input);

    // Escape injection attacks
    // Regex taken from https://biotools.readthedocs.io/en/latest/api_usage_guide.html?highlight=biotoolsid#biotoolsid
    let re = Regex::new(r"^[_\-.0-9a-zA-Z]*$").unwrap();
    if !re.is_match(input) {
        info!("Input did not pass regex, aborting");
        return StatusCode::INTERNAL_SERVER_ERROR;
    }

    if input.contains("--lint-all") {
        info!("Input contains -lint-all, aborting");
        return StatusCode::INTERNAL_SERVER_ERROR;
    }

    let script = "lint_from_server.sh";

    // Command takes arguments as literals so shell expansions is automatically escaped
    let output = Command::new("bash")
        .arg(script)
        .arg(input)
        .arg("--no-color")
        .arg("--exact")
        .current_dir("../")
        .output();

    info!("Output from script: {:?}", output);

    if let Ok(output) = output {
        return match output.status.success() {
            true => StatusCode::OK,
            false => {
                error!("{:#?}", output);

                return StatusCode::INTERNAL_SERVER_ERROR;
            }
        };
    }

    error!("{:#?}", output);

    StatusCode::INTERNAL_SERVER_ERROR
}

/// Lint JSON in the request body. Does not send found errors into the main database.
#[utoipa::path(post, path = "/api/json", request_body = String,
params(JSONParams),
responses(
    (status = 200, description = "JSON lint successfull", body = String,
    ),
),
)]
pub async fn json_api(
    headers: HeaderMap,
    params: Query<JSONParams>,
    json: String,
) -> impl IntoResponse {
    info_statement!(headers, "API-JSON", "");

    let script = "lint_from_server.sh";

    let extra_args = if params.biotools_format.unwrap_or_else(|| false) {
        ["--biotools-format"]
    } else {
        [""]
    };

    // Command takes arguments as literals so shell expansions is automatically escaped
    let mut child = Command::new("bash")
        .arg(script)
        .arg("--no-color")
        .arg("--json")
        .arg("--db=ignore")
        .arg("--exit-on-error")
        .args(extra_args)
        .current_dir("../")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("Failed to start command");

    let mut stdin = child.stdin.take().expect("Failed to open stdin");
    std::thread::spawn(move || {
        stdin
            .write_all(json.as_bytes())
            .expect("Failed to write to stdin");
    });

    let output = child.wait_with_output().expect("Failed to read stdout");

    if output.status.code().unwrap() == 1 {
        return (
            StatusCode::INTERNAL_SERVER_ERROR,
            [(header::CONTENT_TYPE, "text/json")],
            "\"error\": \"could not get data from linter\"".to_string(),
        );
    }

    info!("Output from script: {:?}", output);

    let str_output = String::from_utf8(output.stdout).unwrap();
    let code = match output.status.code().unwrap() {
        254 => StatusCode::BAD_REQUEST,
        _ => StatusCode::OK,
    };

    (
        code,
        [(header::CONTENT_TYPE, "text/json")],
        str_output,
    )
}

/// Download data as csv. Rate limited to 1 request every 2 seconds.
#[utoipa::path(get,
    path = "/api/download",
    params(DownloadParams),
    responses(
        (status = 200, description = "Downloaded CSV"),
    ),
)]
pub async fn download_api(
    headers: HeaderMap,
    State(state): State<ServerState>,
    Query(params): Query<DownloadParams>,
) -> impl IntoResponse {
    info_statement!(headers, "API-DOWNLOAD", "{:?}", params.query);

    let messages = match params.query {
        Some(query) => db::get_messages_all_search(&state.pool, &query).await,
        None => db::get_messages_all(&state.pool).await,
    };

    let header = String::from("time,timestamp,tool,code,severity,text\n");
    let data = messages
        .into_iter()
        .map(|x| {
            format!(
                "{},{},{},{},{},\"{}\"\n",
                x.time,
                x.timestamp,
                x.tool,
                x.code,
                x.severity as i32,
                x.text.replace('\n', "")
            )
        })
        .reduce(|acc, e| acc + &e)
        .unwrap();

    (
        StatusCode::OK,
        [(header::CONTENT_TYPE, "text/csv")],
        header + &data,
    )
}

pub async fn serve_sitemap(headers: HeaderMap) -> impl IntoResponse {
    info_statement!(headers, "WWW-SITEMAP", "");

    let manual_entries = vec![
        UrlEntry {
            loc: "https://biotools-linter.biodata.ceitec.cz/"
                .parse()
                .unwrap(),
            changefreq: Some(ChangeFreq::Daily),
            priority: Some(1.0),
            lastmod: Some(Utc::now()),
        },
        UrlEntry {
            loc: "https://biotools-linter.biodata.ceitec.cz/statistics"
                .parse()
                .unwrap(),
            changefreq: Some(ChangeFreq::Daily),
            priority: Some(0.8),
            lastmod: Some(Utc::now()),
        },
        UrlEntry {
            loc: "https://biotools-linter.biodata.ceitec.cz/docs"
                .parse()
                .unwrap(),
            changefreq: Some(ChangeFreq::Monthly),
            priority: Some(0.6),
            lastmod: None,
        },
        UrlEntry {
            loc: "https://biotools-linter.biodata.ceitec.cz/api/documentation/"
                .parse()
                .unwrap(),
            changefreq: Some(ChangeFreq::Monthly),
            priority: Some(0.6),
            lastmod: None,
        },
    ];

    // Auto generate ones for documentation
    // Reading from disk is fast enough, this whole function completes in 2ms on my machine
    let files = std::fs::read_dir("documentation/").unwrap();
    let docs_entries: Vec<UrlEntry> = files
        .map(|x| UrlEntry {
            loc: format!(
                "https://biotools-linter.biodata.ceitec.cz/docs/{}",
                x.unwrap().file_name().to_str().unwrap()
            )
            .parse()
            .unwrap(),
            changefreq: Some(ChangeFreq::Monthly),
            priority: Some(0.5),
            lastmod: None,
        })
        .collect();

    let result = sitewriter::generate_str(&[manual_entries, docs_entries].concat());

    (StatusCode::OK, [(header::CONTENT_TYPE, "text/xml")], result)
}
