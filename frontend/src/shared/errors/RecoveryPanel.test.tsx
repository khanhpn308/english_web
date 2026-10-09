import * as React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { RecoveryPanel } from './RecoveryPanel';
import { ApiError, NetworkError, MutationUnknownError } from '../api/client';

describe('RecoveryPanel', () => {
  it('renders nothing when error is null', () => {
    const { container } = render(<RecoveryPanel error={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('renders generic unexpected error', () => {
    render(<RecoveryPanel error={new Error('Something bad')} />);
    expect(screen.getByText('Unexpected Error')).toBeInTheDocument();
    expect(screen.getByText('Something bad')).toBeInTheDocument();
  });

  it('handles NetworkError and shows Retry', async () => {
    const onRetry = vi.fn();
    const error = new NetworkError('Failed to fetch', 'GET', '/api/test');
    
    render(<RecoveryPanel error={error} onRetry={onRetry} />);
    
    expect(screen.getByText('Cannot Reach Server')).toBeInTheDocument();
    
    const retryBtn = screen.getByRole('button', { name: /Retry Action/i });
    await userEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it('handles MutationUnknownError and shows Check Status', async () => {
    const onReconcile = vi.fn();
    const error = new MutationUnknownError('Unknown', 'POST', '/api', 'idemp_key_1', 'op_123');
    
    render(<RecoveryPanel error={error} onReconcile={onReconcile} />);
    
    expect(screen.getByText('Connection Lost')).toBeInTheDocument();
    
    const reconcileBtn = screen.getByRole('button', { name: /Check Status/i });
    await userEvent.click(reconcileBtn);
    expect(onReconcile).toHaveBeenCalledWith('idemp_key_1', 'op_123');
  });

  it('renders request ID safely and masks sensitive data', () => {
    const error = new ApiError(422, {
      code: 'VALIDATION_ERROR',
      message: 'Invalid request',
      requestId: 'req_safe_id_123'
    });

    render(<RecoveryPanel error={error} />);
    
    expect(screen.getByText('Invalid Request')).toBeInTheDocument();
    expect(screen.getByText('Request ID: req_safe_id_123')).toBeInTheDocument();
    // Verify no stack trace or sensitive info
    expect(screen.queryByText(/stack/i)).not.toBeInTheDocument();
  });

  describe('ApiError mappings', () => {
    const testCases = [
      { code: 'SESSION_REQUIRED', title: 'Session Expired', button: 'Log In Again', action: 'onRebootstrap' },
      { code: 'SESSION_INVALID', title: 'Session Expired', button: 'Log In Again', action: 'onRebootstrap' },
      { code: 'BRIDGE_UNAVAILABLE', title: 'AI Bridge Unavailable', button: 'Retry Action', action: 'onRetry' },
      { code: 'CONFIGURATION_REQUIRED', title: 'Configuration Required', button: null, action: null },
      { code: 'AI_CONSENT_REQUIRED', title: 'Consent Required', button: 'Review Consent', action: 'onUpdateConsent' },
      { code: 'AI_POLICY_CHANGED', title: 'Consent Required', button: 'Review Consent', action: 'onUpdateConsent' },
      { code: 'REVISION_CONFLICT', title: 'Conflict', button: 'Reload Content', action: 'onReload' },
      { code: 'IDEMPOTENCY_IN_FLIGHT', title: 'In Progress', button: null, action: null },
      { code: 'IDEMPOTENCY_KEY_REUSED', title: 'Invalid Retry', button: null, action: null },
      { code: 'STORAGE_UNAVAILABLE', title: 'Storage Unavailable', button: 'Retry Action', action: 'onRetry' },
      { code: 'VALIDATION_ERROR', title: 'Invalid Request', button: null, action: null },
      { code: 'CROSS_RESOURCE_MISMATCH', title: 'Invalid Request', button: null, action: null },
      { code: 'UNKNOWN_CODE', title: 'Error', button: null, action: null },
    ];

    testCases.forEach(({ code, title, button, action }) => {
      it(`maps ${code} correctly`, async () => {
        const error = new ApiError(400, {
          code,
          message: 'Test message',
          requestId: 'req_123'
        });

        const actions = {
          onRetry: vi.fn(),
          onRebootstrap: vi.fn(),
          onReload: vi.fn(),
          onUpdateConsent: vi.fn(),
        };

        render(<RecoveryPanel error={error} {...actions} />);
        
        expect(screen.getByText(title)).toBeInTheDocument();
        
        if (button) {
          const btn = screen.getByRole('button', { name: new RegExp(button, 'i') });
          expect(btn).toBeInTheDocument();
          if (action) {
            await userEvent.click(btn);
            expect(actions[action as keyof typeof actions]).toHaveBeenCalledOnce();
          }
        }
      });
    });
  });

  it('supports accessibility attributes', () => {
    const error = new ApiError(500, {
      code: 'INTERNAL_ERROR',
      message: 'Server error',
      requestId: 'req_123'
    });

    render(<RecoveryPanel error={error} onDismiss={() => {}} />);
    
    const panel = screen.getByRole('alert');
    expect(panel).toHaveAttribute('aria-live', 'assertive');
    
    // Check keyboard navigation
    const dismissBtn = screen.getByRole('button', { name: /Dismiss/i });
    dismissBtn.focus();
    expect(dismissBtn).toHaveFocus();
  });
});
