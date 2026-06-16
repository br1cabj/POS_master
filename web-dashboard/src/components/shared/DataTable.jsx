import { useState, useMemo, useEffect, useCallback } from 'react';
import { Loading, EmptyState, ErrorState } from '@/components/shared/index.jsx';

export const DataTable = ({
  columns,
  data,
  loading,
  error,
  searchable = true,
  pageSize = 20,
  emptyMessage = 'Sin datos disponibles',
  onRowClick = null,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [sortColumn, setSortColumn] = useState(null);
  const [sortDirection, setSortDirection] = useState('asc');

  useEffect(() => {
    setCurrentPage(1);
    setSearchTerm('');
    setSortColumn(null);
    setSortDirection('asc');
  }, [data]);

  const filteredData = useMemo(() => {
    let result = data || [];

    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter((row) =>
        columns.some((col) => {
          const value = row[col.key];
          if (value == null) return false;
          return String(value).toLowerCase().includes(term);
        })
      );
    }

    if (sortColumn) {
      result = [...result].sort((a, b) => {
        const aVal = a[sortColumn];
        const bVal = b[sortColumn];
        if (aVal == null || bVal == null) return 0;
        if (typeof aVal === 'number' && typeof bVal === 'number') {
          return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
        }
        return sortDirection === 'asc'
          ? String(aVal).localeCompare(String(bVal))
          : String(bVal).localeCompare(String(aVal));
      });
    }

    return result;
  }, [data, searchTerm, sortColumn, sortDirection, columns]);

  const totalPages = Math.ceil(filteredData.length / pageSize);

  useEffect(() => {
    if (currentPage > totalPages && totalPages > 0) {
      setCurrentPage(totalPages);
    }
  }, [totalPages, currentPage]);

  const safeCurrentPage = Math.min(currentPage, Math.max(1, totalPages));
  const paginatedData = filteredData.slice((safeCurrentPage - 1) * pageSize, safeCurrentPage * pageSize);

  const handleSort = useCallback((key) => {
    if (sortColumn === key) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(key);
      setSortDirection('asc');
    }
  }, [sortColumn, sortDirection]);

  const handleSortKeyDown = useCallback((e, key) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleSort(key);
    }
  }, [handleSort]);

  if (loading) return <Loading />;
  if (error) return <ErrorState message={error} />;
  if (!data || data.length === 0) return <EmptyState message={emptyMessage} />;

  return (
    <div>
      {searchable && (
        <div className="mb-3">
          <div className="input-group" style={{ maxWidth: '400px' }}>
            <span className="input-group-text" style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--border)', color: 'var(--text-muted)' }}>
              <i className="bi bi-search"></i>
            </span>
            <input
              type="text"
              className="form-control"
              style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
              placeholder="Buscar..."
              aria-label="Buscar en la tabla"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
            />
          </div>
        </div>
      )}

      <div className="table-responsive">
        <table className="table table-cloudpos">
          <thead>
            <tr>
              {columns.map((col) => {
                const isSortable = col.sortable !== false;
                const isSorted = sortColumn === col.key;
                const sortState = isSorted ? (sortDirection === 'asc' ? 'ascending' : 'descending') : 'none';
                return (
                  <th
                    key={col.key}
                    onClick={() => isSortable && handleSort(col.key)}
                    onKeyDown={(e) => isSortable && handleSortKeyDown(e, col.key)}
                    style={{ cursor: isSortable ? 'pointer' : 'default' }}
                    role="columnheader"
                    aria-sort={isSortable ? sortState : undefined}
                    tabIndex={isSortable ? 0 : undefined}
                  >
                    {col.label}
                    {isSorted && (
                      <i className={`bi bi-sort-${sortDirection === 'asc' ? 'up' : 'down'} ms-1`}></i>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {paginatedData.map((row, idx) => (
              <tr
                key={row.id || idx}
                onClick={() => onRowClick && onRowClick(row)}
                style={{ cursor: onRowClick ? 'pointer' : 'default' }}
              >
                {columns.map((col) => (
                  <td key={col.key}>
                    {col.render ? col.render(row[col.key], row) : row[col.key] ?? '—'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mt-3">
          <span className="font-small text-muted">
            Mostrando {(safeCurrentPage - 1) * pageSize + 1}–{Math.min(safeCurrentPage * pageSize, filteredData.length)} de {filteredData.length}
          </span>
          <nav aria-label="Navegación de paginación">
            <ul className="pagination pagination-sm mb-0">
              <li className={`page-item ${safeCurrentPage === 1 ? 'disabled' : ''}`}>
                <button
                  className="page-link"
                  style={{ backgroundColor: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  aria-label="Página anterior"
                >
                  <i className="bi bi-chevron-left"></i>
                </button>
              </li>
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let page;
                if (totalPages <= 5) {
                  page = i + 1;
                } else if (safeCurrentPage <= 3) {
                  page = i + 1;
                } else if (safeCurrentPage >= totalPages - 2) {
                  page = totalPages - 4 + i;
                } else {
                  page = safeCurrentPage - 2 + i;
                }
                return (
                  <li key={page} className={`page-item ${safeCurrentPage === page ? 'active' : ''}`}>
                    <button
                      className="page-link"
                      style={{ backgroundColor: safeCurrentPage === page ? 'var(--accent)' : 'var(--surface-2)', borderColor: 'var(--border)', color: safeCurrentPage === page ? '#fff' : 'var(--text-primary)' }}
                      onClick={() => setCurrentPage(page)}
                      aria-label={`Ir a página ${page}`}
                      aria-current={safeCurrentPage === page ? 'page' : undefined}
                    >
                      {page}
                    </button>
                  </li>
                );
              })}
              <li className={`page-item ${safeCurrentPage === totalPages ? 'disabled' : ''}`}>
                <button
                  className="page-link"
                  style={{ backgroundColor: 'var(--surface-2)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  aria-label="Página siguiente"
                >
                  <i className="bi bi-chevron-right"></i>
                </button>
              </li>
            </ul>
          </nav>
        </div>
      )}
    </div>
  );
};
