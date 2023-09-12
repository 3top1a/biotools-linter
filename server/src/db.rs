use sqlx::{Pool, Postgres};

use crate::api::{Message, Severity};

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

pub async fn count_total_unique_tools(pool: &Pool<Postgres>) -> i64 {
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

pub async fn count_critical_messages(pool: &Pool<Postgres>) -> i64 {
    sqlx::query_scalar!("SELECT COUNT(*) FROM messages where level = 8")
        .fetch_all(pool)
        .await
        .unwrap()[0]
        .unwrap()
}

pub async fn get_messages_paginated(
    pool: &Pool<Postgres>,
    page: i64,
    severity: Option<Severity>,
) -> Vec<Message> {
    let (min_severity, max_severity): (i32, i32) = match severity {
        Some(s) => {
            let x = s.into();
            (x, x)
        }
        None => (1, 7),
    };

    let rows = sqlx::query_as!(
        DatabaseEntry,
        "SELECT time,tool,code,location,text,level FROM messages WHERE level BETWEEN $1 AND $2 LIMIT 100 OFFSET $3",
        min_severity,
        max_severity,
        (page as i64) * 100,
    )
    .fetch_all(pool)
    .await
    .unwrap();

    // Process output from database entry to message
    rows.into_iter().map(Message::from).collect()
}

pub async fn get_messages_paginated_search(
    pool: &Pool<Postgres>,
    page: i64,
    query: &String,
    severity: Option<Severity>,
) -> Vec<Message> {
    let (min_severity, max_severity): (i32, i32) = match severity {
        Some(s) => {
            let x = s.into();
            (x, x)
        }
        None => (1, 7),
    };

    let rows = sqlx::query_as!(
        DatabaseEntry,
        "SELECT time,tool,code,location,text,level FROM messages WHERE (tool ILIKE $1 OR code ILIKE $1) AND level BETWEEN $3 AND $4 LIMIT 100 OFFSET $2",
        format!("%{}%", html_escape::encode_text(query)),
        (page as i64) * 100,
        min_severity,
        max_severity,
    )
    .fetch_all(pool)
    .await
    .unwrap();

    // Process output from database entry to message
    rows.into_iter().map(Message::from).collect()
}

pub async fn count_messages_paginated(pool: &Pool<Postgres>, severity: Option<Severity>) -> i64 {
    let (min_severity, max_severity): (i32, i32) = match severity {
        Some(s) => {
            let x = s.into();
            (x, x)
        }
        None => (1, 7),
    };

    sqlx::query_scalar!(
        "SELECT COUNT(*) FROM messages WHERE level BETWEEN $1 AND $2",
        min_severity,
        max_severity
    )
    .fetch_all(pool)
    .await
    .unwrap()[0]
        .unwrap()
}

pub async fn count_messages_paginated_search(
    pool: &Pool<Postgres>,
    query: &String,
    severity: Option<Severity>,
) -> i64 {
    let (min_severity, max_severity): (i32, i32) = match severity {
        Some(s) => {
            let x = s.into();
            (x, x)
        }
        None => (1, 7),
    };

    sqlx::query_scalar!(
        "SELECT COUNT(*) FROM messages WHERE (tool ILIKE $1 OR code ILIKE $1) AND level BETWEEN $2 AND $3",
        format!("%{}%", html_escape::encode_text(&query)),
        min_severity,
        max_severity
    )
    .fetch_all(pool)
    .await
    .unwrap()[0]
        .unwrap()
}
