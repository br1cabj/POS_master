import { useState, useMemo, useCallback } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabaseQuery.js';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Badge, Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

const statusColor = (status) => {
  switch (status?.toLowerCase()) {
    case 'pagada':
    case 'completada':
      return 'green';
    case 'pendiente':
      return 'orange';
    case 'anulada':
    case 'cancelada':
      return 'red';
    default:
      return 'orange';
  }
};

export const Purchases = () => {
  const [expandedPurchase, setExpandedPurchase] = useState(null);

  const { data: purchases, loading, error } = useSupabaseQuery('purchases', {
    select: '*, supplier:suppliers(name)',
    order: { column: 'date', ascending: false },
    limit: 500,
  });

  const { data: purchaseDetails, loading: detailsLoading, error: detailsError } = useSupabaseQuery('purchase_details', {
    select: '*, variant:article_variants(barcode, article:articles(name))',
    filter: expandedPurchase ? ['purchase_id', 'eq', expandedPurchase] : null,
    enabled: !!expandedPurchase,
  });

  const columns = useMemo(() => [
    { key: 'date', label: 'Fecha', render: (v) => v ? new Date(v).toLocaleDateString('es-AR') : '—' },
    { key: 'supplier', label: 'Proveedor', render: (_, row) => <span className="font-body-bold">{row.supplier?.name || '—'}</span> },
    { key: 'invoice_number', label: 'Factura', render: (v) => v || '—' },
    { key: 'total_amount', label: 'Total', render: (v) => <span className="font-body-bold">${parseFloat(v || 0).toLocaleString()}</span> },
    { key: 'status', label: 'Estado', render: (v) => <Badge text={v} color={statusColor(v)} /> },
  ], []);

  const handleRowClick = useCallback((row) => {
    setExpandedPurchase((prev) => (prev === row.id ? null : row.id));
  }, []);

  if (loading) return <Loading message="Cargando compras..." />;
  if (error) return <ErrorState message={error} />;
  if (!purchases || purchases.length === 0) return <EmptyState message="No hay compras registradas" />;

  return (
    <div>
      <h2 className="font-title mb-4">Compras a Proveedores</h2>
      <DataTable columns={columns} data={purchases} onRowClick={handleRowClick} />

      {expandedPurchase && (
        <div className="cloudpos-card mt-3" style={{ borderLeft: '4px solid var(--accent)' }}>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="font-heading mb-0">Detalle de Compra</h5>
            <button className="btn btn-cloudpos-ghost btn-sm" onClick={() => setExpandedPurchase(null)} aria-label="Cerrar detalle">
              <i className="bi bi-x-lg"></i>
            </button>
          </div>
          {detailsLoading ? (
            <Loading />
          ) : detailsError ? (
            <ErrorState message={detailsError} />
          ) : !purchaseDetails || purchaseDetails.length === 0 ? (
            <EmptyState message="Sin items en esta compra" />
          ) : (
            <div className="table-responsive">
              <table className="table table-cloudpos">
                <thead>
                  <tr>
                    <th scope="col">Código</th>
                    <th scope="col">Producto</th>
                    <th scope="col">Cantidad</th>
                    <th scope="col">Costo Unit.</th>
                    <th scope="col">Subtotal</th>
                  </tr>
                </thead>
                <tbody>
                  {purchaseDetails.map((item) => (
                    <tr key={item.id}>
                      <td className="font-mono">{item.variant?.barcode || '—'}</td>
                      <td className="font-body-bold">{item.variant?.article?.name || item.description || '—'}</td>
                      <td>{isNaN(parseFloat(item.quantity)) ? '0' : parseFloat(item.quantity).toLocaleString()}</td>
                      <td>${isNaN(parseFloat(item.unit_cost)) ? '0' : parseFloat(item.unit_cost).toLocaleString()}</td>
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

export default Purchases;


