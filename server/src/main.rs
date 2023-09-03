use axum::{
    extract::{ConnectInfo, Query, State},
    response::Html,
    routing::get,
    Json, Router,
};
use chrono::{DateTime, Utc};
use db::DatabaseEntry;
use dotenv::dotenv;
use regex::Regex;
use serde::{Deserialize, Serialize};
use sqlx::{postgres::PgPoolOptions, Pool, Postgres};
use tokio::join;
use std::{
    net::SocketAddr,
    time::{Duration, UNIX_EPOCH},
};
use tera::{Context, Tera};
use tower_http::services::ServeFile;
use tracing::{info, Level};
use tracing_subscriber::FmtSubscriber;
use utoipa::{IntoParams, OpenApi, ToSchema};
use utoipa_swagger_ui::SwaggerUi;

mod db;
mod api;

#[macro_use]
extern crate lazy_static;

const HELP: &str = "\
Biotools linter server

USAGE:
  server [OPTIONS]

FLAGS:
  -h, --help            Prints help information

OPTIONS:
  --port u16           Sets server port
";

/// Represents the query parameters needed by the API.
#[derive(Deserialize, IntoParams)]
struct APIQuery {
    /// A search string used to filter messages (optional).
    ///
    /// If provided, the API will return messages that match this search string
    /// in a case-insensitive manner.
    query: Option<String>,

    /// The page number for pagination (optional).
    ///
    /// Each page contains up to 100 messages. Use this field to specify the
    /// desired page number when retrieving results.
    #[param(style = Simple, minimum = 0)]
    page: Option<u16>,
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
    severity: u8,
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
                format!("<a href=\"{url}\">{url}</a>")
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
            severity: v.level as u8,
        }
    }
}

/// Represents the response sent to web clients.
#[derive(Debug, Serialize, ToSchema)]
struct ApiResponse {
    /// The number of results returned by the query.
    count: i64,
    /// `null` if there is no next page, otherwise returns `?page={page + 1}`
    next: Option<String>,
    /// `null` if there is no previous page, otherwise returns `?page={page - 1}`
    previous: Option<String>,
    /// A list of results matching the query.
    results: Vec<Message>,
}

/// Server state passed to http endpoints that need access to the database
#[derive(Clone)]
pub struct ServerConfig {
    pub pool: Pool<Postgres>,
}

// API
#[derive(OpenApi)]
#[openapi(paths(serve_api), components(schemas(ApiResponse, Message)))]
struct ApiDoc;

// Initialize and cache templates
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

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    // TODO switch to env subscriber
    let subscriber = FmtSubscriber::builder().compact().with_max_level(Level::TRACE).finish();
    tracing::subscriber::set_global_default(subscriber).expect("setting default subscriber failed");

    dotenv().ok();

    // Parse arguments
    let mut pargs = pico_args::Arguments::from_env();
    if pargs.contains(["-h", "--help"]) {
        print!("{HELP}");
        std::process::exit(0);
    }
    let port: u16 = pargs.value_from_str("--port").unwrap_or(3000);

    // Connect to DB
    let conn_str = std::env::var("DATABASE_URL").expect(
        "Expected database connection string (postgres://<username>:<password>@<ip>/<database>)",
    );
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect_lazy(&conn_str)
        .unwrap();

    // Build server state
    let state = ServerConfig { pool: pool };

    // Build router
    let routes = Router::new()
        .route("/", get(index))
        .route("/api", get(serve_api))
        .merge(SwaggerUi::new("/docs").url("/api-docs/openapi.json", ApiDoc::openapi()))
        .nest_service("/robots.txt", ServeFile::new("static/robots.txt"))
        .nest_service("/style.css", ServeFile::new("static/style.css"))
        .with_state(state);

    // Start server
    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    tracing::info!("Listening on http://{}", addr);
    axum::Server::bind(&addr)
        .serve(routes.into_make_service_with_connect_info::<SocketAddr>())
        .await
        .unwrap();

    Ok(())
}

// Serve the main page
async fn index(State(state): State<ServerConfig>) -> Html<String> {
    // Simple statistics, multiple futures executing at once
    let (error_count, oldest_entry_unix, tool_count) = tokio::join!(
        db::count_total_messages(&state.pool),
        db::get_oldest_entry_unix(&state.pool),
        db::count_total_unique_tools(&state.pool),
    );

    let mut c = Context::new();
    c.insert("error_count", &error_count);
    c.insert("tool_count", &tool_count);
    c.insert("last_time", &oldest_entry_unix);
    c.insert("search_value", "");

    Html(TEMPLATES.render("index.html", &c).unwrap())
}

/// Serve API
#[utoipa::path(
   get,
   path = "/api",
   responses(
        (status = 200, description = "Search successful", body = ApiResponse,
        ),
   ),
   params(
    APIQuery
),
)]
async fn serve_api(
    State(state): State<ServerConfig>,
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
        },
        Some(query) => {
            join!(
                db::get_messages_paginated_search(&state.pool, page, &query),
                db::count_messages_paginated_search(&state.pool, &query)
            )
        }
    };

    Json(ApiResponse {
        count: total_count,
        next: if (page as i64) + 100 < total_count {
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
