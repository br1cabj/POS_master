import React from 'react';

export const StatCard = ({ title, value, sub, accent = 'accent' }) => (
  <div className={`stat-card ${accent}`}>
    <div className="font-label-muted">{title}</div>
    <div className={`font-stat mt-1 text-${accent === 'green' ? 'success' : accent === 'orange' ? 'warning' : accent === 'red' ? 'danger' : 'primary'}`}>
      {value}
    </div>
    {sub && <div className="font-small text-muted mt-1">{sub}</div>}
  </div>
);

export const Badge = ({ text, color = 'accent' }) => (
  <span className={`badge-cloudpos badge-${color}`}>{text}</span>
);

export const Loading = ({ message = 'Cargando...' }) => (
  <div className="d-flex flex-column align-items-center justify-content-center py-5">
    <div className="spinner-border text-primary" role="status">
      <span className="visually-hidden">{message}</span>
    </div>
    <span className="font-small text-muted mt-2">{message}</span>
  </div>
);

export const EmptyState = ({ message = 'Sin datos disponibles', icon = 'bi-inbox' }) => (
  <div className="d-flex flex-column align-items-center justify-content-center py-5 text-center">
    <i className={`bi ${icon} fs-1 text-muted mb-2`}></i>
    <p className="font-body text-muted mb-0">{message}</p>
  </div>
);

export const ErrorState = ({ message, onRetry }) => (
  <div className="d-flex flex-column align-items-center justify-content-center py-5 text-center">
    <i className="bi bi-exclamation-triangle fs-1 text-danger mb-2"></i>
    <p className="font-body text-danger mb-2">{message}</p>
    {onRetry && (
      <button className="btn btn-cloudpos-ghost btn-sm" onClick={onRetry}>
        <i className="bi bi-arrow-clockwise me-1"></i> Reintentar
      </button>
    )}
  </div>
);
