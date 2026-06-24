import { useMemo } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabaseQuery.js';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

export const Suppliers = () => {
  const { data: suppliers, loading, error } = useSupabaseQuery('suppliers', {
    select: '*',
    filter: ['is_active', 'eq', true],
    order: { column: 'name', ascending: true },
    limit: 500,
  });

  const columns = useMemo(() => [
    { key: 'name', label: 'Nombre', render: (v) => <span className="font-body-bold">{v}</span> },
    { key: 'phone', label: 'Teléfono', render: (v) => v || '—' },
    { key: 'email', label: 'Email', render: (v) => v || '—' },
    { key: 'address', label: 'Dirección', render: (v) => v || '—' },
    { key: 'credit_balance', label: 'Crédito', render: (v) => {
      const balance = parseFloat(v || 0);
      return <span className={balance > 0 ? 'text-danger' : ''}>${isNaN(balance) ? '0' : balance.toLocaleString()}</span>;
    }},
    { key: 'discount_pct', label: 'Descuento', render: (v) => v ? `${v}%` : '—' },
  ], []);

  if (loading) return <Loading message="Cargando proveedores..." />;
  if (error) return <ErrorState message={error} />;
  if (!suppliers || suppliers.length === 0) return <EmptyState message="No hay proveedores registrados" />;

  return (
    <div>
      <h2 className="font-title mb-4">Proveedores</h2>
      <DataTable columns={columns} data={suppliers} />
    </div>
  );
};

export default Suppliers;
