import { useMemo } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabaseQuery.js';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

export const Categories = () => {
  const { data: categories, loading, error } = useSupabaseQuery('categories', {
    select: '*',
    order: { column: 'name', ascending: true },
    limit: 500,
    skipTenantFilter: true,
  });

  const filtered = useMemo(() => {
    if (!categories) return [];
    return categories.filter((c) => c.tenant_id === null);
  }, [categories]);

  const columns = useMemo(() => [
    { key: 'name', label: 'Nombre', render: (v) => <span className="font-body-bold">{v}</span> },
    { key: 'updated_at', label: 'Última Actualización', render: (v) => v ? new Date(v).toLocaleDateString('es-AR') : '—' },
  ], []);

  if (loading) return <Loading message="Cargando categorías..." />;
  if (error) return <ErrorState message={error} />;
  if (!filtered || filtered.length === 0) return <EmptyState message="No hay categorías registradas" />;

  return (
    <div>
      <h2 className="font-title mb-4">Categorías</h2>
      <DataTable columns={columns} data={filtered} />
    </div>
  );
};

export default Categories;
