import { useState, useMemo, useCallback } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabaseQuery.js';
import { DataTable } from '@/components/shared/DataTable.jsx';
import { Badge, Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

const movementTypeColor = (type) => {
  if (!type) return 'accent';
  if (type.includes('venta') || type.includes('ingreso')) return 'green';
  if (type.includes('gasto') || type.includes('egreso') || type.includes('retiro')) return 'red';
  return 'accent';
};

export const Cash = () => {
  const [expandedSession, setExpandedSession] = useState(null);

  const { data: sessions, loading, error } = useSupabaseQuery('cash_sessions', {
    select: '*, user:users(username, display_name)',
    order: { column: 'opened_at', ascending: false },
    limit: 500,
  });

  const { data: movements, loading: movementsLoading, error: movementsError } = useSupabaseQuery('cash_movements', {
    select: '*, customer:customers(name)',
    filter: expandedSession ? ['session_id', 'eq', expandedSession] : null,
    enabled: !!expandedSession,
  });

  const columns = useMemo(() => [
    { key: 'id', label: 'ID', render: (v) => <span className="font-mono">{v?.slice(0, 8)}</span> },
    { key: 'user', label: 'Usuario', render: (_, row) => row.user?.display_name || row.user?.username || '—' },
    { key: 'opened_at', label: 'Apertura', render: (v) => v ? new Date(v).toLocaleString('es-AR') : '—' },
    { key: 'closed_at', label: 'Cierre', render: (v) => v ? new Date(v).toLocaleString('es-AR') : '—' },
    { key: 'is_open', label: 'Estado', render: (v) => <Badge text={v ? 'Abierta' : 'Cerrada'} color={v ? 'green' : 'orange'} /> },
    { key: 'opening_balance', label: 'Apertura', render: (v) => `$${parseFloat(v || 0).toLocaleString()}` },
    { key: 'closing_balance', label: 'Cierre', render: (v) => <span className="font-body-bold">${parseFloat(v || 0).toLocaleString()}</span> },
    { key: 'expected_amount', label: 'Esperado', render: (v) => v ? `$${parseFloat(v).toLocaleString()}` : '—' },
    { key: 'declared_amount', label: 'Declarado', render: (v) => v ? `$${parseFloat(v).toLocaleString()}` : '—' },
    { key: 'difference', label: 'Diferencia', render: (v) => {
      if (v == null) return '—';
      const diff = parseFloat(v);
      return <span className={diff !== 0 ? 'text-danger' : ''}>${diff.toLocaleString()}</span>;
    }},
  ], []);

  const handleRowClick = useCallback((row) => {
    setExpandedSession((prev) => (prev === row.id ? null : row.id));
  }, []);

  if (loading) return <Loading message="Cargando sesiones de caja..." />;
  if (error) return <ErrorState message={error} />;
  if (!sessions || sessions.length === 0) return <EmptyState message="No hay sesiones de caja" />;

  return (
    <div>
      <h2 className="font-title mb-4">Sesiones de Caja</h2>
      <DataTable columns={columns} data={sessions} onRowClick={handleRowClick} />

      {expandedSession && (
        <div className="cloudpos-card mt-3" style={{ borderLeft: '4px solid var(--accent)' }}>
          <div className="d-flex justify-content-between align-items-center mb-3">
            <h5 className="font-heading mb-0">Movimientos — Sesión #{expandedSession.slice(0, 8)}</h5>
            <button className="btn btn-cloudpos-ghost btn-sm" onClick={() => setExpandedSession(null)} aria-label="Cerrar detalle">
              <i className="bi bi-x-lg"></i>
            </button>
          </div>
          {movementsLoading ? (
            <Loading />
          ) : movementsError ? (
            <ErrorState message={movementsError} />
          ) : !movements || movements.length === 0 ? (
            <EmptyState message="Sin movimientos en esta sesión" />
          ) : (
            <div className="table-responsive">
              <table className="table table-cloudpos">
                <thead>
                  <tr>
                    <th scope="col">Hora</th>
                    <th scope="col">Tipo</th>
                    <th scope="col">Monto</th>
                    <th scope="col">Cliente</th>
                    <th scope="col">Descripción</th>
                  </tr>
                </thead>
                <tbody>
                  {movements.map((m) => (
                    <tr key={m.id}>
                      <td>{m.time ? new Date(m.time).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' }) : '—'}</td>
                      <td><Badge text={m.movement_type || '—'} color={movementTypeColor(m.movement_type)} /></td>
                      <td className="font-body-bold">${parseFloat(m.amount || 0).toLocaleString()}</td>
                      <td>{m.customer?.name || '—'}</td>
                      <td className="font-small text-muted">{m.description || '—'}</td>
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

export default Cash;

