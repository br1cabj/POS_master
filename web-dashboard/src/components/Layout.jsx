import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { sections } from '@/config/sections.js';
import { useRefresh } from '@/context/RefreshContext.jsx';

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

export const Layout = ({ children, theme, onThemeToggle, user, onLogout }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { lastRefresh } = useRefresh();
  const timeAgo = useTimeAgo(lastRefresh);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const mobileMenuRef = useRef(null);
  const hamburgerBtnRef = useRef(null);
  const firstMenuBtnRef = useRef(null);

  const activeSection = sections.find((s) => s.path === location.pathname)?.id || 'dashboard';

  const visibleSections = sections.filter((s) => {
    if (!s.roles || s.roles.length === 0) return true;
    return s.roles.includes(user?.role);
  });

  useEffect(() => {
    setMobileMenuOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (mobileMenuOpen && firstMenuBtnRef.current) {
      firstMenuBtnRef.current.focus();
    }
  }, [mobileMenuOpen]);

  const handleKeyDown = (e) => {
    if (e.key === 'Escape' && mobileMenuOpen) {
      setMobileMenuOpen(false);
      if (hamburgerBtnRef.current) hamburgerBtnRef.current.focus();
    }
  };

  useEffect(() => {
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [mobileMenuOpen]);

  const handleSectionClick = (path) => {
    navigate(path);
  };

  return (
    <div className="min-vh-100" style={{ backgroundColor: 'var(--base)' }}>
      <a
        href="#main-content"
        className="visually-hidden-focusable"
        style={{
          position: 'absolute',
          zIndex: 9999,
          top: '8px',
          left: '8px',
          backgroundColor: 'var(--accent)',
          color: '#fff',
          padding: '8px 12px',
          borderRadius: '6px',
          fontWeight: 'bold',
          fontSize: '12px',
          textDecoration: 'none',
        }}
      >
        Saltar al contenido
      </a>

      <nav className="navbar-cloudpos sticky-top" role="navigation" aria-label="Navegación principal">
        <div className="container-fluid px-3 py-2">
          <div className="d-flex align-items-center gap-2 gap-sm-3">
            <button
              ref={hamburgerBtnRef}
              className="btn btn-cloudpos-ghost d-md-none p-1"
              onClick={() => setMobileMenuOpen((open) => !open)}
              aria-label={mobileMenuOpen ? 'Cerrar menú' : 'Abrir menú'}
              aria-expanded={mobileMenuOpen}
              aria-controls="mobile-menu"
            >
              <i className="bi bi-list fs-5"></i>
            </button>
            <span className="font-title" style={{ color: 'var(--accent-text)' }}>
              CloudPOS
            </span>
            <span className="badge-cloudpos badge-accent d-none d-md-inline">SOLO LECTURA</span>
          </div>
          <div className="d-flex align-items-center gap-1 gap-sm-2">
            <span className="font-small text-muted d-none d-sm-inline">
              {new Date().toLocaleDateString('es-AR', { weekday: 'short', day: 'numeric', month: 'short' })}
            </span>
            <span className="font-small d-none d-lg-inline" style={{ color: 'var(--text-muted)' }} title="Última actualización de datos">
              <i className="bi bi-arrow-clockwise me-1"></i>
              {timeAgo}
            </span>
            {user && (
              <span className="font-small d-none d-md-inline" style={{ color: 'var(--accent-text)' }}>
                <i className="bi bi-person-circle me-1"></i>
                {user.displayName}
                <span className="text-muted ms-1">({user.role})</span>
              </span>
            )}
            <button
              className="btn btn-cloudpos-ghost"
              onClick={onThemeToggle}
              aria-label={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
              title={theme === 'dark' ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
            >
              <i className={`bi ${theme === 'dark' ? 'bi-sun' : 'bi-moon'}`}></i>
            </button>
            {user && (
              <button
                className="btn btn-cloudpos-ghost"
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

      {mobileMenuOpen && (
        <div
          id="mobile-menu"
          ref={mobileMenuRef}
          className="d-md-none"
          role="menu"
          style={{ backgroundColor: 'var(--surface-2)', borderBottom: '1px solid var(--border)', maxHeight: '70vh', overflowY: 'auto' }}
        >
          {user && (
            <div className="px-3 py-2" style={{ borderBottom: '1px solid var(--border)' }}>
              <span className="font-small" style={{ color: 'var(--accent-text)' }}>
                <i className="bi bi-person-circle me-1"></i>
                {user.displayName} ({user.role})
              </span>
            </div>
          )}
          <div className="d-flex flex-column gap-1 p-2">
            {visibleSections.map((section, idx) => (
              <button
                key={section.id}
                ref={idx === 0 ? firstMenuBtnRef : null}
                role="menuitem"
                className={`btn text-start ${activeSection === section.id ? 'nav-link-cloudpos active' : 'nav-link-cloudpos'}`}
                onClick={() => handleSectionClick(section.path)}
                aria-current={activeSection === section.id ? 'page' : undefined}
              >
                <i className={`bi ${section.icon} me-2`}></i>
                {section.label}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="container-fluid">
        <div className="row">
          <div
            className="col-md-2 d-none d-md-block p-3"
            style={{ borderRight: '1px solid var(--border)', minHeight: 'calc(100vh - 56px)' }}
            role="navigation"
            aria-label="Menú lateral"
          >
            <div className="d-flex flex-column gap-1">
              {visibleSections.map((section) => (
                <button
                  key={section.id}
                  className={`btn text-start ${activeSection === section.id ? 'nav-link-cloudpos active' : 'nav-link-cloudpos'}`}
                  onClick={() => handleSectionClick(section.path)}
                  aria-current={activeSection === section.id ? 'page' : undefined}
                >
                  <i className={`bi ${section.icon} me-2`}></i>
                  {section.label}
                </button>
              ))}
            </div>
          </div>

          <main id="main-content" className="col-md-10 p-3 p-md-4" role="main" tabIndex={-1}>
            {children}
          </main>
        </div>
      </div>
    </div>
  );
};
