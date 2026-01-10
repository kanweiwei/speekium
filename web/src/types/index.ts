export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  language?: string;
}

export interface AppState {
  isRecording: boolean;
  isProcessing: boolean;
  isSpeaking: boolean;
  historyCount: number;
}

export interface RecordingResult {
  success: boolean;
  text?: string;
  language?: string;
  audioLength?: number;
  message?: string;
}

export interface ChatChunk {
  type: 'partial' | 'complete' | 'error';
  content: string;
  audio?: string;  // Base64 encoded audio data
  audioFormat?: string;  // MIME type (e.g., 'audio/mpeg', 'audio/wav')
}

export interface AppConfig {
  llm_backend: 'claude' | 'ollama';
  ollama_model: string;
  ollama_base_url: string;
  tts_backend: 'edge' | 'piper';
  tts_rate: string;
  vad_threshold: number;
  max_history: number;
}

export interface PywebviewApi {
  start_recording: () => Promise<RecordingResult>;
  clear_history: () => Promise<void>;
  get_status: () => Promise<AppState>;
  chat_generator: (text: string, language: string) => Promise<ChatChunk[]>;
  get_config: () => Promise<AppConfig>;
  save_config: (config: Partial<AppConfig>) => Promise<void>;
  restart_assistant: () => Promise<void>;
}
