import csv
import os
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
        self._active_filter = 'all'

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)

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

        # ── Filtros rápidos ───────────────────────────────────────────────
        filter_row = ctk.CTkFrame(self, fg_color='transparent')
        filter_row.grid(row=2, column=0, sticky='ew', padx=20, pady=(0, 6))

        self._filter_btns = {}
        _filters = [
            ('all',   'Todos'),
            ('today', 'Hoy'),
            ('week',  'Esta Semana'),
            ('fiado', 'Solo Fiados'),
        ]
        for fkey, flabel in _filters:
            is_active = fkey == 'all'
            btn = ctk.CTkButton(
                filter_row,
                text=flabel,
                height=28,
                corner_radius=6,
                font=('Arial', 11, 'bold') if is_active else ('Arial', 11),
                fg_color=ACCENT_DIM if is_active else SURFACE2,
                hover_color=ACCENT if is_active else SURFACE3,
                text_color=ACCENT_TEXT if is_active else TEXT_SECONDARY,
                border_width=1,
                border_color=ACCENT if is_active else BORDER,
                command=lambda k=fkey: self._apply_filter(k),
            )
            btn.pack(side='left', padx=(0, 6))
            self._filter_btns[fkey] = btn

        ctk.CTkButton(
            filter_row, text='📄  Exportar CSV',
            height=28, corner_radius=6, font=('Arial', 11),
            fg_color=SURFACE2, hover_color=SURFACE3, text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER,
            command=self.export_csv,
        ).pack(side='right')

        # ── Tabla ─────────────────────────────────────────────────────────
        self.table_container = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.table_container.grid(
            row=3, column=0, sticky='nsew', padx=20, pady=(0, 4)
        )

        inner = ctk.CTkFrame(self.table_container, fg_color='transparent')
        inner.pack(fill='both', expand=True, padx=12, pady=12)

        self.tree_scroll = ttk.Scrollbar(inner, orient='vertical')

        columns = ('ID', 'Fecha', 'Cliente', 'Vendedor', 'Descuento', 'Total', 'Ganancia', 'Estado')
        self.tree = ttk.Treeview(
            inner, columns=columns, show='headings',
            yscrollcommand=self.tree_scroll.set,
        )
        self.tree_scroll.configure(command=self.tree.yview)

        _col_widths = {
            'ID': 50, 'Fecha': 130, 'Cliente': 150,
            'Vendedor': 100, 'Descuento': 85, 'Total': 90, 'Ganancia': 90, 'Estado': 100,
        }
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=_col_widths.get(col, 100), anchor='center')

        self.tree_scroll.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<Double-1>', self.open_details_popup)
        self.tree.tag_configure('fiado',      foreground='#fb923c')
        self.tree.tag_configure('pendiente',  foreground='#facc15')
        self.tree.tag_configure('completada', foreground='#4ade80')
        self.tree.tag_configure('odd',        background='#161616')
        self.tree.tag_configure('even',       background='#1a1a1a')
        self.tree.tag_configure('has_disc',   foreground='#fbbf24')  # descuento activo → fila naranja

        # ── Botón Ver Detalle ──────────────────────────────────────────────
        btn_row = ctk.CTkFrame(self, fg_color='transparent')
        btn_row.grid(row=4, column=0, sticky='ew', padx=20, pady=(0, 14))

        ctk.CTkButton(
            btn_row, text='🔍  Ver Detalle de Venta Seleccionada',
            height=34, corner_radius=8, font=('Arial', 12),
            fg_color=SURFACE2, hover_color=SURFACE3, text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER,
            command=lambda: self.open_details_popup(None),
        ).pack(side='left', padx=(0, 8))

        self.after(100, self.load_history)

    def _apply_filter(self, key: str):
        """Activa un filtro rápido y actualiza los botones."""
        self._active_filter = key
        for k, btn in self._filter_btns.items():
            active = k == key
            btn.configure(
                fg_color=ACCENT_DIM if active else SURFACE2,
                hover_color=ACCENT if active else SURFACE3,
                text_color=ACCENT_TEXT if active else TEXT_SECONDARY,
                border_color=ACCENT if active else BORDER,
                font=('Arial', 11, 'bold') if active else ('Arial', 11),
            )
        self._filter_tree()

    def _filter_tree(self, *args):
        """Filtra las ventas por búsqueda + filtro rápido activo."""
        from datetime import date, timedelta
        q = self._search_var.get().lower()
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        def _passes_quick_filter(s):
            if self._active_filter == 'all':
                return True
            raw_date = s.get('date')
            sale_date = raw_date.date() if hasattr(raw_date, 'date') else None
            if self._active_filter == 'today':
                return sale_date == today
            if self._active_filter == 'week':
                return sale_date is not None and sale_date >= week_start
            if self._active_filter == 'fiado':
                return s.get('payment_method') == 'fiado'
            return True

        matches = [
            s for s in self._all_sales
            if _passes_quick_filter(s) and (
                not q
                or q in (s.get('customer_name') or '').lower()
                or q in (s.get('user_name') or '').lower()
                or q in str(s.get('date') or '').lower()
            )
        ]

        for item in self.tree.get_children():
            self.tree.delete(item)

        for sale in matches:
            raw_date = sale.get('date')
            date_str = (
                raw_date.strftime('%Y-%m-%d %H:%M')
                if hasattr(raw_date, 'strftime')
                else str(raw_date)
            )
            total_amount    = float(sale.get('total_amount', 0.0))
            discount_amount = float(sale.get('discount_amount', 0.0))
            profit = float(sale.get('profit', 0.0))
            pm  = sale.get('payment_method', '') or ''
            pm2 = sale.get('payment_method_2', '') or ''
            status = sale.get('status', '') or ''
            if pm == 'fiado':
                estado_label = '💳 Fiado'
                row_color = 'fiado'
            elif status == 'pendiente':
                estado_label = '⏳ Pendiente'
                row_color = 'pendiente'
            elif pm2:
                estado_label = f'💰 Mixto'
                row_color = 'completada'
            else:
                estado_label = '✓ Efectivo' if pm == 'efectivo' else f'✓ {pm.capitalize()}'
                row_color = 'completada'

            disc_str = f'-${discount_amount:.2f}' if discount_amount > 0 else '—'
            row_idx  = len(self.tree.get_children())
            alt_tag  = 'odd' if row_idx % 2 == 0 else 'even'
            # Si hubo descuento, la fila entera toma color naranja para visibilidad
            tags = ('has_disc', alt_tag) if discount_amount > 0 else (row_color, alt_tag)
            self.tree.insert(
                '', 'end',
                values=(
                    sale.get('id'),
                    date_str,
                    sale.get('customer_name', 'Sin Cliente'),
                    sale.get('user_name', 'Desconocido'),
                    disc_str,
                    f'${total_amount:.2f}',
                    f'${profit:.2f}',
                    estado_label,
                ),
                tags=tags,
            )

        total = len(self._all_sales)
        shown = len(matches)
        if hasattr(self, 'lbl_count'):
            self.lbl_count.configure(
                text=f'{shown} de {total}' if q else f'{total} ventas'
            )

    def export_csv(self):
        """Exporta las ventas visibles a un CSV en el escritorio."""
        import tempfile, platform
        rows = []
        for iid in self.tree.get_children():
            rows.append(self.tree.item(iid, 'values'))
        if not rows:
            from CTkMessagebox import CTkMessagebox
            CTkMessagebox(title='Sin datos', message='No hay ventas para exportar.', icon='info')
            return
        try:
            desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
            if not os.path.isdir(desktop):
                desktop = os.path.expanduser('~')
            filepath = os.path.join(desktop, 'historial_ventas.csv')
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                w = csv.writer(f)
                w.writerow(['ID', 'Fecha', 'Cliente', 'Vendedor', 'Descuento', 'Total', 'Ganancia', 'Estado'])
                w.writerows(rows)
            from CTkMessagebox import CTkMessagebox
            CTkMessagebox(
                title='Exportado',
                message=f'Archivo guardado en:\n{filepath}',
                icon='check',
            )
        except Exception as e:
            from CTkMessagebox import CTkMessagebox
            CTkMessagebox(title='Error', message=f'No se pudo exportar: {e}', icon='cancel')

    def load_history(self):
        tenant_id = self.ctx.tenant_id
        self._all_sales = self.controller.get_history(tenant_id)
        self._filter_tree()

    def open_details_popup(self, event):
        selected_item = self.tree.selection()
        if not selected_item:
            from CTkMessagebox import CTkMessagebox
            CTkMessagebox(title='Selección', message='Seleccioná una venta de la tabla primero.', icon='info')
            return

        item_data = self.tree.item(selected_item)
        sale_id = item_data['values'][0]
        tenant_id = self.ctx.tenant_id
        result = self.controller.get_sale_details(tenant_id, sale_id)
        details          = result.get('items', []) if isinstance(result, dict) else result
        discount_amount  = result.get('discount_amount', 0.0) if isinstance(result, dict) else 0.0
        pay_method       = result.get('payment_method', '') if isinstance(result, dict) else ''
        pay_method_2     = result.get('payment_method_2', '') if isinstance(result, dict) else ''
        pay_amount_2     = result.get('amount_method_2', 0.0) if isinstance(result, dict) else 0.0
        sale_total       = result.get('total_amount', 0.0) if isinstance(result, dict) else 0.0

        popup = ctk.CTkToplevel(self)
        popup.title(f'Detalle Venta #{sale_id}')
        popup.geometry('560x420')
        popup.configure(fg_color=SURFACE1)
        popup.attributes('-topmost', True)

        ctk.CTkLabel(
            popup, text=f'Artículos de la Venta  #{sale_id}',
            font=('Arial', 16, 'bold'), text_color=TEXT_PRIMARY,
        ).pack(pady=(18, 10))

        textbox = ctk.CTkTextbox(
            popup, width=520, height=250,
            font=('Consolas', 12),
            fg_color=SURFACE2, text_color=TEXT_PRIMARY,
            border_color=BORDER, border_width=1,
        )
        textbox.pack(pady=(0, 6), padx=20)

        subtotal_items = 0.0
        text_content = ''
        for d in details:
            desc = d.get('description', 'Desconocido')
            raw_qty = float(d.get('quantity', 0))
            qty = f'{int(raw_qty)}' if raw_qty.is_integer() else f'{raw_qty:.2f}'
            price = float(d.get('unit_price', 0.0))
            subtotal = float(d.get('subtotal', 0.0))
            subtotal_items += subtotal
            text_content += f'• {desc[:20]:<20} | x{qty:<5} | ${price:<7.2f} | Sub: ${subtotal:.2f}\n'

        if discount_amount > 0:
            text_content += f'\n{"─" * 58}\n'
            text_content += f'  {"Subtotal:":<30} ${subtotal_items:.2f}\n'
            text_content += f'  {"Descuento aplicado:":<30}-${discount_amount:.2f}\n'
            text_content += f'  {"TOTAL COBRADO:":<30} ${subtotal_items - discount_amount:.2f}\n'

        if pay_method_2 and pay_amount_2 > 0:
            pay_amount_1 = sale_total - pay_amount_2
            text_content += f'\n{"─" * 58}\n'
            text_content += f'  {"Pago Mixto:":<30}\n'
            text_content += f'  {pay_method.capitalize():<30} ${pay_amount_1:.2f}\n'
            text_content += f'  {pay_method_2.capitalize():<30} ${pay_amount_2:.2f}\n'

        textbox.insert('0.0', text_content)
        textbox.configure(state='disabled')
