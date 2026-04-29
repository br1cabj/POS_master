"""
views/sales_view.py
====================
Módulo de Ventas (POS).
Optimizado para alto rendimiento en mostrador (atajos de teclado, lector de código de barras, sin confirmaciones innecesarias).
"""

from decimal import Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.sales_controller import SalesController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_HEADING,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	FONT_NAV,
	FONT_SMALL,
	FONT_SMALL_BOLD,
	FONT_SUBHEADING,
	FONT_TITLE,
	GREEN,
	GREEN_TEXT,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	RED,
	RED_DIM,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	apply_treeview_style,
)

_DISCOUNT_PRESETS = [5, 10, 15, 20]


class SalesView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.sales_ctrl = SalesController(ctx.db_engine)
		self.db_engine = ctx.db_engine
		self.cart = []

		self._discount_pct = Decimal('0')
		self._discount_amount = Decimal('0')
		self._preset_btns: list = []

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_columnconfigure(2, weight=1)
		self.grid_rowconfigure(0, weight=1)

		apply_treeview_style()
		ttk.Style().map('Treeview.Heading', background=[('active', SURFACE4)])
		# Aumentamos tamaño de fuente en la grilla para mejor legibilidad
		ttk.Style().configure('Treeview', font=FONT_SMALL)

		self._build_left_panel()
		self._build_center_panel()
		self._build_right_panel()

		self.customer_map = {}
		self.db_variants = []
		self.touch_buttons = []
		self._barcode_timer = None

		self.after(50, self.load_data)
		self.setup_shortcuts()

	# =========================================================
	# PANEL IZQUIERDO — Búsqueda y Venta Rápida
	# =========================================================
	def _build_left_panel(self):
		self.left_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(10, 5), pady=10)

		hdr = ctk.CTkFrame(self.left_panel, fg_color='transparent')
		hdr.pack(fill='x', padx=14, pady=(14, 0))
		ctk.CTkLabel(
			hdr,
			text='Punto de Venta',
			font=('Arial', 15, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		ctk.CTkLabel(
			self.left_panel,
			text='F6 → foco lector  ·  F5 → cobrar',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(pady=(2, 10))

		# ── LECTOR DE CÓDIGO DE BARRAS ──────────────────────────────────────────
		self._section_title(self.left_panel, '⬛  Código de Barras')

		self.entry_barcode = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Escanear o escribir + Enter',
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			placeholder_text_color=TEXT_MUTED,
			height=38,
			font=FONT_NAV,
		)
		self.entry_barcode.pack(fill='x', padx=14, pady=(4, 10))
		self.entry_barcode.bind('<Return>', self._barcode_on_enter)
		self.entry_barcode.bind('<KeyRelease>', self._barcode_on_key)

		# ── BÚSQUEDA MANUAL OPTIMIZADA ──────────────────────────────────────────
		self._section_title(self.left_panel, '🔍  Búsqueda Manual')

		self.entry_manual_search = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Nombre del artículo + Enter',
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			placeholder_text_color=TEXT_MUTED,
			height=34,
		)
		self.entry_manual_search.pack(fill='x', padx=14, pady=(4, 6))
		self.entry_manual_search.bind('<Return>', self._manual_search_on_enter)

		qty_row = ctk.CTkFrame(self.left_panel, fg_color='transparent')
		qty_row.pack(fill='x', padx=14, pady=(0, 6))

		ctk.CTkLabel(
			qty_row, text='Cantidad:', font=FONT_SMALL, text_color=TEXT_SECONDARY
		).pack(side='left', padx=(0, 8))
		self.qty_entry = ctk.CTkEntry(
			qty_row,
			width=80,
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			height=32,
		)
		self.qty_entry.pack(side='left')
		self.qty_entry.insert(0, '1')
		self.qty_entry.bind('<Return>', self._manual_search_on_enter)

		self.btn_add = ctk.CTkButton(
			self.left_panel,
			text='+ Buscar / Agregar',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			font=FONT_BODY_BOLD,
			height=34,
			corner_radius=8,
			command=self._manual_search_on_enter,
		)
		self.btn_add.pack(fill='x', padx=14, pady=(0, 12))

		ctk.CTkFrame(self.left_panel, height=1, fg_color=BORDER).pack(fill='x', padx=14)

		# ── VENTA LIBRE CON FLUJO DE TECLADO ───────────────────────────────────
		self._section_title(self.left_panel, '⚡  Venta Libre (Sin Stock)')

		self.entry_fast_desc = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Descripción del producto',
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			placeholder_text_color=TEXT_MUTED,
			height=34,
		)
		self.entry_fast_desc.pack(fill='x', padx=14, pady=(4, 5))
		self.entry_fast_desc.bind('<Return>', lambda e: self.entry_fast_price.focus())

		fast_row = ctk.CTkFrame(self.left_panel, fg_color='transparent')
		fast_row.pack(fill='x', padx=14, pady=(0, 6))

		self.entry_fast_price = ctk.CTkEntry(
			fast_row,
			placeholder_text='Precio ($)',
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			placeholder_text_color=TEXT_MUTED,
			height=32,
		)
		self.entry_fast_price.pack(side='left', fill='x', expand=True, padx=(0, 6))
		self.entry_fast_price.bind('<Return>', lambda e: self.entry_fast_qty.focus())

		self.entry_fast_qty = ctk.CTkEntry(
			fast_row,
			placeholder_text='Cant.',
			width=60,
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			placeholder_text_color=TEXT_MUTED,
			height=32,
		)
		self.entry_fast_qty.pack(side='left')
		self.entry_fast_qty.insert(0, '1')
		self.entry_fast_qty.bind('<Return>', lambda e: self.add_fast_to_cart())

		self.btn_add_fast = ctk.CTkButton(
			self.left_panel,
			text='⚡ Agregar Venta Libre',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=ORANGE_TEXT,
			font=FONT_BODY_BOLD,
			border_width=1,
			border_color=ORANGE,
			height=34,
			corner_radius=8,
			command=self.add_fast_to_cart,
		)
		self.btn_add_fast.pack(fill='x', padx=14, pady=(0, 10))

		self.lbl_msg = ctk.CTkLabel(
			self.left_panel, text='', font=FONT_BODY_BOLD, text_color=GREEN_TEXT
		)
		self.lbl_msg.pack(pady=2)

	# =========================================================
	# PANEL CENTRAL — Carrito
	# =========================================================
	def _build_center_panel(self):
		self.center_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.center_panel.grid(row=0, column=1, sticky='nsew', padx=5, pady=10)

		# ── Header con cliente ────────────────────────────────────────────
		hdr = ctk.CTkFrame(self.center_panel, fg_color='transparent')
		hdr.pack(fill='x', padx=14, pady=(14, 8))

		ctk.CTkLabel(
			hdr,
			text='🛒  Carrito',
			font=('Arial', 15, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		ctk.CTkLabel(hdr, text='Cliente:', font=FONT_BODY, text_color=TEXT_MUTED).pack(
			side='left', padx=(20, 4)
		)

		self.customers_combo = ctk.CTkComboBox(
			hdr,
			width=200,
			fg_color=SURFACE3,
			border_color=BORDER,
			button_color=SURFACE4,
			button_hover_color=ACCENT,
			text_color=TEXT_PRIMARY,
			height=30,
		)
		self.customers_combo.set('Cargando...')
		self.customers_combo.pack(side='left')

		ctk.CTkButton(
			hdr,
			text='✕ Vaciar',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			font=FONT_BODY,
			width=70,
			height=28,
			corner_radius=6,
			command=self.clear_entire_cart,
		).pack(side='right')

		ctk.CTkFrame(self.center_panel, height=1, fg_color=BORDER).pack(
			fill='x', padx=14
		)

		# ── Banner caja cerrada ───────────────────────────────────────────
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
			font=FONT_BODY_BOLD,
			text_color=ORANGE_TEXT,
		).pack(pady=8, padx=12)

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
		self.tree.heading('Cant', text='Cant')
		self.tree.heading('Precio', text='Precio Unit.')
		self.tree.heading('Subtotal', text='Subtotal')

		self.tree.column('Artículo', width=220, anchor='w')
		self.tree.column('Cant', width=55, anchor='center')
		self.tree.column('Precio', width=100, anchor='e')
		self.tree.column('Subtotal', width=100, anchor='e')

		self.tree.tag_configure('odd', background=SURFACE2)
		self.tree.tag_configure('even', background=SURFACE3)
		self.tree.tag_configure('new_item', background='#14532d')

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		# ── Quitar seleccionado ───────────────────────────────────────────
		footer = ctk.CTkFrame(self.center_panel, fg_color='transparent')
		footer.pack(fill='x', padx=12, pady=(0, 6))

		self.btn_remove = ctk.CTkButton(
			footer,
			text='🗑  Quitar Seleccionado (Supr)',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			height=32,
			corner_radius=8,
			font=FONT_BODY,
			command=self.remove_from_cart,
		)
		self.btn_remove.pack(side='left')

		# ── Barra de descuento ────────────────────────────────────────────
		self._build_discount_bar()

		# ── Bloque de total ───────────────────────────────────────────────
		self._build_total_block()

		# ── Botón cobrar ──────────────────────────────────────────────────
		self.btn_pay = ctk.CTkButton(
			self.center_panel,
			text='💰  COBRAR  [F5]',
			fg_color=GREEN,
			hover_color='#15803d',
			text_color='#ffffff',
			height=56,
			corner_radius=10,
			font=('Arial', 20, 'bold'),
			cursor='hand2',
			command=self.process_sale,
		)
		self.btn_pay.pack(fill='x', padx=12, pady=(0, 12))

	def _build_discount_bar(self):
		bar = ctk.CTkFrame(
			self.center_panel,
			fg_color=SURFACE3,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		bar.pack(fill='x', padx=12, pady=(0, 6))

		inner = ctk.CTkFrame(bar, fg_color='transparent')
		inner.pack(fill='x', padx=10, pady=8)

		ctk.CTkLabel(
			inner,
			text='🏷  DESCUENTO',
			font=FONT_SMALL_BOLD,
			text_color=TEXT_MUTED,
		).pack(side='left', padx=(0, 8))

		self._preset_btns.clear()
		for pct in _DISCOUNT_PRESETS:
			btn = ctk.CTkButton(
				inner,
				text=f'{pct}%',
				width=42,
				height=28,
				font=FONT_BODY_BOLD,
				fg_color='transparent',
				hover_color=SURFACE4,
				text_color=TEXT_SECONDARY,
				border_width=1,
				border_color=BORDER,
				corner_radius=6,
				command=lambda p=pct: self._set_discount_pct(Decimal(str(p))),
			)
			btn.pack(side='left', padx=2)
			self._preset_btns.append((pct, btn))

		ctk.CTkFrame(inner, width=1, height=20, fg_color=BORDER).pack(
			side='left', padx=8
		)

		self._entry_custom_disc = ctk.CTkEntry(
			inner,
			width=60,
			height=28,
			font=FONT_BODY,
			fg_color=SURFACE2,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			placeholder_text='%',
			placeholder_text_color=TEXT_MUTED,
			justify='center',
		)
		self._entry_custom_disc.pack(side='left', padx=(0, 4))
		self._entry_custom_disc.bind('<Return>', self._apply_custom_discount)
		self._entry_custom_disc.bind('<FocusOut>', self._apply_custom_discount)

		ctk.CTkButton(
			inner,
			text='Aplicar',
			width=60,
			height=28,
			font=FONT_SMALL_BOLD,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			corner_radius=6,
			command=self._apply_custom_discount,
		).pack(side='left')

		self._btn_clear_disc = ctk.CTkButton(
			inner,
			text='× Sin desc.',
			width=80,
			height=28,
			font=FONT_SMALL,
			fg_color='transparent',
			hover_color=RED_DIM,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			corner_radius=6,
			command=lambda: self._set_discount_pct(Decimal('0')),
		)
		self._btn_clear_disc.pack(side='right')

	def _build_total_block(self):
		total_block = ctk.CTkFrame(
			self.center_panel,
			fg_color=SURFACE3,
			corner_radius=10,
		)
		total_block.pack(fill='x', padx=12, pady=(0, 6))

		inner = ctk.CTkFrame(total_block, fg_color='transparent')
		inner.pack(fill='x', padx=14, pady=(10, 4))

		sub_row = ctk.CTkFrame(inner, fg_color='transparent')
		sub_row.pack(fill='x')
		ctk.CTkLabel(
			sub_row,
			text='SUBTOTAL',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(side='left')
		self._lbl_subtotal = ctk.CTkLabel(
			sub_row, text='$0', font=FONT_SUBHEADING, text_color=TEXT_MUTED, anchor='e'
		)
		self._lbl_subtotal.pack(side='right')

		self._disc_row = ctk.CTkFrame(inner, fg_color='transparent')
		self._lbl_disc_label = ctk.CTkLabel(
			self._disc_row,
			text='',
			font=FONT_BODY_BOLD,
			text_color=RED_TEXT,
			anchor='w',
		)
		self._lbl_disc_label.pack(side='left')
		self._lbl_disc_value = ctk.CTkLabel(
			self._disc_row,
			text='',
			font=FONT_HEADING,
			text_color=RED_TEXT,
			anchor='e',
		)
		self._lbl_disc_value.pack(side='right')

		self._divider_total = ctk.CTkFrame(inner, height=1, fg_color=BORDER)

		ctk.CTkLabel(
			inner,
			text='TOTAL',
			font=FONT_BODY_BOLD,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', pady=(6, 0))

		self.lbl_total = ctk.CTkLabel(
			inner,
			text='$0',
			font=('Arial', 44, 'bold'),
			text_color=GREEN_TEXT,
			anchor='w',
		)
		self.lbl_total.pack(anchor='w')

	# =========================================================
	# PANEL DERECHO — Accesos Rápidos
	# =========================================================
	def _build_right_panel(self):
		self.right_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.right_panel.grid(row=0, column=2, sticky='nsew', padx=(5, 10), pady=10)

		hdr = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		hdr.pack(fill='x', padx=14, pady=(14, 4))
		ctk.CTkLabel(
			hdr,
			text='Accesos Rápidos',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		ctk.CTkLabel(
			self.right_panel,
			text='Combos y productos fijos',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
		).pack(pady=(0, 8))

		ctk.CTkFrame(self.right_panel, height=1, fg_color=BORDER).pack(
			fill='x', padx=14, pady=(0, 8)
		)

		self.touch_scroll = ctk.CTkScrollableFrame(
			self.right_panel,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
		)
		self.touch_scroll.pack(fill='both', expand=True, padx=8, pady=(0, 10))

	# =========================================================
	# DESCUENTO — Lógica y estado
	# =========================================================
	def _set_discount_pct(self, pct: Decimal):
		if pct < Decimal('0') or pct > Decimal('100'):
			return
		self._discount_pct = pct

		for preset_pct, btn in self._preset_btns:
			if pct > 0 and Decimal(str(preset_pct)) == pct:
				btn.configure(
					fg_color=ACCENT_DIM,
					text_color=ACCENT_TEXT,
					border_color=ACCENT,
				)
			else:
				btn.configure(
					fg_color='transparent',
					text_color=TEXT_SECONDARY,
					border_color=BORDER,
				)

		if pct in [Decimal(str(p)) for p in _DISCOUNT_PRESETS] or pct == 0:
			self._entry_custom_disc.delete(0, 'end')

		if pct == 0:
			self._btn_clear_disc.configure(text_color=TEXT_MUTED, border_color=BORDER)
		else:
			self._btn_clear_disc.configure(text_color=RED_TEXT, border_color=RED)

		self.update_total()

	def _apply_custom_discount(self, event=None):
		raw = self._entry_custom_disc.get().strip().replace(',', '.').replace('%', '')
		if not raw:
			return
		try:
			pct = Decimal(raw)
			if pct < 0 or pct > 100:
				raise ValueError
			self._set_discount_pct(pct)
		except (ValueError, InvalidOperation):
			self._entry_custom_disc.configure(border_color=RED)
			self.after(
				1200, lambda: self._entry_custom_disc.configure(border_color=BORDER)
			)

	# =========================================================
	# HELPER
	# =========================================================
	def _section_title(self, parent, text: str):
		wrapper = ctk.CTkFrame(parent, fg_color='transparent')
		wrapper.pack(fill='x', padx=14, pady=(12, 4))
		ctk.CTkFrame(wrapper, height=1, fg_color=BORDER).pack(fill='x', pady=(0, 5))
		ctk.CTkLabel(
			wrapper,
			text=text.upper(),
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w')

	def _set_msg(self, text: str, color: str = None):
		self.lbl_msg.configure(text=text, text_color=color or GREEN_TEXT)
		if hasattr(self, '_msg_after_id') and self._msg_after_id:
			try:
				self.after_cancel(self._msg_after_id)
			except Exception:
				pass
		self._msg_after_id = self.after(3000, lambda: self.lbl_msg.configure(text=''))

	# =========================================================
	# CARGA DE DATOS
	# =========================================================
	def _check_cash_status(self):
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

		customers = self.sales_ctrl.get_customers(tenant_id)
		self.customer_map = {c.get('name'): c for c in customers}
		if self.customer_map:
			self.customers_combo.configure(values=list(self.customer_map.keys()))
			self.customers_combo.set('Consumidor Final')
		else:
			self.customers_combo.configure(values=['Consumidor Final'])
			self.customers_combo.set('Consumidor Final')

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

				from utils.settings_manager import get as settings_get

				low_threshold = settings_get('low_stock_threshold', 5)
				stock_int = int(stock)
				if is_disabled:
					stock_label = 'Sin stock'
					stock_color = TEXT_MUTED
				elif stock_int <= low_threshold:
					stock_label = f'Stock: {stock_int}'
					stock_color = ORANGE_TEXT
				else:
					stock_label = f'Stock: {stock_int}'
					stock_color = TEXT_MUTED

				btn_frame = ctk.CTkFrame(
					self.touch_scroll,
					fg_color=SURFACE3 if is_disabled else ACCENT_DIM,
					corner_radius=8,
					border_width=1,
					border_color=BORDER,
					width=118,
					height=80,
				)
				btn_frame.grid(row=row, column=col, padx=4, pady=4)
				btn_frame.grid_propagate(False)

				if not is_disabled:
					btn_frame.bind(
						'<Button-1>',
						lambda e, vid=v.get('variant_id'): self.add_from_touch(vid),
					)

				inner = ctk.CTkFrame(btn_frame, fg_color='transparent')
				inner.place(relx=0.5, rely=0.5, anchor='center')

				lbl_name = ctk.CTkLabel(
					inner,
					text=name,
					font=FONT_BODY_BOLD,
					text_color=TEXT_MUTED if is_disabled else ACCENT_TEXT,
					wraplength=108,
					justify='center',
				)
				lbl_name.pack()
				lbl_price = ctk.CTkLabel(
					inner,
					text=f'${price:.2f}',
					font=FONT_SMALL,
					text_color=TEXT_MUTED if is_disabled else ACCENT_TEXT,
				)
				lbl_price.pack()
				lbl_stock = ctk.CTkLabel(
					inner,
					text=stock_label,
					font=FONT_LABEL,
					text_color=stock_color,
				)
				lbl_stock.pack()

				if not is_disabled:
					for widget in [btn_frame, inner, lbl_name, lbl_price, lbl_stock]:
						widget.bind(
							'<Button-1>',
							lambda e, vid=v.get('variant_id'): self.add_from_touch(vid),
						)
						widget.configure(cursor='hand2')

				self.touch_buttons.append(
					{'variant_id': v.get('variant_id'), 'button': btn_frame}
				)

				col += 1
				if col > 1:
					col = 0
					row += 1

		if not self.touch_buttons:
			ctk.CTkLabel(
				self.touch_scroll,
				text='Sin combos\nasignados',
				font=FONT_BODY,
				text_color=TEXT_MUTED,
				justify='center',
			).pack(pady=40)

		self.entry_barcode.focus()
		self._check_cash_status()

	# =========================================================
	# LÓGICA DEL CARRITO
	# =========================================================
	def _get_qty_in_cart(self, variant_id):
		return sum(
			item.get('qty', 0)
			for item in self.cart
			if item.get('variant_id') == variant_id
		)

	# ─── Búsqueda Manual Optimizado (Sin ComboBox bloqueante) ─────────────
	def _manual_search_on_enter(self, event=None):
		"""Busca artículos por coincidencia de texto. Si hay uno, lo agrega. Si hay varios, muestra pop-up."""
		q = self.entry_manual_search.get().lower().strip()
		if not q:
			return

		matches = [
			v
			for v in self.db_variants
			if q in (v.get('name') or '').lower() or q in (str(v.get('barcode')))
		]

		if len(matches) == 1:
			self._add_variant_to_cart(matches[0], self.qty_entry.get())
			self.entry_manual_search.delete(0, 'end')
		elif len(matches) > 1:
			self._show_search_results_popup(matches)
		else:
			self._set_msg('⚠ No se encontraron artículos', RED_TEXT)

	def _show_search_results_popup(self, matches):
		"""Muestra un modal rápido con los resultados de la búsqueda manual."""
		popup = ctk.CTkToplevel(self)
		popup.title('Resultados de búsqueda')
		popup.geometry('450x350')
		popup.attributes('-topmost', True)
		popup.grab_set()
		popup.bind('<Escape>', lambda e: popup.destroy())

		ctk.CTkLabel(popup, text='Seleccione el artículo', font=FONT_HEADING).pack(
			pady=10
		)

		scroll = ctk.CTkScrollableFrame(popup, fg_color='transparent')
		scroll.pack(fill='both', expand=True, padx=15, pady=5)

		for v in matches:
			name = v.get('name', '')
			price = v.get('selling_price', 0)
			stock = v.get('total_stock', 0)

			btn = ctk.CTkButton(
				scroll,
				text=f'{name}  |  ${price:.2f}  |  Stock: {stock}',
				font=FONT_BODY,
				height=36,
				fg_color=SURFACE3,
				hover_color=ACCENT_DIM,
				text_color=TEXT_PRIMARY,
				command=lambda var=v: [
					self._add_variant_to_cart(var, self.qty_entry.get()),
					popup.destroy(),
				],
			)
			btn.pack(fill='x', pady=3)

	def _add_variant_to_cart(self, variant, qty_str):
		"""Agrega un artículo validado al carrito (usado por búsqueda manual)."""
		self.lbl_msg.configure(text='')
		try:
			qty_to_add = Decimal(qty_str.replace(',', '.'))
			if qty_to_add <= Decimal('0.0'):
				raise ValueError
		except (ValueError, InvalidOperation):
			self._set_msg('⚠ Cantidad inválida', RED_TEXT)
			return

		variant_id = variant.get('variant_id')
		total_stock = Decimal(str(variant.get('total_stock', 0)))
		price = Decimal(str(variant.get('selling_price', 0.0)))
		desc = variant.get('name', 'Artículo')
		current_cart_qty = Decimal(str(self._get_qty_in_cart(variant_id)))

		if (current_cart_qty + qty_to_add) > total_stock:
			self._set_msg(f'⚠ Stock insuficiente. Disponibles: {total_stock}', RED_TEXT)
			return

		subtotal = price * qty_to_add
		qty_visual = (
			f'{int(qty_to_add)}' if qty_to_add % 1 == 0 else f'{qty_to_add:.3f}'
		)

		row_idx = len(self.tree.get_children())
		alt_tag = 'odd' if row_idx % 2 == 0 else 'even'

		item_id = self.tree.insert(
			'',
			'end',
			values=(desc, qty_visual, f'${price:.2f}', f'${subtotal:.2f}'),
			tags=(alt_tag,),
		)

		self.cart.append(
			{
				'tree_id': item_id,
				'variant_id': variant_id,
				'desc': desc,
				'price': float(price),
				'qty': float(qty_to_add),
				'subtotal': float(subtotal),
			}
		)
		self._flash_new_item(item_id, alt_tag)
		self.update_total()
		self.qty_entry.delete(0, 'end')
		self.qty_entry.insert(0, '1')
		self.entry_barcode.focus()

	# ─── Barcode helpers ──────────────────────────────────────────────────
	def _barcode_on_enter(self, event=None):
		if self._barcode_timer:
			self.after_cancel(self._barcode_timer)
			self._barcode_timer = None
		self.add_by_barcode()

	def _barcode_on_key(self, event=None):
		if event and event.keysym in ('Return', 'KP_Enter'):
			return
		if self._barcode_timer:
			self.after_cancel(self._barcode_timer)
		raw = self.entry_barcode.get().strip()
		if len(raw) >= 4:
			self._barcode_timer = self.after(500, self._barcode_auto_add)

	def _barcode_auto_add(self):
		self._barcode_timer = None
		if self.entry_barcode.get().strip():
			self.add_by_barcode()

	def _flash_new_item(self, item_id, original_tag):
		try:
			self.tree.item(item_id, tags=('new_item',))
			self.after(900, lambda: self._restore_tag(item_id, original_tag))
		except Exception:
			pass

	def _restore_tag(self, item_id, tag):
		try:
			self.tree.item(item_id, tags=(tag,))
		except Exception:
			pass

	def add_by_barcode(self, event=None):
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

		if not found_variant and not is_scale_barcode:
			q = raw_code.lower()
			matches = [
				v for v in self.db_variants if q in (v.get('name') or '').lower()
			]
			if len(matches) == 1:
				found_variant = matches[0]
			elif len(matches) > 1:
				self._show_search_results_popup(matches)
				self.entry_barcode.delete(0, 'end')
				return

		if not found_variant:
			self._set_msg(f'⚠ Código no encontrado: {raw_code}', RED_TEXT)
			self.entry_barcode.delete(0, 'end')
			return

		variant_id = found_variant.get('variant_id')
		name = found_variant.get('name', 'Desconocido')
		unit_price = Decimal(str(found_variant.get('selling_price', 0.0)))
		total_stock = Decimal(str(found_variant.get('total_stock', 0)))

		if is_scale_barcode:
			if unit_price == 0:
				self._set_msg('⚠ Producto de balanza con precio $0', RED_TEXT)
				self.entry_barcode.delete(0, 'end')
				return
			qty_to_add = scale_price / unit_price
			subtotal = scale_price
		else:
			qty_to_add = Decimal('1')
			subtotal = unit_price * qty_to_add

		current_cart_qty = Decimal(str(self._get_qty_in_cart(variant_id)))
		if (current_cart_qty + qty_to_add) > total_stock:
			self._set_msg(
				f'⚠ Stock insuficiente — en carrito: {current_cart_qty:.0f}, disponible: {total_stock:.0f}',
				RED_TEXT,
			)
			self.entry_barcode.delete(0, 'end')
			return

		qty_visual = (
			f'{int(qty_to_add)}' if qty_to_add % 1 == 0 else f'{qty_to_add:.3f}'
		)
		row_idx = len(self.tree.get_children())
		alt_tag = 'odd' if row_idx % 2 == 0 else 'even'
		item_id = self.tree.insert(
			'',
			'end',
			values=(name, qty_visual, f'${unit_price:.2f}', f'${subtotal:.2f}'),
			tags=(alt_tag,),
		)

		self.cart.append(
			{
				'tree_id': item_id,
				'variant_id': variant_id,
				'desc': name,
				'price': float(unit_price),
				'qty': float(qty_to_add),
				'subtotal': float(subtotal),
			}
		)
		self._flash_new_item(item_id, alt_tag)
		self.update_total()
		self.entry_barcode.delete(0, 'end')
		self._set_msg(f'✓  {name}')

	def add_from_touch(self, variant_id):
		found = next(
			(v for v in self.db_variants if v['variant_id'] == variant_id), None
		)
		if not found:
			return

		qty_to_add = Decimal('1')
		total_stock = Decimal(str(found.get('total_stock', 0)))
		current_cart_qty = Decimal(str(self._get_qty_in_cart(variant_id)))

		if (current_cart_qty + qty_to_add) > total_stock:
			self._set_msg('⚠ No hay stock suficiente.', RED_TEXT)
			return

		price = Decimal(str(found.get('selling_price', 0.0)))
		name = found.get('name')

		row_idx = len(self.tree.get_children())
		alt_tag = 'odd' if row_idx % 2 == 0 else 'even'
		item_id = self.tree.insert(
			'',
			'end',
			values=(name, '1', f'${price:.2f}', f'${price:.2f}'),
			tags=(alt_tag,),
		)

		self.cart.append(
			{
				'tree_id': item_id,
				'variant_id': variant_id,
				'desc': name,
				'price': float(price),
				'qty': 1.0,
				'subtotal': float(price),
			}
		)

		self._flash_new_item(item_id, alt_tag)
		self.update_total()
		self._set_msg(f'✓ Agregado: {name}')

	def add_fast_to_cart(self):
		"""Agrega artículo de venta libre y devuelve foco al lector para agilidad."""
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
			self._set_msg('⚠ Ingresá números válidos', RED_TEXT)
			return

		subtotal = price * qty
		visual_desc = f'*(Libre)* {desc}'
		qty_visual = f'{int(qty)}' if qty % 1 == 0 else f'{qty:.2f}'

		row_idx = len(self.tree.get_children())
		alt_tag = 'odd' if row_idx % 2 == 0 else 'even'

		item_id = self.tree.insert(
			'',
			'end',
			values=(visual_desc, qty_visual, f'${price:.2f}', f'${subtotal:.2f}'),
			tags=(alt_tag,),
		)

		self.cart.append(
			{
				'tree_id': item_id,
				'variant_id': None,
				'desc': visual_desc,
				'price': float(price),
				'qty': float(qty),
				'subtotal': float(subtotal),
			}
		)

		self._flash_new_item(item_id, alt_tag)
		self.update_total()

		self.entry_fast_desc.delete(0, 'end')
		self.entry_fast_price.delete(0, 'end')
		self.entry_fast_qty.delete(0, 'end')
		self.entry_fast_qty.insert(0, '1')
		self.entry_barcode.focus()  # Vuelve foco rápido

	def remove_from_cart(self, event=None):
		"""Eliminación silenciosa y veloz de artículos seleccionados."""
		self.lbl_msg.configure(text='')
		selected_item = self.tree.selection()
		if not selected_item:
			return

		for item_id in selected_item:
			for i, item in enumerate(self.cart):
				if item.get('tree_id') == item_id:
					self.cart.pop(i)
					break
			self.tree.delete(item_id)

		self._refresh_row_tags()
		self.update_total()
		self.entry_barcode.focus()

	def _refresh_row_tags(self):
		for i, item_id in enumerate(self.tree.get_children()):
			tag = 'odd' if i % 2 == 0 else 'even'
			self.tree.item(item_id, tags=(tag,))

	def update_total(self):
		from utils.settings_manager import fmt_price

		raw = sum(
			(Decimal(str(item.get('subtotal', 0))) for item in self.cart),
			Decimal('0.0'),
		)

		if self._discount_pct > 0 and raw > 0:
			disc = (raw * self._discount_pct / Decimal('100')).quantize(Decimal('0.01'))
		else:
			disc = Decimal('0.0')
		self._discount_amount = disc
		final = raw - disc

		self._lbl_subtotal.configure(text=fmt_price(float(raw)))
		self.lbl_total.configure(text=fmt_price(float(final)))

		if disc > 0:
			pct_str = f'{self._discount_pct:.4g}%'
			self._lbl_disc_label.configure(text=f'DESCUENTO  ({pct_str})')
			self._lbl_disc_value.configure(text=f'-{fmt_price(float(disc))}')
			self._disc_row.pack(fill='x', after=self._lbl_subtotal.master)
			self._divider_total.pack(fill='x', pady=(4, 0))
		else:
			self._disc_row.pack_forget()
			self._divider_total.pack_forget()

	def clear_entire_cart(self):
		if not self.cart:
			return
		if (
			CTkMessagebox(
				title='Anular Venta',
				message='¿Vaciar todo el carrito?',
				icon='warning',
				option_1='No',
				option_2='Sí',
			).get()
			== 'Sí'
		):
			self.cart.clear()
			for item in self.tree.get_children():
				self.tree.delete(item)
			self._set_discount_pct(Decimal('0'))
			self.update_total()
			self._set_msg('Venta anulada.', RED_TEXT)
			self.entry_barcode.focus()

	# =========================================================
	# POP-UP DE COBRO (Optimizado para teclado y monitores chicos)
	# =========================================================
	def process_sale(self):
		if not self.cart:
			self._set_msg('⚠ Agregá productos antes de cobrar', RED_TEXT)
			return

		raw_total = sum(
			(Decimal(str(item.get('subtotal', 0))) for item in self.cart),
			Decimal('0.0'),
		)
		self._discount_amount = (
			(raw_total * self._discount_pct / Decimal('100')).quantize(Decimal('0.01'))
			if self._discount_pct > 0
			else Decimal('0.0')
		)
		self.current_total = raw_total - self._discount_amount
		self.customer_name = self.customers_combo.get()

		self.popup = ctk.CTkToplevel(self)
		self.popup.title('Cobrar Venta')
		self.popup.configure(fg_color=SURFACE2)
		self.popup.attributes('-topmost', True)
		self.popup.grab_set()
		self.popup.update_idletasks()

		# Tamaño más conservador para pantallas 1366x768 o 1024x768
		pw, ph = 460, 620
		rx = self.winfo_rootx() + (self.winfo_width() - pw) // 2
		ry = self.winfo_rooty() + (self.winfo_height() - ph) // 2
		self.popup.geometry(f'{pw}x{ph}+{rx}+{ry}')

		self.popup.bind('<Escape>', lambda e: self.popup.destroy())

		# ── Header ────────────────────────────────────────────────────────
		ctk.CTkLabel(
			self.popup,
			text='Resumen de Venta',
			font=FONT_SUBHEADING,
			text_color=TEXT_MUTED,
		).pack(pady=(16, 4))

		if self._discount_amount > 0:
			breakdown = ctk.CTkFrame(
				self.popup,
				fg_color=SURFACE3,
				corner_radius=10,
				border_width=1,
				border_color=BORDER,
			)
			breakdown.pack(padx=24, fill='x', pady=(0, 8))

			inner_bd = ctk.CTkFrame(breakdown, fg_color='transparent')
			inner_bd.pack(fill='x', padx=16, pady=8)

			row_sub = ctk.CTkFrame(inner_bd, fg_color='transparent')
			row_sub.pack(fill='x')
			ctk.CTkLabel(
				row_sub,
				text='Subtotal',
				font=FONT_BODY,
				text_color=TEXT_MUTED,
				anchor='w',
			).pack(side='left')
			ctk.CTkLabel(
				row_sub,
				text=f'${raw_total:,.2f}',
				font=FONT_BODY,
				text_color=TEXT_MUTED,
				anchor='e',
			).pack(side='right')

			row_disc = ctk.CTkFrame(inner_bd, fg_color='transparent')
			row_disc.pack(fill='x', pady=(2, 0))
			pct_str = f'{self._discount_pct:.4g}%'
			ctk.CTkLabel(
				row_disc,
				text=f'Descuento ({pct_str})',
				font=FONT_BODY_BOLD,
				text_color=RED_TEXT,
				anchor='w',
			).pack(side='left')
			ctk.CTkLabel(
				row_disc,
				text=f'-${self._discount_amount:,.2f}',
				font=FONT_BODY_BOLD,
				text_color=RED_TEXT,
				anchor='e',
			).pack(side='right')

			ctk.CTkFrame(inner_bd, height=1, fg_color=BORDER).pack(fill='x', pady=6)

			row_total = ctk.CTkFrame(inner_bd, fg_color='transparent')
			row_total.pack(fill='x')
			ctk.CTkLabel(
				row_total,
				text='TOTAL A COBRAR',
				font=FONT_BODY_BOLD,
				text_color=TEXT_PRIMARY,
				anchor='w',
			).pack(side='left')
			ctk.CTkLabel(
				row_total,
				text=f'${self.current_total:,.2f}',
				font=FONT_TITLE,
				text_color=GREEN_TEXT,
				anchor='e',
			).pack(side='right')

		else:
			ctk.CTkLabel(
				self.popup,
				text=f'${self.current_total:,.2f}',
				font=('Arial', 46, 'bold'),
				text_color=GREEN_TEXT,
			).pack(pady=(0, 4))

		if self.customer_name and self.customer_name != 'Consumidor Final':
			ctk.CTkLabel(
				self.popup,
				text=f'📋  Cliente: {self.customer_name}',
				font=FONT_HEADING,
				text_color=ACCENT_TEXT,
			).pack(pady=(0, 4))

		ctk.CTkFrame(self.popup, height=1, fg_color=BORDER).pack(
			fill='x', padx=24, pady=10
		)

		# ── Método de pago ────────────────────────────────────────────────
		ctk.CTkLabel(
			self.popup,
			text='MÉTODO DE PAGO',
			font=FONT_SMALL_BOLD,
			text_color=TEXT_MUTED,
		).pack(padx=24, anchor='w')
		self.combo_payment = ctk.CTkComboBox(
			self.popup,
			values=['Efectivo', 'Tarjeta', 'Transferencia', 'QR Billetera'],
			fg_color=SURFACE3,
			border_color=BORDER,
			button_color=SURFACE4,
			button_hover_color=ACCENT,
			text_color=TEXT_PRIMARY,
			font=FONT_SUBHEADING,
			width=300,
			height=36,
			command=self._on_payment_change,
		)
		self.combo_payment.set('Efectivo')
		self.combo_payment.pack(pady=(6, 8), padx=24)

		# ── Pago Mixto switch ─────────────────────────────────────────────
		mixto_row = ctk.CTkFrame(self.popup, fg_color='transparent')
		mixto_row.pack(fill='x', padx=24, pady=(0, 6))
		self._mixto_var = ctk.BooleanVar(value=False)
		ctk.CTkSwitch(
			mixto_row,
			text='💰  Pago Mixto (dos métodos)',
			variable=self._mixto_var,
			font=FONT_BODY_BOLD,
			text_color=TEXT_SECONDARY,
			fg_color=SURFACE3,
			progress_color=ACCENT,
			command=self._toggle_mixto,
		).pack(side='left')

		# ── Sección mixto (oculta por defecto) ────────────────────────────
		self._mixto_section = ctk.CTkFrame(
			self.popup,
			fg_color=SURFACE3,
			corner_radius=8,
			border_width=1,
			border_color=BORDER,
		)
		_mx = ctk.CTkFrame(self._mixto_section, fg_color='transparent')
		_mx.pack(fill='x', padx=12, pady=10)
		ctk.CTkLabel(
			_mx,
			text='Segundo método:',
			font=FONT_SMALL_BOLD,
			text_color=TEXT_MUTED,
		).pack(anchor='w')
		self.combo_payment_2 = ctk.CTkComboBox(
			_mx,
			values=['Transferencia', 'Tarjeta', 'QR Billetera', 'Efectivo'],
			fg_color=SURFACE2,
			border_color=BORDER,
			button_color=SURFACE4,
			button_hover_color=ACCENT,
			text_color=TEXT_PRIMARY,
			font=FONT_NAV,
			height=34,
		)
		self.combo_payment_2.set('Transferencia')
		self.combo_payment_2.pack(fill='x', pady=(4, 8))
		ctk.CTkLabel(
			_mx,
			text='Monto del segundo método ($):',
			font=FONT_SMALL_BOLD,
			text_color=TEXT_MUTED,
		).pack(anchor='w')
		self.entry_amount_2 = ctk.CTkEntry(
			_mx,
			font=FONT_TITLE,
			justify='center',
			fg_color=SURFACE2,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			height=40,
		)
		self.entry_amount_2.pack(fill='x', pady=(4, 6))
		self.entry_amount_2.bind('<KeyRelease>', self._on_amount2_change)
		self._lbl_amount_1_auto = ctk.CTkLabel(
			_mx, text='', font=FONT_BODY_BOLD, text_color=GREEN_TEXT, anchor='e'
		)
		self._lbl_amount_1_auto.pack(fill='x')

		# ── Sección efectivo (oculta cuando mixto ON) ─────────────────────
		self._lbl_cash = ctk.CTkLabel(
			self.popup,
			text='EL CLIENTE ABONA (efectivo) - Presione Enter',
			font=FONT_SMALL_BOLD,
			text_color=TEXT_MUTED,
		)
		self._lbl_cash.pack(padx=24, anchor='w')
		self.entry_paid = ctk.CTkEntry(
			self.popup,
			font=('Arial', 24),
			justify='center',
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			height=48,
			width=300,
		)
		self.entry_paid.pack(pady=(6, 0), padx=24)
		self.entry_paid.focus()
		self.entry_paid.bind('<KeyRelease>', self._calculate_change)

		# Confirmación ultrarrápida con Teclado
		self.entry_paid.bind('<Return>', lambda e: self._confirm_and_save(False))

		self.lbl_change = ctk.CTkLabel(
			self.popup,
			text='Vuelto: $0.00',
			font=('Arial', 24, 'bold'),
			text_color=ACCENT_TEXT,
		)
		self.lbl_change.pack(pady=8)
		self.lbl_error_popup = ctk.CTkLabel(
			self.popup, text='', text_color=RED_TEXT, font=FONT_NAV
		)
		self.lbl_error_popup.pack()

		ctk.CTkButton(
			self.popup,
			text='✅  CONFIRMAR COBRO (Enter)',
			fg_color=GREEN,
			hover_color='#15803d',
			text_color='#fff',
			height=48,
			font=('Arial', 16, 'bold'),
			corner_radius=10,
			command=lambda: self._confirm_and_save(False),
		).pack(fill='x', padx=24, pady=(10, 6))

		if self.customer_name != 'Consumidor Final':
			ctk.CTkButton(
				self.popup,
				text='📝  Anotar como Fiado',
				fg_color=SURFACE3,
				hover_color=SURFACE4,
				text_color=ORANGE_TEXT,
				font=FONT_HEADING,
				border_width=1,
				border_color=ORANGE,
				height=42,
				corner_radius=10,
				command=lambda: self._confirm_and_save(True),
			).pack(fill='x', padx=24, pady=(0, 6))

		ctk.CTkButton(
			self.popup,
			text='⬅  Volver / Agregar más (Esc)',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			font=FONT_NAV,
			height=36,
			corner_radius=8,
			command=self.popup.destroy,
		).pack(fill='x', padx=24)

	def _on_payment_change(self, value=None):
		if getattr(self, '_mixto_var', None) and self._mixto_var.get():
			return
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
				self.lbl_change.configure(text='⚠ Falta dinero', text_color=RED_TEXT)
			else:
				self.lbl_change.configure(
					text=f'Vuelto: ${change:,.2f}', text_color=ACCENT_TEXT
				)
		except (ValueError, InvalidOperation):
			self.lbl_change.configure(text='Monto inválido', text_color=RED_TEXT)

	def _toggle_mixto(self):
		is_on = self._mixto_var.get()
		if is_on:
			self._mixto_section.pack(
				fill='x', padx=24, pady=(0, 8), before=self._lbl_cash
			)
			self._lbl_cash.pack_forget()
			self.entry_paid.pack_forget()
			self.lbl_change.pack_forget()
			self.entry_amount_2.focus()
		else:
			self._mixto_section.pack_forget()
			self._lbl_cash.pack(padx=24, anchor='w', before=self.lbl_error_popup)
			self.entry_paid.pack(pady=(6, 0), padx=24, before=self.lbl_error_popup)
			self.lbl_change.pack(pady=8, before=self.lbl_error_popup)
			self.entry_paid.focus()
			self._on_payment_change()

	def _on_amount2_change(self, event=None):
		try:
			raw2 = self.entry_amount_2.get().strip().replace(',', '.')
			amt2 = Decimal(raw2) if raw2 else Decimal('0')
			amt1 = self.current_total - amt2
			method1 = self.combo_payment.get()
			if amt1 < 0:
				self._lbl_amount_1_auto.configure(
					text='⚠ El monto excede el total', text_color=RED_TEXT
				)
			else:
				self._lbl_amount_1_auto.configure(
					text=f'{method1}: ${amt1:,.2f}', text_color=GREEN_TEXT
				)
		except (ValueError, InvalidOperation):
			pass

	def _confirm_and_save(self, is_fiado=False):
		payment_method = self.combo_payment.get()
		payment_method_2 = None
		amount_method_2 = None

		if getattr(self, '_mixto_var', None) and self._mixto_var.get() and not is_fiado:
			payment_method_2 = self.combo_payment_2.get()
			raw2 = self.entry_amount_2.get().strip().replace(',', '.')
			try:
				amount_method_2 = Decimal(raw2) if raw2 else Decimal('0')
				limit = self.current_total - Decimal('0.01')
				if amount_method_2 <= 0 or amount_method_2 >= self.current_total:
					self.lbl_error_popup.configure(
						text=f'El monto del 2do método debe ser entre $0.01 y ${limit:,.2f}'
					)
					return
			except (ValueError, InvalidOperation):
				self.lbl_error_popup.configure(
					text='Monto inválido para el segundo método'
				)
				return
		elif not is_fiado and payment_method == 'Efectivo':
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
		self.finalize_sale(
			customer_id, is_fiado, payment_method, payment_method_2, amount_method_2
		)

	def finalize_sale(
		self,
		customer_id,
		is_fiado,
		payment_method,
		payment_method_2=None,
		amount_method_2=None,
	):
		tenant_id = self.ctx.tenant_id
		user_id = self.ctx.user_id
		success, msg = self.sales_ctrl.process_sale(
			tenant_id,
			user_id,
			self.cart,
			customer_id,
			is_fiado,
			payment_method,
			discount_amount=self._discount_amount,
			payment_method_2=payment_method_2,
			amount_method_2=amount_method_2,
		)
		if success:
			CTkMessagebox(title='¡Venta registrada!', message=msg, icon='check')
			self.cart.clear()
			for item in self.tree.get_children():
				self.tree.delete(item)
			self._set_discount_pct(Decimal('0'))
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
		self.bind(
			'<Destroy>', lambda e: self.destroy_custom() if e.widget is self else None
		)

	def destroy_custom(self):
		top = self.winfo_toplevel()
		for key in ('<F5>', '<F6>', '<F7>', '<Delete>', '<Control-Delete>'):
			try:
				top.unbind(key)
			except Exception:
				pass
