// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Speekium contributors

/**
 * Enum definitions for shared-types
 */

/**
 * Recording mode - how the user triggers recording
 */
export enum RecordingMode {
  PushToTalk = "push-to-talk",
  Continuous = "continuous",
}

/**
 * Work mode - how the user interacts with the assistant
 */
export enum WorkMode {
  Conversation = "conversation",
  TextInput = "text-input",
}

/**
 * Application status
 */
export enum AppStatus {
  Idle = "idle",
  Listening = "listening",
  Recording = "recording",
  AsrProcessing = "asr-processing",
  LlmProcessing = "llm-processing",
  TtsProcessing = "tts-processing",
  Playing = "playing",
  Error = "error",
}

/**
 * Daemon status
 */
export enum DaemonStatus {
  Starting = "starting",
  Ready = "ready",
  Busy = "busy",
  Stopped = "stopped",
  Error = "error",
}

/**
 * Health status of a component
 */
export enum HealthStatus {
  Healthy = "healthy",
  Degraded = "degraded",
  Unhealthy = "unhealthy",
  Unknown = "unknown",
}

/**
 * Processing stage
 */
export enum ProcessingStage {
  Asr = "asr",
  Llm = "llm",
  Tts = "tts",
}

/**
 * Model type
 */
export enum ModelType {
  Asr = "asr",
  Llm = "llm",
  Vad = "vad",
  Tts = "tts",
}

/**
 * Progress stage for model loading
 */
export enum ProgressStage {
  Downloading = "downloading",
  Verifying = "verifying",
  Loading = "loading",
  Ready = "ready",
}

/**
 * PTT state
 */
export enum PttState {
  Idle = "idle",
  Pressed = "pressed",
  Locked = "locked",
}

/**
 * Message role in chat
 */
export enum MessageRole {
  User = "user",
  Assistant = "assistant",
  System = "system",
}

/**
 * Event category for filtering
 */
export enum EventCategory {
  State = "state",
  Recording = "recording",
  Processing = "processing",
  Config = "config",
  Daemon = "daemon",
  Model = "model",
  Chat = "chat",
  Audio = "audio",
  Ptt = "ptt",
  Ui = "ui",
  Error = "error",
}

/**
 * Error category
 */
export enum ErrorCategory {
  Network = "network",
  Io = "io",
  Serialization = "serialization",
  Model = "model",
  Daemon = "daemon",
  Config = "config",
  Unknown = "unknown",
}

/**
 * Stop reason for recording
 */
export enum StopReason {
  User = "user",
  Silence = "silence",
  Timeout = "timeout",
  Error = "error",
}
