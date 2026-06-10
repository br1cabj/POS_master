import React, { useState } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabase.jsx';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Badge, Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

export const PurchaseReturns = () => {
  const [expandedReturn, setExpandedReturn] = useState(null);

  const { data: returns, loading, error } = useSupabaseQuery('purchase_returns', {
    select: '*, purchase(invoice_number, supplier(name))',
    order: { column: 'date', ascending: false },
    limit: 500,
  });

  const { data: returnItems, loading: itemsLoading, error: itemsError } = useSupabaseQuery('purchase_return_items', {
    select: '*, variant(name, barcode)',
    filter: expandedReturn ? ['purchase_return_id', 'eq', expandedReturn] : null,
    enabled: !!expandedReturn,
  });

  const columns = [
    { key: 'date', label: 'Fecha', render: (v) => v ? new Date(v).toLocaleDateString('es-AR') : '—' },
    { key: 'purchase', label: 'Proveedor', render: (_, row) => <span className="font-body-bold">{row.purchase?.supplier?.name || '—'}</span> },
    { key: 'purchase', label: 'Factura', render: (_, row) => row.purchase?.invoice_number || '—' },
    { key: 'reason', label: 'Motivo', render: (v) => v || '—' },
    { key: 'refund_type', label: 'Tipo Reembolso', render: (v) => <Badge text={v} color="orange" /> },
    { key: 'total_refund', label: 'Monto', render: (v) => <span className="font-body-bold" style={{ color: 'var(--red-text)' }}>${parseFloat(v || 0).toLocaleString()}</span> },
    { key: 'notes', label: 'Notas', render: (v) => <span className="font-small text-muted">{v || '—'}</span> },
  ];

  const handleRowClick = (row) => {
    setExpandedReturn(expandedReturn === row.id ? null : row.id);
  };

  if (loading) return <Loading message="Cargando devoluciones..." />;
  if (error) return <ErrorState message={error} />;
  if (!returns || returns.length === 0) return <EmptyState message="No hay devoluciones registradas" />;

  return (
    <div>
      <h2 className="font-title mb-4">Devoluciones a Proveedores</h2>
      <DataTable columns={columns} data={returns} onRowClick={handleRowClick} />

      {expandedReturn && (
        <div className="cloudpos-card mt-3" style={{ borderLeft: '4px solid var(--red)' }}>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="font-heading mb-0">Detalle de Devolución</h5>
            <button className="btn btn-cloudpos-ghost btn-sm" onClick={() => setExpandedReturn(null)} aria-label="Cerrar detalle">
              <i className="bi bi-x-lg"></i>
            </button>
          </div>
          {itemsLoading ? (
            <Loading />
          ) : itemsError ? (
            <ErrorState message={itemsError} />
          ) : !returnItems || returnItems.length === 0 ? (
            <EmptyState message="Sin items en esta devolución" />
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
                  {returnItems.map((item) => (
                    <tr key={item.id}>
                      <td className="font-mono">{item.variant?.barcode || '—'}</td>
                      <td className="font-body-bold">{item.variant?.name || item.description || '—'}</td>
                      <td>{isNaN(parseFloat(item.quantity_returned)) ? '0' : parseFloat(item.quantity_returned).toLocaleString()}</td>
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
