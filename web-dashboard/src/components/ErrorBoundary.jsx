import { ErrorBoundary } from 'react-error-boundary';
import { ErrorState } from '@/components/shared/index.jsx';

function ErrorFallback({ error, resetErrorBoundary }) {
  return (
    <ErrorState
      message={`Algo salió mal: ${error.message}`}
      onRetry={resetErrorBoundary}
    />
  );
}

export function AppErrorBoundary({ children }) {
  return (
    <ErrorBoundary
      FallbackComponent={ErrorFallback}
      onReset={() => window.location.reload()}
    >
      {children}
    </ErrorBoundary>
  );
}
