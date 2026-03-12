/**
 * Error Context Provider
 *
 * Provides centralized error state management for the entire application.
 * Handles global errors, API errors, and uncaught exceptions.
 */

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { SystemToast } from '@/components/SystemToast';

/**
 * Error type definition
 */
export interface AppError {
  /** Unique error ID */
  id: string;
  /** Error message */
  message: string;
  /** Error type/category */
  type: 'api' | 'network' | 'runtime' | 'permission' | 'unknown';
  /** Timestamp when error occurred */
  timestamp: number;
  /** Whether the error has been dismissed */
  dismissed: boolean;
}

/**
 * ErrorContext interface definition
 */
interface ErrorContextValue {
  /** Current active error (most recent undismissed) */
  currentError: AppError | null;
  /** All errors in the queue */
  errorQueue: AppError[];
  /** Add a new error to the queue */
  addError: (message: string, type?: AppError['type']) => void;
  /** Dismiss the current error */
  dismissError: () => void;
  /** Clear all errors */
  clearErrors: () => void;
  /** Check if there are any active errors */
  hasErrors: boolean;
}

/**
 * Create Context
 */
const ErrorContext = createContext<ErrorContextValue | undefined>(undefined);

/**
 * Generate unique error ID
 */
function generateErrorId(): string {
  return `error-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * ErrorProvider component
 *
 * Provides global state management for application errors
 */
export function ErrorProvider({ children }: { children: React.ReactNode }) {
  const [errorQueue, setErrorQueue] = useState<AppError[]>([]);
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(new Set());

  /**
   * Add a new error to the queue
   */
  const addError = useCallback((message: string, type: AppError['type'] = 'unknown') => {
    const newError: AppError = {
      id: generateErrorId(),
      message,
      type,
      timestamp: Date.now(),
      dismissed: false,
    };

    setErrorQueue(prev => [...prev, newError]);

    // Auto-dismiss after 5 seconds for non-critical errors
    if (type !== 'runtime') {
      setTimeout(() => {
        setDismissedIds(prev => new Set([...prev, newError.id]));
      }, 5000);
    }
  }, []);

  /**
   * Dismiss the current (oldest) error
   */
  const dismissError = useCallback(() => {
    const activeErrors = errorQueue.filter(e => !dismissedIds.has(e.id));
    if (activeErrors.length > 0) {
      setDismissedIds(prev => new Set([...prev, activeErrors[0].id]));
    }
  }, [errorQueue, dismissedIds]);

  /**
   * Clear all errors
   */
  const clearErrors = useCallback(() => {
    setErrorQueue([]);
    setDismissedIds(new Set());
  }, []);

  /**
   * Get active (non-dismissed) errors
   */
  const activeErrors = errorQueue.filter(e => !dismissedIds.has(e.id));

  /**
   * Current error (most recent)
   */
  const currentError = activeErrors.length > 0 ? activeErrors[activeErrors.length - 1] : null;

  /**
   * Check if there are any active errors
   */
  const hasErrors = activeErrors.length > 0;

  /**
   * Set up global error handlers
   */
  useEffect(() => {
    // Handle uncaught JavaScript errors
    const handleGlobalError = (event: ErrorEvent) => {
      console.error('[ErrorContext] Uncaught error:', event.error);
      addError(event.message || 'An unexpected error occurred', 'runtime');
    };

    // Handle unhandled promise rejections
    const handleUnhandledRejection = (event: PromiseRejectionEvent) => {
      console.error('[ErrorContext] Unhandled rejection:', event.reason);
      const message = event.reason?.message || event.reason?.toString() || 'An unexpected error occurred';
      addError(message, 'runtime');
    };

    window.addEventListener('error', handleGlobalError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);

    return () => {
      window.removeEventListener('error', handleGlobalError);
      window.removeEventListener('unhandledrejection', handleUnhandledRejection);
    };
  }, [addError]);

  const contextValue: ErrorContextValue = {
    currentError,
    errorQueue: activeErrors,
    addError,
    dismissError,
    clearErrors,
    hasErrors,
  };

  return (
    <ErrorContext.Provider value={contextValue}>
      {children}
      {/* Render SystemToast for current error */}
      {currentError && (
        <SystemToast
          type="error"
          message={currentError.message}
          duration={0} // Don't auto-close critical errors
          onClose={dismissError}
        />
      )}
    </ErrorContext.Provider>
  );
}

/**
 * useError Hook
 *
 * Used to access error state and methods in components
 *
 * @example
 * ```tsx
 * const { currentError, addError, dismissError } = useError();
 * ```
 */
export const useError = (): ErrorContextValue => {
  const context = useContext(ErrorContext);
  if (!context) {
    throw new Error('useError must be used within ErrorProvider');
  }
  return context;
};
