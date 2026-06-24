import { useState, useMemo, useCallback } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabaseQuery.js';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Badge, Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

const statusColor = (status) => {
  switch (status) {
    case 'completada': return 'green';
    case 'pendiente': return 'orange';
    case 'anulada': return 'red';
    case 'devolucion': return 'red';
    default: return 'accent';
  }
};

export const Sales = () => {
  const [expandedSale, setExpandedSale] = useState(null);

  const { data: sales, loading, error } = useSupabaseQuery('sales', {
    select: '*, customer:customers(name), user:users(username)',
    order: { column: 'date', ascending: false },
    limit: 500,
  });

  const { data: saleDetails, loading: detailsLoading, error: detailsError } = useSupabaseQuery('sale_details', {
    select: '*, variant:article_variants(barcode, article:articles(name))',
    filter: expandedSale ? ['sale_id', 'eq', expandedSale] : null,
    enabled: !!expandedSale,
  });

  const columns = useMemo(() => [
    { key: 'id', label: 'ID', render: (v) => <span className="font-mono">{v?.slice(0, 8)}</span> },
    { key: 'date', label: 'Fecha', render: (v) => v ? new Date(v).toLocaleString('es-AR') : '—' },
    { key: 'customer', label: 'Cliente', render: (_, row) => row.customer?.name || 'Consumidor Final' },
    { key: 'total_amount', label: 'Total', render: (v) => <span className="font-body-bold">${parseFloat(v || 0).toLocaleString()}</span> },
    { key: 'payment_method', label: 'Método', render: (v, row) => {
      if (row.payment_method_2) {
        return <span>{v} + {row.payment_method_2}</span>;
      }
      return v || '—';
    }},
    { key: 'status', label: 'Estado', render: (v) => <Badge text={v} color={statusColor(v)} /> },
  ], []);

  const handleRowClick = useCallback((row) => {
    setExpandedSale((prev) => (prev === row.id ? null : row.id));
  }, []);

  if (loading) return <Loading message="Cargando ventas..." />;
  if (error) return <ErrorState message={error} />;
  if (!sales || sales.length === 0) return <EmptyState message="No hay ventas registradas" />;

  return (
    <div>
      <h2 className="font-title mb-4">Historial de Ventas</h2>
      <DataTable columns={columns} data={sales} onRowClick={handleRowClick} />

      {expandedSale && (
        <div className="cloudpos-card mt-3" style={{ borderLeft: '4px solid var(--accent)' }}>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="font-heading mb-0">Detalle de Venta #{expandedSale.slice(0, 8)}</h5>
            <button className="btn btn-cloudpos-ghost btn-sm" onClick={() => setExpandedSale(null)} aria-label="Cerrar detalle">
              <i className="bi bi-x-lg"></i>
            </button>
          </div>
          {detailsLoading ? (
            <Loading />
          ) : detailsError ? (
            <ErrorState message={detailsError} />
          ) : !saleDetails || saleDetails.length === 0 ? (
            <EmptyState message="Sin items en esta venta" />
          ) : (
            <div className="table-responsive">
              <table className="table table-cloudpos">
                <thead>
                  <tr>
                    <th scope="col">Código</th>
                    <th scope="col">Producto</th>
                    <th scope="col">Cantidad</th>
                    <th scope="col">P. Unitario</th>
                    <th scope="col">Subtotal</th>
                  </tr>
                </thead>
                <tbody>
                  {saleDetails.map((item) => (
                    <tr key={item.id}>
                      <td className="font-mono">{item.variant?.barcode || '—'}</td>
                      <td className="font-body-bold">{item.variant?.article?.name || item.description || '—'}</td>
                      <td>{isNaN(parseFloat(item.quantity)) ? '0' : parseFloat(item.quantity).toLocaleString()}</td>
                      <td>${isNaN(parseFloat(item.unit_price)) ? '0' : parseFloat(item.unit_price).toLocaleString()}</td>
                      <td className="font-body-bold">${isNaN(parseFloat(item.subtotal)) ? '0' : parseFloat(item.subtotal).toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default Sales;


