import { useMemo } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabase.jsx';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Badge, Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

const movementTypeColor = (type) => {
  if (!type) return 'accent';
  if (type.includes('entrada') || type.includes('compra') || (type.includes('ajuste') && type.includes('positivo'))) return 'green';
  if (type.includes('salida') || type.includes('venta') || type.includes('devolucion') || (type.includes('ajuste') && type.includes('negativo'))) return 'red';
  return 'accent';
};

export const StockMovements = () => {
  const { data: movements, loading, error } = useSupabaseQuery('stock_movements', {
    select: '*, variant(name, barcode), user(username)',
    order: { column: 'date', ascending: false },
    limit: 500,
  });

  const columns = useMemo(() => [
    { key: 'date', label: 'Fecha', render: (v) => v ? new Date(v).toLocaleString('es-AR') : '—' },
    { key: 'variant_name', label: 'Producto', render: (_, row) => <span className="font-body-bold">{row.variant?.name || '—'}</span> },
    { key: 'variant_barcode', label: 'Código', render: (_, row) => <span className="font-mono">{row.variant?.barcode || '—'}</span> },
    { key: 'movement_type', label: 'Tipo', render: (v) => <Badge text={v} color={movementTypeColor(v)} /> },
    { key: 'quantity', label: 'Cantidad', render: (v) => parseFloat(v || 0).toLocaleString() },
    { key: 'user', label: 'Usuario', render: (_, row) => row.user?.username || '—' },
    { key: 'reference', label: 'Referencia', render: (v) => v || '—' },
  ], []);

  if (loading) return <Loading message="Cargando movimientos de stock..." />;
  if (error) return <ErrorState message={error} />;
  if (!movements || movements.length === 0) return <EmptyState message="No hay movimientos de stock" />;

  return (
    <div>
      <h2 className="font-title mb-4">Movimientos de Stock</h2>
      <DataTable columns={columns} data={movements} />
    </div>
  );
};
