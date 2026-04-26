from tkinter import ttk

import customtkinter as ctk

from core.base_view import BaseView
from core.context import AppContext
from controllers.sales_controller import SalesController
from utils.styles import (
    ACCENT, ACCENT_DIM, ACCENT_TEXT, BORDER, SURFACE1, SURFACE2, SURFACE3,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    apply_treeview_style,
)


class HistoryView(BaseView):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, ctx)
        self.controller = SalesController(ctx.db_engine)

        self._all_sales = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)

        apply_treeview_style()

        # ── Header ────────────────────────────────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color='transparent')
        header_frame.grid(row=0, column=0, sticky='ew', pady=(20, 6), padx=20)

        ctk.CTkLabel(
            header_frame,
            text='📊  Historial de Ventas y Ganancias',
            font=('Arial', 22, 'bold'), text_color=TEXT_PRIMARY, anchor='w',
        ).pack(side='left')

        ctk.CTkButton(
            header_frame, text='↻  Actualizar',
            fg_color=SURFACE2, hover_color=SURFACE3, text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER,
            width=120, height=34, corner_radius=8,
            command=self.load_history,
        ).pack(side='right')

        # ── Barra de búsqueda en tiempo real ──────────────────────────────
        search_row = ctk.CTkFrame(self, fg_color='transparent')
        search_row.grid(row=1, column=0, sticky='ew', padx=20, pady=(0, 8))

        self._search_var = ctk.StringVar()
        self._search_var.trace_add('write', self._filter_tree)
        ctk.CTkEntry(
            search_row,
            textvariable=self._search_var,
            placeholder_text='🔍 Buscar por cliente, vendedor o fecha...',
            fg_color=SURFACE2, border_color=BORDER,
            text_color=TEXT_PRIMARY, height=34,
        ).pack(side='left', fill='x', expand=True)

        self.lbl_count = ctk.CTkLabel(
            search_row, text='', font=('Arial', 10),
            text_color=TEXT_MUTED, width=110, anchor='e',
        )
        self.lbl_count.pack(side='right', padx=(8, 0))

        # ── Tabla ─────────────────────────────────────────────────────────
        self.table_container = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.table_container.grid(
            row=2, column=0, sticky='nsew', padx=20, pady=(0, 20)
        )

        inner = ctk.CTkFrame(self.table_container, fg_color='transparent')
        inner.pack(fill='both', expand=True, padx=12, pady=12)

        self.tree_scroll = ttk.Scrollbar(inner, orient='vertical')

        columns = ('ID', 'Fecha', 'Cliente', 'Vendedor', 'Total', 'Ganancia')
        self.tree = ttk.Treeview(
            inner, columns=columns, show='headings',
            yscrollcommand=self.tree_scroll.set,
        )
        self.tree_scroll.configure(command=self.tree.yview)

        for col in columns:
            self.tree.heading(col, text=col)
            width = 150 if col == 'Cliente' else 100
            self.tree.column(col, width=width, anchor='center')

        self.tree_scroll.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<Double-1>', self.open_details_popup)

        self.after(100, self.load_history)

    def _filter_tree(self, *args):
        """Filtra las ventas en tiempo real."""
        q = self._search_var.get().lower()
        matches = [
            s for s in self._all_sales
            if q in (s.get('customer_name') or '').lower()
            or q in (s.get('user_name') or '').lower()
            or q in str(s.get('date') or '').lower()
        ] if q else self._all_sales

        for item in self.tree.get_children():
            self.tree.delete(item)

        for sale in matches:
            raw_date = sale.get('date')
            date_str = (
                raw_date.strftime('%Y-%m-%d %H:%M')
                if hasattr(raw_date, 'strftime')
                else str(raw_date)
            )
            total_amount = float(sale.get('total_amount', 0.0))
            profit = float(sale.get('profit', 0.0))
            self.tree.insert(
                '', 'end',
                values=(
                    sale.get('id'),
                    date_str,
                    sale.get('customer_name', 'Sin Cliente'),
                    sale.get('user_name', 'Desconocido'),
                    f'${total_amount:.2f}',
                    f'${profit:.2f}',
                ),
            )

        total = len(self._all_sales)
        shown = len(matches)
        if hasattr(self, 'lbl_count'):
            self.lbl_count.configure(
                text=f'{shown} de {total}' if q else f'{total} ventas'
            )

    def load_history(self):
        tenant_id = self.ctx.tenant_id
        self._all_sales = self.controller.get_history(tenant_id)
        self._filter_tree()

    def open_details_popup(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            return

        item_data = self.tree.item(selected_item)
        sale_id = item_data['values'][0]
        tenant_id = self.ctx.tenant_id
        details = self.controller.get_sale_details(tenant_id, sale_id)

        popup = ctk.CTkToplevel(self)
        popup.title(f'Detalle Venta #{sale_id}')
        popup.geometry('560x380')
        popup.configure(fg_color=SURFACE1)
        popup.attributes('-topmost', True)

        ctk.CTkLabel(
            popup, text=f'Artículos de la Venta  #{sale_id}',
            font=('Arial', 16, 'bold'), text_color=TEXT_PRIMARY,
        ).pack(pady=(18, 10))

        textbox = ctk.CTkTextbox(
            popup, width=520, height=270,
            font=('Consolas', 12),
            fg_color=SURFACE2, text_color=TEXT_PRIMARY,
            border_color=BORDER, border_width=1,
        )
        textbox.pack(pady=(0, 14), padx=20)

        text_content = ''
        for d in details:
            desc = d.get('description', 'Desconocido')
            raw_qty = float(d.get('quantity', 0))
            qty = f'{int(raw_qty)}' if raw_qty.is_integer() else f'{raw_qty:.2f}'
            price = float(d.get('unit_price', 0.0))
            subtotal = float(d.get('subtotal', 0.0))
            text_content += f'• {desc[:20]:<20} | x{qty:<5} | ${price:<7.2f} | Sub: ${subtotal:.2f}\n'

        textbox.insert('0.0', text_content)
        textbox.configure(state='disabled')
