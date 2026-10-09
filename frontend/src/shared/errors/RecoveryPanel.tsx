import * as React from 'react';
import { mapErrorToUIState } from '../api/errors';
import { Button } from '@/components/ui/button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { AlertCircle, RotateCw, RefreshCcw, LogIn, ShieldAlert } from 'lucide-react';

export interface RecoveryPanelProps {
  error: unknown;
  onRetry?: () => void;
  onReconcile?: (idempotencyKey?: string, operationId?: string) => void;
  onRebootstrap?: () => void;
  onReload?: () => void;
  onUpdateConsent?: () => void;
  onDismiss?: () => void;
  className?: string;
}

export function RecoveryPanel({
  error,
  onRetry,
  onReconcile,
  onRebootstrap,
  onReload,
  onUpdateConsent,
  onDismiss,
  className
}: RecoveryPanelProps) {
  if (!error) return null;

  const state = mapErrorToUIState(error);

  const handleAction = () => {
    switch (state.actionType) {
      case 'RETRY':
        onRetry?.();
        break;
      case 'RECONCILE':
        onReconcile?.(state.idempotencyKey, state.operationId);
        break;
      case 'REBOOTSTRAP':
        onRebootstrap?.();
        break;
      case 'RELOAD':
        onReload?.();
        break;
      case 'UPDATE_CONSENT':
        onUpdateConsent?.();
        break;
    }
  };

  const getActionLabel = () => {
    switch (state.actionType) {
      case 'RETRY': return 'Retry Action';
      case 'RECONCILE': return 'Check Status';
      case 'REBOOTSTRAP': return 'Log In Again';
      case 'RELOAD': return 'Reload Content';
      case 'UPDATE_CONSENT': return 'Review Consent';
      default: return null;
    }
  };

  const getActionIcon = () => {
    switch (state.actionType) {
      case 'RETRY': return <RotateCw className="w-4 h-4 mr-2" aria-hidden="true" />;
      case 'RECONCILE': return <RefreshCcw className="w-4 h-4 mr-2" aria-hidden="true" />;
      case 'REBOOTSTRAP': return <LogIn className="w-4 h-4 mr-2" aria-hidden="true" />;
      case 'RELOAD': return <RotateCw className="w-4 h-4 mr-2" aria-hidden="true" />;
      case 'UPDATE_CONSENT': return <ShieldAlert className="w-4 h-4 mr-2" aria-hidden="true" />;
      default: return null;
    }
  };

  const label = getActionLabel();
  const hasActions = label || onDismiss || state.requestId;

  return (
    <Card className={`border-destructive bg-destructive/10 ${className || ''}`} role="alert" aria-live="assertive">
      <CardHeader>
        <CardTitle className="text-destructive flex items-center gap-2 text-lg font-semibold">
          <AlertCircle className="w-5 h-5" aria-hidden="true" />
          {state.title}
        </CardTitle>
        <CardDescription className="text-foreground text-sm mt-1">
          {state.message}
        </CardDescription>
      </CardHeader>
      
      {hasActions && (
        <CardFooter className="flex flex-col items-start gap-4 sm:flex-row sm:items-center sm:justify-between pt-0">
          <div className="flex flex-wrap gap-2">
            {label && (
              <Button variant="default" onClick={handleAction}>
                {getActionIcon()}
                {label}
              </Button>
            )}
            {onDismiss && (
              <Button variant="outline" onClick={onDismiss}>
                Dismiss
              </Button>
            )}
          </div>
          {state.requestId && (
            <p className="text-xs text-muted-foreground font-mono bg-background/50 px-2 py-1 rounded">
              Request ID: {state.requestId}
            </p>
          )}
        </CardFooter>
      )}
    </Card>
  );
}
