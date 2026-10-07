import { useMemo, useCallback } from 'react';
import { useApiQuery } from '@/hooks/useApiQuery.js';
import { Loading, ErrorState, EmptyState, Badge } from '@/components/shared/index.jsx';
import { DataTable } from '@/components/shared/DataTable.jsx';

export const StockAlerts = () => {
  const { data: stocks, loading, error } = useApiQuery('stocks', {
    select: 'quantity, variant:article_variants(id, barcode, article:articles(name, min_stock)), warehouse:warehouses(name)',
    enabled: true,
  });

  const alertas = useMemo(() => {
    if (!stocks) return [];

    const stockByVariant = {};
    stocks.forEach((s) => {
      const variantId = s.variant?.id;
      if (!variantId) return;
      if (!stockByVariant[variantId]) {
        stockByVariant[variantId] = {
          name: s.variant?.article?.name || '—',
          barcode: s.variant?.barcode || '—',
          minStock: s.variant?.article?.min_stock || 0,
          warehouses: {},
        };
      }
      stockByVariant[variantId].totalStock = (stockByVariant[variantId].totalStock || 0) + parseFloat(s.quantity || 0);
      stockByVariant[variantId].warehouses[s.warehouse?.name || '—'] = parseFloat(s.quantity || 0);
    });

    return Object.values(stockByVariant)
      .filter((s) => s.minStock > 0)
      .map((s) => {
        const ratio = s.totalStock / s.minStock;
        let severidad;
        if (s.totalStock === 0) severidad = 'AGOTADO';
        else if (ratio <= 0.25) severidad = 'CRÍTICO';
        else if (ratio <= 0.5) severidad = 'ALERTA';
        else return null;

        return { ...s, severidad, ratio };
      })
      .filter(Boolean)
      .sort((a, b) => {
        const order = { AGOTADO: 0, CRÍTICO: 1, ALERTA: 2 };
        return order[a.severidad] - order[b.severidad];
      });
  }, [stocks]);

  const resumen = useMemo(() => {
    const agotados = alertas.filter((a) => a.severidad === 'AGOTADO').length;
    const criticos = alertas.filter((a) => a.severidad === 'CRÍTICO').length;
    const alerta = alertas.filter((a) => a.severidad === 'ALERTA').length;
    return { agotados, criticos, alerta, total: alertas.length };
  }, [alertas]);

  const exportarCSV = useCallback(() => {
    const headers = ['Producto', 'Código', 'Stock Actual', 'Stock Mínimo', 'Severidad'];
    const rows = alertas.map((a) => [
      `"${String(a.name).replace(/"/g, '""')}"`,
      `"${String(a.barcode).replace(/"/g, '""')}"`,
      a.totalStock,
      a.minStock,
      a.severidad,
    ]);
    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `alertas-stock-${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [alertas]);

  const columns = useMemo(() => [
    { key: 'name', label: 'Producto', render: (v) => <span className="font-body-bold">{v}</span> },
    { key: 'barcode', label: 'Código', render: (v) => <span className="font-mono">{v}</span> },
    { key: 'totalStock', label: 'Stock Actual', render: (v) => <span className="font-body-bold">{v}</span> },
    { key: 'minStock', label: 'Stock Mínimo', render: (v) => v },
    { key: 'severidad', label: 'Severidad', render: (v) => (
      <Badge text={v} color={v === 'AGOTADO' ? 'red' : v === 'CRÍTICO' ? 'orange' : 'accent'} />
    )},
  ], []);

  if (loading) return <Loading message="Cargando alertas..." />;
  if (error) return <ErrorState message={error} />;

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
        <h2 className="font-title mb-0">Alertas de Stock</h2>
        <button className="btn btn-cloudpos-ghost btn-sm" onClick={exportarCSV}>
          <i className="bi bi-download me-1"></i> Exportar CSV
        </button>
      </div>

      <div className="row g-3 mb-4">
        <div className="col-md-4">
          <div className="cloudpos-card" style={{ borderLeft: '4px solid var(--red)' }}>
            <div className="font-label-muted">Agotados</div>
            <div className="font-stat" style={{ color: 'var(--red-text)' }}>{resumen.agotados}</div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="cloudpos-card" style={{ borderLeft: '4px solid var(--orange)' }}>
            <div className="font-label-muted">Críticos</div>
            <div className="font-stat" style={{ color: 'var(--orange-text)' }}>{resumen.criticos}</div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="cloudpos-card" style={{ borderLeft: '4px solid var(--accent)' }}>
            <div className="font-label-muted">Alerta</div>
            <div className="font-stat" style={{ color: 'var(--accent-text)' }}>{resumen.alerta}</div>
          </div>
        </div>
      </div>

      {alertas.length > 0 ? (
        <DataTable columns={columns} data={alertas} />
      ) : (
        <EmptyState message="No hay alertas de stock" icon="bi-check-circle" />
      )}
    </div>
  );
};

export default StockAlerts;


