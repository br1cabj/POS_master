import { memo } from 'react';
import { Badge } from '@/components/shared/index.jsx';

export const LowStockAlert = memo(({ items }) => {
  if (!items || items.length === 0) return null;

  return (
    <div className="cloudpos-card mb-3" style={{ borderLeft: '4px solid var(--red)' }}>
      <h5 className="font-heading mb-2" style={{ color: 'var(--red-text)' }}>
        <i className="bi bi-exclamation-triangle me-1"></i> Stock Bajo ({items.length})
      </h5>
      <div className="d-flex flex-wrap gap-2">
        {items.slice(0, 5).map((item) => (
          <div key={item.name} className="d-flex align-items-center gap-2 p-2" style={{ backgroundColor: 'var(--red-dim)', borderRadius: '6px' }}>
            <span className="font-body-bold" style={{ color: 'var(--red-text)' }}>{item.name}</span>
            <Badge text={`${item.current}/${item.min}`} color="red" />
          </div>
        ))}
        {items.length > 5 && (
          <span className="font-small text-muted">+{items.length - 5} más</span>
        )}
      </div>
    </div>
  );
});

LowStockAlert.displayName = 'LowStockAlert';
