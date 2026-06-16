import { useState, useMemo, useCallback } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabase.jsx';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Badge, Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

const statusColor = (status) => {
  switch (status) {
    case 'aceptada': return 'green';
    case 'enviada': return 'accent';
    case 'borrador': return 'orange';
    case 'rechazada': return 'red';
    default: return 'accent';
  }
};

export const Quotations = () => {
  const [expandedQuotation, setExpandedQuotation] = useState(null);

  const { data: quotations, loading, error } = useSupabaseQuery('quotations', {
    select: '*, customer:customers(name), user:users(username)',
    order: { column: 'date', ascending: false },
    limit: 500,
  });

  const { data: quotationItems, loading: itemsLoading, error: itemsError } = useSupabaseQuery('quotation_items', {
    select: '*, variant:article_variants(barcode, article:articles(name))',
    filter: expandedQuotation ? ['quotation_id', 'eq', expandedQuotation] : null,
    enabled: !!expandedQuotation,
  });

  const columns = useMemo(() => [
    { key: 'number', label: 'Número', render: (v) => <span className="font-mono">{v}</span> },
    { key: 'date', label: 'Fecha', render: (v) => v ? new Date(v).toLocaleDateString('es-AR') : '—' },
    { key: 'customer', label: 'Cliente', render: (_, row) => row.customer?.name || '—' },
    { key: 'total_amount', label: 'Total', render: (v) => <span className="font-body-bold">${parseFloat(v || 0).toLocaleString()}</span> },
    { key: 'status', label: 'Estado', render: (v) => <Badge text={v} color={statusColor(v)} /> },
  ], []);

  const handleRowClick = useCallback((row) => {
    setExpandedQuotation((prev) => (prev === row.id ? null : row.id));
  }, []);

  if (loading) return <Loading message="Cargando cotizaciones..." />;
  if (error) return <ErrorState message={error} />;
  if (!quotations || quotations.length === 0) return <EmptyState message="No hay cotizaciones" />;

  return (
    <div>
      <h2 className="font-title mb-4">Cotizaciones</h2>
      <DataTable columns={columns} data={quotations} onRowClick={handleRowClick} />

      {expandedQuotation && (
        <div className="cloudpos-card mt-3" style={{ borderLeft: '4px solid var(--accent)' }}>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="font-heading mb-0">Detalle Cotización #{expandedQuotation.slice(0, 8)}</h5>
            <button className="btn btn-cloudpos-ghost btn-sm" onClick={() => setExpandedQuotation(null)} aria-label="Cerrar detalle">
              <i className="bi bi-x-lg"></i>
            </button>
          </div>
          {itemsLoading ? (
            <Loading />
          ) : itemsError ? (
            <ErrorState message={itemsError} />
          ) : !quotationItems || quotationItems.length === 0 ? (
            <EmptyState message="Sin items en esta cotización" />
          ) : (
            <div className="table-responsive">
              <table className="table table-cloudpos">
                <thead>
                  <tr>
                    <th scope="col">Código</th>
                    <th scope="col">Descripción</th>
                    <th scope="col">Cantidad</th>
                    <th scope="col">P. Unitario</th>
                    <th scope="col">Subtotal</th>
                  </tr>
                </thead>
                <tbody>
                  {quotationItems.map((item) => (
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

export default Quotations;


