import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabase.jsx';
import { supabase } from '@/lib/supabase.jsx';
import { useAuth } from '@/context/AuthContext.jsx';
import { StatCard, Loading, ErrorState, Badge } from '@/components/shared/index.jsx';
import { AreaChart, DonutChart, HorizontalBarChart, LineChart, SalesByHourChart } from '@/components/charts/index.jsx';
import { useRefresh } from '@/context/RefreshContext.jsx';

const REFRESH_INTERVAL = 120000;

const getTodayStr = () => new Date().toISOString().split('T')[0];
const getDaysAgoStr = (days) => {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().split('T')[0];
};

export const Dashboard = () => {
  const { user } = useAuth();
  const { markRefreshed } = useRefresh();
  const [topProducts, setTopProducts] = useState([]);
  const mountedRef = useRef(true);

  const todayStr = useMemo(() => getTodayStr(), []);
  const weekAgoStr = useMemo(() => getDaysAgoStr(7), []);
  const monthAgoStr = useMemo(() => getDaysAgoStr(30), []);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const { data: sales, loading: salesLoading, error: salesError } = useSupabaseQuery('sales', {
    select: 'id, total_amount, profit, date, status, payment_method',
    filter: ['date', 'gte', monthAgoStr],
    enabled: true,
    refreshInterval: REFRESH_INTERVAL,
    silent: true,
    onRefresh: markRefreshed,
  });

  const { data: activePromos, loading: promosLoading } = useSupabaseQuery('promotions', {
    select: 'id, name, promo_type, discount_value, buy_qty, pay_qty, date_to',
    filter: ['is_active', 'eq', true],
    enabled: true,
    refreshInterval: REFRESH_INTERVAL,
    silent: true,
  });

  const { data: lowStock, loading: stockLoading } = useSupabaseQuery('view_low_stock', {
    select: 'product_name, current_stock, min_stock',
    enabled: true,
    refreshInterval: REFRESH_INTERVAL,
    silent: true,
  });

  const fetchTopProducts = useCallback(async () => {
    if (!user?.tenantId) return;
    try {
      const { data, error } = await supabase.rpc('get_top_products', {
        p_tenant_id: user.tenantId,
        p_start_date: monthAgoStr,
        p_limit: 5
      });
      if (error) {
        console.error('Failed to fetch top products:', error);
        return;
      }
      if (data && mountedRef.current) setTopProducts(data);
    } catch (err) {
      console.error('Failed to fetch top products:', err);
    }
  }, [user?.tenantId, monthAgoStr]);

  useEffect(() => {
    fetchTopProducts();
    const interval = setInterval(fetchTopProducts, REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchTopProducts]);

  const { data: purchases, loading: purchasesLoading } = useSupabaseQuery('purchases', {
    select: 'id, total_amount, date, status',
    filter: ['date', 'gte', monthAgoStr],
    enabled: true,
    refreshInterval: REFRESH_INTERVAL,
    silent: true,
  });

  const dashboardStats = useMemo(() => {
    if (!sales) return { revenue: 0, profit: 0, tickets: 0, margin: 0, avgTicket: 0, weeklySales: [], paymentMethods: [], salesByHour: [], salesVsPurchases: [], salesVsPurchasesCategories: [], anulaciones: 0, devoluciones: 0 };

    const todaySales = sales.filter((s) => s.date?.startsWith(todayStr) && s.status === 'completada');
    const revenue = todaySales.reduce((sum, s) => sum + parseFloat(s.total_amount || 0), 0);
    const profit = todaySales.reduce((sum, s) => sum + parseFloat(s.profit || 0), 0);
    const tickets = todaySales.length;
    const margin = revenue > 0 ? ((profit / revenue) * 100).toFixed(1) : 0;
    const avgTicket = tickets > 0 ? Math.round(revenue / tickets) : 0;

    const dailyTotals = {};
    const hourlyTotals = {};
    const paymentCounts = {};
    sales.forEach((s) => {
      if (s.status !== 'completada') return;
      const date = s.date?.split('T')[0] || s.date?.substring(0, 10);
      if (!date) return;
      if (!dailyTotals[date]) dailyTotals[date] = 0;
      dailyTotals[date] += parseFloat(s.total_amount || 0);

      const hour = s.date?.split('T')[1]?.substring(0, 2);
      if (hour) {
        if (!hourlyTotals[hour]) hourlyTotals[hour] = 0;
        hourlyTotals[hour] += parseFloat(s.total_amount || 0);
      }

      const method = s.payment_method || 'efectivo';
      if (!paymentCounts[method]) paymentCounts[method] = 0;
      paymentCounts[method] += parseFloat(s.total_amount || 0);
    });

    const weeklySales = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date();
      d.setDate(d.getDate() - i);
      const dateStr = d.toISOString().split('T')[0];
      const label = d.toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' });
      weeklySales.push({ label, value: Math.round(dailyTotals[dateStr] || 0) });
    }

    const salesByHour = [];
    for (let h = 0; h < 24; h++) {
      const hourStr = h.toString().padStart(2, '0');
      salesByHour.push({ label: `${hourStr}:00`, value: Math.round(hourlyTotals[hourStr] || 0) });
    }

    const paymentMethods = Object.entries(paymentCounts)
      .map(([label, value]) => ({ label: label.charAt(0).toUpperCase() + label.slice(1), value: Math.round(value) }))
      .sort((a, b) => b.value - a.value);

    const monthlySales = {};
    const monthlyPurchases = {};
    sales.forEach((s) => {
      if (s.status !== 'completada') return;
      const date = s.date?.split('T')[0];
      if (!date) return;
      if (!monthlySales[date]) monthlySales[date] = 0;
      monthlySales[date] += parseFloat(s.total_amount || 0);
    });
    purchases?.forEach((p) => {
      if (p.status !== 'pagada') return;
      const date = p.date?.split('T')[0];
      if (!date) return;
      if (!monthlyPurchases[date]) monthlyPurchases[date] = 0;
      monthlyPurchases[date] += parseFloat(p.total_amount || 0);
    });

    const allDates = [...new Set([...Object.keys(monthlySales), ...Object.keys(monthlyPurchases)])].sort();
    const salesVsPurchases = [
      { name: 'Ventas', data: allDates.map((d) => Math.round(monthlySales[d] || 0)) },
      { name: 'Compras', data: allDates.map((d) => Math.round(monthlyPurchases[d] || 0)) },
    ];
    const salesVsPurchasesCategories = allDates.map((d) => {
      const date = new Date(d);
      return date.toLocaleDateString('es-AR', { day: '2-digit', month: 'short' });
    });

    const anulaciones = sales.filter((s) => s.status === 'anulada').length;
    const devoluciones = sales.filter((s) => s.status === 'devolucion').length;

    return { revenue, profit, tickets, margin, avgTicket, weeklySales, paymentMethods, salesByHour, salesVsPurchases, salesVsPurchasesCategories, anulaciones, devoluciones };
  }, [sales, purchases, todayStr]);

  const lowStockItems = useMemo(() => {
    if (!lowStock) return [];
    return lowStock.map((s) => ({
      name: s.product_name || '—',
      current: parseFloat(s.current_stock || 0),
      min: s.min_stock || 0,
    }));
  }, [lowStock]);

  if (salesLoading) return <Loading message="Cargando dashboard..." />;
  if (salesError) return <ErrorState message={salesError} />;

  const { revenue, profit, tickets, margin, avgTicket, weeklySales, paymentMethods, salesByHour, salesVsPurchases, salesVsPurchasesCategories, anulaciones, devoluciones } = dashboardStats;

  return (
    <div>
      <div className="d-flex justify-content-between align-items-center mb-4">
        <div>
          <h2 className="font-title mb-1">Dashboard</h2>
          <p className="font-body text-muted mb-0">Resumen de actividad del día</p>
        </div>
      </div>

      <div className="row g-3 mb-4">
        <div className="col-md-3 col-6">
          <StatCard title="Ventas de Hoy" value={`$${revenue.toLocaleString()}`} sub={`${tickets} tickets`} accent="green" />
        </div>
        <div className="col-md-3 col-6">
          <StatCard title="Ganancia" value={`$${profit.toLocaleString()}`} sub={`Margen ${margin}%`} accent="accent" />
        </div>
        <div className="col-md-3 col-6">
          <StatCard title="Ticket Promedio" value={`$${avgTicket.toLocaleString()}`} sub={`${tickets} tickets`} accent="orange" />
        </div>
        <div className="col-md-3 col-6">
          <StatCard title="Anulaciones" value={anulaciones.toString()} sub={`${devoluciones} devoluciones`} accent="red" />
        </div>
      </div>

      {lowStockItems.length > 0 && (
        <div className="cloudpos-card mb-3" style={{ borderLeft: '4px solid var(--red)' }}>
          <h5 className="font-heading mb-2" style={{ color: 'var(--red-text)' }}>
            <i className="bi bi-exclamation-triangle me-1"></i> Stock Bajo ({lowStockItems.length})
          </h5>
          <div className="d-flex flex-wrap gap-2">
            {lowStockItems.slice(0, 5).map((item) => (
              <div key={item.name} className="d-flex align-items-center gap-2 p-2" style={{ backgroundColor: 'var(--red-dim)', borderRadius: '6px' }}>
                <span className="font-body-bold" style={{ color: 'var(--red-text)' }}>{item.name}</span>
                <Badge text={`${item.current}/${item.min}`} color="red" />
              </div>
            ))}
            {lowStockItems.length > 5 && (
              <span className="font-small text-muted">+{lowStockItems.length - 5} más</span>
            )}
          </div>
        </div>
      )}

      <div className="row g-3 mb-3">
        <div className="col-12">
          <div className="cloudpos-card">
            <h5 className="font-heading mb-3">Ventas — últimos 7 días</h5>
            <AreaChart data={weeklySales} height={220} title="Ventas" />
          </div>
        </div>
      </div>

      <div className="row g-3 mb-3">
        <div className="col-lg-4 col-md-6">
          <div className="cloudpos-card">
            <h5 className="font-heading mb-3">Métodos de Pago</h5>
            {paymentMethods.length > 0 ? (
              <DonutChart data={paymentMethods} height={250} title="Métodos" />
            ) : (
              <p className="text-muted font-body text-center py-4">Sin datos</p>
            )}
          </div>
        </div>
        <div className="col-lg-4 col-md-6">
          <div className="cloudpos-card">
            <h5 className="font-heading mb-3">Top 5 Productos</h5>
            {topProducts.length > 0 ? (
              <HorizontalBarChart data={topProducts} height={250} title="Cantidad" />
            ) : (
              <p className="text-muted font-body text-center py-4">Sin datos</p>
            )}
          </div>
        </div>
        <div className="col-lg-4">
          <div className="cloudpos-card">
            <h5 className="font-heading mb-3">Promociones Activas ({activePromos?.length || 0})</h5>
            {promosLoading ? (
              <Loading />
            ) : !activePromos || activePromos.length === 0 ? (
              <p className="text-muted font-body">Sin promociones activas ahora.</p>
            ) : (
              activePromos.map((promo) => {
                const detail =
                  promo.promo_type === 'nxm'
                    ? `Lleva ${promo.buy_qty} Paga ${promo.pay_qty}`
                    : promo.promo_type === 'pct'
                    ? `${promo.discount_value}% off`
                    : `$${promo.discount_value} c/u`;
                return (
                  <div key={promo.id} className="d-flex flex-wrap align-items-center gap-2 p-2 mb-2" style={{ backgroundColor: 'var(--surface-3)', borderRadius: '8px' }}>
                    <span className="badge-cloudpos badge-green flex-shrink-0">{(promo.promo_type || '—').toUpperCase()}</span>
                    <div className="flex-fill min-width-0">
                      <div className="font-body-bold">{promo.name}</div>
                      <div className="font-small text-muted">{detail}</div>
                    </div>
                    <div className="font-small text-muted flex-shrink-0">≤ {new Date(promo.date_to).toLocaleDateString('es-AR')}</div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      <div className="row g-3 mb-3">
        <div className="col-lg-6">
          <div className="cloudpos-card">
            <h5 className="font-heading mb-3">Ventas por Hora</h5>
            <SalesByHourChart data={salesByHour} height={220} />
          </div>
        </div>
        <div className="col-lg-6">
          <div className="cloudpos-card">
            <h5 className="font-heading mb-3">Ventas vs Compras (30 días)</h5>
            {salesVsPurchases[0]?.data?.length > 0 ? (
              <LineChart datasets={salesVsPurchases} categories={salesVsPurchasesCategories} height={220} />
            ) : (
              <p className="text-muted font-body text-center py-4">Sin datos</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
