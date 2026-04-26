from decimal import Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from core.base_view import BaseView
from core.context import AppContext
from controllers.sales_controller import SalesController
from utils.styles import (
    ACCENT, ACCENT_DIM, ACCENT_TEXT, BORDER,
    GREEN, GREEN_TEXT, ORANGE, ORANGE_DIM, ORANGE_TEXT,
    RED, SURFACE1, SURFACE2, SURFACE3, SURFACE4,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
    FONT_HEADING, FONT_BODY, FONT_BODY_BOLD, FONT_LABEL_BOLD,
    apply_treeview_style,
)


class SalesView(BaseView):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, ctx)
        self.sales_ctrl = SalesController(ctx.db_engine)
        self.db_engine = ctx.db_engine
        self.cart = []

        self.grid_columnconfigure(0, weight=1)   # Búsqueda
        self.grid_columnconfigure(1, weight=2)   # Carrito
        self.grid_columnconfigure(2, weight=1)   # Touch
        self.grid_rowconfigure(0, weight=1)

        # Treeview style
        apply_treeview_style()
        ttk.Style().map('Treeview.Heading', background=[('active', SURFACE4)])

        # ── Paneles ───────────────────────────────────────────────────────
        self._build_left_panel()
        self._build_center_panel()
        self._build_right_panel()

        # Mapas y carga
        self.variant_map = {}
        self.customer_map = {}
        self.db_variants = []
        self.touch_buttons = []

        self.after(50, self.load_data)
        self.setup_shortcuts()

    # =========================================================
    # PANEL IZQUIERDO — Búsqueda y Venta Rápida
    # =========================================================
    def _build_left_panel(self):
        self.left_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(10, 5), pady=10)

        # Header
        hdr = ctk.CTkFrame(self.left_panel, fg_color='transparent')
        hdr.pack(fill='x', padx=14, pady=(14, 0))
        ctk.CTkLabel(
            hdr, text='Punto de Venta',
            font=('Arial', 15, 'bold'), text_color=TEXT_PRIMARY, anchor='w'
        ).pack(side='left')

        # Atajos rápidos label
        ctk.CTkLabel(
            self.left_panel,
            text='F6 → foco lector  ·  F5 → cobrar',
            font=('Arial', 9), text_color=TEXT_MUTED,
        ).pack(pady=(2, 10))

        # ── Sección escáner ───────────────────────────────────────────────
        self._section_title(self.left_panel, '⬛  Código de Barras')

        self.entry_barcode = ctk.CTkEntry(
            self.left_panel,
            placeholder_text='Escanear o escribir + Enter',
            fg_color=SURFACE3, border_color=BORDER, text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_MUTED,
            height=38, font=('Arial', 13),
        )
        self.entry_barcode.pack(fill='x', padx=14, pady=(4, 10))
        self.entry_barcode.bind('<Return>', self.add_by_barcode)

        # ── Sección búsqueda manual ───────────────────────────────────────
        self._section_title(self.left_panel, '🔍  Búsqueda Manual')

        self.products_combo = ctk.CTkComboBox(
            self.left_panel,
            fg_color=SURFACE3, border_color=BORDER,
            button_color=SURFACE4, button_hover_color=ACCENT,
            text_color=TEXT_PRIMARY,
        )
        self.products_combo.set('Cargando...')
        self.products_combo.pack(fill='x', padx=14, pady=(4, 6))

        qty_row = ctk.CTkFrame(self.left_panel, fg_color='transparent')
        qty_row.pack(fill='x', padx=14, pady=(0, 6))

        ctk.CTkLabel(
            qty_row, text='Cantidad:', font=('Arial', 11), text_color=TEXT_SECONDARY
        ).pack(side='left', padx=(0, 8))
        self.qty_entry = ctk.CTkEntry(
            qty_row, width=80,
            fg_color=SURFACE3, border_color=BORDER, text_color=TEXT_PRIMARY,
            height=32,
        )
        self.qty_entry.pack(side='left')
        self.qty_entry.insert(0, '1')

        self.btn_add = ctk.CTkButton(
            self.left_panel,
            text='+ Agregar al Carrito',
            fg_color=ACCENT_DIM, hover_color=ACCENT,
            text_color=ACCENT_TEXT, font=('Arial', 12, 'bold'),
            height=34, corner_radius=8,
            command=self.add_to_cart,
        )
        self.btn_add.pack(fill='x', padx=14, pady=(0, 12))

        # Divisor
        ctk.CTkFrame(self.left_panel, height=1, fg_color=BORDER).pack(fill='x', padx=14)

        # ── Venta Rápida ──────────────────────────────────────────────────
        self._section_title(self.left_panel, '⚡  Venta Libre (Sin Stock)')

        self.entry_fast_desc = ctk.CTkEntry(
            self.left_panel, placeholder_text='Descripción del producto',
            fg_color=SURFACE3, border_color=BORDER, text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_MUTED, height=34,
        )
        self.entry_fast_desc.pack(fill='x', padx=14, pady=(4, 5))

        fast_row = ctk.CTkFrame(self.left_panel, fg_color='transparent')
        fast_row.pack(fill='x', padx=14, pady=(0, 6))

        self.entry_fast_price = ctk.CTkEntry(
            fast_row, placeholder_text='Precio ($)',
            fg_color=SURFACE3, border_color=BORDER, text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_MUTED, height=32,
        )
        self.entry_fast_price.pack(side='left', fill='x', expand=True, padx=(0, 6))

        self.entry_fast_qty = ctk.CTkEntry(
            fast_row, placeholder_text='Cant.', width=60,
            fg_color=SURFACE3, border_color=BORDER, text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_MUTED, height=32,
        )
        self.entry_fast_qty.pack(side='left')
        self.entry_fast_qty.insert(0, '1')

        self.btn_add_fast = ctk.CTkButton(
            self.left_panel,
            text='⚡ Agregar Venta Libre',
            fg_color=SURFACE3, hover_color=SURFACE4,
            text_color=ORANGE_TEXT, font=('Arial', 12, 'bold'),
            border_width=1, border_color=ORANGE,
            height=34, corner_radius=8,
            command=self.add_fast_to_cart,
        )
        self.btn_add_fast.pack(fill='x', padx=14, pady=(0, 10))

        # Feedback
        self.lbl_msg = ctk.CTkLabel(
            self.left_panel, text='', font=('Arial', 11), text_color=GREEN_TEXT
        )
        self.lbl_msg.pack(pady=2)

    # =========================================================
    # PANEL CENTRAL — Carrito
    # =========================================================
    def _build_center_panel(self):
        self.center_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.center_panel.grid(row=0, column=1, sticky='nsew', padx=5, pady=10)

        # ── Header con cliente ────────────────────────────────────────────
        hdr = ctk.CTkFrame(self.center_panel, fg_color='transparent')
        hdr.pack(fill='x', padx=14, pady=(14, 8))

        ctk.CTkLabel(
            hdr, text='🛒  Carrito',
            font=('Arial', 15, 'bold'), text_color=TEXT_PRIMARY, anchor='w'
        ).pack(side='left')

        # Cliente en el header
        ctk.CTkLabel(
            hdr, text='Cliente:',
            font=('Arial', 11), text_color=TEXT_MUTED
        ).pack(side='left', padx=(20, 4))

        self.customers_combo = ctk.CTkComboBox(
            hdr, width=200,
            fg_color=SURFACE3, border_color=BORDER,
            button_color=SURFACE4, button_hover_color=ACCENT,
            text_color=TEXT_PRIMARY, height=30,
        )
        self.customers_combo.set('Cargando...')
        self.customers_combo.pack(side='left')

        # Botón vaciar
        ctk.CTkButton(
            hdr,
            text='✕ Vaciar',
            fg_color='transparent', hover_color=SURFACE3,
            text_color=TEXT_MUTED, font=('Arial', 11),
            width=70, height=28, corner_radius=6,
            command=self.clear_entire_cart,
        ).pack(side='right')

        # Divisor
        ctk.CTkFrame(self.center_panel, height=1, fg_color=BORDER).pack(fill='x', padx=14)

        # ── Banner caja cerrada (oculto por defecto) ───────────────────────
        self.banner_caja = ctk.CTkFrame(
            self.center_panel,
            fg_color=ORANGE_DIM,
            corner_radius=8,
            border_width=1,
            border_color=ORANGE,
        )
        ctk.CTkLabel(
            self.banner_caja,
            text='⚠  No hay caja abierta · Las ventas no podrán procesarse',
            font=('Arial', 11, 'bold'),
            text_color=ORANGE_TEXT,
        ).pack(pady=8, padx=12)
        # Se muestra dinámicamente en _check_cash_status()

        # ── Tabla ─────────────────────────────────────────────────────────
        table_wrap = ctk.CTkFrame(self.center_panel, fg_color='transparent')
        table_wrap.pack(fill='both', expand=True, padx=10, pady=8)

        self.tree_scroll = ttk.Scrollbar(table_wrap, orient='vertical')

        self.tree = ttk.Treeview(
            table_wrap,
            columns=('Artículo', 'Cant', 'Precio', 'Subtotal'),
            show='headings',
            yscrollcommand=self.tree_scroll.set,
        )
        self.tree_scroll.configure(command=self.tree.yview)

        self.tree.heading('Artículo', text='Artículo')
        self.tree.heading('Cant',     text='Cant')
        self.tree.heading('Precio',   text='Precio Unit.')
        self.tree.heading('Subtotal', text='Subtotal')

        self.tree.column('Artículo', width=220, anchor='w')
        self.tree.column('Cant',     width=55,  anchor='center')
        self.tree.column('Precio',   width=100, anchor='e')
        self.tree.column('Subtotal', width=100, anchor='e')

        self.tree_scroll.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)

        # ── Footer: quitar, total, cobrar ─────────────────────────────────
        footer = ctk.CTkFrame(self.center_panel, fg_color='transparent')
        footer.pack(fill='x', padx=12, pady=(4, 12))

        self.btn_remove = ctk.CTkButton(
            footer,
            text='🗑  Quitar Seleccionado',
            fg_color='transparent', hover_color=SURFACE3,
            text_color=TEXT_MUTED,
            border_width=1, border_color=BORDER,
            height=32, corner_radius=8, font=('Arial', 11),
            command=self.remove_from_cart,
        )
        self.btn_remove.pack(side='left')

        # Total grande + botón cobrar
        total_block = ctk.CTkFrame(
            self.center_panel, fg_color=SURFACE3, corner_radius=10
        )
        total_block.pack(fill='x', padx=12, pady=(0, 10))

        total_inner = ctk.CTkFrame(total_block, fg_color='transparent')
        total_inner.pack(fill='x', padx=14, pady=10)

        ctk.CTkLabel(
            total_inner, text='TOTAL',
            font=('Arial', 10, 'bold'), text_color=TEXT_MUTED, anchor='w'
        ).pack(anchor='w')

        self.lbl_total = ctk.CTkLabel(
            total_inner, text='$0',
            font=('Arial', 38, 'bold'), text_color=GREEN_TEXT, anchor='w'
        )
        self.lbl_total.pack(anchor='w')

        self.btn_pay = ctk.CTkButton(
            self.center_panel,
            text='💰  COBRAR  [F5]',
            fg_color=GREEN, hover_color='#15803d',
            text_color='#ffffff',
            height=52, corner_radius=10,
            font=('Arial', 18, 'bold'),
            cursor='hand2',
            command=self.process_sale,
        )
        self.btn_pay.pack(fill='x', padx=12, pady=(0, 12))

    # =========================================================
    # PANEL DERECHO — Accesos Rápidos
    # =========================================================
    def _build_right_panel(self):
        self.right_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.right_panel.grid(row=0, column=2, sticky='nsew', padx=(5, 10), pady=10)

        hdr = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        hdr.pack(fill='x', padx=14, pady=(14, 4))
        ctk.CTkLabel(
            hdr, text='Accesos Rápidos',
            font=('Arial', 13, 'bold'), text_color=TEXT_PRIMARY, anchor='w'
        ).pack(side='left')

        ctk.CTkLabel(
            self.right_panel,
            text='Combos y productos fijos',
            font=('Arial', 10), text_color=TEXT_MUTED,
        ).pack(pady=(0, 8))

        ctk.CTkFrame(self.right_panel, height=1, fg_color=BORDER).pack(fill='x', padx=14, pady=(0, 8))

        self.touch_scroll = ctk.CTkScrollableFrame(
            self.right_panel, fg_color='transparent',
            scrollbar_button_color=SURFACE3,
        )
        self.touch_scroll.pack(fill='both', expand=True, padx=8, pady=(0, 10))

    # =========================================================
    # HELPER
    # =========================================================
    def _section_title(self, parent, text: str):
        ctk.CTkLabel(
            parent,
            text=text,
            font=('Arial', 10, 'bold'),
            text_color=TEXT_MUTED,
            anchor='w',
        ).pack(fill='x', padx=14, pady=(10, 2))

    # =========================================================
    # AUXILIARES
    # =========================================================
    # =========================================================
    # CARGA DE DATOS
    # =========================================================
    def _check_cash_status(self):
        """Muestra u oculta el banner de caja cerrada."""
        try:
            from controllers.cash_controller import CashController
            ctrl = CashController(self.db_engine)
            session = ctrl.get_active_session(self.ctx.tenant_id, self.ctx.user_id)
            if session:
                self.banner_caja.pack_forget()
            else:
                self.banner_caja.pack(fill='x', padx=12, pady=(8, 0))
        except Exception:
            pass

    def load_data(self):
        tenant_id = self.ctx.tenant_id
        self.db_variants = self.sales_ctrl.get_articles_for_sale(tenant_id)

        self.variant_map = {v.get('name'): v for v in self.db_variants if v.get('name')}
        if self.variant_map:
            self.products_combo.configure(values=list(self.variant_map.keys()))
            self.products_combo.set('Seleccionar...')
        else:
            self.products_combo.configure(values=['Sin productos'])
            self.products_combo.set('Sin productos')

        customers = self.sales_ctrl.get_customers(tenant_id)
        self.customer_map = {c.get('name'): c for c in customers}
        if self.customer_map:
            self.customers_combo.configure(values=list(self.customer_map.keys()))
            self.customers_combo.set('Consumidor Final')
        else:
            self.customers_combo.configure(values=['Consumidor Final'])
            self.customers_combo.set('Consumidor Final')

        # Reconstruir touch buttons
        for w in self.touch_scroll.winfo_children():
            w.destroy()
        self.touch_buttons.clear()

        row, col = 0, 0
        for v in self.db_variants:
            if v.get('is_combo') or v.get('show_on_touch'):
                stock = Decimal(str(v.get('total_stock', 0)))
                price = Decimal(str(v.get('selling_price', 0)))
                name = v.get('name', 'Promo')
                is_disabled = stock <= 0

                btn = ctk.CTkButton(
                    self.touch_scroll,
                    text=f'{name}\n${price:.2f}',
                    fg_color=SURFACE3 if is_disabled else ACCENT_DIM,
                    hover_color=ACCENT if not is_disabled else SURFACE3,
                    text_color=TEXT_MUTED if is_disabled else ACCENT_TEXT,
                    state='disabled' if is_disabled else 'normal',
                    width=118, height=72,
                    font=('Arial', 11, 'bold'),
                    corner_radius=8,
                    border_width=1,
                    border_color=BORDER,
                    command=lambda var_id=v.get('variant_id'): self.add_from_touch(var_id),
                )
                btn.grid(row=row, column=col, padx=4, pady=4)
                self.touch_buttons.append({'variant_id': v.get('variant_id'), 'button': btn})

                col += 1
                if col > 1:
                    col = 0
                    row += 1

        if not self.touch_buttons:
            ctk.CTkLabel(
                self.touch_scroll,
                text='Sin combos\nasignados',
                font=('Arial', 11),
                text_color=TEXT_MUTED,
                justify='center',
            ).pack(pady=40)

        self.entry_barcode.focus()
        self._check_cash_status()

    # =========================================================
    # LÓGICA DEL CARRITO (sin cambios funcionales)
    # =========================================================
    def _get_qty_in_cart(self, variant_id):
        return sum(
            item.get('qty', 0) for item in self.cart if item.get('variant_id') == variant_id
        )

    def add_by_barcode(self, event=None):
        self.lbl_msg.configure(text='')
        raw_code = self.entry_barcode.get().strip()
        if not raw_code:
            return

        is_scale_barcode = False
        scale_price = Decimal('0.0')
        search_code = raw_code.lstrip('0') or '0'

        if len(raw_code) == 13 and raw_code.startswith('20'):
            plu_code = str(int(raw_code[2:7]))
            price_str = raw_code[7:12]
            scale_price = Decimal(price_str)
            search_code = plu_code
            is_scale_barcode = True

        found_variant = next(
            (v for v in self.db_variants if str(v.get('barcode')) == search_code), None
        )

        if not found_variant:
            CTkMessagebox(title='Error', message=f'Código no encontrado:\n{search_code}', icon='cancel')
            self.entry_barcode.delete(0, 'end')
            return

        variant_id = found_variant.get('variant_id')
        name = found_variant.get('name', 'Desconocido')
        unit_price = Decimal(str(found_variant.get('selling_price', 0.0)))
        total_stock = Decimal(str(found_variant.get('total_stock', 0)))

        if is_scale_barcode:
            if unit_price == 0:
                CTkMessagebox(title='Error', message='El producto de balanza tiene precio $0 en la base.', icon='cancel')
                return
            qty_to_add = scale_price / unit_price
            subtotal = scale_price
        else:
            qty_to_add = Decimal('1')
            subtotal = unit_price * qty_to_add

        current_cart_qty = Decimal(str(self._get_qty_in_cart(variant_id)))
        if (current_cart_qty + qty_to_add) > total_stock:
            CTkMessagebox(title='Stock Insuficiente',
                message=f'Llevas {current_cart_qty:.3f} en el carrito y solo hay {total_stock:.3f} disponibles.',
                icon='warning')
            self.entry_barcode.delete(0, 'end')
            return

        qty_visual = f'{int(qty_to_add)}' if qty_to_add % 1 == 0 else f'{qty_to_add:.3f}'
        item_id = self.tree.insert('', 'end',
            values=(name, qty_visual, f'${unit_price:.2f}', f'${subtotal:.2f}'))

        self.cart.append({'tree_id': item_id, 'variant_id': variant_id, 'desc': name,
                          'price': float(unit_price), 'qty': float(qty_to_add), 'subtotal': float(subtotal)})
        self.update_total()
        self.entry_barcode.delete(0, 'end')
        self.lbl_msg.configure(text=f'✓ Agregado: {name}', text_color=GREEN_TEXT)

    def add_from_touch(self, variant_id):
        found = next((v for v in self.db_variants if v['variant_id'] == variant_id), None)
        if not found:
            return

        qty_to_add = Decimal('1')
        total_stock = Decimal(str(found.get('total_stock', 0)))
        current_cart_qty = Decimal(str(self._get_qty_in_cart(variant_id)))

        if (current_cart_qty + qty_to_add) > total_stock:
            CTkMessagebox(title='Sin Stock', message='No hay stock suficiente.', icon='warning')
            return

        price = Decimal(str(found.get('selling_price', 0.0)))
        name = found.get('name')
        item_id = self.tree.insert('', 'end', values=(name, '1', f'${price:.2f}', f'${price:.2f}'))
        self.cart.append({'tree_id': item_id, 'variant_id': variant_id, 'desc': name,
                          'price': float(price), 'qty': 1.0, 'subtotal': float(price)})
        self.update_total()
        self.lbl_msg.configure(text=f'✓ Agregado: {name}', text_color=GREEN_TEXT)

    def add_to_cart(self):
        self.lbl_msg.configure(text='')
        desc = self.products_combo.get()
        qty_str = self.qty_entry.get().replace(',', '.')

        try:
            qty_to_add = Decimal(qty_str)
            if qty_to_add <= Decimal('0.0'):
                raise ValueError
        except (ValueError, InvalidOperation):
            CTkMessagebox(title='Error', message='Cantidad inválida.', icon='cancel')
            return

        if desc in self.variant_map:
            variant = self.variant_map[desc]
            variant_id = variant.get('variant_id')
            total_stock = Decimal(str(variant.get('total_stock', 0)))
            price = Decimal(str(variant.get('selling_price', 0.0)))
            current_cart_qty = Decimal(str(self._get_qty_in_cart(variant_id)))

            if (current_cart_qty + qty_to_add) > total_stock:
                CTkMessagebox(title='Stock Insuficiente',
                    message=f'Llevas {current_cart_qty} en el carrito y solo quedan {total_stock} disponibles.',
                    icon='warning')
                return

            subtotal = price * qty_to_add
            qty_visual = f'{int(qty_to_add)}' if qty_to_add % 1 == 0 else f'{qty_to_add:.3f}'
            item_id = self.tree.insert('', 'end',
                values=(desc, qty_visual, f'${price:.2f}', f'${subtotal:.2f}'))
            self.cart.append({'tree_id': item_id, 'variant_id': variant_id, 'desc': desc,
                               'price': float(price), 'qty': float(qty_to_add), 'subtotal': float(subtotal)})
            self.update_total()
            self.qty_entry.delete(0, 'end')
            self.qty_entry.insert(0, '1')

    def add_fast_to_cart(self):
        self.lbl_msg.configure(text='')
        desc = self.entry_fast_desc.get().strip()
        price_str = self.entry_fast_price.get().strip().replace(',', '.')
        qty_str = self.entry_fast_qty.get().strip().replace(',', '.')

        if not desc or not price_str or not qty_str:
            return

        try:
            price = Decimal(price_str)
            qty = Decimal(qty_str)
            if price < Decimal('0.0') or qty <= Decimal('0.0'):
                raise ValueError
        except (ValueError, InvalidOperation):
            CTkMessagebox(title='Datos Inválidos', message='Ingresá números válidos.', icon='cancel')
            return

        subtotal = price * qty
        visual_desc = f'*(Libre)* {desc}'
        qty_visual = f'{int(qty)}' if qty % 1 == 0 else f'{qty:.2f}'
        item_id = self.tree.insert('', 'end',
            values=(visual_desc, qty_visual, f'${price:.2f}', f'${subtotal:.2f}'))
        self.cart.append({'tree_id': item_id, 'variant_id': None, 'desc': visual_desc,
                           'price': float(price), 'qty': float(qty), 'subtotal': float(subtotal)})
        self.update_total()
        self.entry_fast_desc.delete(0, 'end')
        self.entry_fast_price.delete(0, 'end')
        self.entry_fast_qty.delete(0, 'end')
        self.entry_fast_qty.insert(0, '1')

    def remove_from_cart(self):
        self.lbl_msg.configure(text='')
        selected_item = self.tree.selection()
        if not selected_item:
            CTkMessagebox(title='Atención', message='Primero seleccioná un artículo.', icon='info')
            return

        if CTkMessagebox(title='Confirmar', message='¿Quitar este artículo del carrito?',
                         icon='question', option_1='No', option_2='Sí').get() == 'Sí':
            for item_id in selected_item:
                for i, item in enumerate(self.cart):
                    if item.get('tree_id') == item_id:
                        self.cart.pop(i)
                        break
                self.tree.delete(item_id)
            self.update_total()

    def update_total(self):
        total = sum((Decimal(str(item.get('subtotal', 0))) for item in self.cart), Decimal('0.0'))
        self.lbl_total.configure(text=f'${total:,.0f}')

    def clear_entire_cart(self):
        if not self.cart:
            return
        if CTkMessagebox(title='Anular Venta', message='¿Vaciar todo el carrito?',
                         icon='warning', option_1='No', option_2='Sí').get() == 'Sí':
            self.cart.clear()
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.update_total()
            self.lbl_msg.configure(text='Venta anulada.', text_color='#f87171')
            self.entry_barcode.focus()

    # =========================================================
    # POP-UP DE COBRO
    # =========================================================
    def process_sale(self):
        if not self.cart:
            CTkMessagebox(title='Carrito Vacío', message='Agregá productos antes de cobrar.', icon='warning')
            return

        self.current_total = sum(
            (Decimal(str(item.get('subtotal', 0))) for item in self.cart), Decimal('0.0')
        )
        self.customer_name = self.customers_combo.get()

        self.popup = ctk.CTkToplevel(self)
        self.popup.title('Cobrar Venta')
        self.popup.geometry('420x560')
        self.popup.configure(fg_color=SURFACE2)
        self.popup.attributes('-topmost', True)
        self.popup.grab_set()

        # Header
        ctk.CTkLabel(self.popup, text='Total a Cobrar',
                     font=('Arial', 13), text_color=TEXT_MUTED).pack(pady=(24, 0))
        ctk.CTkLabel(self.popup, text=f'${self.current_total:,.2f}',
                     font=('Arial', 40, 'bold'), text_color=GREEN_TEXT).pack(pady=(4, 0))

        if self.customer_name and self.customer_name != 'Consumidor Final':
            ctk.CTkLabel(
                self.popup,
                text=f'📋  Cliente: {self.customer_name}',
                font=('Arial', 12, 'bold'),
                text_color=ACCENT_TEXT,
            ).pack(pady=(4, 0))

        ctk.CTkFrame(self.popup, height=1, fg_color=BORDER).pack(fill='x', padx=24, pady=16)

        # Método de pago
        ctk.CTkLabel(self.popup, text='MÉTODO DE PAGO',
                     font=('Arial', 10, 'bold'), text_color=TEXT_MUTED).pack(padx=24, anchor='w')
        self.combo_payment = ctk.CTkComboBox(
            self.popup,
            values=['Efectivo', 'Tarjeta', 'Transferencia', 'QR Billetera'],
            fg_color=SURFACE3, border_color=BORDER,
            button_color=SURFACE4, button_hover_color=ACCENT,
            text_color=TEXT_PRIMARY, font=('Arial', 13),
            width=300, command=self._on_payment_change,
        )
        self.combo_payment.set('Efectivo')
        self.combo_payment.pack(pady=(6, 16), padx=24)

        # Importe abonado
        ctk.CTkLabel(self.popup, text='EL CLIENTE ABONA (efectivo)',
                     font=('Arial', 10, 'bold'), text_color=TEXT_MUTED).pack(padx=24, anchor='w')
        self.entry_paid = ctk.CTkEntry(
            self.popup, font=('Arial', 22), justify='center',
            fg_color=SURFACE3, border_color=BORDER, text_color=TEXT_PRIMARY,
            height=48, width=300,
        )
        self.entry_paid.pack(pady=(6, 0), padx=24)
        self.entry_paid.focus()
        self.entry_paid.bind('<KeyRelease>', self._calculate_change)

        self.lbl_change = ctk.CTkLabel(
            self.popup, text='Vuelto: $0.00',
            font=('Arial', 22, 'bold'), text_color=ACCENT_TEXT,
        )
        self.lbl_change.pack(pady=12)
        self.lbl_error_popup = ctk.CTkLabel(self.popup, text='', text_color='#f87171', font=('Arial', 12))
        self.lbl_error_popup.pack()

        # Botones
        ctk.CTkButton(
            self.popup, text='✅  CONFIRMAR COBRO',
            fg_color=GREEN, hover_color='#15803d', text_color='#fff',
            height=46, font=('Arial', 14, 'bold'), corner_radius=10,
            command=lambda: self._confirm_and_save(False),
        ).pack(fill='x', padx=24, pady=(12, 6))

        if self.customer_name != 'Consumidor Final':
            ctk.CTkButton(
                self.popup, text='📝  Anotar como Fiado',
                fg_color=SURFACE3, hover_color=SURFACE4,
                text_color=ORANGE_TEXT, font=('Arial', 13, 'bold'),
                border_width=1, border_color=ORANGE,
                height=40, corner_radius=10,
                command=lambda: self._confirm_and_save(True),
            ).pack(fill='x', padx=24, pady=(0, 6))

        ctk.CTkButton(
            self.popup, text='⬅  Volver / Agregar más',
            fg_color='transparent', hover_color=SURFACE3,
            text_color=TEXT_MUTED, font=('Arial', 12),
            height=36, corner_radius=8,
            command=self.popup.destroy,
        ).pack(fill='x', padx=24)

    def _on_payment_change(self, value=None):
        """Activa/desactiva entry_paid según si el pago es Efectivo."""
        is_cash = self.combo_payment.get() == 'Efectivo'
        self.entry_paid.configure(
            state='normal' if is_cash else 'disabled',
            fg_color=SURFACE3 if is_cash else SURFACE2,
        )
        self._calculate_change()

    def _calculate_change(self, event=None):
        if self.combo_payment.get() != 'Efectivo':
            self.lbl_change.configure(text='Sin vuelto', text_color=TEXT_MUTED)
            return
        paid_str = self.entry_paid.get().strip().replace(',', '.')
        if not paid_str:
            self.lbl_change.configure(text='Vuelto: $0.00', text_color=ACCENT_TEXT)
            return
        try:
            paid = Decimal(paid_str)
            change = paid - self.current_total
            if change < Decimal('0.0'):
                self.lbl_change.configure(text='⚠ Falta dinero', text_color='#f87171')
            else:
                self.lbl_change.configure(text=f'Vuelto: ${change:,.2f}', text_color=ACCENT_TEXT)
        except (ValueError, InvalidOperation):
            self.lbl_change.configure(text='Monto inválido', text_color='#f87171')

    def _confirm_and_save(self, is_fiado=False):
        payment_method = self.combo_payment.get()
        if not is_fiado and payment_method == 'Efectivo':
            try:
                paid_str = self.entry_paid.get().strip().replace(',', '.')
                paid = Decimal(paid_str) if paid_str else self.current_total
                if paid < self.current_total:
                    self.lbl_error_popup.configure(text='El pago es menor al total')
                    return
            except (ValueError, InvalidOperation):
                self.lbl_error_popup.configure(text='Monto inválido')
                return

        if hasattr(self, 'popup') and self.popup:
            self.popup.destroy()

        customer_id = None
        if self.customer_name in self.customer_map:
            customer_id = self.customer_map[self.customer_name].get('id')
        self.finalize_sale(customer_id, is_fiado, payment_method)

    def finalize_sale(self, customer_id, is_fiado, payment_method):
        tenant_id = self.ctx.tenant_id
        user_id = self.ctx.user_id
        success, msg = self.sales_ctrl.process_sale(
            tenant_id, user_id, self.cart, customer_id, is_fiado, payment_method
        )
        if success:
            CTkMessagebox(title='¡Venta registrada!', message=msg, icon='check')
            self.cart.clear()
            for item in self.tree.get_children():
                self.tree.delete(item)
            self.update_total()
            self.load_data()
            self.entry_barcode.focus()
        else:
            CTkMessagebox(title='Error', message=msg, icon='cancel')

    # =========================================================
    # ATAJOS DE TECLADO
    # =========================================================
    def setup_shortcuts(self):
        top = self.winfo_toplevel()
        top.bind('<F5>', lambda e: self.process_sale())
        top.bind('<F6>', lambda e: self.entry_barcode.focus())
        top.bind('<F7>', lambda e: self.entry_fast_desc.focus())
        top.bind('<Delete>', lambda e: self.remove_from_cart())
        top.bind('<Control-Delete>', lambda e: self.clear_entire_cart())

        # Limpiar atajos al destruir esta vista para evitar leaks
        self.bind('<Destroy>', lambda e: self.destroy_custom() if e.widget is self else None)

        # Los atajos se muestran en la barra inferior del dashboard

    def destroy_custom(self):
        top = self.winfo_toplevel()
        for key in ('<F5>', '<F6>', '<F7>', '<Delete>', '<Control-Delete>'):
            top.unbind(key)
