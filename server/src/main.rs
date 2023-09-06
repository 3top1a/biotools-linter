mod api;
mod db;

use api::*;
use axum::{routing::get, Router};

use dotenv::dotenv;

use sqlx::{postgres::PgPoolOptions, Pool, Postgres};
use std::{net::SocketAddr, path::{Path, PathBuf}};

use tower_http::services::ServeFile;
use tracing::Level;
use tracing_subscriber::FmtSubscriber;
use utoipa::OpenApi;
use utoipa_swagger_ui::SwaggerUi;

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
  --stats path         Where to read statistics
";

/// Server state passed to http endpoints that need access to the database
#[derive(Clone)]
pub struct ServerState {
    pub pool: Pool<Postgres>,
    pub stats_file_path: PathBuf,
}

// API
#[derive(OpenApi)]
#[openapi(paths(serve_api), components(schemas(ApiResponse, Message)))]
struct ApiDoc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    // TODO switch to env subscriber
    let subscriber = FmtSubscriber::builder()
        .compact()
        .with_max_level(Level::TRACE)
        .finish();
    tracing::subscriber::set_global_default(subscriber).expect("setting default subscriber failed");

    dotenv().ok();

    // Parse arguments
    let mut pargs = pico_args::Arguments::from_env();
    if pargs.contains(["-h", "--help"]) {
        print!("{HELP}");
        std::process::exit(0);
    }
    let port: u16 = pargs.value_from_str("--port").unwrap_or(3000);
    let stats_file_path: PathBuf = pargs.value_from_str("--stats").expect("Need a statistics file");

    // Connect to DB
    let conn_str = std::env::var("DATABASE_URL").expect(
        "Expected database connection string (postgres://<username>:<password>@<ip>/<database>)",
    );
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect_lazy(&conn_str)
        .unwrap();

    // Build server state
    let state = ServerState { pool, stats_file_path };

    let routes = app(&state);

    // Start server
    let addr = SocketAddr::from(([0, 0, 0, 0], port));
    tracing::info!("Listening on http://{}", addr);
    axum::Server::bind(&addr)
        .serve(routes.into_make_service_with_connect_info::<SocketAddr>())
        .await
        .unwrap();

    Ok(())
}

/// Having a function that produces our app makes it easy to call it from tests
/// without having to create an HTTP server.
fn app(state: &ServerState) -> Router {
    Router::new()
        .route("/", get(serve_index))
        .route("/statistics", get(serve_statistics))
        .route("/api/search", get(serve_api))
        .merge(SwaggerUi::new("/docs").url("/api/openapi.json", ApiDoc::openapi()))
        .nest_service("/robots.txt", ServeFile::new("static/robots.txt"))
        .nest_service("/style.css", ServeFile::new("static/style.css"))
        .with_state(state.clone())
}
