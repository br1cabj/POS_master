"""
views/price_update_view.py
==========================
Vista para la actualización masiva de precios (Inflación/Descuentos).
"""

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.article_controller import ArticleController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
    ACCENT,
    ACCENT_DIM,
    ACCENT_TEXT,
    BORDER,
    BORDER_ACTIVE,
    FONT_HEADING,
    FONT_LABEL_BOLD,
    FONT_SMALL_BOLD,
    GREEN,
    GREEN_DIM,
    GREEN_TEXT,
    ORANGE,
    ORANGE_DIM,
    ORANGE_TEXT,
    SURFACE2,
    SURFACE3,
    SURFACE4,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    apply_treeview_style,
)

_PRESETS = ['+5', '+10', '+15', '+20', '-10']
_STEP_LABELS = ['① Configurar', '② Simular', '③ Aplicar']


class PriceUpdateView(BaseView):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, ctx)
        self.controller = ArticleController(ctx.db_engine)

        self.catalog = []
        self.simulation_results = []
        self._current_preview_data = []
        self._sim_is_stale = False

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        apply_treeview_style()

        self._build_left_panel()
        self._build_right_panel()

        self.winfo_toplevel().bind(
            '<Control-g>',
            lambda e: (
                self.apply_changes()
                if self.winfo_exists()
                and self.winfo_ismapped()
                and self.btn_save.cget('state') == 'normal'
                else None
            ),
        )

        self.suppliers_map = {}
        self.after(100, self.load_data)

    def destroy_custom(self):
        try:
            self.winfo_toplevel().unbind('<Control-g>')
        except Exception:
            pass

    # =========================================================
    # LEFT PANEL
    # =========================================================
    def _build_left_panel(self):
        self.left_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)

        # ── Indicador de pasos ────────────────────────────────
        step_bar = ctk.CTkFrame(self.left_panel, fg_color='transparent')
        step_bar.pack(fill='x', padx=16, pady=(18, 4))

        self._step_labels: list = []
        for i, label in enumerate(_STEP_LABELS):
            lbl = ctk.CTkLabel(
                step_bar,
                text=label,
                font=FONT_LABEL_BOLD,
                fg_color=SURFACE3,
                text_color=TEXT_MUTED,
                corner_radius=6,
                padx=10, pady=4,
            )
            lbl.pack(side='left', expand=True, fill='x', padx=(0 if i == 0 else 4, 0))
            self._step_labels.append(lbl)

        self._set_step(0)

        ctk.CTkLabel(
            self.left_panel, text='📈  Ajuste de Precios',
            font=('Arial', 17, 'bold'), text_color=TEXT_PRIMARY,
        ).pack(pady=(14, 10))

        # 1. Filtro Proveedor
        ctk.CTkLabel(
            self.left_panel, text='1. FILTRAR POR PROVEEDOR',
            font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
        ).pack(padx=20, anchor='w')

        self.combo_supplier = ctk.CTkComboBox(
            self.left_panel, values=['Todos los proveedores'],
            fg_color=SURFACE3, border_color=BORDER_ACTIVE, text_color=TEXT_PRIMARY,
            height=36, command=self._invalidate_simulation,
        )
        self.combo_supplier.pack(pady=(2, 12), padx=20, fill='x')
        self.combo_supplier.set('Todos los proveedores')

        # 2. Objetivo
        ctk.CTkLabel(
            self.left_panel, text='2. ¿QUÉ MODIFICAR?',
            font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
        ).pack(padx=20, anchor='w')

        self.combo_target = ctk.CTkComboBox(
            self.left_panel,
            values=['Costo y Venta', 'Solo Precio de Venta', 'Solo Costo'],
            fg_color=SURFACE3, border_color=BORDER_ACTIVE, text_color=TEXT_PRIMARY,
            height=36, command=self._invalidate_simulation,
        )
        self.combo_target.pack(pady=(2, 12), padx=20, fill='x')
        self.combo_target.set('Costo y Venta')

        # 3. Porcentaje
        ctk.CTkLabel(
            self.left_panel, text='3. PORCENTAJE  (+aumento / −descuento)',
            font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
        ).pack(padx=20, anchor='w')

        self.entry_percent = ctk.CTkEntry(
            self.left_panel, placeholder_text='Ej: 15  o  -10',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE, text_color=TEXT_PRIMARY,
            height=36,
        )
        self.entry_percent.pack(pady=(2, 6), padx=20, fill='x')
        self.entry_percent.bind('<KeyRelease>', self._invalidate_simulation)
        self.entry_percent.bind('<Return>', lambda e: self.simulate_prices())

        # Presets de porcentaje
        preset_row = ctk.CTkFrame(self.left_panel, fg_color='transparent')
        preset_row.pack(fill='x', padx=20, pady=(0, 12))
        for val in _PRESETS:
            is_neg = val.startswith('-')
            ctk.CTkButton(
                preset_row,
                text=f'{val}%',
                width=44, height=26,
                font=FONT_LABEL_BOLD,
                fg_color=ORANGE_DIM if is_neg else ACCENT_DIM,
                hover_color=SURFACE4,
                text_color=ORANGE_TEXT if is_neg else ACCENT_TEXT,
                corner_radius=6,
                command=lambda v=val: self._apply_preset(v),
            ).pack(side='left', padx=(0, 4))

        self.check_round_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            self.left_panel, text='Redondear a números enteros',
            variable=self.check_round_var,
            text_color=TEXT_SECONDARY,
            command=self._invalidate_simulation,
        ).pack(pady=(0, 16), padx=20, anchor='w')

        self.btn_simulate = ctk.CTkButton(
            self.left_panel,
            text='🧮  SIMULAR CAMBIO',
            fg_color=ORANGE_DIM, hover_color=ORANGE,
            text_color=ORANGE_TEXT,
            border_width=1, border_color=ORANGE,
            height=40, corner_radius=8,
            command=self.simulate_prices,
        )
        self.btn_simulate.pack(pady=(0, 20), padx=20, fill='x')

    def _apply_preset(self, val: str):
        self.entry_percent.delete(0, 'end')
        self.entry_percent.insert(0, val.lstrip('+'))
        self._invalidate_simulation()

    def _set_step(self, active: int):
        for i, lbl in enumerate(self._step_labels):
            if i == active:
                lbl.configure(fg_color=ACCENT_DIM, text_color=ACCENT_TEXT)
            elif i < active:
                lbl.configure(fg_color=GREEN_DIM, text_color=GREEN_TEXT)
            else:
                lbl.configure(fg_color=SURFACE3, text_color=TEXT_MUTED)

    # =========================================================
    # RIGHT PANEL
    # =========================================================
    def _build_right_panel(self):
        self.right_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER,
        )
        self.right_panel.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=16)

        hdr = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        hdr.pack(fill='x', padx=16, pady=(16, 4))
        ctk.CTkLabel(
            hdr, text='Vista Previa de los Nuevos Precios',
            font=('Arial', 15, 'bold'), text_color=TEXT_PRIMARY, anchor='w',
        ).pack(side='left')

        search_frame = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        search_frame.pack(fill='x', padx=14, pady=(0, 8))

        self.entry_preview_search = ctk.CTkEntry(
            search_frame,
            placeholder_text='🔍 Buscar producto en la simulación...',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE, text_color=TEXT_PRIMARY,
            height=34,
        )
        self.entry_preview_search.pack(side='left', fill='x', expand=True)
        self.entry_preview_search.bind('<KeyRelease>', self._filter_preview)

        self.lbl_preview_count = ctk.CTkLabel(
            search_frame, text='0 productos',
            font=FONT_SMALL_BOLD, text_color=TEXT_MUTED,
        )
        self.lbl_preview_count.pack(side='right', padx=(10, 0))

        # Contenedor de tabla + overlay de simulación desactualizada
        self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        self.table_container.pack(fill='both', expand=True, padx=14, pady=(0, 8))

        self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

        columns = (
            'Producto', 'Proveedor',
            'Costo Ant.', 'Costo NUEVO',
            'Venta Ant.', 'Venta NUEVA',
            'Impacto',
        )
        self.tree = ttk.Treeview(
            self.table_container, columns=columns,
            show='headings', height=15,
            yscrollcommand=self.tree_scroll.set,
        )
        self.tree_scroll.configure(command=self.tree.yview)

        for col in columns:
            self.tree.heading(col, text=col)
            width = 220 if col == 'Producto' else 80 if col == 'Impacto' else 90
            anchor = 'w' if col in ('Producto', 'Proveedor') else 'center'
            self.tree.column(col, anchor=anchor, width=width)

        self.tree_scroll.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)

        self.tree.tag_configure('increase', background='#14532d', foreground='white')
        self.tree.tag_configure('decrease', background='#4c1d1d', foreground='#fca5a5')
        self.tree.tag_configure('neutral',  background='#1e293b', foreground='#94a3b8')

        # Overlay para simulación desactualizada
        self._stale_overlay = ctk.CTkFrame(
            self.table_container,
            fg_color=SURFACE2,
            corner_radius=8,
            border_width=1,
            border_color=ORANGE,
        )
        ctk.CTkLabel(
            self._stale_overlay,
            text='⚠️  Los parámetros cambiaron\n\nPresioná  🧮 SIMULAR CAMBIO  para actualizar la vista previa',
            font=FONT_LABEL_BOLD,
            text_color=ORANGE_TEXT,
            justify='center',
        ).place(relx=0.5, rely=0.5, anchor='center')

        self.btn_save = ctk.CTkButton(
            self.right_panel,
            text='💾  CONFIRMAR Y APLICAR A TODOS (Ctrl+G)',
            fg_color=GREEN_DIM, hover_color=GREEN, text_color=GREEN_TEXT,
            border_width=1, border_color=GREEN,
            height=52, font=FONT_HEADING, corner_radius=8,
            state='disabled', command=self.apply_changes,
        )
        self.btn_save.pack(pady=(4, 16), padx=14, fill='x')

    def _show_stale_overlay(self):
        if not self._sim_is_stale:
            self._sim_is_stale = True
            self._stale_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _hide_stale_overlay(self):
        self._sim_is_stale = False
        self._stale_overlay.place_forget()

    # =========================================================
    # DATA
    # =========================================================
    def load_data(self):
        if not self.winfo_exists():
            return
        tenant_id = self.ctx.tenant_id
        current_supplier = self.combo_supplier.get()

        self.catalog = self.controller.get_all_variants(tenant_id)
        suppliers = self.controller.get_suppliers_for_combo(tenant_id)
        self.suppliers_map = {s['name']: s['id'] for s in suppliers}

        combo_vals = ['Todos los proveedores'] + list(self.suppliers_map.keys())
        self.combo_supplier.configure(values=combo_vals)
        # Preservar selección si el proveedor sigue existiendo
        self.combo_supplier.set(
            current_supplier if current_supplier in combo_vals else 'Todos los proveedores'
        )

    def _invalidate_simulation(self, event=None):
        if self.simulation_results or self.btn_save.cget('state') == 'normal':
            self.btn_save.configure(state='disabled')
            self._show_stale_overlay()
            self._set_step(0)

    def _filter_preview(self, event=None):
        query = self.entry_preview_search.get().lower().strip()

        for item in self.tree.get_children():
            self.tree.delete(item)

        count = 0
        for row in self._current_preview_data:
            if not query or query in row[0].lower() or query in row[1].lower():
                impacto = row[6]
                if impacto.startswith('+'):
                    tag = 'increase'
                elif impacto.startswith('-'):
                    tag = 'decrease'
                else:
                    tag = 'neutral'
                self.tree.insert('', 'end', values=row, tags=(tag,))
                count += 1

        total = len(self.simulation_results)
        if query:
            self.lbl_preview_count.configure(
                text=f'Mostrando {count} de {total}', text_color=TEXT_PRIMARY,
            )
        else:
            self.lbl_preview_count.configure(
                text=f'{total} productos listos para actualizar', text_color=GREEN_TEXT,
            )

    # =========================================================
    # SIMULATION
    # =========================================================
    def simulate_prices(self):
        percent_str = self.entry_percent.get().strip().replace(',', '.')
        try:
            percent = Decimal(percent_str)
            if percent == Decimal('0'):
                raise ValueError
        except (ValueError, InvalidOperation):
            CTkMessagebox(
                title='Error',
                message='Ingresá un porcentaje válido (Ej: 15 o -10).',
                icon='cancel',
            )
            return

        supplier_filter = self.combo_supplier.get()
        target = self.combo_target.get()
        should_round = self.check_round_var.get()
        multiplier = Decimal('1') + (percent / Decimal('100'))

        self.simulation_results = []
        self._current_preview_data = []

        def round_val(v: Decimal) -> Decimal:
            return v.quantize(
                Decimal('1') if should_round else Decimal('0.01'),
                rounding=ROUND_CEILING if (percent > 0 and should_round) else ROUND_HALF_UP,
            )

        base_articles = [item for item in self.catalog if not item.get('base_variant_id')]
        pack_articles = [item for item in self.catalog if item.get('base_variant_id')]
        updated_base_costs: dict = {}

        for item in base_articles:
            if (supplier_filter != 'Todos los proveedores'
                    and item.get('supplier_name') != supplier_filter):
                continue

            old_cost    = Decimal(str(item.get('cost_price') or '0'))
            old_selling = Decimal(str(item.get('selling_price') or '0'))

            new_cost    = round_val(old_cost * multiplier)    if target in ('Costo y Venta', 'Solo Costo')            else old_cost
            new_selling = round_val(old_selling * multiplier) if target in ('Costo y Venta', 'Solo Precio de Venta') else old_selling
            new_cost    = max(Decimal('0'), new_cost)
            new_selling = max(Decimal('0'), new_selling)

            updated_base_costs[item['variant_id']] = new_cost
            self.simulation_results.append({
                'variant_id': item['variant_id'],
                'new_cost': str(new_cost),
                'new_selling': str(new_selling),
            })
            self._prepare_visual_row(item, old_cost, new_cost, old_selling, new_selling, target)

        for item in pack_articles:
            if (supplier_filter != 'Todos los proveedores'
                    and item.get('supplier_name') != supplier_filter):
                continue

            base_id = item.get('base_variant_id')
            units   = Decimal(str(item.get('units_per_pack') or '1'))
            old_cost    = Decimal(str(item.get('cost_price') or '0'))
            old_selling = Decimal(str(item.get('selling_price') or '0'))

            new_selling = round_val(old_selling * multiplier) if target in ('Costo y Venta', 'Solo Precio de Venta') else old_selling
            if target in ('Costo y Venta', 'Solo Costo'):
                new_cost = (updated_base_costs[base_id] * units
                            if base_id in updated_base_costs
                            else round_val(old_cost * multiplier))
            else:
                new_cost = old_cost

            new_cost    = max(Decimal('0'), new_cost)
            new_selling = max(Decimal('0'), new_selling)

            self.simulation_results.append({
                'variant_id': item['variant_id'],
                'new_cost': str(new_cost),
                'new_selling': str(new_selling),
            })
            self._prepare_visual_row(item, old_cost, new_cost, old_selling, new_selling, target)

        self._hide_stale_overlay()

        if self.simulation_results:
            self._filter_preview()
            self.btn_save.configure(state='normal')
            self.btn_save.focus()
            self._set_step(2)
        else:
            self._filter_preview()
            self._set_step(0)
            CTkMessagebox(
                title='Sin resultados',
                message='No se encontraron productos para el filtro seleccionado.',
                icon='info',
            )

    def _prepare_visual_row(
        self, item, old_cost: Decimal, new_cost: Decimal,
        old_selling: Decimal, new_selling: Decimal, target: str,
    ):
        display_name = item.get('name', '')
        if item.get('pack_label'):
            display_name += f' ({item.get("pack_label")})'

        # Columnas de costo: ocultar si no aplica
        if target == 'Solo Precio de Venta':
            cost_old_str = '—'
            cost_new_str = '—'
        else:
            cost_old_str = f'${float(old_cost):,.2f}'
            cost_new_str = f'${float(new_cost):,.2f}'

        # Columnas de venta: ocultar si no aplica
        if target == 'Solo Costo':
            venta_old_str = '—'
            venta_new_str = '—'
        else:
            venta_old_str = f'${float(old_selling):,.2f}'
            venta_new_str = f'${float(new_selling):,.2f}'

        # Impacto: delta del precio que realmente cambió
        if target == 'Solo Costo':
            diff = new_cost - old_cost
        else:
            diff = new_selling - old_selling

        if diff > 0:
            impacto_str = f'+${float(diff):,.2f}'
        elif diff < 0:
            impacto_str = f'-${float(abs(diff)):,.2f}'
        else:
            impacto_str = '$0.00'

        self._current_preview_data.append((
            display_name,
            item.get('supplier_name', '-'),
            cost_old_str, cost_new_str,
            venta_old_str, venta_new_str,
            impacto_str,
        ))

    # =========================================================
    # APPLY
    # =========================================================
    def apply_changes(self):
        if not self.simulation_results:
            return

        total = len(self.simulation_results)
        msg = CTkMessagebox(
            title='¡ATENCIÓN!',
            message=f'Se actualizarán {total} productos en la base de datos de forma permanente.\n¿Deseás continuar?',
            icon='warning',
            option_1='Cancelar',
            option_2='Sí, Guardar Cambios',
        )

        if msg.get() != 'Sí, Guardar Cambios':
            return

        success, message = self.controller.apply_bulk_price_changes(
            self.ctx.tenant_id, self.ctx.user_id, self.simulation_results,
        )

        if success:
            self.show_toast(message, 'success')
            self.btn_save.configure(state='disabled')
            self.entry_preview_search.delete(0, 'end')
            self.entry_percent.delete(0, 'end')
            self.simulation_results = []
            self._current_preview_data = []
            self._filter_preview()
            self._set_step(0)
            self.load_data()
        else:
            self.show_toast(message, 'error')
