use axum::{
    extract::State,
    http::StatusCode,
    response::Html,
    routing::{get, post},
    Extension, Json, Router,
};
use pico_args::Arguments;
use serde::{Deserialize, Serialize};
use sqlx::{PgPool, Pool, Postgres};
use std::net::SocketAddr;
use tera::{Context, Tera};
use tokio::sync::RwLock;
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
struct DatabaseEntry {
    id: u32,
    time: u64,
    tool: String,
    code: String,
    location: String,
    value: String,
}

#[derive(Clone)]
pub struct ServerConfig {
    pub db: Pool<Postgres>,
}

lazy_static! {
    pub static ref TEMPLATES: Tera = {
        let tera = match Tera::new("templates/*.html") {
            Ok(t) => t,
            Err(e) => {
                println!("Parsing error(s): {}", e);
                ::std::process::exit(1);
            }
        };
        tera
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
    let routes = Router::new().route("/", get(root)).with_state(state);

    // Start server
    let addr = SocketAddr::from(([127, 0, 0, 1], port));
    tracing::info!("Listening on http://{}", addr);
    axum::Server::bind(&addr)
        .serve(routes.into_make_service())
        .await
        .unwrap();

    Ok(())
}

// basic handler that responds with a static string
async fn root(State(state): State<ServerConfig>) -> Html<String> {
    let total = sqlx::query_scalar!("SELECT COUNT(*) FROM messages")
        .fetch_all(&state.db)
        .await
        .unwrap()[0]
        .unwrap();

    let mut c = Context::new();
    c.insert("count", &total);

    Html(TEMPLATES.render("index.html", &c).unwrap())
}
