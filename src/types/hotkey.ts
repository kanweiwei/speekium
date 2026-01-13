/**
 * Modifier key types for hotkey combinations
 */
export type ModifierKey = 'CmdOrCtrl' | 'Shift' | 'Alt' | 'Meta';

/**
 * Hotkey configuration structure
 */
export interface HotkeyConfig {
  modifiers: ModifierKey[];
  key: string;
  displayName: string;
}

/**
 * Keyboard event for recording
 */
export interface KeyboardEvent {
  code: string;
  key: string;
  modifiers: ModifierKey[];
}

/**
 * Validation result
 */
export interface HotkeyValidation {
  valid: boolean;
  error?: string;
}
