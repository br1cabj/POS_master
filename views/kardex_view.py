from tkinter import ttk

import customtkinter as ctk

from core.base_view import BaseView
from core.context import AppContext
from controllers.inventory_controller import InventoryController
from utils.styles import (
    ACCENT, ACCENT_DIM, ACCENT_TEXT, BORDER, GREEN_TEXT, ORANGE_TEXT,
    RED_TEXT, SURFACE1, SURFACE2, SURFACE3,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    apply_treeview_style,
)


class KardexView(BaseView):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, ctx)
        self.controller = InventoryController(ctx.db_engine)
        self.current_page = 1

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        apply_treeview_style()

        # ── Header ────────────────────────────────────────────────────────
        header_frame = ctk.CTkFrame(self, fg_color='transparent')
        header_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='ew')

        ctk.CTkLabel(
            header_frame,
            text='📊  Kardex: Auditoría de Inventario',
            font=('Arial', 22, 'bold'), text_color=TEXT_PRIMARY, anchor='w',
        ).pack(side='left')

        controls_frame = ctk.CTkFrame(header_frame, fg_color='transparent')
        controls_frame.pack(side='right')

        self.btn_prev = ctk.CTkButton(
            controls_frame, text='◀  Anterior', width=90,
            fg_color=SURFACE2, hover_color=SURFACE3, text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER, height=34, corner_radius=8,
            command=self.prev_page,
        )
        self.btn_prev.pack(side='left', padx=4)

        self.lbl_page = ctk.CTkLabel(
            controls_frame, text=f'Página {self.current_page}',
            font=('Arial', 13, 'bold'), text_color=TEXT_PRIMARY,
        )
        self.lbl_page.pack(side='left', padx=10)

        self.btn_next = ctk.CTkButton(
            controls_frame, text='Siguiente  ▶', width=90,
            fg_color=SURFACE2, hover_color=SURFACE3, text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER, height=34, corner_radius=8,
            command=self.next_page,
        )
        self.btn_next.pack(side='left', padx=4)

        self.btn_refresh = ctk.CTkButton(
            controls_frame, text='↻  Actualizar', width=110,
            fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=ACCENT_TEXT,
            border_width=1, border_color=ACCENT, height=34, corner_radius=8,
            command=self.refresh_data,
        )
        self.btn_refresh.pack(side='left', padx=(12, 0))

        # ── Tabla ─────────────────────────────────────────────────────────
        self.table_frame = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.table_frame.grid(row=1, column=0, sticky='nsew', padx=20, pady=(0, 20))

        inner = ctk.CTkFrame(self.table_frame, fg_color='transparent')
        inner.pack(fill='both', expand=True, padx=12, pady=12)

        self.tree_scroll = ttk.Scrollbar(inner, orient='vertical')

        columns = ('Fecha', 'Tipo', 'Producto', 'Cantidad', 'Referencia', 'Usuario')
        self.tree = ttk.Treeview(
            inner, columns=columns, show='headings',
            yscrollcommand=self.tree_scroll.set,
        )
        self.tree_scroll.configure(command=self.tree.yview)

        for col in columns:
            self.tree.heading(col, text=col)
            if col in ['Producto', 'Referencia']:
                self.tree.column(col, anchor='center', width=200)
            else:
                self.tree.column(col, anchor='center', width=100)

        self.tree_scroll.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)

        self.tree.tag_configure('entrada', foreground=GREEN_TEXT)
        self.tree.tag_configure('salida', foreground=RED_TEXT)
        self.tree.tag_configure('ajuste', foreground=ORANGE_TEXT)

        self.after(100, self.load_data)

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def next_page(self):
        self.current_page += 1
        self.load_data()

    def refresh_data(self):
        self.current_page = 1
        self.load_data()

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.lbl_page.configure(text=f'Página {self.current_page}')
        tenant_id = self.ctx.tenant_id

        movements = self.controller.get_kardex(tenant_id, page=self.current_page, limit=100)

        if not movements and self.current_page > 1:
            self.btn_next.configure(state='disabled')
            return
        else:
            self.btn_next.configure(state='normal')

        self.btn_prev.configure(state='disabled' if self.current_page == 1 else 'normal')

        for mov in movements:
            raw_date = mov.get('date')
            date_str = (
                raw_date.strftime('%d/%m/%Y %H:%M')
                if hasattr(raw_date, 'strftime')
                else str(raw_date)
            )

            mov_type = mov.get('movement_type')
            if mov_type == 'in':
                tipo, tag = '🟢 ENTRADA', 'entrada'
            elif mov_type == 'out':
                tipo, tag = '🔴 SALIDA', 'salida'
            else:
                tipo, tag = '🟡 AJUSTE', 'ajuste'

            raw_qty = float(mov.get('quantity', 0))
            cantidad = f'{int(raw_qty)}' if raw_qty.is_integer() else f'{raw_qty:.4f}'

            item_id = self.tree.insert(
                '', 'end',
                values=(
                    date_str, tipo,
                    mov.get('article_name', 'Desconocido'),
                    cantidad,
                    mov.get('reference') or '-',
                    mov.get('user_name', 'Sistema').capitalize(),
                ),
            )
            self.tree.item(item_id, tags=(tag,))
