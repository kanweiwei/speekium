import type { HotkeyConfig } from '@/types/hotkey';

/**
 * Parse hotkey configuration into individual key parts for display
 * @param config - Hotkey configuration object
 * @returns Array of key symbols to display (e.g., ['⌘', '1'])
 */
export function parseHotkeyDisplay(config?: HotkeyConfig | null): string[] {
  if (!config) {
    return ['⌥', '3']; // Default fallback: Alt+3
  }

  const keyParts: string[] = [];
  const modifiers = config.modifiers || [];
  const key = config.key || '';

  // Parse modifier keys
  if (modifiers.includes('CmdOrCtrl')) {
    keyParts.push('⌘');
  }
  if (modifiers.includes('Shift')) {
    keyParts.push('⇧');
  }
  if (modifiers.includes('Alt')) {
    keyParts.push('⌥');
  }

  // Parse main key
  if (key.startsWith('Digit')) {
    keyParts.push(key.replace('Digit', ''));
  } else if (key.startsWith('Key')) {
    keyParts.push(key.replace('Key', '').toUpperCase());
  } else if (key) {
    keyParts.push(key);
  } else {
    // Fallback if no key specified
    keyParts.push('3');
  }

  return keyParts;
}

/**
 * Get hotkey display name from config
 * @param config - Hotkey configuration object
 * @returns Display name (e.g., '⌥+3')
 */
export function getHotkeyDisplayName(config?: HotkeyConfig | null): string {
  // Always parse dynamically from modifiers and key, don't use stored displayName
  // This ensures display is always in sync with the actual configuration
  const parts = parseHotkeyDisplay(config);
  return parts.join('+');
}
