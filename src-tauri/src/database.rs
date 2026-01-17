// ============================================================================
// Database Module - SQLite History Storage
// ============================================================================

use rusqlite::{params, Connection, Result as SqliteResult};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;
use std::sync::Mutex;
use tauri::Manager;

// ============================================================================
// Data Structures
// ============================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Session {
    pub id: String,
    pub title: String,
    #[serde(default)]
    pub is_favorite: bool,
    pub created_at: i64,
    pub updated_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Message {
    pub id: String,
    pub session_id: String,
    pub role: String,
    pub content: String,
    pub timestamp: i64,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct PaginatedResult<T> {
    pub items: Vec<T>,
    pub total: i64,
    pub page: i32,
    pub page_size: i32,
    pub has_more: bool,
}

// ============================================================================
// Database Manager
// ============================================================================

pub struct Database {
    conn: Mutex<Connection>,
}

impl Database {
    /// Create a new database instance at the specified path
    pub fn new(db_path: PathBuf) -> Result<Self, String> {
        // Ensure parent directory exists
        if let Some(parent) = db_path.parent() {
            std::fs::create_dir_all(parent)
                .map_err(|e| format!("Failed to create database directory: {}", e))?;
        }

        // Open database connection
        let conn = Connection::open(&db_path)
            .map_err(|e| format!("Failed to open database: {}", e))?;

        // Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON", [])
            .map_err(|e| format!("Failed to enable foreign keys: {}", e))?;

        let db = Database {
            conn: Mutex::new(conn),
        };

        // Run migrations
        db.run_migrations()?;

        println!("✅ Database initialized at: {:?}", db_path);

        Ok(db)
    }

    /// Run database migrations
    fn run_migrations(&self) -> Result<(), String> {
        let conn = self.conn.lock().unwrap();

        // Get current schema version
        let version: i32 = conn
            .pragma_query_value(None, "user_version", |row| row.get(0))
            .map_err(|e| format!("Failed to get schema version: {}", e))?;

        println!("📊 Current database schema version: {}", version);

        // Migration v0 -> v1: Initial schema
        if version < 1 {
            println!("🔄 Running migration v0 -> v1: Initial schema");

            conn.execute_batch(
                "
                -- Sessions table
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);

                -- Messages table
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                    content TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, timestamp ASC);

                -- Update schema version
                PRAGMA user_version = 1;
                ",
            )
            .map_err(|e| format!("Migration v1 failed: {}", e))?;

            println!("✅ Migration v1 completed");
        }

        // Migration v1 -> v2: Add is_favorite column
        if version < 2 {
            println!("🔄 Running migration v1 -> v2: Add is_favorite column");

            conn.execute_batch(
                "
                -- Add is_favorite column to sessions table
                ALTER TABLE sessions ADD COLUMN is_favorite INTEGER NOT NULL DEFAULT 0;

                -- Create index for favorite filtering
                CREATE INDEX IF NOT EXISTS idx_sessions_favorite ON sessions(is_favorite, updated_at DESC);

                -- Update schema version
                PRAGMA user_version = 2;
                ",
            )
            .map_err(|e| format!("Migration v2 failed: {}", e))?;

            println!("✅ Migration v2 completed");
        }

        Ok(())
    }

    // ========================================================================
    // Session CRUD Operations
    // ========================================================================

    /// Create a new session
    pub fn create_session(&self, title: String) -> Result<Session, String> {
        let conn = self.conn.lock().unwrap();

        let id = uuid::Uuid::new_v4().to_string();
        let now = chrono::Utc::now().timestamp_millis();

        conn.execute(
            "INSERT INTO sessions (id, title, is_favorite, created_at, updated_at) VALUES (?1, ?2, ?3, ?4, ?5)",
            params![id, title, 0, now, now],
        )
        .map_err(|e| format!("Failed to create session: {}", e))?;

        Ok(Session {
            id,
            title,
            is_favorite: false,
            created_at: now,
            updated_at: now,
        })
    }

    /// List sessions with pagination
    #[allow(dead_code)]
    pub fn list_sessions(&self, page: i32, page_size: i32) -> Result<PaginatedResult<Session>, String> {
        self.list_sessions_filtered(page, page_size, None)
    }

    /// List sessions with pagination and optional favorite filter
    pub fn list_sessions_filtered(
        &self,
        page: i32,
        page_size: i32,
        filter_favorite: Option<bool>,
    ) -> Result<PaginatedResult<Session>, String> {
        let conn = self.conn.lock().unwrap();

        // Build WHERE clause for filtering
        let where_clause = match filter_favorite {
            Some(true) => " WHERE is_favorite = 1",
            Some(false) => " WHERE is_favorite = 0",
            None => "",
        };

        // Get total count
        let total: i64 = conn
            .query_row(
                &format!("SELECT COUNT(*) FROM sessions{}", where_clause),
                [],
                |row| row.get(0),
            )
            .map_err(|e| format!("Failed to count sessions: {}", e))?;

        // Calculate offset
        let offset = (page - 1) * page_size;

        // Query sessions
        let query = format!(
            "SELECT id, title, is_favorite, created_at, updated_at FROM sessions{} ORDER BY updated_at DESC LIMIT ?1 OFFSET ?2",
            where_clause
        );

        let mut stmt = conn
            .prepare(&query)
            .map_err(|e| format!("Failed to prepare query: {}", e))?;

        let sessions = stmt
            .query_map(params![page_size, offset], |row| {
                Ok(Session {
                    id: row.get(0)?,
                    title: row.get(1)?,
                    is_favorite: row.get::<_, i32>(2)? == 1,
                    created_at: row.get(3)?,
                    updated_at: row.get(4)?,
                })
            })
            .map_err(|e| format!("Failed to query sessions: {}", e))?
            .collect::<SqliteResult<Vec<_>>>()
            .map_err(|e| format!("Failed to collect sessions: {}", e))?;

        let has_more = (offset + page_size) < total as i32;

        Ok(PaginatedResult {
            items: sessions,
            total,
            page,
            page_size,
            has_more,
        })
    }

    /// Get a single session by ID
    pub fn get_session(&self, session_id: &str) -> Result<Session, String> {
        let conn = self.conn.lock().unwrap();

        conn.query_row(
            "SELECT id, title, is_favorite, created_at, updated_at FROM sessions WHERE id = ?1",
            params![session_id],
            |row| {
                Ok(Session {
                    id: row.get(0)?,
                    title: row.get(1)?,
                    is_favorite: row.get::<_, i32>(2)? == 1,
                    created_at: row.get(3)?,
                    updated_at: row.get(4)?,
                })
            },
        )
        .map_err(|e| format!("Session not found: {}", e))
    }

    /// Toggle favorite status of a session
    pub fn toggle_favorite(&self, session_id: &str) -> Result<bool, String> {
        let conn = self.conn.lock().unwrap();

        // Get current state directly without calling get_session (avoids deadlock)
        let current_state: i32 = conn
            .query_row(
                "SELECT is_favorite FROM sessions WHERE id = ?1",
                params![session_id],
                |row| row.get(0),
            )
            .map_err(|e| format!("Failed to query session: {}", e))?;

        let new_state = current_state == 0;

        // Update state
        let now = chrono::Utc::now().timestamp_millis();
        let rows_affected = conn
            .execute(
                "UPDATE sessions SET is_favorite = ?1, updated_at = ?2 WHERE id = ?3",
                params![if new_state { 1 } else { 0 }, now, session_id],
            )
            .map_err(|e| format!("Failed to toggle favorite: {}", e))?;

        if rows_affected == 0 {
            return Err("Session not found".to_string());
        }

        Ok(new_state)
    }

    /// Update a session's title
    pub fn update_session(&self, session_id: &str, title: String) -> Result<Session, String> {
        let conn = self.conn.lock().unwrap();

        let now = chrono::Utc::now().timestamp_millis();

        let rows_affected = conn
            .execute(
                "UPDATE sessions SET title = ?1, updated_at = ?2 WHERE id = ?3",
                params![title, now, session_id],
            )
            .map_err(|e| format!("Failed to update session: {}", e))?;

        if rows_affected == 0 {
            return Err("Session not found".to_string());
        }

        // Return updated session
        drop(conn);
        self.get_session(session_id)
    }

    /// Delete a session and all its messages
    pub fn delete_session(&self, session_id: &str) -> Result<bool, String> {
        let conn = self.conn.lock().unwrap();

        let rows_affected = conn
            .execute("DELETE FROM sessions WHERE id = ?1", params![session_id])
            .map_err(|e| format!("Failed to delete session: {}", e))?;

        Ok(rows_affected > 0)
    }

    // ========================================================================
    // Message CRUD Operations
    // ========================================================================

    /// Add a message to a session
    pub fn add_message(
        &self,
        session_id: &str,
        role: &str,
        content: &str,
    ) -> Result<Message, String> {
        let conn = self.conn.lock().unwrap();

        let id = uuid::Uuid::new_v4().to_string();
        let now = chrono::Utc::now().timestamp_millis();

        // Insert message
        conn.execute(
            "INSERT INTO messages (id, session_id, role, content, timestamp) VALUES (?1, ?2, ?3, ?4, ?5)",
            params![id, session_id, role, content, now],
        )
        .map_err(|e| format!("Failed to add message: {}", e))?;

        // Update session's updated_at
        conn.execute(
            "UPDATE sessions SET updated_at = ?1 WHERE id = ?2",
            params![now, session_id],
        )
        .map_err(|e| format!("Failed to update session timestamp: {}", e))?;

        Ok(Message {
            id,
            session_id: session_id.to_string(),
            role: role.to_string(),
            content: content.to_string(),
            timestamp: now,
        })
    }

    /// Get messages for a session with pagination
    pub fn get_messages(
        &self,
        session_id: &str,
        page: i32,
        page_size: i32,
    ) -> Result<PaginatedResult<Message>, String> {
        let conn = self.conn.lock().unwrap();

        // Get total count for this session
        let total: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM messages WHERE session_id = ?1",
                params![session_id],
                |row| row.get(0),
            )
            .map_err(|e| format!("Failed to count messages: {}", e))?;

        // Calculate offset
        let offset = (page - 1) * page_size;

        // Query messages (ordered by timestamp ascending for chat display)
        let mut stmt = conn
            .prepare(
                "SELECT id, session_id, role, content, timestamp FROM messages
                 WHERE session_id = ?1
                 ORDER BY timestamp ASC
                 LIMIT ?2 OFFSET ?3",
            )
            .map_err(|e| format!("Failed to prepare query: {}", e))?;

        let messages = stmt
            .query_map(params![session_id, page_size, offset], |row| {
                Ok(Message {
                    id: row.get(0)?,
                    session_id: row.get(1)?,
                    role: row.get(2)?,
                    content: row.get(3)?,
                    timestamp: row.get(4)?,
                })
            })
            .map_err(|e| format!("Failed to query messages: {}", e))?
            .collect::<SqliteResult<Vec<_>>>()
            .map_err(|e| format!("Failed to collect messages: {}", e))?;

        let has_more = (offset + page_size) < total as i32;

        Ok(PaginatedResult {
            items: messages,
            total,
            page,
            page_size,
            has_more,
        })
    }

    /// Delete a single message
    pub fn delete_message(&self, message_id: &str) -> Result<bool, String> {
        let conn = self.conn.lock().unwrap();

        let rows_affected = conn
            .execute("DELETE FROM messages WHERE id = ?1", params![message_id])
            .map_err(|e| format!("Failed to delete message: {}", e))?;

        Ok(rows_affected > 0)
    }
}

// ============================================================================
// Helper Functions
// ============================================================================

/// Get the database path for the application
pub fn get_database_path(app_handle: &tauri::AppHandle) -> Result<PathBuf, String> {
    let app_data_dir = app_handle
        .path()
        .app_data_dir()
        .map_err(|e| format!("Failed to get app data dir: {}", e))?;

    Ok(app_data_dir.join("speekium.db"))
}
