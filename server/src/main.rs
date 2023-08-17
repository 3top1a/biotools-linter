use axum::{
    extract::{ConnectInfo, Query, State},
    response::Html,
    routing::get,
    Json, Router,
};
use dotenv::dotenv;
use regex::Regex;
use serde::{Deserialize, Serialize};
use sqlx::{postgres::PgPoolOptions, Pool, Postgres};
use std::{collections::HashMap, net::SocketAddr};
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

/// What gets recieved from the database, plus `processed_text` which is added at runtime
#[derive(Debug, Serialize, Deserialize)]
struct Message {
    id: i32,
    time: i32,
    tool: String,
    code: String,
    location: String,
    value: String,
    processed_text: Option<String>,
}
impl Message {
    /// Escape HTML
    fn escape(self) -> Self {
        let mut m = self;

        // Escape characters
        m.tool = html_escape::encode_text(&m.tool).to_string();
        m.code = html_escape::encode_text(&m.code).to_string();
        m.location = html_escape::encode_text(&m.location).to_string();
        m.value = html_escape::encode_text(&m.value).to_string();

        m
    }

    /// Add `processed_text` to message
    fn add_processed_text(self) -> Self {
        let mut m = self;

        m.processed_text = match m.code.as_str() {
            "NONE001" => Some(format!("Important value  at {} is null/empty.", m.location)),
            "URL---" => Some(format!(
                "Linter error: {} {}",
                m.value, m.location
            )),
            "URL001" => Some(format!(
                "URL {} at {} does not match a valid URL.",
                m.value, m.location
            )),
            "URL002" => Some(format!(
                "URL {} at {} doesn't returns 200 (HTTP_OK).",
                m.value, m.location
            )),
            "URL003" => Some(format!(
                "URL {} at {} timeouted after 30 seconds.",
                m.value, m.location
            )),
            "URL004" => Some(format!(
                "URL {} at {} returned an SSL error.",
                m.value, m.location
            )),
            "URL005" => Some(format!(
                "URL {} at {} returns a permanent redirect.",
                m.value, m.location
            )),
            "URL006" => Some(format!(
                "URL {} at {} does not use SSL.",
                m.value, m.location
            )),
            "URL007" => Some(format!(
                "URL {} at {} does not start with https:// but site uses SSL.",
                m.value, m.location
            )),
            _ => None,
        };

        // Autolink URLs
        if m.processed_text.is_some() {
            let re = Regex::new(r"(http[s]?|ftp)://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+").unwrap();

            m.processed_text = Some(
                re.replace_all(&m.processed_text.unwrap(), |caps: &regex::Captures| {
                    let url = caps.get(0).unwrap().as_str();
                    format!("<a href=\"{url}\">{url}</a>")
                })
                .to_string(),
            );
        }

        m
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
        .nest_service("/simple.css", ServeFile::new("static/simple.css"))
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
        let rows = sqlx::query!(
            "SELECT * FROM messages WHERE tool ILIKE $1 OR code ILIKE $1 LIMIT 100 OFFSET $2",
            format!("%{}%", html_escape::encode_text(query.unwrap())),
            page * 100,
        )
        .fetch_all(&state.db)
        .await
        .unwrap();

        // Process output, escape and add processed text that is not stored in the DB
        rows.into_iter()
            .map(|row| {
                Message {
                    code: row.code,
                    id: row.id,
                    location: row.location,
                    time: row.time,
                    tool: row.tool,
                    value: row.value,
                    processed_text: None,
                }
                .escape()
                .add_processed_text()
            })
            .collect()

        // TODO Escape query
    } else {
        let rows = sqlx::query!("SELECT * FROM messages LIMIT 100 OFFSET $1", page * 100,)
            .fetch_all(&state.db)
            .await
            .unwrap();

        // Process output, escape and add processed text that is not stored in the DB
        rows.into_iter()
            .map(|row| {
                Message {
                    code: row.code,
                    id: row.id,
                    location: row.location,
                    time: row.time,
                    tool: row.tool,
                    value: row.value,
                    processed_text: None,
                }
                .escape()
                .add_processed_text()
            })
            .collect()
    };

    let total_count = if query.is_some() {
        sqlx::query_scalar!(
            "SELECT COUNT(*) FROM messages WHERE tool ILIKE $1",
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
