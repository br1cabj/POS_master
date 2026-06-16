import { create } from 'zustand';

export const useUIStore = create((set) => ({
  lastRefresh: Date.now(),
  sidebarCollapsed: false,
  expandedRows: {},
  globalFilters: {},

  markRefreshed: () => set({ lastRefresh: Date.now() }),

  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),

  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

  toggleRow: (tableId, rowId) =>
    set((state) => ({
      expandedRows: {
        ...state.expandedRows,
        [tableId]: state.expandedRows[tableId] === rowId ? null : rowId,
      },
    })),

  clearExpandedRows: (tableId) =>
    set((state) => {
      const newRows = { ...state.expandedRows };
      delete newRows[tableId];
      return { expandedRows: newRows };
    }),

  setGlobalFilter: (key, value) =>
    set((state) => ({
      globalFilters: { ...state.globalFilters, [key]: value },
    })),

  clearGlobalFilters: () => set({ globalFilters: {} }),
}));
