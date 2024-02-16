mod api;
mod db;
mod test;

use api::{
    ApiResponse, Message, __path_download_api, __path_json_api, __path_serve_search_api,
    __path_serve_statistics_api, relint_api, serve_documentation_index, serve_documentation_page,
    serve_index_page, serve_search_api, serve_statistics_api, serve_statistics_page, Severity,
    Statistics, StatisticsEntry, __path_relint_api, download_api, json_api, serve_sitemap,
};
use axum::{
    error_handling::HandleErrorLayer,
    http::StatusCode,
    routing::{get, post},
    BoxError, Router,
};
use tower::{buffer::BufferLayer, limit::RateLimitLayer, ServiceBuilder};

use dotenv::dotenv;

use sqlx::{postgres::PgPoolOptions, Pool, Postgres};
use std::{net::SocketAddr, path::PathBuf, time::Duration};

use env_logger::{Builder, Env};
use std::io::Write;
use tower_http::services::ServeFile;
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

/// Server state passed to endpoints
#[derive(Clone)]
pub struct ServerState {
    /// Connection to the postgresql database, shared across all endpoints
    pub pool: Pool<Postgres>,
    /// Path to the statistics file used for graphs, generated with linter/statistics.py
    pub stats_file_path: PathBuf,
}

/// Auto generated API Documentation
/// Remember to add additional paths and schemas
#[derive(OpenApi)]
#[openapi(
    info(description = "", title = "Biotools linter"),
    paths(
        serve_search_api,
        serve_statistics_api,
        relint_api,
        download_api,
        json_api
    ),
    components(schemas(ApiResponse, Message, Statistics, StatisticsEntry, Severity,))
)]
struct ApiDoc;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize tracing
    let mut builder = Builder::from_env(Env::default().default_filter_or("info"));
    builder
        .format(|buf, record| {
            writeln!(
                buf,
                "{} {}:{} - {}",
                chrono::Utc::now().format("%Y-%m-%d %H:%M:%S"),
                record.file().unwrap_or("<unknown>"),
                record.line().unwrap_or(0),
                record.args()
            )
        })
        .init();

    dotenv().ok();

    // Parse arguments
    let mut pargs = pico_args::Arguments::from_env();
    if pargs.contains(["-h", "--help"]) {
        print!("{HELP}");
        std::process::exit(0);
    }
    let port: u16 = pargs.value_from_str("--port").unwrap_or(3000);
    let stats_file_path: PathBuf = pargs
        .value_from_str("--stats")
        .expect("Need a statistics file");

    // Connect to DB
    let conn_str = std::env::var("DATABASE_URL").expect(
        "Expected database connection string (postgres://<username>:<password>@<ip>/<database>)",
    );
    let pool = PgPoolOptions::new()
        .max_connections(5)
        .connect_lazy(&conn_str)
        .unwrap();

    // Build server state
    let state = ServerState {
        pool,
        stats_file_path,
    };

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
    let ratelimit = ServiceBuilder::new()
        .layer(HandleErrorLayer::new(|err: BoxError| async move {
            (
                StatusCode::INTERNAL_SERVER_ERROR,
                format!("Unhandled error: {}", err),
            )
        }))
        .layer(BufferLayer::new(1024))
        .layer(RateLimitLayer::new(1, Duration::from_secs(2)));

    Router::new()
        .route("/api/lint", post(relint_api))
        .route("/api/json", post(json_api))
        .route("/api/download", get(download_api))
        .layer(ratelimit.clone()) // Only rate limit the routes above
        .route("/", get(serve_index_page))
        .route("/docs/:query_title", get(serve_documentation_page))
        .route("/docs/", get(serve_documentation_index))
        .route("/docs", get(serve_documentation_index))
        .route("/statistics", get(serve_statistics_page))
        .route("/api/search", get(serve_search_api))
        .route("/api/statistics", get(serve_statistics_api))
        .merge(SwaggerUi::new("/api/documentation").url("/api/openapi.json", ApiDoc::openapi()))
        .nest_service("/robots.txt", ServeFile::new("static/robots.txt"))
        .nest_service("/style.css", ServeFile::new("static/style.css"))
        .nest_service("/sitemap.xml", get(serve_sitemap))
        .with_state(state.clone())
}
