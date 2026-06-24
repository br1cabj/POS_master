import { useState, useEffect, useRef, useCallback, memo, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { sections } from '@/config/sections.js';

const BOTTOM_NAV_ITEMS = [
  { id: 'dashboard', path: '/', icon: 'bi-house-door', label: 'Inicio' },
  { id: 'sales', path: '/sales', icon: 'bi-receipt', label: 'Ventas' },
  { id: 'products', path: '/products', icon: 'bi-box', label: 'Productos' },
  { id: 'customers', path: '/customers', icon: 'bi-people', label: 'Clientes' },
];

function useTimeAgo(timestamp) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 10000);
    return () => clearInterval(interval);
  }, []);
  const diff = Math.floor((now - timestamp) / 1000);
  if (diff < 60) return 'hace un momento';
  if (diff < 3600) return `hace ${Math.floor(diff / 60)} min`;
  return `hace ${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)} min`;
}

function useCurrentDate() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const interval = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(interval);
  }, []);
  return now;
}

const DesktopNavMenu = memo(({ sections, activeSection, onNavigate }) => (
  <div className="desktop-nav-menu">
    {sections.map((section) => (
      <button
        key={section.id}
        className={`nav-link-cloudpos desktop-nav-item ${activeSection === section.id ? 'active' : ''}`}
        onClick={() => onNavigate(section.path)}
        aria-current={activeSection === section.id ? 'page' : undefined}
      >
        <i className={`bi ${section.icon} nav-icon`}></i>
        <span className="nav-label">{section.label}</span>
      </button>
    ))}
  </div>
));

DesktopNavMenu.displayName = 'DesktopNavMenu';

export const Layout = memo(({ children, theme, onThemeToggle, user, onLogout }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [lastRefresh, setLastRefresh] = useState(Date.now());
  const timeAgo = useTimeAgo(lastRefresh);
  const currentDate = useCurrentDate();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const overlayRef = useRef(null);
  const drawerRef = useRef(null);
  const hamburgerBtnRef = useRef(null);

  useEffect(() => {
    const interval = setInterval(() => setLastRefresh(Date.now()), 120000);
    return () => clearInterval(interval);
  }, []);

  const activeSection = useMemo(
    () => sections.find((s) => s.path === location.pathname)?.id || 'dashboard',
    [location.pathname]
  );

  const visibleSections = useMemo(() =>
    sections.filter((s) => {
      if (!s.roles || s.roles.length === 0) return true;
      return s.roles.includes(user?.role);
    }),
    [user?.role]
  );

  const bottomNavItems = useMemo(() =>
    BOTTOM_NAV_ITEMS.filter((item) => {
      const section = sections.find((s) => s.id === item.id);
      if (!section) return false;
      if (!section.roles || section.roles.length === 0) return true;
      return section.roles.includes(user?.role);
    }),
    [user?.role]
  );

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (drawerOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [drawerOpen]);

  const handleKeyDown = useCallback((e) => {
    if (e.key === 'Escape' && drawerOpen) {
      setDrawerOpen(false);
      if (hamburgerBtnRef.current) hamburgerBtnRef.current.focus();
    }
  }, [drawerOpen]);

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const closeDrawer = useCallback(() => {
    setDrawerOpen(false);
  }, []);

  const toggleDrawer = useCallback(() => {
    setDrawerOpen((prev) => !prev);
  }, []);

  const handleNavigate = useCallback((path) => {
    navigate(path);
    setDrawerOpen(false);
  }, [navigate]);

  return (
    <div className="app-layout">
      <a
        href="#main-content"
        className="skip-link"
      >
        Saltar al contenido
      </a>

      <nav className="navbar-cloudpos sticky-top" role="navigation" aria-label="Navegación principal">
        <div className="navbar-content">
          <div className="navbar-start">
            <button
              ref={hamburgerBtnRef}
              className="hamburger-btn d-md-none"
              onClick={toggleDrawer}
              aria-label={drawerOpen ? 'Cerrar menú' : 'Abrir menú'}
              aria-expanded={drawerOpen}
              aria-controls="mobile-drawer"
            >
              <i className="bi bi-list"></i>
            </button>
            <span className="navbar-brand">
              {sections.find((s) => s.id === activeSection)?.label || 'CloudPOS'}
            </span>
            <span className="badge-cloudpos badge-accent d-none d-md-inline">SOLO LECTURA</span>
          </div>
          <div className="navbar-end">
            <span className="navbar-date d-none d-sm-inline">
              {currentDate.toLocaleDateString('es-AR', { weekday: 'short', day: 'numeric', month: 'short' })}
            </span>
            <span className="navbar-refresh d-none d-lg-inline">
              <i className="bi bi-arrow-clockwise"></i>
              {timeAgo}
            </span>
            {user && (
              <span className="navbar-user d-none d-md-inline">
                <i className="bi bi-person-circle"></i>
                {user.displayName}
                <span className="user-role">({user.role})</span>
              </span>
            )}
            <button
              className="icon-btn"
              onClick={onThemeToggle}
              aria-label={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
              title={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
            >
              <i className={`bi ${theme === 'dark' ? 'bi-sun' : 'bi-moon'}`}></i>
            </button>
            {user && (
              <button
                className="icon-btn"
                onClick={onLogout}
                aria-label="Cerrar sesión"
                title="Cerrar sesión"
              >
                <i className="bi bi-box-arrow-right"></i>
              </button>
            )}
          </div>
        </div>
      </nav>

      {drawerOpen && (
        <div
          ref={overlayRef}
          className="drawer-overlay"
          onClick={closeDrawer}
          aria-hidden="true"
        />
      )}

      <aside
        id="mobile-drawer"
        ref={drawerRef}
        className={`mobile-drawer d-md-none ${drawerOpen ? 'drawer-open' : ''}`}
        role="dialog"
        aria-modal="true"
        aria-label="Menú de navegación"
      >
        <div className="drawer-header">
          <span className="drawer-brand">CloudPOS</span>
          <button className="drawer-close" onClick={closeDrawer} aria-label="Cerrar menú">
            <i className="bi bi-x-lg"></i>
          </button>
        </div>
        {user && (
          <div className="drawer-user-info">
            <i className="bi bi-person-circle"></i>
            <div>
              <div className="user-name">{user.displayName}</div>
              <div className="user-role-text">{user.role}</div>
            </div>
          </div>
        )}
        <nav className="drawer-nav" role="menu">
          {visibleSections.map((section) => (
            <button
              key={section.id}
              role="menuitem"
              className={`drawer-nav-item ${activeSection === section.id ? 'active' : ''}`}
              onClick={() => handleNavigate(section.path)}
              aria-current={activeSection === section.id ? 'page' : undefined}
            >
              <i className={`bi ${section.icon}`}></i>
              <span>{section.label}</span>
            </button>
          ))}
        </nav>
      </aside>

      <div className="app-body">
        <aside className="sidebar-desktop d-none d-md-block" role="navigation" aria-label="Menú lateral">
          <DesktopNavMenu
            sections={visibleSections}
            activeSection={activeSection}
            onNavigate={handleNavigate}
          />
        </aside>

        <main id="main-content" className="main-content" role="main" tabIndex={-1}>
          {children}
        </main>
      </div>

      {bottomNavItems.length > 0 && (
        <nav className="bottom-nav d-md-none" role="navigation" aria-label="Navegación inferior">
          {bottomNavItems.map((item) => (
            <button
              key={item.id}
              className={`bottom-nav-item ${activeSection === item.id ? 'active' : ''}`}
              onClick={() => handleNavigate(item.path)}
              aria-current={activeSection === item.id ? 'page' : undefined}
            >
              <i className={`bi ${item.icon}`}></i>
              <span>{item.label}</span>
            </button>
          ))}
          <button
            className="bottom-nav-item more-btn"
            onClick={toggleDrawer}
            aria-label="Más opciones"
          >
            <i className="bi bi-grid"></i>
            <span>Más</span>
          </button>
        </nav>
      )}
    </div>
  );
});

Layout.displayName = 'Layout';
