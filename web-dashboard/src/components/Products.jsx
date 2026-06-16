import React, { useState } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabase.jsx';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

export const Products = () => {
  const [page, setPage] = useState(0);
  const pageSize = 50;
  const { data: variants, loading, error } = useSupabaseQuery('article_variants', {
    select: '*, article(name, description, min_stock, category(name), supplier(name)), stocks(quantity, warehouse(name))',
    filter: ['is_active', 'eq', true],
    order: { column: 'updated_at', ascending: false },
    range: [page * pageSize, (page + 1) * pageSize - 1],
  });

  const columns = [
    { key: 'barcode', label: 'Código', render: (v) => <span className="font-mono">{v || '—'}</span> },
    { key: 'article_name', label: 'Nombre', render: (_, row) => <span className="font-body-bold">{row.article?.name || '—'}</span> },
    { key: 'article_category', label: 'Categoría', render: (_, row) => row.article?.category?.name || '—' },
    { key: 'article_supplier', label: 'Proveedor', render: (_, row) => row.article?.supplier?.name || '—' },
    { key: 'cost_price', label: 'Costo', render: (v) => v ? `$${parseFloat(v).toLocaleString()}` : '—' },
    { key: 'selling_price', label: 'Venta', render: (v) => <span className="font-body-bold" style={{ color: 'var(--green-text)' }}>{v ? `$${parseFloat(v).toLocaleString()}` : '—'}</span> },
    { key: 'stocks', label: 'Stock', render: (v) => {
      if (!v || v.length === 0) return '0';
      const total = v.reduce((sum, s) => sum + parseFloat(s.quantity || 0), 0);
      return <span className={total === 0 ? 'text-danger' : ''}>{total.toLocaleString()}</span>;
    }},
  ];

  if (loading && page === 0) return <Loading message="Cargando productos..." />;
  if (error) return <ErrorState message={error} />;
  if (!variants || (variants.length === 0 && page === 0)) return <EmptyState message="No hay productos registrados" />;

  return (
    <div>
      <h2 className="font-title mb-4">Catálogo de Productos</h2>
      <DataTable columns={columns} data={variants} />
      
      <div className="d-flex justify-content-between align-items-center mt-4">
        <button 
          className="btn btn-outline-secondary" 
          onClick={() => setPage(p => Math.max(0, p - 1))}
          disabled={page === 0 || loading}
        >
          Anterior
        </button>
        <span className="text-muted">Página {page + 1}</span>
        <button 
          className="btn btn-outline-secondary" 
          onClick={() => setPage(p => p + 1)}
          disabled={!variants || variants.length < pageSize || loading}
        >
          Siguiente
        </button>
      </div>
    </div>
  );
};
