import math
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from core.base_view import BaseView
from core.context import AppContext
from controllers.article_controller import ArticleController
from utils.styles import (
    ACCENT, ACCENT_DIM, ACCENT_TEXT, BORDER, BORDER_ACTIVE,
    GREEN, GREEN_DIM, GREEN_TEXT, ORANGE, ORANGE_DIM, ORANGE_TEXT,
    SURFACE1, SURFACE2, SURFACE3, SURFACE4,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    apply_treeview_style,
)


class PriceUpdateView(BaseView):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, ctx)
        self.controller = ArticleController(ctx.db_engine)

        self.catalog = []
        self.simulation_results = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        apply_treeview_style()

        # ── Panel izquierdo: Controles de inflación ──────────────────────
        self.left_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)

        ctk.CTkLabel(
            self.left_panel, text='📈  Ajuste de Precios',
            font=('Arial', 17, 'bold'), text_color=TEXT_PRIMARY,
        ).pack(pady=(22, 16))

        ctk.CTkLabel(
            self.left_panel, text='1. FILTRAR POR PROVEEDOR',
            font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
        ).pack(padx=20, anchor='w')
        self.combo_supplier = ctk.CTkComboBox(
            self.left_panel, values=['Todos los proveedores'],
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
            button_color=SURFACE3, button_hover_color=SURFACE4,
            dropdown_fg_color=SURFACE2, dropdown_text_color=TEXT_PRIMARY,
        )
        self.combo_supplier.pack(pady=(2, 12), padx=20, fill='x')

        ctk.CTkLabel(
            self.left_panel, text='2. ¿QUÉ MODIFICAR?',
            font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
        ).pack(padx=20, anchor='w')
        self.combo_target = ctk.CTkComboBox(
            self.left_panel,
            values=['Costo y Venta', 'Solo Precio de Venta', 'Solo Costo'],
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
            button_color=SURFACE3, button_hover_color=SURFACE4,
            dropdown_fg_color=SURFACE2, dropdown_text_color=TEXT_PRIMARY,
        )
        self.combo_target.pack(pady=(2, 12), padx=20, fill='x')

        ctk.CTkLabel(
            self.left_panel, text='3. PORCENTAJE DE AUMENTO (%)',
            font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
        ).pack(padx=20, anchor='w')
        self.entry_percent = ctk.CTkEntry(
            self.left_panel, placeholder_text='Ej: 15  (para 15%)',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
        )
        self.entry_percent.pack(pady=(2, 14), padx=20, fill='x')

        self.check_round_var = ctk.BooleanVar(value=True)
        self.check_round = ctk.CTkCheckBox(
            self.left_panel,
            text='Redondear a números enteros',
            variable=self.check_round_var,
            text_color=TEXT_SECONDARY,
        )
        self.check_round.pack(pady=(0, 16), padx=20, anchor='w')

        self.btn_simulate = ctk.CTkButton(
            self.left_panel, text='🧮  SIMULAR AUMENTO',
            fg_color=ORANGE_DIM, hover_color=ORANGE, text_color=ORANGE_TEXT,
            border_width=1, border_color=ORANGE, height=40, corner_radius=8,
            command=self.simulate_prices,
        )
        self.btn_simulate.pack(pady=(0, 20), padx=20, fill='x')

        # ── Panel derecho: Vista previa ──────────────────────────────────
        self.right_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.right_panel.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=16)

        hdr = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        hdr.pack(fill='x', padx=16, pady=(16, 4))
        ctk.CTkLabel(
            hdr, text='Vista Previa de los Nuevos Precios',
            font=('Arial', 15, 'bold'), text_color=TEXT_PRIMARY, anchor='w',
        ).pack(side='left')

        ctk.CTkLabel(
            self.right_panel,
            text='Revisá la tabla antes de guardar. Nada se cambiará hasta confirmar.',
            font=('Arial', 10), text_color=TEXT_MUTED,
        ).pack(anchor='w', padx=16, pady=(0, 10))

        self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        self.table_container.pack(fill='both', expand=True, padx=14, pady=(0, 8))

        self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

        columns = (
            'Producto', 'Proveedor',
            'Costo Ant.', 'Costo NUEVO',
            'Venta Ant.', 'Venta NUEVA',
        )
        self.tree = ttk.Treeview(
            self.table_container, columns=columns, show='headings',
            height=15, yscrollcommand=self.tree_scroll.set,
        )
        self.tree_scroll.configure(command=self.tree.yview)

        for col in columns:
            self.tree.heading(col, text=col)
            width = 180 if col == 'Producto' else 90
            self.tree.column(
                col,
                anchor='center' if 'Costo' in col or 'Venta' in col else 'w',
                width=width,
            )

        self.tree_scroll.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)

        self.tree.tag_configure('simulated', background='#0d2818')

        self.btn_save = ctk.CTkButton(
            self.right_panel,
            text='💾  CONFIRMAR Y APLICAR A LA BASE DE DATOS',
            fg_color=GREEN_DIM, hover_color=GREEN, text_color=GREEN_TEXT,
            border_width=1, border_color=GREEN,
            height=52, font=('Arial', 14, 'bold'), corner_radius=8,
            state='disabled',
            command=self.apply_changes,
        )
        self.btn_save.pack(pady=(4, 16), padx=14, fill='x')

        self.suppliers_map = {}
        self.after(100, self.load_data)

    def load_data(self):
        tenant_id = self.ctx.tenant_id
        self.catalog = self.controller.get_all_variants(tenant_id)
        suppliers = self.controller.get_suppliers_for_combo(tenant_id)
        self.suppliers_map = {s['name']: s['id'] for s in suppliers}
        combo_vals = ['Todos los proveedores'] + list(self.suppliers_map.keys())
        self.combo_supplier.configure(values=combo_vals)

    def simulate_prices(self):
        percent_str = self.entry_percent.get().strip().replace(',', '.')
        try:
            percent = float(percent_str)
            if percent == 0:
                raise ValueError
        except ValueError:
            CTkMessagebox(
                title='Error', message='Ingresá un porcentaje válido (Ej: 15).', icon='cancel'
            )
            return

        supplier_filter = self.combo_supplier.get()
        target = self.combo_target.get()
        should_round = self.check_round_var.get()
        multiplier = 1 + (percent / 100)

        for item in self.tree.get_children():
            self.tree.delete(item)
        self.simulation_results = []

        for item in self.catalog:
            if (
                supplier_filter != 'Todos los proveedores'
                and item.get('supplier_name') != supplier_filter
            ):
                continue

            old_cost = float(item.get('cost_price', 0))
            old_selling = float(item.get('selling_price', 0))
            new_cost = old_cost
            new_selling = old_selling

            if target in ['Costo y Venta', 'Solo Costo']:
                new_cost = old_cost * multiplier
                if should_round:
                    new_cost = math.ceil(new_cost)

            if target in ['Costo y Venta', 'Solo Precio de Venta']:
                new_selling = old_selling * multiplier
                if should_round:
                    new_selling = math.ceil(new_selling)

            self.simulation_results.append({
                'variant_id': item['variant_id'],
                'new_cost': new_cost,
                'new_selling': new_selling,
            })

            row_id = self.tree.insert(
                '', 'end',
                values=(
                    item.get('name'),
                    item.get('supplier_name', '-'),
                    f'${old_cost:.2f}', f'${new_cost:.2f}',
                    f'${old_selling:.2f}', f'${new_selling:.2f}',
                ),
            )
            self.tree.item(row_id, tags=('simulated',))

        if self.simulation_results:
            self.btn_save.configure(state='normal')
        else:
            CTkMessagebox(
                title='Sin resultados',
                message='No se encontraron productos para ese proveedor.',
                icon='info',
            )

    def apply_changes(self):
        if not self.simulation_results:
            return

        msg = CTkMessagebox(
            title='¡ATENCIÓN!',
            message=f'Estás a punto de modificar {len(self.simulation_results)} productos de forma permanente.\n¿Deseás continuar?',
            icon='warning', option_1='Cancelar', option_2='Sí, Guardar Cambios',
        )

        if msg.get() == 'Sí, Guardar Cambios':
            tenant_id = self.ctx.tenant_id
            user_id = self.ctx.user_id
            success, message = self.controller.apply_bulk_price_changes(
                tenant_id, user_id, self.simulation_results
            )

            if success:
                self.show_success(message)
                self.btn_save.configure(state='disabled')
                for item in self.tree.get_children():
                    self.tree.delete(item)
                self.simulation_results = []
                self.entry_percent.delete(0, 'end')
                self.load_data()
            else:
                CTkMessagebox(title='Error', message=message, icon='cancel')
