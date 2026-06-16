import { useMemo } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabase.jsx';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

export const Customers = () => {
  const { data: customers, loading, error } = useSupabaseQuery('customers', {
    select: '*',
    filter: ['is_active', 'eq', true],
    order: { column: 'name', ascending: true },
    limit: 500,
  });

  const columns = useMemo(() => [
    { key: 'name', label: 'Nombre', render: (v) => <span className="font-body-bold">{v}</span> },
    { key: 'phone', label: 'Teléfono', render: (v) => v || '—' },
    { key: 'current_balance', label: 'Deuda', render: (v) => {
      const balance = parseFloat(v || 0);
      return <span className={balance > 0 ? 'text-danger' : ''}>${isNaN(balance) ? '0' : balance.toLocaleString()}</span>;
    }},
    { key: 'price_list', label: 'Lista', render: (v) => v || 'A' },
    { key: 'updated_at', label: 'Última Actualización', render: (v) => v ? new Date(v).toLocaleDateString('es-AR') : '—' },
  ], []);

  if (loading) return <Loading message="Cargando clientes..." />;
  if (error) return <ErrorState message={error} />;
  if (!customers || customers.length === 0) return <EmptyState message="No hay clientes registrados" />;

  return (
    <div>
      <h2 className="font-title mb-4">Clientes</h2>
      <DataTable columns={columns} data={customers} />
    </div>
  );
};

export default Customers;
