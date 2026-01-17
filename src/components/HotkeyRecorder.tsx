import { useState, useCallback, useEffect, useRef } from 'react';
import { HotkeyConfig, ModifierKey } from '../types/hotkey';
import { parseHotkeyDisplay } from '../utils/hotkeyParser';
import styles from './HotkeyRecorder.module.css';

interface HotkeyRecorderProps {
  value: HotkeyConfig;
  onChange: (config: HotkeyConfig) => void;
  disabled?: boolean;
}

const MODIFIER_DISPLAY: Record<ModifierKey, string> = {
  'CmdOrCtrl': '⌘',
  'Shift': '⇧',
  'Alt': '⌥',
  'Meta': '◆',
};

// Helper function to parse hotkey config into display keys
function getDisplayKeys(config: HotkeyConfig): string[] {
  // Use the same parsing logic as parseHotkeyDisplay for consistency
  return parseHotkeyDisplay(config);
}

export function HotkeyRecorder({ value, onChange, disabled }: HotkeyRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [currentKeys, setCurrentKeys] = useState<string[]>([]);
  const recordingRef = useRef(false);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (!recordingRef.current) return;

    e.preventDefault();
    e.stopPropagation();

    // Escape to cancel
    if (e.key === 'Escape') {
      setIsRecording(false);
      setCurrentKeys([]);
      recordingRef.current = false;
      return;
    }

    const keys: string[] = [];
    const modifiers: ModifierKey[] = [];

    // Collect modifiers
    if (e.metaKey || e.ctrlKey) {
      modifiers.push('CmdOrCtrl');
      keys.push(MODIFIER_DISPLAY['CmdOrCtrl']);
    }
    if (e.shiftKey) {
      modifiers.push('Shift');
      keys.push(MODIFIER_DISPLAY['Shift']);
    }
    if (e.altKey) {
      modifiers.push('Alt');
      keys.push(MODIFIER_DISPLAY['Alt']);
    }

    // Get main key (not a modifier)
    if (!['Control', 'Meta', 'Alt', 'Shift'].includes(e.key)) {
      const displayKey = e.key.length === 1 ? e.key.toUpperCase() : e.key;
      keys.push(displayKey);

      const newConfig: HotkeyConfig = {
        modifiers,
        key: e.code,
        displayName: keys.join('+'),
      };

      onChange(newConfig);
      setIsRecording(false);
      setCurrentKeys([]);
      recordingRef.current = false;
    } else {
      // Show current modifiers being pressed
      setCurrentKeys(keys);
    }
  }, [onChange]);

  const handleKeyUp = useCallback((e: KeyboardEvent) => {
    if (!recordingRef.current) return;
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const startRecording = useCallback(() => {
    if (disabled) return;
    setIsRecording(true);
    setCurrentKeys([]);
    recordingRef.current = true;
  }, [disabled]);

  useEffect(() => {
    if (isRecording) {
      window.addEventListener('keydown', handleKeyDown, { capture: true });
      window.addEventListener('keyup', handleKeyUp, { capture: true });

      return () => {
        window.removeEventListener('keydown', handleKeyDown, { capture: true });
        window.removeEventListener('keyup', handleKeyUp, { capture: true });
      };
    }
  }, [isRecording, handleKeyDown, handleKeyUp]);

  return (
    <div className={styles.recorderContainer}>
      <div className={styles.hotkeyDisplay}>
        {isRecording ? (
          currentKeys.length > 0 ? (
            currentKeys.map((key, i) => (
              <span key={i} className={styles.key}>{key}</span>
            ))
          ) : (
            <span className={styles.hint}>按下快捷键...</span>
          )
        ) : (
          getDisplayKeys(value).map((key, i) => (
            <span key={i} className={styles.key}>{key}</span>
          ))
        )}
      </div>
      <button
        className={`${styles.recorderButton} ${isRecording ? styles.recording : ''}`}
        onClick={startRecording}
        disabled={disabled}
      >
        {isRecording ? '录制中... (ESC 取消)' : '录制'}
      </button>
    </div>
  );
}
