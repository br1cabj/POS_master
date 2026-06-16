import { useMemo } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabase.jsx';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Badge, Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

export const Users = () => {
  const { data: users, loading, error } = useSupabaseQuery('users', {
    select: '*',
    filter: ['is_active', 'eq', true],
    order: { column: 'username', ascending: true },
    limit: 500,
  });

  const columns = useMemo(() => [
    { key: 'username', label: 'Usuario', render: (v) => <span className="font-body-bold">{v}</span> },
    { key: 'display_name', label: 'Nombre', render: (v) => v || '—' },
    { key: 'role', label: 'Rol', render: (v) => {
      const color = v === 'admin' ? 'accent' : v === 'supervisor' ? 'orange' : 'green';
      return <Badge text={v} color={color} />;
    }},
    { key: 'is_active', label: 'Estado', render: (v) => <Badge text={v ? 'Activo' : 'Inactivo'} color={v ? 'green' : 'red'} /> },
    { key: 'updated_at', label: 'Última Actualización', render: (v) => v ? new Date(v).toLocaleDateString('es-AR') : '—' },
  ], []);

  if (loading) return <Loading message="Cargando usuarios..." />;
  if (error) return <ErrorState message={error} />;
  if (!users || users.length === 0) return <EmptyState message="No hay usuarios registrados" />;

  return (
    <div>
      <h2 className="font-title mb-4">Usuarios</h2>
      <DataTable columns={columns} data={users} />
    </div>
  );
};
