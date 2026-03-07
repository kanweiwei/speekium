import { useState, useCallback, useEffect, useRef } from 'react';
import { HotkeyConfig, ModifierKey } from '../types/hotkey';
import { parseHotkeyDisplay } from '../utils/hotkeyParser';
import styles from './HotkeyRecorder.module.css';

interface HotkeyRecorderProps {
  value: HotkeyConfig;
  onChange: (config: HotkeyConfig) => void;
  disabled?: boolean;
  defaultValue?: HotkeyConfig;
}

// 预设快捷键方案
const PRESET_HOTKEYS: { label: string; config: HotkeyConfig }[] = [
  { label: '空格', config: { modifiers: [], key: 'Space', displayName: 'Space' } },
  { label: '⌘ + 空格', config: { modifiers: ['CmdOrCtrl'], key: 'Space', displayName: '⌘+Space' } },
  { label: '⌘ + Shift + S', config: { modifiers: ['CmdOrCtrl', 'Shift'], key: 'KeyS', displayName: '⌘+⇧+S' } },
  { label: '⌥ + 空格', config: { modifiers: ['Alt'], key: 'Space', displayName: '⌥+Space' } },
];

const MODIFIER_DISPLAY: Record<ModifierKey, string> = {
  'CmdOrCtrl': '⌘',
  'Shift': '⇧',
  'Alt': '⌥',
  'Meta': '◆',
};

function getDisplayKeys(config: HotkeyConfig): string[] {
  return parseHotkeyDisplay(config);
}

export function HotkeyRecorder({ 
  value, 
  onChange, 
  disabled,
  defaultValue 
}: HotkeyRecorderProps) {
  const [isRecording, setIsRecording] = useState(false);
  const [currentKeys, setCurrentKeys] = useState<string[]>([]);
  const [showPresets, setShowPresets] = useState(false);
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

  const resetToDefault = useCallback(() => {
    if (defaultValue) {
      onChange(defaultValue);
    }
  }, [defaultValue, onChange]);

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

  const handlePresetClick = (preset: typeof PRESET_HOTKEYS[number]) => {
    onChange(preset.config);
    setShowPresets(false);
  };

  const hasValue = value && (value.modifiers.length > 0 || value.key);

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
        ) : hasValue ? (
          getDisplayKeys(value).map((key, i) => (
            <span key={i} className={styles.key}>{key}</span>
          ))
        ) : (
          <span className={styles.hint}>点击录制...</span>
        )}
      </div>
      
      <div className={styles.buttonGroup}>
        <button
          className={`${styles.recorderButton} ${isRecording ? styles.recording : ''}`}
          onClick={startRecording}
          disabled={disabled}
        >
          {isRecording ? '录制中... (ESC 取消)' : '录制'}
        </button>

        {defaultValue && hasValue && (
          <button
            className={`${styles.recorderButton} ${styles.resetButton}`}
            onClick={resetToDefault}
            disabled={disabled}
            title="重置为默认"
          >
            ↩
          </button>
        )}

        <button
          className={`${styles.recorderButton} ${showPresets ? styles.presetsActive : ''}`}
          onClick={() => setShowPresets(!showPresets)}
          disabled={disabled}
        >
          ⋮
        </button>
      </div>

      {showPresets && (
        <div className={styles.presetsDropdown}>
          {PRESET_HOTKEYS.map((preset, i) => (
            <button
              key={i}
              className={styles.presetItem}
              onClick={() => handlePresetClick(preset)}
              disabled={disabled}
            >
              <span className={styles.presetLabel}>{preset.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
