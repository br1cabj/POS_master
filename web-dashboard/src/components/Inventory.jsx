import { useMemo } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabase.jsx';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Badge, Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

export const Inventory = () => {
  const { data: stocks, loading, error } = useSupabaseQuery('stocks', {
    select: '*, variant(name, barcode, article(min_stock)), warehouse(name)',
    order: { column: 'quantity', ascending: true },
    limit: 500,
  });

  const columns = useMemo(() => [
    { key: 'variant_name', label: 'Producto', render: (_, row) => <span className="font-body-bold">{row.variant?.name || '—'}</span> },
    { key: 'variant_barcode', label: 'Código', render: (_, row) => <span className="font-mono">{row.variant?.barcode || '—'}</span> },
    { key: 'warehouse', label: 'Depósito', render: (_, row) => row.warehouse?.name || '—' },
    { key: 'quantity', label: 'Stock', render: (v) => parseFloat(v || 0).toLocaleString() },
    { key: 'min_stock', label: 'Stock Mínimo', render: (_, row) => row.variant?.article?.min_stock || 0 },
    { key: 'stock_status', label: 'Estado', render: (v, row) => {
      const qty = parseFloat(row.quantity || 0);
      const min = row.variant?.article?.min_stock || 0;
      return <Badge text={qty >= min ? 'OK' : 'Bajo'} color={qty >= min ? 'green' : 'red'} />;
    }},
    { key: 'batch_number', label: 'Lote', render: (v) => v || '—' },
    { key: 'expiration_date', label: 'Vencimiento', render: (v) => v ? new Date(v).toLocaleDateString('es-AR') : '—' },
  ], []);

  if (loading) return <Loading message="Cargando inventario..." />;
  if (error) return <ErrorState message={error} />;
  if (!stocks || stocks.length === 0) return <EmptyState message="No hay stock registrado" />;

  return (
    <div>
      <h2 className="font-title mb-4">Inventario</h2>
      <DataTable columns={columns} data={stocks} />
    </div>
  );
};
