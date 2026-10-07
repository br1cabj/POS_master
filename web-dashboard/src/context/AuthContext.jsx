import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiRequest } from '@/lib/api.js';

const AuthContext = createContext(null);

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
};

const MAX_ATTEMPTS = 5;
const LOCKOUT_MINUTES = 5;
const ATTEMPTS_KEY = 'cloudpos_login_attempts';
const LAST_ATTEMPT_KEY = 'cloudpos_last_attempt_time';
const USER_KEY = 'cloudpos_user';
const SESSION_KEY = 'cloudpos_web_session';

function getAttempts() {
  const raw = localStorage.getItem(ATTEMPTS_KEY);
  return raw ? parseInt(raw, 10) || 0 : 0;
}

function setAttempts(count) {
  localStorage.setItem(ATTEMPTS_KEY, String(count));
  localStorage.setItem(LAST_ATTEMPT_KEY, String(Date.now()));
}

function resetAttempts() {
  localStorage.removeItem(ATTEMPTS_KEY);
  localStorage.removeItem(LAST_ATTEMPT_KEY);
}

function isLockedOut() {
  if (getAttempts() < MAX_ATTEMPTS) return false;
  const elapsed = (Date.now() - Number(localStorage.getItem(LAST_ATTEMPT_KEY) || 0)) / 60000;
  return elapsed < LOCKOUT_MINUTES;
}

function lockoutRemainingMinutes() {
  const elapsed = (Date.now() - Number(localStorage.getItem(LAST_ATTEMPT_KEY) || 0)) / 60000;
  return Math.max(1, Math.ceil(LOCKOUT_MINUTES - elapsed));
}

function normalizeUser(row) {
  if (!row?.id || !row?.username || !row?.tenant_id || !row?.role) return null;
  return {
    id: row.id,
    username: row.username,
    displayName: row.display_name || row.username,
    role: row.role,
    tenantId: row.tenant_id,
  };
}

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    const restoreSession = async () => {
      const token = localStorage.getItem(SESSION_KEY);
      if (!token) {
        if (!cancelled) setLoading(false);
        return;
      }
      try {
        const restoredUser = normalizeUser(await apiRequest('/auth/session'));
        if (!restoredUser) throw new Error('La sesión expiró');
        if (!cancelled) {
          setUser(restoredUser);
          localStorage.setItem(USER_KEY, JSON.stringify(restoredUser));
        }
      } catch {
        localStorage.removeItem(SESSION_KEY);
        localStorage.removeItem(USER_KEY);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    restoreSession();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (username, password, tenantId) => {
    setLoading(true);
    setError(null);
    if (isLockedOut()) {
      setError(`Demasiados intentos fallidos. Intente nuevamente en ${lockoutRemainingMinutes()} minuto(s).`);
      setLoading(false);
      return false;
    }
    try {
      const result = await apiRequest('/auth/login', {
        method: 'POST', authenticated: false,
        body: { username, password, tenant_id: tenantId },
      });
      const loggedUser = normalizeUser(result);
      if (!loggedUser || !result?.session_token) throw new Error('Credenciales o empresa incorrectas.');
      localStorage.setItem(SESSION_KEY, result.session_token);
      localStorage.setItem(USER_KEY, JSON.stringify(loggedUser));
      setUser(loggedUser);
      resetAttempts();
      return true;
    } catch (err) {
      const attempts = getAttempts() + 1;
      setAttempts(attempts);
      setError(attempts >= MAX_ATTEMPTS
        ? `Credenciales incorrectas. Cuenta bloqueada por ${lockoutRemainingMinutes()} minuto(s).`
        : (err.message || `Credenciales incorrectas. Intentos restantes: ${MAX_ATTEMPTS - attempts}`));
      return false;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    apiRequest('/auth/logout', { method: 'POST' }).catch(() => {});
    setUser(null);
    localStorage.removeItem(SESSION_KEY);
    localStorage.removeItem(USER_KEY);
    resetAttempts();
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, error }}>
      {children}
    </AuthContext.Provider>
  );
};
