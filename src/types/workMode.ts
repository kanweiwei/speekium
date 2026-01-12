/**
 * Work Mode Type Definitions
 */

/**
 * Work mode enumeration
 * - conversation: Conversation mode (Voice → AI dialogue → TTS playback)
 * - text: Text input mode (Voice → Direct text input to focused field)
 */
export type WorkMode = 'conversation' | 'text';

/**
 * Work mode configuration interface
 */
export interface WorkModeConfig {
  /** Current work mode */
  currentMode: WorkMode;
  /** Last modified timestamp */
  lastModified: number;
}

/**
 * Work mode change event interface
 */
export interface WorkModeChangeEvent {
  /** New work mode */
  mode: WorkMode;
  /** Event timestamp */
  timestamp: number;
  /** Event source */
  source: 'settings' | 'tray' | 'hotkey' | 'api';
}

/**
 * Work mode display information interface
 */
export interface WorkModeDisplayInfo {
  /** Mode identifier */
  mode: WorkMode;
  /** Display label */
  label: string;
  /** Description */
  description: string;
  /** Icon name (Lucide React) */
  icon: 'MessageCircle' | 'Type';
  /** Theme color */
  color: 'blue' | 'green';
}

/**
 * Work mode metadata mapping
 */
export const WORK_MODE_INFO: Record<WorkMode, WorkModeDisplayInfo> = {
  conversation: {
    mode: 'conversation',
    label: 'Conversation Mode',
    description: 'Voice → AI conversation → Text-to-Speech',
    icon: 'MessageCircle',
    color: 'blue',
  },
  text: {
    mode: 'text',
    label: 'Text Input Mode',
    description: 'Voice → Direct text input to focused field',
    icon: 'Type',
    color: 'green',
  },
};

/**
 * Default work mode
 */
export const DEFAULT_WORK_MODE: WorkMode = 'conversation';

/**
 * LocalStorage key name
 */
export const WORK_MODE_STORAGE_KEY = 'speekium-work-mode';
