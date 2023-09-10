#[cfg(test)]
mod tests {
    use axum::http::StatusCode;
    use axum_test_helper::TestClient;

    #[tokio::test]
    async fn sql() {
        use crate::*;

        let subscriber = FmtSubscriber::builder()
            .compact()
            .with_max_level(Level::TRACE)
            .finish();
        tracing::subscriber::set_global_default(subscriber)
            .expect("setting default subscriber failed");

        dotenv().ok();

        // Connect to DB
        let conn_str = std::env::var("DATABASE_URL").expect(
            "Expected database connection string (postgres://<username>:<password>@<ip>/<database>)",
        );
        let pool = PgPoolOptions::new()
            .max_connections(5)
            .connect(&conn_str)
            .await
            .unwrap();

        // Build server state
        let state = ServerState {
            pool,
            stats_file_path: "./sample_data.json".into(),
        };

        let routes = app(&state);
        let client = TestClient::new(routes);

        for url in [
            "/",
            "/statistics",
            "/api/search?page=0",
            "/api/statistics",
            "/api/documentation/",
            "/robots.txt",
            "/style.css",
        ] {
            dbg!("Testing {}", url);

            let res = client.get(url).send().await;
            assert_eq!(res.status(), StatusCode::OK);
        }

        // Sanity check
        let res = client.get("/invalid").send().await;
        assert_ne!(res.status(), StatusCode::OK);
    }
}
