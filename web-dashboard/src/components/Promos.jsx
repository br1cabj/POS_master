import { useMemo } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabase.jsx';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Badge, Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

export const Promos = () => {
  const { data: promos, loading, error } = useSupabaseQuery('promotions', {
    select: '*, variant:article_variants(article:articles(name)), category:categories(name)',
    order: { column: 'date_to', ascending: true },
    limit: 500,
  });

  const columns = useMemo(() => [
    { key: 'name', label: 'Nombre', render: (v) => <span className="font-body-bold">{v}</span> },
    { key: 'promo_type', label: 'Tipo', render: (v) => {
      const type = v || '—';
      const color = type === 'nxm' ? 'green' : type === 'pct' ? 'accent' : 'orange';
      return <Badge text={type.toUpperCase()} color={color} />;
    }},
    { key: 'discount_value', label: 'Detalle', render: (_, row) => {
      const type = row.promo_type;
      if (type === 'nxm') return `Lleva ${row.buy_qty || 0} Paga ${row.pay_qty || 0}`;
      if (type === 'pct') return `${row.discount_value ?? 0}% off`;
      return `$${row.discount_value ?? 0} c/u`;
    }},
    { key: 'variant', label: 'Producto', render: (_, row) => row.variant?.article?.name || (row.category ? `Categoría: ${row.category.name}` : '—') },
    { key: 'is_active', label: 'Estado', render: (v) => <Badge text={v ? 'Activa' : 'Inactiva'} color={v ? 'green' : 'red'} /> },
    { key: 'date_to', label: 'Vence', render: (v) => v ? new Date(v).toLocaleDateString('es-AR') : '—' },
  ], []);

  if (loading) return <Loading message="Cargando promociones..." />;
  if (error) return <ErrorState message={error} />;
  if (!promos || promos.length === 0) return <EmptyState message="No hay promociones" />;

  return (
    <div>
      <h2 className="font-title mb-4">Promociones</h2>
      <DataTable columns={columns} data={promos} />
    </div>
  );
};

export default Promos;


