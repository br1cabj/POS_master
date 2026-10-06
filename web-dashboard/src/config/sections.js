export const sections = [
  { id: 'dashboard', label: 'Dashboard', icon: 'bi-house-door', path: '/', roles: [] },
  { id: 'sales', label: 'Ventas', icon: 'bi-receipt', path: '/sales', roles: [] },
  { id: 'products', label: 'Productos', icon: 'bi-box', path: '/products', roles: [] },
  { id: 'customers', label: 'Clientes', icon: 'bi-people', path: '/customers', roles: [] },
  { id: 'quotations', label: 'Cotizaciones', icon: 'bi-file-earmark-text', path: '/quotations', roles: [] },
  { id: 'inventory', label: 'Inventario', icon: 'bi-clipboard-data', path: '/inventory', roles: [] },
  { id: 'purchases', label: 'Compras', icon: 'bi-cart', path: '/purchases', roles: ['admin', 'supervisor'] },
  { id: 'promos', label: 'Promociones', icon: 'bi-tag', path: '/promos', roles: ['admin', 'supervisor'] },
  { id: 'suppliers', label: 'Proveedores', icon: 'bi-building', path: '/suppliers', roles: ['admin', 'supervisor'] },
  { id: 'cash', label: 'Caja', icon: 'bi-cash-stack', path: '/cash', roles: ['admin', 'supervisor'] },
  { id: 'users', label: 'Usuarios', icon: 'bi-person-badge', path: '/users', roles: ['admin'] },
  { id: 'stock-movements', label: 'Mov. Stock', icon: 'bi-arrow-left-right', path: '/stock-movements', roles: [] },
  { id: 'article-history', label: 'Hist. Precios', icon: 'bi-clock-history', path: '/article-history', roles: ['admin', 'supervisor'] },
  { id: 'categories', label: 'Categorías', icon: 'bi-tag-fill', path: '/categories', roles: ['admin', 'supervisor'] },
  { id: 'purchase-returns', label: 'Devoluciones', icon: 'bi-arrow-return-left', path: '/purchase-returns', roles: ['admin', 'supervisor'] },
  { id: 'combos', label: 'Combos', icon: 'bi-grid-3x3', path: '/combos', roles: ['admin', 'supervisor'] },
  { id: 'reporte-cierre', label: 'Reporte Cierre', icon: 'bi-file-earmark-bar-graph', path: '/reporte-cierre', roles: ['admin', 'supervisor'] },
  { id: 'stock-alerts', label: 'Alertas Stock', icon: 'bi-exclamation-triangle', path: '/stock-alerts', roles: [] },
  { id: 'customer-ledger', label: 'Estado Cuenta', icon: 'bi-person-lines-fill', path: '/customer-ledger', roles: ['admin', 'supervisor'] },
];

export function isSectionAllowed(path, role) {
  const section = sections.find((s) => s.path === path);
  if (!section) return false;
  if (!section.roles || section.roles.length === 0) return true;
  return section.roles.includes(role);
}
