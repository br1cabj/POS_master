import React, { useState } from 'react';
import { useAuth } from '@/context/AuthContext.jsx';

export const Login = () => {
  const { login, error, loading } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!username.trim()) return;
    await login(username.trim(), password);
  };

  return (
    <div className="min-vh-100 d-flex align-items-center justify-content-center" style={{ backgroundColor: 'var(--base)' }}>
      <div className="cloudpos-card" style={{ width: '100%', maxWidth: '380px', padding: 'clamp(16px, 5vw, 32px)' }}>
        <div className="text-center mb-4">
          <span className="font-title" style={{ color: 'var(--accent-text)', fontSize: '24px' }}>
            CloudPOS
          </span>
          <p className="font-small text-muted mt-1 mb-0">Dashboard de consulta</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="mb-3">
            <label className="font-label-muted d-block mb-1">Usuario</label>
            <input
              type="text"
              className="form-control"
              style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--border)', color: 'var(--text-primary)', height: '42px' }}
              placeholder="Tu nombre de usuario"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoFocus
              autoComplete="username"
            />
          </div>

          <div className="mb-4">
            <label className="font-label-muted d-block mb-1">Contraseña</label>
            <input
              type="password"
              className="form-control"
              style={{ backgroundColor: 'var(--surface-1)', borderColor: 'var(--border)', color: 'var(--text-primary)', height: '42px' }}
              placeholder="Tu contraseña"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="mb-3 p-2" style={{ backgroundColor: 'var(--red-dim)', borderRadius: '6px', border: '1px solid var(--red)' }}>
              <span className="font-small" style={{ color: 'var(--red-text)' }}>{error}</span>
            </div>
          )}

          <button
            type="submit"
            className="btn w-100"
            style={{ backgroundColor: 'var(--accent)', color: 'var(--text-primary)', height: '42px', fontWeight: 'bold', borderRadius: '6px' }}
            disabled={loading || !username.trim()}
          >
            {loading ? (
              <span className="spinner-border spinner-border-sm me-1" role="status"></span>
            ) : null}
            Ingresar
          </button>
        </form>

        <p className="font-small text-muted text-center mt-3 mb-0">
          Acceso solo lectura a datos sincronizados
        </p>
      </div>
    </div>
  );
};
