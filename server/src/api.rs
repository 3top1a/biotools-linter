use axum::{
    extract::{ConnectInfo, Query, State},
    response::Html,
    Json,
};
use chrono::{DateTime, Utc};
use db::DatabaseEntry;

use regex::Regex;
use serde::{Deserialize, Serialize};
use serde_json::{Map, Value};

use std::{
    fs,
    net::SocketAddr,
    time::{Duration, UNIX_EPOCH},
};
use tera::{Context, Tera};
use tokio::join;

use tracing::info;

use utoipa::{IntoParams, ToSchema};

use serde_repr::{Deserialize_repr, Serialize_repr};

use crate::db;
use crate::ServerState;

// Initialize and cache templates and regex
lazy_static! {
    pub static ref TEMPLATES: Tera = {
        match Tera::new("templates/*.html") {
            Ok(t) => t,
            Err(e) => {
                println!("Parsing error(s): {e}");
                ::std::process::exit(1);
            }
        }
    };
    pub static ref LINK_REGEX: Regex = {
        Regex::new(
            r"(http[s]?|ftp)://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+(?:\#[^\s]*)?",
        )
        .unwrap()
    };
}
#[derive(Debug, Serialize_repr, Deserialize_repr, ToSchema)]
#[repr(u8)]
/// Enumerable severity score
/// - Error (1) -> Obsolete, no longer used
/// - LinterError (2) -> Uncaught linter error
/// - ReportCritical (4) -> Indicates a critical error reserved for security vulnerabilities.
/// - ReportHigh (5) -> Represents a high-severity error.
/// - ReportMedium (6) -> Represents a medium-severity error.
/// - ReportLow (7) -> Represents a low-severity error.
pub enum Severity {
    /// Obsolete, no longer used
    Error = 1,
    /// Uncaught linter error
    LinterError = 2,
    /// Indicates a critical error reserved for security vulnerabilities.
    ReportCritical = 4,
    /// Represents a high-severity error.
    ReportHigh = 5,
    /// Represents a medium-severity error.
    ReportMedium = 6,
    /// Represents a low-severity error.
    ReportLow = 7,
}

impl From<i32> for Severity {
    fn from(value: i32) -> Self {
        match value {
            2 => Self::LinterError,
            4 => Self::ReportCritical,
            5 => Self::ReportHigh,
            6 => Self::ReportMedium,
            7 => Self::ReportLow,
            _ => Self::Error,
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
    // Optional severity, TODO
    //severity: Option<u8>,
}

/// Represents a single result in the API response.
#[derive(Debug, Serialize, ToSchema)]
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

/// Statistics data
#[derive(Serialize, Deserialize, ToSchema)]
pub struct Statistics {
    pub data: Vec<StatisticsEntry>,
}

#[derive(Serialize, Deserialize, ToSchema)]
pub struct StatisticsEntry {
    pub time: u64,
    pub total_count_on_biotools: u64,
    pub total_errors: u64,
    pub unique_tools: u64,
    pub error_types: Map<String, Value>,
}

/// Represents the response sent to web clients.
#[derive(Debug, Serialize, ToSchema)]
pub struct ApiResponse {
    /// The number of results returned by the query.
    count: i64,
    /// `null` if there is no next page, otherwise returns `?page={page + 1}`
    next: Option<String>,
    /// `null` if there is no previous page, otherwise returns `?page={page - 1}`
    previous: Option<String>,
    /// A list of results matching the query.
    results: Vec<Message>,
}

/// Serve the main page
pub async fn serve_index_page(State(state): State<ServerState>) -> Html<String> {
    // Simple statistics, multiple futures executing at once
    let (error_count, oldest_entry_unix, tool_count) = tokio::join!(
        db::count_total_messages(&state.pool),
        db::get_oldest_entry_unix(&state.pool),
        db::count_total_unique_tools(&state.pool),
    );

    // Timestamp
    let d = UNIX_EPOCH + Duration::from_secs(oldest_entry_unix.try_into().unwrap());
    let datetime = DateTime::<Utc>::from(d);
    let timestamp = datetime.format("%Y-%m-%d %H:%M").to_string();

    let mut c = Context::new();
    c.insert("error_count", &error_count);
    c.insert("tool_count", &tool_count);
    c.insert("last_time", &timestamp);
    c.insert("search_value", "");

    Html(TEMPLATES.render("index.html", &c).unwrap())
}

/// Serve the stats page
pub async fn serve_statistics_page() -> Html<String> {
    let c = Context::new();
    Html(TEMPLATES.render("statistics.html", &c).unwrap())
}

/// Serve statistics JSON data
#[utoipa::path(
    get,
    path = "/api/statistics",
    responses(
         (status = 200, description = "Request successful", body = ApiResponse,
         ),
    ),
    params(
 ),
 )]
pub async fn serve_statistics_api(
    State(state): State<ServerState>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
) -> Json<Statistics> {
    // Get parameters
    info!("Listing statistics from `{}`", addr);

    let json_str =
        fs::read_to_string(state.stats_file_path).expect("Should have been able to read json file");

    let json: Statistics = serde_json::from_str(&json_str).expect("Could not parse JSON");

    return Json(json);
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
    State(state): State<ServerState>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    Query(params): Query<APIQuery>,
) -> Json<ApiResponse> {
    // Get parameters
    let page = params.page.unwrap_or(0);
    let query = params.query;

    info!(
        "Listing API from `{}` page {} query {:?}",
        addr, page, query
    );

    let (messages, total_count) = match query.clone() {
        None => {
            join!(
                db::get_messages_paginated(&state.pool, page),
                db::count_messages_paginated(&state.pool)
            )
        }
        Some(query) => {
            join!(
                db::get_messages_paginated_search(&state.pool, page, &query),
                db::count_messages_paginated_search(&state.pool, &query)
            )
        }
    };

    Json(ApiResponse {
        count: total_count,
        next: if page + 100 < total_count {
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
