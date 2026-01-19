// src-tauri/src/types.rs
//
// 类型定义模块

use serde::{Deserialize, Serialize};

// ============================================================================
// 录音模式
// ============================================================================

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RecordingMode {
    Continuous,
    PushToTalk,
}

impl RecordingMode {
    pub fn as_str(&self) -> &'static str {
        match self {
            RecordingMode::Continuous => "continuous",
            RecordingMode::PushToTalk => "push-to-talk",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "continuous" => Some(RecordingMode::Continuous),
            "push-to-talk" => Some(RecordingMode::PushToTalk),
            _ => None,
        }
    }
}

// ============================================================================
// 工作模式
// ============================================================================

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum WorkMode {
    Conversation,
    TextInput,
}

impl WorkMode {
    pub fn as_str(&self) -> &'static str {
        match self {
            WorkMode::Conversation => "conversation",
            WorkMode::TextInput => "text-input",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "conversation" => Some(WorkMode::Conversation),
            "text-input" => Some(WorkMode::TextInput),
            _ => None,
        }
    }
}

// ============================================================================
// 应用状态
// ============================================================================

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppStatus {
    Idle,              // 空闲状态
    Listening,         // 自动模式监听中
    Recording,         // 录音中
    AsrProcessing,     // ASR识别中
    LlmProcessing,     // LLM思考中
    TtsProcessing,     // TTS生成中
    Playing,           // TTS播放中
}

impl AppStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            AppStatus::Idle => "idle",
            AppStatus::Listening => "listening",
            AppStatus::Recording => "recording",
            AppStatus::AsrProcessing => "asr",
            AppStatus::LlmProcessing => "llm",
            AppStatus::TtsProcessing => "tts",
            AppStatus::Playing => "playing",
        }
    }

    pub fn from_str(s: &str) -> Option<Self> {
        match s {
            "idle" => Some(AppStatus::Idle),
            "listening" => Some(AppStatus::Listening),
            "recording" => Some(AppStatus::Recording),
            "asr" => Some(AppStatus::AsrProcessing),
            "llm" => Some(AppStatus::LlmProcessing),
            "tts" => Some(AppStatus::TtsProcessing),
            "playing" => Some(AppStatus::Playing),
            _ => None,
        }
    }

    pub fn can_be_interrupted(&self, interrupt_priority: u8) -> bool {
        match interrupt_priority {
            1 => true,  // Mode switch: can interrupt everything
            2 => matches!(self, AppStatus::Recording | AppStatus::Listening),  // Manual stop
            3 => !matches!(self, AppStatus::Recording),  // App exit: wait for recording
            _ => false,
        }
    }
}

// ============================================================================
// 守护进程模式
// ============================================================================

#[derive(Debug)]
pub enum DaemonMode {
    Development { script_path: std::path::PathBuf },
    Production { executable_path: std::path::PathBuf },
}

// ============================================================================
// 命令结果类型
// ============================================================================

#[derive(Serialize, Deserialize, Debug)]
pub struct RecordResult {
    pub success: bool,
    pub text: Option<String>,
    pub language: Option<String>,
    pub error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct ChatResult {
    pub success: bool,
    pub content: Option<String>,
    pub error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct TTSResult {
    pub success: bool,
    pub audio_path: Option<String>,
    pub error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct ConfigResult {
    pub success: bool,
    pub config: Option<serde_json::Value>,
    pub error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct HealthResult {
    pub success: bool,
    pub status: Option<String>,
    pub command_count: Option<u32>,
    pub models_loaded: Option<serde_json::Value>,
    pub error: Option<String>,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct ModelInfo {
    pub loaded: bool,
    pub exists: bool,
    pub name: String,
    pub path: String,
    pub size: String,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct ModelStatusResult {
    pub success: bool,
    pub models: Option<serde_json::Value>,
    pub error: Option<String>,
}

#[derive(Clone, Serialize, Debug)]
pub struct DaemonStatusPayload {
    pub status: String,   // "loading" | "ready" | "error"
    pub message: String,  // User-readable status message
}

/// Download progress event payload
#[derive(Clone, Serialize, Debug)]
pub struct DownloadProgressPayload {
    pub event_type: String,  // "started" | "progress" | "completed"
    pub model: String,       // Model name (e.g., "SenseVoice ASR", "Silero VAD")
    pub percent: Option<u32>, // Download progress percentage (0-100)
    pub speed: Option<String>, // Download speed (e.g., "1.5 MB/s")
    pub total_size: Option<String>, // Total size (e.g., "200 MB")
    pub downloaded: Option<u64>, // Bytes downloaded
    pub total: Option<u64>,   // Total bytes
}

/// Model loading progress event payload
#[derive(Clone, Serialize, Debug)]
pub struct ModelLoadingPayload {
    pub stage: String,       // "vad" | "asr" | "llm" | "tts" | "complete"
    pub status: String,      // "loading" | "loaded" | "skipped"
    pub message: String,     // User-readable message
}
