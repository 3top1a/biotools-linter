use axum::{
    extract::{ConnectInfo, Query, State},
    response::Html,
    routing::get,
    Json, Router,
};
use chrono::{DateTime, Utc};
use dotenv::dotenv;
use regex::Regex;
use serde::{Deserialize, Serialize};
use sqlx::{postgres::PgPoolOptions, Pool, Postgres};
use std::{
    collections::HashMap,
    net::SocketAddr,
    time::{Duration, UNIX_EPOCH},
};
use tera::{Context, Tera};
use tower_http::services::ServeFile;
use tracing::info;
use tracing_subscriber::FmtSubscriber;

#[macro_use]
extern crate lazy_static;

const HELP: &str = "\
Biotools linter serber

USAGE:
  app [OPTIONS]

FLAGS:
  -h, --help            Prints help information

OPTIONS:
  --port u16           Sets server port
";

/// What gets recieved from the database
struct DatabaseEntry {
    id: i32,
    time: i32,
    tool: String,
    code: String,
    location: String,
    value: String,
}

/// Middle part of what gets sent to client
#[derive(Debug, Serialize, Deserialize)]
struct Message {
    timestamp: String,
    tool: String,
    code: String,
    processed_text: String,
}
impl From<DatabaseEntry> for Message {
    fn from(value: DatabaseEntry) -> Self {
        let mut v = value;

        // Escape
        v.tool = html_escape::encode_text(&v.tool).to_string();
        v.code = html_escape::encode_text(&v.code).to_string();
        v.location = html_escape::encode_text(&v.location).to_string();
        v.value = html_escape::encode_text(&v.value).to_string();

        // Process text
        let processed_text = match v.code.as_str() {
            "NONE001" => format!("Important value  at {} is null/empty.", v.location),
            "URL---" => format!("Linter error: {} {}", v.value, v.location),
            "URL001" => format!(
                "URL {} at {} does not match a valid URL (there may be hidden unicode).",
                v.value, v.location
            ),
            "URL002" => format!(
                "URL {} at {} doesn't return ok status (>399).",
                v.value, v.location
            ),
            "URL003" => format!(
                "URL {} at {} timeouted after 30 seconds.",
                v.value, v.location
            ),
            "URL004" => format!("URL {} at {} returned an SSL error.", v.value, v.location),
            "URL005" => format!(
                "URL {} at {} returns a permanent redirect.",
                v.value, v.location
            ),
            "URL006" => format!("URL {} at {} does not use SSL.", v.value, v.location),
            "URL007" => format!(
                "URL {} at {} does not start with https:// but site uses SSL.",
                v.value, v.location
            ),
            "URL008" => format!(
                "URL {} at {} returned a connection error, it may not exist.",
                v.value, v.location
            ),
            _ => String::from("Invalid entry code found, please file a bug report."),
        };

        // Autolink
        let processed_text = LINK_REGEX
            .replace_all(&processed_text, |caps: &regex::Captures| {
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
            processed_text,
            timestamp,
        }
    }
}

/// What gets sent out to web clients
#[derive(Debug, Serialize)]
struct ApiResponse {
    count: i64,
    next: Option<String>,
    previous: Option<String>,
    results: Vec<Message>,
}

// Server state passed to every http call
#[derive(Clone)]
pub struct ServerConfig {
    pub db: Pool<Postgres>,
}

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
            r"(http[s]?|ftp)://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
        )
        .unwrap()
    };
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    // TODO switch to env subscriber
    let subscriber = FmtSubscriber::builder().finish();
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
    let state = ServerConfig { db: pool };

    // Build router
    let routes = Router::new()
        .route("/", get(index))
        .route("/api", get(serve_api))
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
    let total_count = sqlx::query_scalar!("SELECT COUNT(*) FROM messages")
        .fetch_all(&state.db)
        .await
        .unwrap()[0]
        .unwrap();

    let oldest_entry_unix = sqlx::query_scalar!("SELECT MIN(time) from messages")
        .fetch_all(&state.db)
        .await
        .unwrap()[0]
        .unwrap();

    let mut c = Context::new();
    c.insert("count", &total_count);
    c.insert("last_time", &oldest_entry_unix);
    c.insert("search_value", "");

    Html(TEMPLATES.render("index.html", &c).unwrap())
}

/// Serve API
async fn serve_api(
    State(state): State<ServerConfig>,
    ConnectInfo(addr): ConnectInfo<SocketAddr>,
    Query(params): Query<HashMap<String, String>>,
) -> Json<ApiResponse> {
    // Get parameters
    let page_default: String = String::from("0");
    let page = params.get("page").unwrap_or(&page_default);
    let page: i64 = page.parse().unwrap_or(0);
    let query = params.get("query");

    info!(
        "Listing API from `{}` page {} query {:?}",
        addr, page, query
    );

    let messages = if query.is_some() {
        let rows = sqlx::query_as!(
            DatabaseEntry,
            "SELECT * FROM messages WHERE tool ILIKE $1 OR code ILIKE $1 LIMIT 100 OFFSET $2",
            format!("%{}%", html_escape::encode_text(query.unwrap())),
            page * 100,
        )
        .fetch_all(&state.db)
        .await
        .unwrap();

        // Process output from database entry to message
        rows.into_iter().map(Message::from).collect()
    } else {
        let rows = sqlx::query_as!(
            DatabaseEntry,
            "SELECT * FROM messages LIMIT 100 OFFSET $1",
            page * 100,
        )
        .fetch_all(&state.db)
        .await
        .unwrap();

        // Process output from database entry to message
        rows.into_iter().map(Message::from).collect()
    };

    let total_count = if query.is_some() {
        sqlx::query_scalar!(
            "SELECT COUNT(*) FROM messages WHERE tool ILIKE $1 OR code ILIKE $1",
            format!("%{}%", html_escape::encode_text(query.unwrap()))
        )
        .fetch_all(&state.db)
        .await
        .unwrap()[0]
            .unwrap()
    } else {
        sqlx::query_scalar!("SELECT COUNT(*) FROM messages")
            .fetch_all(&state.db)
            .await
            .unwrap()[0]
            .unwrap()
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
