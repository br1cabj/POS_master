import { lazy, Suspense, useState, useEffect } from 'react';
import { HashRouter, Routes, Route, Navigate, Outlet, useLocation } from 'react-router-dom';
import './App.css';
import { AuthProvider, useAuth } from '@/context/AuthContext.jsx';
import { RefreshProvider } from '@/context/RefreshContext.jsx';
import { Login } from '@/components/Login.jsx';
import { Layout } from '@/components/Layout.jsx';
import { Loading } from '@/components/shared/index.jsx';
import { isSectionAllowed } from '@/config/sections.js';

const Dashboard = lazy(() => import('@/components/Dashboard.jsx'));
const Sales = lazy(() => import('@/components/Sales.jsx'));
const Products = lazy(() => import('@/components/Products.jsx'));
const Customers = lazy(() => import('@/components/Customers.jsx'));
const Quotations = lazy(() => import('@/components/Quotations.jsx'));
const Inventory = lazy(() => import('@/components/Inventory.jsx'));
const Purchases = lazy(() => import('@/components/Purchases.jsx'));
const Promos = lazy(() => import('@/components/Promos.jsx'));
const Suppliers = lazy(() => import('@/components/Suppliers.jsx'));
const Cash = lazy(() => import('@/components/Cash.jsx'));
const Users = lazy(() => import('@/components/Users.jsx'));
const StockMovements = lazy(() => import('@/components/StockMovements.jsx'));
const ArticleHistory = lazy(() => import('@/components/ArticleHistory.jsx'));
const Categories = lazy(() => import('@/components/Categories.jsx'));
const PurchaseReturns = lazy(() => import('@/components/PurchaseReturns.jsx'));
const Combos = lazy(() => import('@/components/Combos.jsx'));
const ReporteCierre = lazy(() => import('@/components/ReporteCierre.jsx'));
const StockAlerts = lazy(() => import('@/components/StockAlerts.jsx'));
const CustomerLedger = lazy(() => import('@/components/CustomerLedger.jsx'));

const routeSections = [
  { path: '/', Component: Dashboard, id: 'dashboard' },
  { path: '/sales', Component: Sales, id: 'sales' },
  { path: '/products', Component: Products, id: 'products' },
  { path: '/customers', Component: Customers, id: 'customers' },
  { path: '/quotations', Component: Quotations, id: 'quotations' },
  { path: '/inventory', Component: Inventory, id: 'inventory' },
  { path: '/purchases', Component: Purchases, id: 'purchases' },
  { path: '/promos', Component: Promos, id: 'promos' },
  { path: '/suppliers', Component: Suppliers, id: 'suppliers' },
  { path: '/cash', Component: Cash, id: 'cash' },
  { path: '/users', Component: Users, id: 'users' },
  { path: '/stock-movements', Component: StockMovements, id: 'stock-movements' },
  { path: '/article-history', Component: ArticleHistory, id: 'article-history' },
  { path: '/categories', Component: Categories, id: 'categories' },
  { path: '/purchase-returns', Component: PurchaseReturns, id: 'purchase-returns' },
  { path: '/combos', Component: Combos, id: 'combos' },
  { path: '/reporte-cierre', Component: ReporteCierre, id: 'reporte-cierre' },
  { path: '/stock-alerts', Component: StockAlerts, id: 'stock-alerts' },
  { path: '/customer-ledger', Component: CustomerLedger, id: 'customer-ledger' },
];

const ProtectedRoute = () => {
  const { user, loading, logout } = useAuth();
  const location = useLocation();
  const [theme, setTheme] = useState(() => document.documentElement.getAttribute('data-bs-theme') || 'dark');

  useEffect(() => {
    document.documentElement.setAttribute('data-bs-theme', theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'));

  if (loading) return <Loading message="Iniciando sesión..." />;

  if (!user) {
    return (
      <Suspense fallback={<Loading message="Cargando..." />}>
        <Login />
      </Suspense>
    );
  }

  const allowed = isSectionAllowed(location.pathname, user.role);
  if (!allowed) {
    return <Navigate to="/" replace />;
  }

  return (
    <Layout theme={theme} onThemeToggle={toggleTheme} onLogout={logout} user={user}>
      <Suspense fallback={<Loading message="Cargando sección..." />}>
        <Outlet />
      </Suspense>
    </Layout>
  );
};

function App() {
  return (
    <HashRouter>
      <AuthProvider>
        <RefreshProvider>
          <Routes>
            <Route element={<ProtectedRoute />}>
              {routeSections.map(({ path, Component }) => (
                <Route key={path} path={path} element={<Component />} />
              ))}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </RefreshProvider>
      </AuthProvider>
    </HashRouter>
  );
}

export default App;
