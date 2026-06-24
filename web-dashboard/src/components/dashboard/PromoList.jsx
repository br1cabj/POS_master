import { memo } from 'react';
import { Skeleton } from '@/components/shared/index.jsx';
import { formatToLocal } from '@/utils/dateUtils.js';

export const PromoList = memo(({ promos, loading }) => {
  if (loading) return <Skeleton lines={3} />;
  if (!promos || promos.length === 0) {
    return <p className="text-muted font-body">Sin promociones activas ahora.</p>;
  }

  return promos.map((promo) => {
    const detail =
      promo.promo_type === 'nxm'
        ? `Lleva ${promo.buy_qty} Paga ${promo.pay_qty}`
        : promo.promo_type === 'pct'
        ? `${promo.discount_value}% off`
        : `$${promo.discount_value} c/u`;
    return (
      <div key={promo.id} className="d-flex flex-wrap align-items-center gap-2 p-2 mb-2" style={{ backgroundColor: 'var(--surface-3)', borderRadius: '8px' }}>
        <span className="badge-cloudpos badge-green flex-shrink-0">{(promo.promo_type || '—').toUpperCase()}</span>
        <div className="flex-fill min-width-0">
          <div className="font-body-bold">{promo.name}</div>
          <div className="font-small text-muted">{detail}</div>
        </div>
        <div className="font-small text-muted flex-shrink-0">≤ {formatToLocal(promo.date_to)}</div>
      </div>
    );
  });
});

PromoList.displayName = 'PromoList';
