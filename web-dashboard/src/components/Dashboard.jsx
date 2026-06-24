import { useState, useMemo, useCallback, useEffect, useRef, memo } from 'react';
import { useSupabaseQuery } from '@/hooks/useSupabaseQuery.js';
import { supabase } from '@/lib/supabase.jsx';
import { useAuth } from '@/context/AuthContext.jsx';
import { StatCard, Loading, ErrorState, Badge, Skeleton } from '@/components/shared/index.jsx';
import { AreaChart, DonutChart, HorizontalBarChart, LineChart, SalesByHourChart } from '@/components/charts/index.jsx';
import { getTodayStr, getDaysAgoStr } from '@/utils/dateUtils.js';

const REFRESH_INTERVAL = 120000;

import { LowStockAlert } from '@/components/dashboard/LowStockAlert.jsx';
import { PromoList } from '@/components/dashboard/PromoList.jsx';

export const Dashboard = () => {
  const { user } = useAuth();
  const [topProducts, setTopProducts] = useState([]);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const todayStr = useMemo(() => getTodayStr(), []);
  const monthAgoStr = useMemo(() => getDaysAgoStr(30), []);

  const { data: sales, loading: salesLoading, error: salesError } = useSupabaseQuery('sales', {
    select: 'id, total_amount, profit, date, status, payment_method',
    filter: ['date', 'gte', monthAgoStr],
    refreshInterval: REFRESH_INTERVAL,
    silent: true,
  });

  const { data: activePromos, loading: promosLoading } = useSupabaseQuery('promotions', {
    select: 'id, name, promo_type, discount_value, buy_qty, pay_qty, date_to',
    filter: ['is_active', 'eq', true],
    refreshInterval: REFRESH_INTERVAL,
    silent: true,
  });

  const { data: lowStock } = useSupabaseQuery('view_low_stock', {
    select: 'product_name, current_stock, min_stock',
    refreshInterval: REFRESH_INTERVAL,
    silent: true,
  });

  const { data: purchases } = useSupabaseQuery('purchases', {
    select: 'id, total_amount, date, status',
    filter: ['date', 'gte', monthAgoStr],
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
  }, [fetchTopProducts]);

  const dashboardStats = useMemo(() => {
    if (!sales) return { revenue: 0, profit: 0, tickets: 0, margin: 0, avgTicket: 0, weeklySales: [], paymentMethods: [], salesByHour: [], salesVsPurchases: [], salesVsPurchasesCategories: [], anulaciones: 0, devoluciones: 0 };

    let revenue = 0, profit = 0, tickets = 0, anulaciones = 0, devoluciones = 0;
    const dailyTotals = {};
    const hourlyTotals = {};
    const paymentCounts = {};
    const monthlySales = {};

    sales.forEach((s) => {
      const isToday = s.date?.startsWith(todayStr);
      const amount = parseFloat(s.total_amount || 0);

      if (s.status === 'completada') {
        if (isToday) {
          revenue += amount;
          profit += parseFloat(s.profit || 0);
          tickets++;
        }

        const date = s.date?.split('T')[0] || s.date?.substring(0, 10);
        if (date) {
          dailyTotals[date] = (dailyTotals[date] || 0) + amount;
          monthlySales[date] = (monthlySales[date] || 0) + amount;
        }

        const hour = s.date?.split('T')[1]?.substring(0, 2);
        if (hour) {
          hourlyTotals[hour] = (hourlyTotals[hour] || 0) + amount;
        }

        const method = s.payment_method || 'efectivo';
        paymentCounts[method] = (paymentCounts[method] || 0) + amount;

      } else if (s.status === 'anulada') {
        anulaciones++;
      } else if (s.status === 'devolucion') {
        devoluciones++;
      }
    });

    const margin = revenue > 0 ? ((profit / revenue) * 100).toFixed(1) : 0;
    const avgTicket = tickets > 0 ? Math.round(revenue / tickets) : 0;

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

    const monthlyPurchases = {};
    purchases?.forEach((p) => {
      if (p.status !== 'pagada') return;
      const date = p.date?.split('T')[0];
      if (!date) return;
      monthlyPurchases[date] = (monthlyPurchases[date] || 0) + parseFloat(p.total_amount || 0);
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

      <LowStockAlert items={lowStockItems} />

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
            <PromoList promos={activePromos} loading={promosLoading} />
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
