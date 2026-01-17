// src-tauri/src/platform/mod.rs
//
// 平台特定代码模块

#[cfg(target_os = "macos")]
pub mod macos;

#[cfg(target_os = "macos")]
pub use macos::type_text;

// Tauri command - must be in the same module where it's registered
#[tauri::command]
pub async fn type_text_command(text: String) -> Result<String, String> {

    #[cfg(target_os = "macos")]
    {
        type_text(&text)?;
        Ok(format!("Typed {} characters", text.chars().count()))
    }

    #[cfg(not(target_os = "macos"))]
    {
        Err("Text input is only supported on macOS".to_string())
    }
}
