from tkinter import ttk

import customtkinter as ctk

from core.base_view import BaseView
from core.context import AppContext
from controllers.alerts_controller import AlertsController
from utils.styles import (
    ACCENT_DIM, ACCENT_TEXT, BORDER, ORANGE_TEXT,
    RED_TEXT, GREEN_TEXT, SURFACE1, SURFACE2, SURFACE3,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    apply_treeview_style,
)


class AlertsView(BaseView):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, ctx)
        self.controller = AlertsController(ctx.db_engine)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        apply_treeview_style()

        # ── Header ────────────────────────────────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color='transparent')
        header_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='ew')

        ctk.CTkLabel(
            header_frame,
            text='⚠️  Productos con Stock Crítico',
            font=('Arial', 22, 'bold'), text_color=ORANGE_TEXT, anchor='w',
        ).pack(side='left')

        self.lbl_count = ctk.CTkLabel(
            header_frame, text='Buscando...',
            font=('Arial', 13), text_color=TEXT_MUTED,
        )
        self.lbl_count.pack(side='right', padx=(0, 12))

        ctk.CTkButton(
            header_frame, text='↻  Actualizar',
            fg_color=SURFACE2, hover_color=SURFACE3, text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER,
            width=120, height=34, corner_radius=8,
            command=self.load_data,
        ).pack(side='right', padx=(0, 8))

        # ── Tabla ─────────────────────────────────────────────────────────
        self.table_frame = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.table_frame.grid(row=1, column=0, sticky='nsew', padx=20, pady=(0, 20))

        inner = ctk.CTkFrame(self.table_frame, fg_color='transparent')
        inner.pack(fill='both', expand=True, padx=12, pady=12)

        self.tree_scroll = ttk.Scrollbar(inner, orient='vertical')

        columns = ('Código', 'Producto', 'Stock Actual', 'Nivel de Alerta')
        self.tree = ttk.Treeview(
            inner, columns=columns, show='headings', height=20,
            yscrollcommand=self.tree_scroll.set,
        )
        self.tree_scroll.configure(command=self.tree.yview)

        for col in columns:
            self.tree.heading(col, text=col)
            width = 250 if col == 'Producto' else 120
            self.tree.column(col, anchor='center', width=width)

        self.tree_scroll.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)

        self.load_data()

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        tenant_id = self.ctx.tenant_id

        low_stock_items = self.controller.get_low_stock_variants(tenant_id, threshold=5)

        for item in low_stock_items:
            stock_actual = item.get('stock', 0)
            stock_format = (
                f'{int(stock_actual)}'
                if float(stock_actual).is_integer()
                else f'{float(stock_actual):.2f}'
            )
            alerta_nivel = item.get('threshold', 5)
            self.tree.insert(
                '', 'end',
                values=(
                    item.get('barcode', 'Sin código') or 'Sin código',
                    item.get('name', 'Desconocido'),
                    stock_format,
                    f'Menor o igual a {alerta_nivel}',
                ),
            )

        cantidad = len(low_stock_items)
        if cantidad == 0:
            self.lbl_count.configure(
                text='¡Todo excelente!  No hay alertas.', text_color=GREEN_TEXT
            )
        else:
            self.lbl_count.configure(
                text=f'{cantidad} artículos para reponer', text_color=RED_TEXT
            )
