import { memo } from 'react';

export const StatCard = memo(({ title, value, sub, accent = 'accent' }) => (
  <div className={`stat-card ${accent}`}>
    <div className="font-label-muted">{title}</div>
    <div className={`font-stat mt-1 text-${accent === 'green' ? 'success' : accent === 'orange' ? 'warning' : accent === 'red' ? 'danger' : 'primary'}`}>
      {value}
    </div>
    {sub && <div className="font-small text-muted mt-1">{sub}</div>}
  </div>
));

StatCard.displayName = 'StatCard';

export const Badge = memo(({ text, color = 'accent' }) => (
  <span className={`badge-cloudpos badge-${color}`}>{text}</span>
));

Badge.displayName = 'Badge';

export const Loading = memo(({ message = 'Cargando...' }) => (
  <div className="d-flex flex-column align-items-center justify-content-center py-5">
    <div className="spinner-border text-primary" role="status">
      <span className="visually-hidden">{message}</span>
    </div>
    <span className="font-small text-muted mt-2">{message}</span>
  </div>
));

Loading.displayName = 'Loading';

export const EmptyState = memo(({ message = 'Sin datos disponibles', icon = 'bi-inbox' }) => (
  <div className="d-flex flex-column align-items-center justify-content-center py-5 text-center">
    <i className={`bi ${icon} fs-1 text-muted mb-2`}></i>
    <p className="font-body text-muted mb-0">{message}</p>
  </div>
));

EmptyState.displayName = 'EmptyState';

export const ErrorState = memo(({ message, onRetry }) => (
  <div className="d-flex flex-column align-items-center justify-content-center py-5 text-center">
    <i className="bi bi-exclamation-triangle fs-1 text-danger mb-2"></i>
    <p className="font-body text-danger mb-2">{message}</p>
    {onRetry && (
      <button className="btn btn-cloudpos-ghost btn-sm" onClick={onRetry}>
        <i className="bi bi-arrow-clockwise me-1"></i> Reintentar
      </button>
    )}
  </div>
));

ErrorState.displayName = 'ErrorState';

export const Skeleton = memo(({ lines = 3, height = '20px' }) => (
  <div className="skeleton-loader" aria-label="Cargando contenido" role="status">
    {Array.from({ length: lines }).map((_, i) => (
      <div
        key={i}
        className="skeleton-line"
        style={{
          height,
          backgroundColor: 'var(--surface-2)',
          borderRadius: '4px',
          marginBottom: i < lines - 1 ? '8px' : '0',
          animation: 'pulse 1.5s ease-in-out infinite',
        }}
      />
    ))}
  </div>
));

Skeleton.displayName = 'Skeleton';

export const TableRowSkeleton = memo(({ columns = 5 }) => (
  <>
    {Array.from({ length: 5 }).map((_, rowIdx) => (
      <tr key={rowIdx}>
        {Array.from({ length: columns }).map((_, colIdx) => (
          <td key={colIdx}>
            <div
              style={{
                height: '16px',
                backgroundColor: 'var(--surface-2)',
                borderRadius: '4px',
                width: colIdx === 0 ? '60px' : colIdx === 1 ? '150px' : '100px',
                animation: 'pulse 1.5s ease-in-out infinite',
                animationDelay: `${(rowIdx * columns + colIdx) * 0.05}s`,
              }}
            />
          </td>
        ))}
      </tr>
    ))}
  </>
));

TableRowSkeleton.displayName = 'TableRowSkeleton';
