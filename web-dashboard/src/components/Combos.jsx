import { useMemo } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabase.jsx';
import { Badge, Loading, ErrorState, EmptyState } from '@/components/shared/index.jsx';

export const Combos = () => {
  const { data: combos, loading, error } = useSupabaseQuery('article_variants', {
    select: '*, article(name), combo_items(ingredient_id, quantity_required, ingredient:ingredient_id(name, barcode))',
    filter: ['is_combo', 'eq', true],
    order: { column: 'updated_at', ascending: false },
    limit: 500,
  });

  const comboElements = useMemo(() => combos?.map((combo) => {
    const items = combo.combo_items || [];
    return (
      <div key={combo.id} className="cloudpos-card mb-3">
        <div className="d-flex justify-content-between align-items-center mb-2">
          <h5 className="font-heading mb-0">{combo.article?.name}</h5>
          <span className="font-body-bold" style={{ color: 'var(--green-text)' }}>
            ${parseFloat(combo.selling_price || 0).toLocaleString()}
          </span>
        </div>
        {items.length > 0 ? (
          <div className="table-responsive">
            <table className="table table-cloudpos">
              <thead>
                <tr>
                  <th scope="col">Código</th>
                  <th scope="col">Ingrediente</th>
                  <th scope="col">Cantidad</th>
                </tr>
              </thead>
              <tbody>
                {items.map((ci, idx) => (
                  <tr key={ci.id || `${ci.ingredient_id}-${idx}`}>
                    <td className="font-mono">{ci.ingredient?.barcode || '—'}</td>
                    <td className="font-body-bold">{ci.ingredient?.name || '—'}</td>
                    <td>{isNaN(parseFloat(ci.quantity_required)) ? '0' : parseFloat(ci.quantity_required).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState message="Sin ingredientes definidos" />
        )}
      </div>
    );
  }), [combos]);

  if (loading) return <Loading message="Cargando combos..." />;
  if (error) return <ErrorState message={error} />;
  if (!combos || combos.length === 0) return <EmptyState message="No hay combos registrados" />;

  return (
    <div>
      <h2 className="font-title mb-4">Combos</h2>
      {comboElements}
    </div>
  );
};
