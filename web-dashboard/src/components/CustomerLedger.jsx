import React, { useState, useMemo } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabase.jsx';
import { Loading, ErrorState, EmptyState, Badge } from '@/components/shared/index.jsx';
import { DataTable } from '@/components/shared/DataTable.jsx';
import jsPDF from 'jspdf';
import 'jspdf-autotable';

export const CustomerLedger = () => {
  const [selectedCustomer, setSelectedCustomer] = useState(null);

  const { data: customers, loading: customersLoading, error: customersError } = useSupabaseQuery('customers', {
    select: '*',
    filter: ['is_active', 'eq', true],
    order: { column: 'name', ascending: true },
    limit: 500,
  });

  const { data: sales, loading: salesLoading, error: salesError } = useSupabaseQuery('sales', {
    select: '*, customer(name), items(quantity, unit_price, subtotal, description)',
    filter: selectedCustomer ? [['customer_id', 'eq', selectedCustomer]] : null,
    order: { column: 'date', ascending: true },
    enabled: !!selectedCustomer,
  });

  const { data: cashMovements, loading: cashLoading, error: cashError } = useSupabaseQuery('cash_movements', {
    select: 'amount, description, time, customer_id',
    filter: selectedCustomer ? [['customer_id', 'eq', selectedCustomer]] : null,
    order: { column: 'time', ascending: true },
    enabled: !!selectedCustomer,
  });

  const selectedCustomerData = customers?.find((c) => c.id === selectedCustomer);

  const ledger = useMemo(() => {
    if (!selectedCustomer || !sales) return [];

    const entries = [];

    sales.forEach((s) => {
      entries.push({
        date: s.date,
        type: 'cargo',
        description: `Venta ${s.id?.slice(0, 8)}`,
        amount: parseFloat(s.total_amount || 0),
        balance: 0,
        items: s.items || [],
      });
    });

    cashMovements?.forEach((m) => {
      entries.push({
        date: m.time,
        type: 'abono',
        description: m.description || 'Abono',
        amount: parseFloat(m.amount || 0),
        balance: 0,
        items: [],
      });
    });

    entries.sort((a, b) => new Date(a.date) - new Date(b.date));

    let balance = 0;
    entries.forEach((e) => {
      if (e.type === 'cargo') balance += e.amount;
      else balance -= e.amount;
      e.balance = balance;
    });

    return entries;
  }, [selectedCustomer, sales, cashMovements]);

  const exportarPDF = () => {
    try {
      if (!selectedCustomerData || ledger.length === 0) return;
      const doc = new jsPDF();
      doc.setFontSize(16);
      doc.text('Estado de Cuenta', 14, 20);
      doc.setFontSize(12);
      doc.text(`Cliente: ${selectedCustomerData.name}`, 14, 30);
      doc.text(`Teléfono: ${selectedCustomerData.phone || '—'}`, 14, 36);
      doc.text(`Saldo Actual: $${(selectedCustomerData.current_balance || 0).toLocaleString()}`, 14, 42);

      doc.autoTable({
        startY: 50,
        head: [['Fecha', 'Tipo', 'Descripción', 'Cargo', 'Abono', 'Balance']],
        body: ledger.map((e) => [
          e.date ? new Date(e.date).toLocaleDateString('es-AR') : '—',
          e.type === 'cargo' ? 'Cargo' : 'Abono',
          e.description,
          e.type === 'cargo' ? `$${e.amount.toLocaleString()}` : '—',
          e.type === 'abono' ? `$${e.amount.toLocaleString()}` : '—',
          `$${e.balance.toLocaleString()}`,
        ]),
      });

      doc.save(`estado-cuenta-${selectedCustomerData.name}-${new Date().toISOString().split('T')[0]}.pdf`);
    } catch (err) {
      console.error('Error al exportar PDF:', err);
    }
  };

  const columns = [
    { key: 'date', label: 'Fecha', render: (v) => v ? new Date(v).toLocaleDateString('es-AR') : '—' },
    { key: 'type', label: 'Tipo', render: (v) => (
      <Badge text={v === 'cargo' ? 'Cargo' : 'Abono'} color={v === 'cargo' ? 'red' : 'green'} />
    )},
    { key: 'description', label: 'Descripción', render: (v) => <span className="font-body">{v}</span> },
    { key: 'amount', label: 'Monto', render: (v, row) => (
      <span className="font-body-bold" style={{ color: row.type === 'cargo' ? 'var(--red-text)' : 'var(--green-text)' }}>
        ${v.toLocaleString()}
      </span>
    )},
    { key: 'balance', label: 'Balance', render: (v) => (
      <span className="font-body-bold" style={{ color: v > 0 ? 'var(--red-text)' : 'var(--green-text)' }}>
        ${v.toLocaleString()}
      </span>
    )},
  ];

  if (customersLoading) return <Loading message="Cargando clientes..." />;
  if (customersError) return <ErrorState message={customersError} />;

  return (
    <div>
      <h2 className="font-title mb-4">Estado de Cuenta de Clientes</h2>

      <div className="cloudpos-card mb-4">
        <label htmlFor="customer-select" className="font-label-muted d-block mb-2">Seleccionar Cliente</label>
        <select
          id="customer-select"
          className="form-select"
          style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--border)', color: 'var(--text-primary)' }}
          value={selectedCustomer || ''}
          onChange={(e) => setSelectedCustomer(e.target.value || null)}
        >
          <option value="">— Seleccionar cliente —</option>
          {customers?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} — Deuda: ${parseFloat(c.current_balance || 0).toLocaleString()}
            </option>
          ))}
        </select>
      </div>

      {selectedCustomer && selectedCustomerData && (
        <>
          <div className="cloudpos-card mb-3">
            <div className="d-flex justify-content-between align-items-center flex-wrap gap-2">
              <div>
                <h5 className="font-heading mb-1">{selectedCustomerData.name}</h5>
                <span className="font-small text-muted">
                  {selectedCustomerData.phone || '—'} · Lista {selectedCustomerData.price_list || 'A'}
                </span>
              </div>
              <div className="d-flex gap-2 align-items-center">
                <span className="font-body-bold" style={{ color: 'var(--red-text)' }}>
                  Saldo: ${parseFloat(selectedCustomerData.current_balance || 0).toLocaleString()}
                </span>
                <button className="btn btn-cloudpos-ghost btn-sm" onClick={exportarPDF}>
                  <i className="bi bi-file-earmark-pdf me-1"></i> Exportar PDF
                </button>
              </div>
            </div>
          </div>

          {salesError || cashError ? (
            <ErrorState message={salesError || cashError} />
          ) : salesLoading || cashLoading ? (
            <Loading message="Cargando movimientos..." />
          ) : ledger.length > 0 ? (
            <DataTable columns={columns} data={ledger} />
          ) : (
            <EmptyState message="Sin movimientos para este cliente" />
          )}
        </>
      )}
    </div>
  );
};
