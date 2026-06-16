import { useState, useMemo, useCallback } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabase.jsx';
import { StatCard, Loading, ErrorState, EmptyState, Badge } from '@/components/shared/index.jsx';
import { DonutChart, HorizontalBarChart } from '@/components/charts/index.jsx';
import jsPDF from 'jspdf';
import 'jspdf-autotable';
import { sanitizeText } from '@/utils/helpers.js';

const getTodayStr = () => new Date().toISOString().split('T')[0];
const getDaysAgoStr = (days) => {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().split('T')[0];
};

export const ReporteCierre = () => {
  const [periodo, setPeriodo] = useState('hoy');
  const [fechaDesde, setFechaDesde] = useState('');
  const [fechaHasta, setFechaHasta] = useState('');
  const [pdfError, setPdfError] = useState(null);

  const todayStr = useMemo(() => getTodayStr(), []);
  const weekAgoStr = useMemo(() => getDaysAgoStr(7), []);
  const monthAgoStr = useMemo(() => getDaysAgoStr(30), []);

  let fechaInicio = todayStr;
  let fechaFin = todayStr;

  if (periodo === 'semana') {
    fechaInicio = weekAgoStr;
  } else if (periodo === 'mes') {
    fechaInicio = monthAgoStr;
  } else if (periodo === 'personalizado' && fechaDesde && fechaHasta) {
    fechaInicio = fechaDesde;
    fechaFin = fechaHasta;
  }

  const fechaFinCompleta = useMemo(() => {
    const endDay = periodo === 'personalizado' && fechaHasta ? fechaHasta : fechaFin;
    const nextDay = new Date(endDay);
    nextDay.setDate(nextDay.getDate() + 1);
    return nextDay.toISOString().split('T')[0];
  }, [periodo, fechaFin, fechaHasta]);

  const { data: sales, loading: salesLoading, error: salesError } = useSupabaseQuery('sales', {
    select: '*, customer(name), user(username), items(quantity, unit_price, subtotal, description, variant(name))',
    filter: [['date', 'gte', fechaInicio], ['date', 'lt', fechaFinCompleta]],
    enabled: true,
  });

  const { data: purchases, loading: purchasesLoading, error: purchasesError } = useSupabaseQuery('purchases', {
    select: 'total_amount, date, status',
    filter: [['date', 'gte', fechaInicio], ['date', 'lt', fechaFinCompleta]],
    enabled: true,
  });

  const { data: cashMovements, loading: cashLoading, error: cashError } = useSupabaseQuery('cash_movements', {
    select: 'movement_type, amount, description, time',
    filter: [['time', 'gte', fechaInicio], ['time', 'lt', fechaFinCompleta]],
    enabled: true,
  });

  const reporte = useMemo(() => {
    if (!sales) return null;

    const completadas = sales.filter((s) => s.status === 'completada');
    const anuladas = sales.filter((s) => s.status === 'anulada');
    const devoluciones = sales.filter((s) => s.status === 'devolucion');

    const revenue = completadas.reduce((sum, s) => sum + parseFloat(s.total_amount || 0), 0);
    const profit = completadas.reduce((sum, s) => sum + parseFloat(s.profit || 0), 0);
    const tickets = completadas.length;
    const margin = revenue > 0 ? ((profit / revenue) * 100).toFixed(1) : 0;
    const avgTicket = tickets > 0 ? Math.round(revenue / tickets) : 0;

    const anulacionesTotal = anuladas.reduce((sum, s) => sum + parseFloat(s.total_amount || 0), 0);
    const devolucionesTotal = devoluciones.reduce((sum, s) => sum + parseFloat(s.total_amount || 0), 0);

    const paymentMethods = {};
    completadas.forEach((s) => {
      const method = s.payment_method || 'efectivo';
      if (!paymentMethods[method]) paymentMethods[method] = { count: 0, total: 0 };
      paymentMethods[method].count++;
      paymentMethods[method].total += parseFloat(s.total_amount || 0);
    });

    const topProducts = {};
    sales.forEach((s) => {
      if (s.status !== 'completada' || !s.items) return;
      s.items.forEach((item) => {
        const name = item.variant?.name || item.description || '—';
        if (!topProducts[name]) topProducts[name] = { qty: 0, revenue: 0 };
        topProducts[name].qty += parseFloat(item.quantity || 0);
        topProducts[name].revenue += parseFloat(item.subtotal || 0);
      });
    });

    const topProductsList = Object.entries(topProducts)
      .map(([name, data]) => ({ name, ...data }))
      .sort((a, b) => b.qty - a.qty)
      .slice(0, 8);

    const manualMovements = cashMovements?.filter((m) => {
      if (!m.movement_type) return false;
      return m.movement_type.includes('manual') || m.movement_type.includes('ingreso') || m.movement_type.includes('gasto');
    }) || [];

    const ingresosManuales = manualMovements
      .filter((m) => m.movement_type?.includes('ingreso'))
      .reduce((sum, m) => sum + parseFloat(m.amount || 0), 0);

    const gastosManuales = manualMovements
      .filter((m) => m.movement_type?.includes('gasto') || m.movement_type?.includes('retiro'))
      .reduce((sum, m) => sum + parseFloat(m.amount || 0), 0);

    const totalCompras = purchases?.filter((p) => p.status === 'pagada')
      .reduce((sum, p) => sum + parseFloat(p.total_amount || 0), 0) || 0;

    return {
      revenue, profit, tickets, margin, avgTicket,
      anulaciones: { count: anuladas.length, total: anulacionesTotal },
      devoluciones: { count: devoluciones.length, total: devolucionesTotal },
      paymentMethods,
      topProducts: topProductsList,
      ingresosManuales,
      gastosManuales,
      totalCompras,
    };
  }, [sales, purchases, cashMovements]);

  const exportarPDF = useCallback(() => {
    try {
      setPdfError(null);
      if (!reporte) return;
      const doc = new jsPDF();
      doc.setFontSize(16);
      doc.text('Reporte de Cierre', 14, 20);
      doc.setFontSize(10);
      doc.text(`Período: ${fechaInicio} a ${fechaFin}`, 14, 28);
      doc.text(`Generado: ${new Date().toLocaleString('es-AR')}`, 14, 34);

      doc.setFontSize(12);
      doc.text('KPIs', 14, 44);
      doc.setFontSize(10);
      doc.text(`Ventas: $${reporte.revenue.toLocaleString()}`, 14, 52);
      doc.text(`Ganancia: $${reporte.profit.toLocaleString()}`, 14, 58);
      doc.text(`Margen: ${reporte.margin}%`, 14, 64);
      doc.text(`Tickets: ${reporte.tickets}`, 14, 70);
      doc.text(`Ticket Promedio: $${reporte.avgTicket.toLocaleString()}`, 14, 76);

      const sanitizedBody = reporte.topProducts.map((p) => [
        sanitizeText(p.name),
        p.qty.toLocaleString(),
        `$${p.revenue.toLocaleString()}`,
      ]);

      doc.autoTable({
        startY: 85,
        head: [['Producto', 'Cantidad', 'Revenue']],
        body: sanitizedBody,
      });

      doc.save(`reporte-cierre-${fechaInicio}-${fechaFin}.pdf`);
    } catch (err) {
      setPdfError(`Error al exportar PDF: ${err.message}`);
    }
  }, [reporte, fechaInicio, fechaFin]);

  if (salesLoading) return <Loading message="Cargando reporte..." />;
  if (salesError) return <ErrorState message={salesError} />;
  if (!reporte || (reporte.tickets === 0 && reporte.totalCompras === 0)) {
    return <EmptyState message="Sin datos para el período seleccionado" />;
  }

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4 flex-wrap gap-2">
        <h2 className="font-title mb-0">Reporte de Cierre</h2>
        <div className="d-flex gap-2 align-items-center flex-wrap">
          <select
            className="form-select form-select-sm"
            style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--border)', color: 'var(--text-primary)', width: 'auto' }}
            value={periodo}
            onChange={(e) => setPeriodo(e.target.value)}
            aria-label="Seleccionar período"
          >
            <option value="hoy">Hoy</option>
            <option value="semana">Última Semana</option>
            <option value="mes">Último Mes</option>
            <option value="personalizado">Personalizado</option>
          </select>
          {periodo === 'personalizado' && (
            <>
              <input
                type="date"
                className="form-control form-control-sm"
                style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--border)', color: 'var(--text-primary)', width: 'auto' }}
                value={fechaDesde}
                onChange={(e) => setFechaDesde(e.target.value)}
                aria-label="Fecha desde"
              />
              <input
                type="date"
                className="form-control form-control-sm"
                style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--border)', color: 'var(--text-primary)', width: 'auto' }}
                value={fechaHasta}
                onChange={(e) => setFechaHasta(e.target.value)}
                aria-label="Fecha hasta"
              />
            </>
          )}
          <button className="btn btn-cloudpos-ghost btn-sm" onClick={exportarPDF}>
            <i className="bi bi-file-earmark-pdf me-1"></i> Exportar PDF
          </button>
        </div>
      </div>

      {pdfError && (
        <div className="alert alert-danger alert-dismissible fade show" role="alert">
          {pdfError}
          <button type="button" className="btn-close" onClick={() => setPdfError(null)} aria-label="Cerrar"></button>
        </div>
      )}

      <div className="row g-3 mb-4">
        <div className="col-md-3 col-6">
          <StatCard title="Ventas" value={`$${reporte.revenue.toLocaleString()}`} sub={`${reporte.tickets} tickets`} accent="green" />
        </div>
        <div className="col-md-3 col-6">
          <StatCard title="Ganancia" value={`$${reporte.profit.toLocaleString()}`} sub={`Margen ${reporte.margin}%`} accent="accent" />
        </div>
        <div className="col-md-3 col-6">
          <StatCard title="Ticket Promedio" value={`$${reporte.avgTicket.toLocaleString()}`} sub={`${reporte.tickets} tickets`} accent="orange" />
        </div>
        <div className="col-md-3 col-6">
          <StatCard title="Compras" value={`$${reporte.totalCompras.toLocaleString()}`} sub="período" accent="red" />
        </div>
      </div>

      <div className="row g-3 mb-3">
        <div className="col-lg-4 col-md-6">
          <div className="cloudpos-card">
            <h5 className="font-heading mb-3">Métodos de Pago</h5>
            {Object.keys(reporte.paymentMethods).length > 0 ? (
              <DonutChart
                data={Object.entries(reporte.paymentMethods).map(([label, data]) => ({
                  label: `${label.charAt(0).toUpperCase() + label.slice(1)} (${data.count})`,
                  value: Math.round(data.total),
                }))}
                height={250}
              />
            ) : (
              <EmptyState message="Sin datos" />
            )}
          </div>
        </div>
        <div className="col-lg-4 col-md-6">
          <div className="cloudpos-card">
            <h5 className="font-heading mb-3">Top 8 Productos</h5>
            {reporte.topProducts.length > 0 ? (
              <HorizontalBarChart
                data={reporte.topProducts.map((p) => ({ label: p.name.length > 20 ? p.name.slice(0, 18) + '…' : p.name, value: Math.round(p.qty) }))}
                height={250}
              />
            ) : (
              <EmptyState message="Sin datos" />
            )}
          </div>
        </div>
        <div className="col-lg-4 col-md-12">
          <div className="cloudpos-card mb-3">
            <h5 className="font-heading mb-3">Anulaciones y Devoluciones</h5>
            <div className="d-flex justify-content-between mb-2">
              <span className="font-body text-muted">Anulaciones</span>
              <span className="font-body-bold" style={{ color: 'var(--red-text)' }}>
                {reporte.anulaciones.count} — ${reporte.anulaciones.total.toLocaleString()}
              </span>
            </div>
            <div className="d-flex justify-content-between mb-2">
              <span className="font-body text-muted">Devoluciones</span>
              <span className="font-body-bold" style={{ color: 'var(--orange-text)' }}>
                {reporte.devoluciones.count} — ${reporte.devoluciones.total.toLocaleString()}
              </span>
            </div>
          </div>
          <div className="cloudpos-card">
            <h5 className="font-heading mb-3">Movimientos Manuales</h5>
            <div className="d-flex justify-content-between mb-2">
              <span className="font-body text-muted">Ingresos</span>
              <span className="font-body-bold" style={{ color: 'var(--green-text)' }}>
                ${reporte.ingresosManuales.toLocaleString()}
              </span>
            </div>
            <div className="d-flex justify-content-between">
              <span className="font-body text-muted">Gastos</span>
              <span className="font-body-bold" style={{ color: 'var(--red-text)' }}>
                ${reporte.gastosManuales.toLocaleString()}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
