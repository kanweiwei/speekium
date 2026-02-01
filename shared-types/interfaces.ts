// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Speekium contributors

/**
 * Interface definitions for shared-types
 */

import type {
  RecordingMode,
  WorkMode,
  AppStatus,
  DaemonStatus,
  ProcessingStage,
  MessageRole,
  ErrorCategory,
} from './enums';

/**
 * Recording state
 */
export interface RecordingState {
  is_recording: boolean;
  is_processing: boolean;
  audio_level_db: number;
  duration_seconds: number;
}

/**
 * Processing state
 */
export interface ProcessingState {
  current_stage: ProcessingStage | null;
  stage_progress: number;
  stage_message: string;
}

/**
 * Processing result
 */
export interface ProcessingResult {
  success: boolean;
  output?: string;
  error?: string;
}

/**
 * User configuration
 */
export interface UserConfig {
  llm_provider: string;
  llm_model: string;
  tts_backend: string;
  recording_mode: RecordingMode;
  work_mode: WorkMode;
  theme: string;
  language: string;
}

/**
 * Chat message
 */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
}

/**
 * Audio level info
 */
export interface AudioLevel {
  rms: number;
  peak: number;
  db: number;
}

/**
 * Statistics
 */
export interface Statistics {
  total_conversations: number;
  total_messages: number;
  total_recording_time: number;
  average_response_time: number;
}

/**
 * Error information
 */
export interface ErrorInfo {
  id: string;
  category: ErrorCategory;
  message: string;
  context?: Record<string, unknown>;
  timestamp: number;
  recoverable: boolean;
}

/**
 * Application state snapshot
 */
export interface AppStateSnapshot {
  timestamp: number;
  app_status: AppStatus;
  recording_state: RecordingState;
  processing_state: ProcessingState;
  work_mode: WorkMode;
  recording_mode: RecordingMode;
  daemon_status: DaemonStatus;
  daemon_connected: boolean;
}
