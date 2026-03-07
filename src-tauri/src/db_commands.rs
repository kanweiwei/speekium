use tauri::State;

use crate::database::{Session, Message, PaginatedResult};
use crate::state::AppState;

// ============================================================================
// Database Commands
// ============================================================================

#[tauri::command]
pub async fn db_create_session(
    state: State<'_, AppState>,
    title: String,
) -> Result<Session, String> {
    state.db.create_session(title)
}

#[tauri::command]
pub async fn db_list_sessions(
    state: State<'_, AppState>,
    page: i32,
    page_size: i32,
    filter_favorite: Option<bool>,
) -> Result<PaginatedResult<Session>, String> {
    state.db.list_sessions_filtered(page, page_size, filter_favorite)
}

#[tauri::command]
pub async fn db_get_session(
    state: State<'_, AppState>,
    session_id: String,
) -> Result<Session, String> {
    state.db.get_session(&session_id)
}

#[tauri::command]
pub async fn db_toggle_favorite(
    state: State<'_, AppState>,
    session_id: String,
) -> Result<bool, String> {
    state.db.toggle_favorite(&session_id)
}

#[tauri::command]
pub async fn db_update_session(
    state: State<'_, AppState>,
    session_id: String,
    title: String,
) -> Result<Session, String> {
    state.db.update_session(&session_id, title)
}

#[tauri::command]
pub async fn db_delete_session(
    state: State<'_, AppState>,
    session_id: String,
) -> Result<bool, String> {
    state.db.delete_session(&session_id)
}

#[tauri::command]
pub async fn db_add_message(
    state: State<'_, AppState>,
    session_id: String,
    role: String,
    content: String,
) -> Result<Message, String> {
    state.db.add_message(&session_id, &role, &content)
}

#[tauri::command]
pub async fn db_get_messages(
    state: State<'_, AppState>,
    session_id: String,
    page: i32,
    page_size: i32,
) -> Result<PaginatedResult<Message>, String> {
    state.db.get_messages(&session_id, page, page_size)
}

#[tauri::command]
pub async fn db_delete_message(
    state: State<'_, AppState>,
    message_id: String,
) -> Result<bool, String> {
    state.db.delete_message(&message_id)
}

#[tauri::command]
pub async fn export_conversation(
    state: State<'_, AppState>,
    session_id: String,
) -> Result<String, String> {
    use chrono::{DateTime, Local};
    
    // Get session info
    let session = state.db.get_session(&session_id)
        .map_err(|e| format!("Failed to get session: {}", e))?;
    
    // Get all messages for the session
    let messages = state.db.get_messages(&session_id, 0, 1000)
        .map_err(|e| format!("Failed to get messages: {}", e))?;
    
    // Build Markdown content
    let mut markdown = format!("# {}\n\n", session.title);
    markdown.push_str(&format!("导出时间: {}\n\n", Local::now().format("%Y-%m-%d %H:%M:%S")));
    markdown.push_str("---\n\n");
    
    for msg in messages.items {
        let role_emoji = match msg.role.as_str() {
            "user" => "👤 用户",
            "assistant" => "🤖 助手",
            _ => "📝 系统",
        };
        let timestamp = DateTime::from_timestamp_millis(msg.timestamp)
            .map(|dt| dt.format("%Y-%m-%d %H:%M:%S").to_string())
            .unwrap_or_else(|| "Unknown".to_string());
        
        markdown.push_str(&format!("### {} - {}\n\n{}\n\n", role_emoji, timestamp, msg.content));
    }
    
    Ok(markdown)
}
