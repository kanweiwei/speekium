// src-tauri/src/state.rs
//
// 应用状态管理

use crate::database::Database;

// ============================================================================
// App State (for Database)
// ============================================================================

pub struct AppState {
    pub db: Database,
}
