use sqlx::{Pool, Postgres};

use crate::Message;


/// What gets received from the database
pub struct DatabaseEntry {
    pub time: i64,
    pub tool: String,
    pub code: String,
    pub location: String,
    pub text: String,
    pub level: i32,
}

pub async fn count_total_messages(pool: &Pool<Postgres>) -> i64 {
    sqlx::query_scalar!("SELECT COUNT(*) FROM messages")
    .fetch_all(pool)
    .await
    .unwrap()[0]
    .unwrap()
}

pub async fn count_total_unique_tools(pool: &Pool<Postgres>) -> i64{
    sqlx::query_scalar!("SELECT COUNT(DISTINCT tool) FROM messages")
        .fetch_all(pool)
        .await
        .unwrap()[0]
        .unwrap()
}

pub async fn get_oldest_entry_unix(pool: &Pool<Postgres>) -> i64 {
    sqlx::query_scalar!("SELECT MIN(time) from messages")
    .fetch_all(pool)
    .await
    .unwrap()[0]
    .unwrap()
}

pub async fn get_messages_paginated(pool: &Pool<Postgres>, page: u16) -> Vec<Message> {
    let rows = sqlx::query_as!(
        DatabaseEntry,
        "SELECT time,tool,code,location,text,level FROM messages LIMIT 100 OFFSET $1",
        (page as i64) * 100,
    )
    .fetch_all(pool)
    .await
    .unwrap();

    // Process output from database entry to message
    rows.into_iter().map(Message::from).collect()
}

pub async fn get_messages_paginated_search(pool: &Pool<Postgres>, page: u16, query: &String) -> Vec<Message> {
    let rows = sqlx::query_as!(
        DatabaseEntry,
        "SELECT time,tool,code,location,text,level FROM messages WHERE tool ILIKE $1 OR code ILIKE $1 LIMIT 100 OFFSET $2",
        format!("%{}%", html_escape::encode_text(query)),
        (page as i64) * 100,
    )
    .fetch_all(pool)
    .await
    .unwrap();

    // Process output from database entry to message
    rows.into_iter().map(Message::from).collect()
}

pub async fn count_messages_paginated(pool: &Pool<Postgres>) -> i64 {
    sqlx::query_scalar!("SELECT COUNT(*) FROM messages")
    .fetch_all(pool)
    .await
    .unwrap()[0]
    .unwrap()
}

pub async fn count_messages_paginated_search(pool: &Pool<Postgres>, query: &String) -> i64 {
    sqlx::query_scalar!(
        "SELECT COUNT(*) FROM messages WHERE tool ILIKE $1 OR code ILIKE $1",
        format!("%{}%", html_escape::encode_text(&query))
    )
    .fetch_all(pool)
    .await
    .unwrap()[0]
    .unwrap()
}
