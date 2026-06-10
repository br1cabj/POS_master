import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { supabase } from '@/lib/supabase.jsx';
import bcrypt from 'bcryptjs';

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

function getAttempts() {
  const raw = localStorage.getItem(ATTEMPTS_KEY);
  return raw ? parseInt(raw, 10) : 0;
}

function getLastAttemptTime() {
  const raw = localStorage.getItem(LAST_ATTEMPT_KEY);
  return raw ? parseInt(raw, 10) : 0;
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
  const attempts = getAttempts();
  if (attempts < MAX_ATTEMPTS) return false;
  const lastAttempt = getLastAttemptTime();
  const elapsed = (Date.now() - lastAttempt) / 1000 / 60;
  return elapsed < LOCKOUT_MINUTES;
}

function lockoutRemainingMinutes() {
  const lastAttempt = getLastAttemptTime();
  const elapsed = (Date.now() - lastAttempt) / 1000 / 60;
  return Math.ceil(LOCKOUT_MINUTES - elapsed);
}

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const saved = localStorage.getItem('cloudpos_user');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        if (parsed && parsed.id && parsed.username && parsed.role) {
          setUser(parsed);
        } else {
          localStorage.removeItem('cloudpos_user');
        }
      } catch {
        localStorage.removeItem('cloudpos_user');
      }
    }
    setLoading(false);
  }, []);

  const login = useCallback(async (username, password) => {
    setLoading(true);
    setError(null);

    if (isLockedOut()) {
      const remaining = lockoutRemainingMinutes();
      setError(`Demasiados intentos fallidos. Intente nuevamente en ${remaining} minuto${remaining !== 1 ? 's' : ''}.`);
      setLoading(false);
      return false;
    }

    try {
      const { data: users, error: err } = await supabase
        .from('users')
        .select('id, username, display_name, role, tenant_id, is_active, deleted_at, password_hash')
        .eq('username', username)
        .is('deleted_at', null)
        .limit(1);

      if (err) throw err;
      if (!users || users.length === 0) {
        setAttempts(getAttempts() + 1);
        setError('Usuario no encontrado');
        setLoading(false);
        return false;
      }

      const foundUser = users[0];

      if (!foundUser.is_active) {
        setAttempts(getAttempts() + 1);
        setError('Usuario desactivado');
        setLoading(false);
        return false;
      }

      if (!foundUser.password_hash) {
        setAttempts(getAttempts() + 1);
        setError('Error de autenticación');
        setLoading(false);
        return false;
      }

      const passwordVerified = await new Promise((resolve) => {
        try {
          bcrypt.compare(password, foundUser.password_hash, (err, result) => {
            if (err) resolve(false);
            else resolve(result);
          });
        } catch {
          resolve(false);
        }
      });

      if (!passwordVerified) {
        const newAttempts = getAttempts() + 1;
        setAttempts(newAttempts);
        if (isLockedOut()) {
          const remaining = lockoutRemainingMinutes();
          setError(`Contraseña incorrecta. Cuenta bloqueada por ${remaining} minuto${remaining !== 1 ? 's' : ''}.`);
        } else {
          setError(`Contraseña incorrecta. Intentos restantes: ${MAX_ATTEMPTS - newAttempts}`);
        }
        setLoading(false);
        return false;
      }

      const foundUserObj = {
        id: foundUser.id,
        username: foundUser.username,
        displayName: foundUser.display_name || foundUser.username,
        role: foundUser.role,
        tenantId: foundUser.tenant_id,
      };

      setUser(foundUserObj);
      localStorage.setItem('cloudpos_user', JSON.stringify(foundUserObj));
      resetAttempts();
      setLoading(false);
      return true;
    } catch (err) {
      setAttempts(getAttempts() + 1);
      setError(err.message);
      setLoading(false);
      return false;
    }
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    localStorage.removeItem('cloudpos_user');
    resetAttempts();
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, error }}>
      {children}
    </AuthContext.Provider>
  );
};
