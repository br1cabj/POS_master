import { createContext, useContext, useState, useEffect, useCallback } from 'react';
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
const USER_KEY = 'cloudpos_user';
const USER_SIG_KEY = 'cloudpos_user_sig';

function simpleHash(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return hash.toString(36);
}

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

function storeUser(userObj) {
  const serialized = JSON.stringify(userObj);
  const sig = simpleHash(serialized + navigator.userAgent);
  localStorage.setItem(USER_KEY, serialized);
  localStorage.setItem(USER_SIG_KEY, sig);
}

function loadUser() {
  try {
    const serialized = localStorage.getItem(USER_KEY);
    const sig = localStorage.getItem(USER_SIG_KEY);
    if (!serialized || !sig) return null;
    const expectedSig = simpleHash(serialized + navigator.userAgent);
    if (sig !== expectedSig) {
      localStorage.removeItem(USER_KEY);
      localStorage.removeItem(USER_SIG_KEY);
      return null;
    }
    const parsed = JSON.parse(serialized);
    if (parsed && parsed.id && parsed.username && parsed.role) {
      return parsed;
    }
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(USER_SIG_KEY);
    return null;
  } catch {
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(USER_SIG_KEY);
    return null;
  }
}

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const savedUser = loadUser();
    if (savedUser) {
      setUser(savedUser);
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
        .select('id, username, password_hash, recovery_pin_hash, display_name, role, tenant_id, is_active')
        .eq('username', username)
        .is('deleted_at', null)
        .limit(1);

      if (err) throw err;

      if (!users || users.length === 0) {
        bcrypt.compareSync(password, '$2b$10$dummydummydummydummydummydummydummydummydummydummydummyd');
        const newAttempts = getAttempts() + 1;
        setAttempts(newAttempts);
        if (isLockedOut()) {
          const remaining = lockoutRemainingMinutes();
          setError(`Credenciales incorrectas. Cuenta bloqueada por ${remaining} minuto${remaining !== 1 ? 's' : ''}.`);
        } else {
          setError(`Usuario o contraseña incorrectos. Intentos restantes: ${MAX_ATTEMPTS - newAttempts}`);
        }
        setLoading(false);
        return false;
      }

      const foundUser = users[0];

      const passwordMatch = bcrypt.compareSync(password, foundUser.password_hash);

      if (!passwordMatch) {
        const newAttempts = getAttempts() + 1;
        setAttempts(newAttempts);
        if (isLockedOut()) {
          const remaining = lockoutRemainingMinutes();
          setError(`Credenciales incorrectas. Cuenta bloqueada por ${remaining} minuto${remaining !== 1 ? 's' : ''}.`);
        } else {
          setError(`Usuario o contraseña incorrectos. Intentos restantes: ${MAX_ATTEMPTS - newAttempts}`);
        }
        setLoading(false);
        return false;
      }

      if (!foundUser.is_active) {
        setError('Usuario desactivado');
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
      storeUser(foundUserObj);
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
    localStorage.removeItem(USER_KEY);
    localStorage.removeItem(USER_SIG_KEY);
    resetAttempts();
  }, []);

  return (
    <AuthContext.Provider value={{ user, login, logout, loading, error }}>
      {children}
    </AuthContext.Provider>
  );
};
