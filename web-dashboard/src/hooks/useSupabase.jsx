import { useState, useEffect, useCallback, useRef } from 'react';
import { supabase } from '@/lib/supabase.jsx';
import { useAuth } from '@/context/AuthContext.jsx';
import { useRefresh } from '@/context/RefreshContext.jsx';

const TABLES_WITH_SOFT_DELETE = new Set([
  'users', 'customers', 'suppliers', 'articles', 'article_variants',
]);

const TABLES_WITHOUT_TENANT_ID = new Set([
  'sale_details', 'purchase_details', 'purchase_return_items',
  'quotation_items', 'cash_movements', 'stocks', 'article_variants', 'combo_items'
]);

function deepEqual(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

export function useSupabaseQuery(table, options = {}) {
  const { user } = useAuth();
  const { lastRefresh } = useRefresh();
  const tenantId = user?.tenantId;

  const {
    select = '*',
    filter = null,
    order = null,
    limit = null,
    range = null,
    enabled = true,
    skipTenantFilter = false,
    refreshInterval = 0,
    silent = false,
    onRefresh,
  } = options;

  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const isInitialLoad = useRef(true);
  const mountedRef = useRef(true);
  const abortControllerRef = useRef(null);
  const filterRef = useRef(filter);
  const rangeRef = useRef(range);

  useEffect(() => {
    if (!deepEqual(filterRef.current, filter)) {
      filterRef.current = filter;
    }
  }, [filter]);

  useEffect(() => {
    if (!deepEqual(rangeRef.current, range)) {
      rangeRef.current = range;
    }
  }, [range]);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const fetchData = useCallback(async (isSilent = false) => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    if (!isSilent || isInitialLoad.current) {
      setLoading(true);
    }
    setError(null);

    try {
      let query = supabase.from(table).select(select);

      if (tenantId && !skipTenantFilter && !TABLES_WITHOUT_TENANT_ID.has(table)) {
        query = query.filter('tenant_id', 'eq', tenantId);
      }

      if (TABLES_WITH_SOFT_DELETE.has(table)) {
        query = query.filter('deleted_at', 'is', null);
      }

      const currentFilter = filterRef.current;
      if (currentFilter && Array.isArray(currentFilter) && currentFilter.length > 0) {
        const filters = Array.isArray(currentFilter[0]) ? currentFilter : [currentFilter];
        filters.forEach(([column, operator, value]) => {
          if (column && operator !== undefined && value !== undefined) {
            query = query.filter(column, operator, value);
          }
        });
      }

      if (order) {
        const { column, ascending = false } = order;
        query = query.order(column, { ascending });
      }

      if (limit) {
        query = query.limit(limit);
      }

      const currentRange = rangeRef.current;
      if (currentRange && Array.isArray(currentRange) && currentRange.length === 2 && typeof currentRange[0] === 'number' && typeof currentRange[1] === 'number') {
        query = query.range(currentRange[0], currentRange[1]);
      }

      const { data: result, error: err } = await query;

      if (err) throw err;

      if (!mountedRef.current) return;

      setData(result || []);
      setLoading(false);
      isInitialLoad.current = false;

      if (onRefresh) onRefresh();
    } catch (err) {
      if (err.name === 'AbortError') return;
      if (!mountedRef.current) return;
      const message = err && typeof err === 'object' && err.message ? err.message : String(err);
      setError(message);
      setLoading(false);
      isInitialLoad.current = false;
    }
  }, [table, select, order?.column, order?.ascending, limit, enabled, tenantId, skipTenantFilter, onRefresh]);

  useEffect(() => {
    fetchData();
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [fetchData]);

  useEffect(() => {
    if (!refreshInterval || refreshInterval <= 0) return;
    const interval = setInterval(() => {
      fetchData(true);
    }, refreshInterval);
    return () => clearInterval(interval);
  }, [refreshInterval, fetchData]);

  useEffect(() => {
    if (lastRefresh && !isInitialLoad.current) {
      fetchData(true);
    }
  }, [lastRefresh]);

  return { data, loading, error, refetch: fetchData };
}
