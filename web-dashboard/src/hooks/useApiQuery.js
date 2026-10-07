import { useQuery } from '@tanstack/react-query';
import { fetchTable } from '@/lib/api.js';
import { useAuth } from '@/context/AuthContext.jsx';

function buildQueryKey(table, options, tenantId) {
  const { select = '*', filter = null, order = null, limit = null, range = null } = options;
  return ['api', table, tenantId, select, JSON.stringify(filter), order?.column ?? null,
    order?.ascending ?? false, limit, range ? JSON.stringify(range) : null];
}

export function useApiQuery(table, options = {}) {
  const { user } = useAuth();
  const { enabled = true, refreshInterval = 0, silent = false, ...queryOptions } = options;
  const result = useQuery({
    queryKey: buildQueryKey(table, options, user?.tenantId),
    queryFn: () => fetchTable(table, options),
    enabled: enabled && !!user?.tenantId,
    refetchInterval: refreshInterval > 0 ? refreshInterval : false,
    refetchIntervalInBackground: false,
    placeholderData: silent ? (previousData) => previousData : undefined,
    ...queryOptions,
  });
  return {
    data: result.data ?? [], loading: result.isLoading,
    error: result.error ? result.error.message : null,
    refetch: result.refetch, isFetching: result.isFetching,
  };
}

export function invalidateTable(queryClient, table) {
  queryClient.invalidateQueries({ queryKey: ['api', table] });
}

export function invalidateAllTables(queryClient) {
  queryClient.invalidateQueries({ queryKey: ['api'] });
}
