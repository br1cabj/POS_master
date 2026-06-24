import { createContext, useContext, useState, useCallback } from 'react';

const RefreshContext = createContext(null);

export const useRefresh = () => {
  const ctx = useContext(RefreshContext);
  if (!ctx) throw new Error('useRefresh must be used within RefreshProvider');
  return ctx;
};

export const RefreshProvider = ({ children }) => {
  const [lastRefresh, setLastRefresh] = useState(Date.now());

  const markRefreshed = useCallback(() => {
    setLastRefresh(Date.now());
  }, []);

  return (
    <RefreshContext.Provider value={{ lastRefresh, markRefreshed }}>
      {children}
    </RefreshContext.Provider>
  );
};
