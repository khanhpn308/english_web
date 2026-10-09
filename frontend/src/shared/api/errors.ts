import { ApiError, NetworkError, MutationUnknownError } from './client';

export type ErrorRecoveryActionType =
  | 'RETRY'
  | 'RECONCILE'
  | 'REBOOTSTRAP'
  | 'RELOAD'
  | 'UPDATE_CONSENT'
  | 'NONE';

export interface UIErrorState {
  title: string;
  message: string;
  actionType: ErrorRecoveryActionType;
  requestId?: string;
  idempotencyKey?: string;
  operationId?: string;
  isTerminal: boolean;
}

export function mapErrorToUIState(error: unknown): UIErrorState {
  if (error instanceof MutationUnknownError) {
    return {
      title: 'Connection Lost',
      message: 'We lost connection to the server. The action might have completed successfully. You can safely attempt to reconcile or retry.',
      actionType: 'RECONCILE',
      idempotencyKey: error.idempotencyKey,
      operationId: error.operationId,
      isTerminal: false,
    };
  }

  if (error instanceof NetworkError) {
    return {
      title: 'Cannot Reach Server',
      message: 'The local API server is unavailable. Please check if the backend is running.',
      actionType: 'RETRY',
      isTerminal: true,
    };
  }

  if (error instanceof ApiError) {
    const requestId = error.requestId;
    
    switch (error.code) {
      case 'SESSION_REQUIRED':
      case 'SESSION_INVALID':
        return {
          title: 'Session Expired',
          message: 'Your session has expired or is invalid. Please log in again.',
          actionType: 'REBOOTSTRAP',
          requestId,
          isTerminal: true,
        };
      case 'BRIDGE_UNAVAILABLE':
      case 'BRIDGE_INVALID_RESPONSE':
      case 'BRIDGE_AUTH_ERROR':
      case 'NETWORK_REQUIRED':
        return {
          title: 'AI Bridge Unavailable',
          message: 'The AI bridge is currently down, timed out, or not reachable. Please try again later.',
          actionType: 'RETRY',
          requestId,
          isTerminal: true,
        };
      case 'CONFIGURATION_REQUIRED':
        return {
          title: 'Configuration Required',
          message: 'The application configuration is missing or incomplete.',
          actionType: 'NONE',
          requestId,
          isTerminal: true,
        };
      case 'AI_CONSENT_REQUIRED':
      case 'AI_POLICY_CHANGED':
        return {
          title: 'Consent Required',
          message: error.message || 'You must review and grant AI consent to continue.',
          actionType: 'UPDATE_CONSENT',
          requestId,
          isTerminal: true,
        };
      case 'REVISION_CONFLICT':
        return {
          title: 'Conflict',
          message: 'The resource has been modified by another process. Please reload to see the latest version.',
          actionType: 'RELOAD',
          requestId,
          isTerminal: true,
        };
      case 'IDEMPOTENCY_IN_FLIGHT':
        return {
          title: 'In Progress',
          message: 'This action is already being processed.',
          actionType: 'NONE',
          requestId,
          isTerminal: false,
        };
      case 'IDEMPOTENCY_KEY_REUSED':
        return {
          title: 'Invalid Retry',
          message: 'This exact action has already been performed with different parameters.',
          actionType: 'NONE',
          requestId,
          isTerminal: true,
        };
      case 'STORAGE_UNAVAILABLE':
      case 'STORAGE_BUSY':
        return {
          title: 'Storage Unavailable',
          message: 'Local storage or database is currently busy or unavailable.',
          actionType: 'RETRY',
          requestId,
          isTerminal: true,
        };
      case 'VALIDATION_ERROR':
      case 'CROSS_RESOURCE_MISMATCH':
        return {
          title: 'Invalid Request',
          message: error.message || 'The request was invalid.',
          actionType: 'NONE',
          requestId,
          isTerminal: true,
        };
      case 'INTERNAL_ERROR':
        return {
          title: 'Internal Server Error',
          message: 'An unexpected internal error occurred.',
          actionType: 'RETRY',
          requestId,
          isTerminal: true,
        };
      default:
        return {
          title: 'Error',
          message: error.message || 'An unexpected error occurred.',
          actionType: 'NONE',
          requestId,
          isTerminal: true,
        };
    }
  }

  return {
    title: 'Unexpected Error',
    message: error instanceof Error ? error.message : 'An unknown error occurred.',
    actionType: 'NONE',
    isTerminal: true,
  };
}
