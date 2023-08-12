use axum::{extract::{State, Path}, response::Html, routing::get, Router};
use serde::{Deserialize, Serialize};
use sqlx::{Pool, Postgres};
use std::net::SocketAddr;
use tera::{Context, Tera};
use tracing::Level;
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
  --port INT8           Sets server port
";

#[derive(Serialize, Deserialize)]
struct Message {
    id: i32,
    time: i32,
    tool: String,
    code: String,
    location: String,
    value: String,
    processed_text: Option<String>
}

impl Message {
    fn add_processed_text(self: Message) -> Message{
        let mut m = self;

        m.processed_text = match m.code.as_str() {
            "NONE001" => Some(format!("Important value  at {} is null/empty.", m.location)),
            "URL001" => Some(format!("URL {} at {} does not match a valid URL.", m.value, m.location)),
            "URL002" => Some(format!("URL {} at {} doesn't returns 200 (HTTP_OK).", m.value, m.location)),
            "URL003" => Some(format!("URL {} at {} timeouted after 30 seconds.", m.value, m.location)),
            "URL004" => Some(format!("URL {} at {} returned an SSL error.", m.value, m.location)),
            "URL005" => Some(format!("URL {} at {} returns a permanent redirect.", m.value, m.location)),
            "URL006" => Some(format!("URL {} at {} does not use SSL.", m.value, m.location)),
            "URL007" => Some(format!("URL {} at {} does not start with https:// but site uses SSL.", m.value, m.location)),
            _ => None
        };
        
        return m;
    }
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
            Ok(t) => {
                t
            },
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
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::TRACE)
        .finish();
    tracing::subscriber::set_global_default(subscriber).expect("setting default subscriber failed");

    // Parse arguments
    let mut pargs = pico_args::Arguments::from_env();
    if pargs.contains(["-h", "--help"]) {
        print!("{}", HELP);
        std::process::exit(0);
    }
    let port: u16 = pargs.value_from_str("--port").unwrap_or(3000);

    // Connect to DB
    let conn_str = std::env::var("DATABASE_URL").expect(
        "Expected database connection string (postgres://username:password@localhost/dbname)",
    );
    let pool = sqlx::PgPool::connect(&conn_str).await.unwrap();

    // Build server state
    let state = ServerConfig { db: pool };

    // Build router
    let routes = Router::new()
        .route("/", get(index))
        .route("/search/:name", get(search))
        .with_state(state);

    // Start server
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    tracing::info!("Listening on http://{}", addr);
    axum::Server::bind(&addr)
        .serve(routes.into_make_service())
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

    Html(TEMPLATES.render("index.html", &c).unwrap())
}

// Serve the search page
async fn search(State(state): State<ServerConfig>, Path(name): Path<String>) -> Html<String> {
    let rows = sqlx::query!(
        "SELECT * FROM messages WHERE tool ILIKE $1",
        format!("%{}%", name)
    )
    .fetch_all(&state.db)
    .await
    .unwrap();

    // Process output, add text that is not stored in the DB
    let messages: Vec<Message> = rows.into_iter().map(|row| {
        Message {
            code: row.code,
            id: row.id,
            location: row.location,
            time: row.time,
            tool: row.tool,
            value: row.value,
            processed_text: None,
        }.add_processed_text()
    }).collect();

    let mut c = Context::new();
    c.insert("entries", &messages);
    c.insert("count", &messages.len());
    c.insert("page", &0);

    Html(TEMPLATES.render("search.html", &c).unwrap())
}
