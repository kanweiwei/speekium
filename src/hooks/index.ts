/**
 * Hooks Index
 *
 * Exports all custom React hooks for Speekium.
 */

// Event listener hooks
export {
  useEventListener,
  useEventListenerSubscription,
  useRecordingEvents,
  useProcessingEvents,
  useDaemonEvents,
  useModelEvents,
  useChatEvents,
  useErrorEvents,
  usePttEvents,
  type UseEventListenerReturn,
  type EventCallback,
  type EventFilterOptions,
} from './useEventListener';

// App state hooks
export {
  useAppState,
  useRecordingState,
  useProcessingState,
  useDaemonState,
  useChatState,
  useUIState,
  useErrorState,
  type UseAppStateReturn,
} from './useAppState';
