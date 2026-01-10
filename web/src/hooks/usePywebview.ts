import { useState, useEffect } from 'react';
import { AppState, PywebviewApi } from '../types';

interface WindowWithPywebview extends Window {
  pywebview?: {
    api: PywebviewApi;
    state: AppState;
  };
}

declare const window: WindowWithPywebview;

export function usePywebview() {
  const [isReady, setIsReady] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [historyCount, setHistoryCount] = useState(0);

  useEffect(() => {
    if (window.pywebview) {
      setIsReady(true);
      
      const handleStateChange = (e: any) => {
        const newState = e.detail;
        if ('is_recording' in newState) {
          setIsRecording(newState.is_recording);
        }
        if ('is_processing' in newState) {
          setIsProcessing(newState.is_processing);
        }
        if ('is_speaking' in newState) {
          setIsSpeaking(newState.is_speaking);
        }
        if ('history_count' in newState) {
          setHistoryCount(newState.history_count);
        }
      };

      window.addEventListener('pywebview-state-change', handleStateChange);
      
      return () => {
        window.removeEventListener('pywebview-state-change', handleStateChange);
      };
    }
  }, []);

  return {
    isReady,
    isRecording,
    isProcessing,
    isSpeaking,
    historyCount,
    api: window.pywebview?.api
  };
}
