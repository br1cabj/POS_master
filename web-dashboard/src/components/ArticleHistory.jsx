import { useMemo } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabaseQuery.js';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Badge, Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

export const ArticleHistory = () => {
  const { data: history, loading, error } = useSupabaseQuery('article_history', {
    select: '*, user:users(username)',
    order: { column: 'date', ascending: false },
    limit: 500,
  });

  const columns = useMemo(() => [
    { key: 'date', label: 'Fecha', render: (v) => v ? new Date(v).toLocaleString('es-AR') : '—' },
    { key: 'article_name', label: 'Artículo', render: (v) => <span className="font-body-bold">{v}</span> },
    { key: 'action_type', label: 'Acción', render: (v) => <Badge text={v} color="accent" /> },
    { key: 'old_cost', label: 'Costo Anterior', render: (v) => v ? `$${parseFloat(v).toLocaleString()}` : '—' },
    { key: 'new_cost', label: 'Costo Nuevo', render: (v) => v ? `$${parseFloat(v).toLocaleString()}` : '—' },
    { key: 'old_price', label: 'Precio Anterior', render: (v) => v ? `$${parseFloat(v).toLocaleString()}` : '—' },
    { key: 'new_price', label: 'Precio Nuevo', render: (v) => v ? `$${parseFloat(v).toLocaleString()}` : '—' },
    { key: 'user', label: 'Usuario', render: (_, row) => row.user?.username || '—' },
  ], []);

  if (loading) return <Loading message="Cargando historial de precios..." />;
  if (error) return <ErrorState message={error} />;
  if (!history || history.length === 0) return <EmptyState message="No hay historial de precios" />;

  return (
    <div>
      <h2 className="font-title mb-4">Historial de Cambios de Precios</h2>
      <DataTable columns={columns} data={history} />
    </div>
  );
};

export default ArticleHistory;

