import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/lib/supabase.jsx';
import { useAuth } from '@/context/AuthContext.jsx';

const TABLES_WITH_SOFT_DELETE = new Set([
  'users', 'customers', 'suppliers', 'articles', 'article_variants',
]);

const TABLES_WITHOUT_TENANT_ID = new Set([
  'sale_details', 'purchase_details', 'purchase_return_items',
  'quotation_items', 'cash_movements', 'stocks', 'article_variants', 'combo_items'
]);

function buildQueryKey(table, options) {
  return ['supabase', table, JSON.stringify(options)];
}

async function fetchFromSupabase(table, options, tenantId) {
  const {
    select = '*',
    filter = null,
    order = null,
    limit = null,
    range = null,
    skipTenantFilter = false,
  } = options;

  let query = supabase.from(table).select(select);

  if (tenantId && !skipTenantFilter && !TABLES_WITHOUT_TENANT_ID.has(table)) {
    query = query.filter('tenant_id', 'eq', tenantId);
  }

  if (TABLES_WITH_SOFT_DELETE.has(table)) {
    query = query.filter('deleted_at', 'is', null);
  }

  if (filter && Array.isArray(filter) && filter.length > 0) {
    const filters = Array.isArray(filter[0]) ? filter : [filter];
    for (const [column, operator, value] of filters) {
      if (column && operator !== undefined && value !== undefined) {
        query = query.filter(column, operator, value);
      }
    }
  }

  if (order) {
    const { column, ascending = false } = order;
    query = query.order(column, { ascending });
  }

  if (limit) {
    query = query.limit(limit);
  }

  if (range && Array.isArray(range) && range.length === 2) {
    query = query.range(range[0], range[1]);
  }

  const { data, error } = await query;

  if (error) throw error;

  return data || [];
}

export function useSupabaseQuery(table, options = {}) {
  const { user } = useAuth();
  const tenantId = user?.tenantId;

  const {
    enabled = true,
    refreshInterval = 0,
    silent = false,
    ...queryOptions
  } = options;

  const queryKey = buildQueryKey(table, options);

  const result = useQuery({
    queryKey,
    queryFn: () => fetchFromSupabase(table, options, tenantId),
    enabled: enabled && !!tenantId,
    refetchInterval: refreshInterval > 0 ? refreshInterval : false,
    refetchIntervalInBackground: false,
    placeholderData: silent ? (previousData) => previousData : undefined,
    ...queryOptions,
  });

  return {
    data: result.data ?? [],
    loading: result.isLoading,
    error: result.error ? result.error.message : null,
    refetch: result.refetch,
    isFetching: result.isFetching,
  };
}

export function invalidateTable(queryClient, table) {
  queryClient.invalidateQueries({
    queryKey: ['supabase', table],
  });
}

export function invalidateAllTables(queryClient) {
  queryClient.invalidateQueries({
    queryKey: ['supabase'],
  });
}
