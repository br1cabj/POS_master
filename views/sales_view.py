"""
views/sales_view.py
====================
Módulo de Ventas (POS).
Optimizado para alto rendimiento en mostrador.
Solucionados errores de precisión Decimal, cierres de ciclos asíncronos y serialización.
"""

import logging
import tkinter
from decimal import Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

import utils.settings_manager as _cfg_mgr
from controllers.cash_controller import CashController
from controllers.sales_controller import SalesController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	FONT_AMOUNT,
	FONT_AMOUNT_BOLD,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_DISPLAY,
	FONT_HEADING,
	FONT_INPUT_LG,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	FONT_NAV,
	FONT_SMALL,
	FONT_SMALL_BOLD,
	FONT_SUBHEADING,
	FONT_SUBHEADING_BOLD,
	FONT_TITLE,
	FONT_TITLE_SM,
	FONT_XL_BOLD,
	GREEN,
	GREEN_HOVER,
	GREEN_MID,
	GREEN_TEXT,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	RED,
	RED_DIM,
	RED_TEXT,
	SURFACE1,
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
	def __init__(self, master, ctx: AppContext, context_data=None):
		super().__init__(master, ctx)
		self._context_data = context_data
		self.sales_ctrl = SalesController(ctx.db_engine)
		self._cash_ctrl = CashController(ctx.db_engine)
		self.db_engine = ctx.db_engine
		self.cart = []

		self._discount_pct = Decimal('0')
		self._discount_amount = Decimal('0')
		self._preset_btns: list = []
		self._paid_amount = None
		self._active_price_list = 'A'

		self._is_loading_data = False
		self._search_popup = None
		self._search_mode = 'scan'

		# Timers unificados
		self._flash_timers = {}
		self._barcode_timer = None
		self._msg_timer_id = None
		self._touch_batch_timer = None
		self._disc_border_timer = None

		self.grid_columnconfigure(0, weight=3)
		self.grid_columnconfigure(1, weight=1)
		self.grid_rowconfigure(0, weight=1)

		apply_treeview_style()
		ttk.Style().map('Treeview.Heading', background=[('active', SURFACE4)])
		ttk.Style().configure('Treeview', font=FONT_SMALL)

		self._build_main_panel()
		self._build_right_panel()

		self.customer_map = {}
		self.db_variants = []
		self.touch_buttons = []

		self.after(50, self.load_data)
		self.setup_shortcuts()

	# =========================================================
	# HELPERS DE UX
	# =========================================================
	def _select_all_text(self, event):
		event.widget.select_range(0, 'end')
		event.widget.icursor('end')

	# =========================================================
	# PANEL PRINCIPAL
	# =========================================================
	def _build_main_panel(self):
		self.main_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.main_panel.grid(row=0, column=0, sticky='nsew', padx=(10, 5), pady=10)
		self.center_panel = self.main_panel

		search_zone = ctk.CTkFrame(
			self.main_panel,
			fg_color=ACCENT_DIM,
			corner_radius=12,
			border_width=1,
			border_color=ACCENT,
		)
		search_zone.pack(fill='x', padx=10, pady=(10, 5))

		search_inner = ctk.CTkFrame(search_zone, fg_color='transparent')
		search_inner.pack(fill='x', padx=12, pady=(10, 4))
		ctk.CTkLabel(
			search_inner, text='🔍', font=FONT_HEADING, text_color=ACCENT_TEXT
		).pack(side='left', padx=(0, 8))

		self.entry_barcode = ctk.CTkEntry(
			search_inner,
			placeholder_text='Escanear código de barras o escribir nombre...',
			fg_color=SURFACE1,
			border_color=ACCENT,
			text_color=TEXT_PRIMARY,
			placeholder_text_color=ACCENT_TEXT,
			height=52,
			font=FONT_INPUT_LG,
			border_width=2,
		)
		self.entry_barcode.pack(side='left', fill='x', expand=True)
		self.entry_barcode.bind('<Return>', self._barcode_on_enter)
		self.entry_barcode.bind('<KeyRelease>', self._barcode_on_key)
		self.entry_barcode.bind('<FocusOut>', self._on_search_entry_focus_out)
		self.entry_manual_search = self.entry_barcode

		bottom_search = ctk.CTkFrame(search_zone, fg_color='transparent')
		bottom_search.pack(fill='x', padx=12, pady=(2, 10))

		toggle_wrap = ctk.CTkFrame(bottom_search, fg_color=SURFACE1, corner_radius=8)
		toggle_wrap.pack(side='left', padx=(0, 10))

		self._btn_scan_mode = ctk.CTkButton(
			toggle_wrap,
			text='📷  Escanear',
			font=FONT_SMALL_BOLD,
			height=30,
			width=110,
			corner_radius=7,
			fg_color=ACCENT,
			hover_color=ACCENT,
			text_color=TEXT_PRIMARY,
			command=lambda: self._set_search_mode('scan'),
		)
		self._btn_scan_mode.pack(side='left', padx=2, pady=2)

		self._btn_search_mode = ctk.CTkButton(
			toggle_wrap,
			text='🔍  Buscar',
			font=FONT_SMALL_BOLD,
			height=30,
			width=100,
			corner_radius=7,
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_SECONDARY,
			command=lambda: self._set_search_mode('search'),
		)
		self._btn_search_mode.pack(side='left', padx=2, pady=2)

		ctk.CTkLabel(
			bottom_search, text='Cant:', font=FONT_SMALL_BOLD, text_color=ACCENT_TEXT
		).pack(side='left', padx=(0, 4))
		self.qty_entry = ctk.CTkEntry(
			bottom_search,
			width=72,
			fg_color=SURFACE1,
			border_color=ACCENT,
			text_color=TEXT_PRIMARY,
			height=34,
			font=FONT_BODY_BOLD,
			justify='center',
		)
		self.qty_entry.pack(side='left', padx=(0, 8))
		self.qty_entry.insert(0, '1')
		self.qty_entry.bind('<Return>', self._manual_search_on_enter)
		self.qty_entry.bind('<FocusIn>', self._select_all_text)

		ctk.CTkButton(
			bottom_search,
			text='⚡  Venta Libre',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=ORANGE_TEXT,
			font=FONT_SMALL_BOLD,
			border_width=1,
			border_color=ORANGE,
			height=34,
			corner_radius=8,
			command=self._open_venta_libre_popup,
		).pack(side='left')

		customer_row = ctk.CTkFrame(
			self.main_panel,
			fg_color=SURFACE3,
			corner_radius=8,
			border_width=1,
			border_color=BORDER,
		)
		customer_row.pack(fill='x', padx=10, pady=(0, 5))
		self._customer_row_ref = customer_row

		self._dropdown_frame = ctk.CTkFrame(
			self.main_panel,
			fg_color=SURFACE3,
			corner_radius=8,
			border_width=1,
			border_color=BORDER,
		)
		self._dropdown_items = []

		_cr = ctk.CTkFrame(customer_row, fg_color='transparent')
		_cr.pack(fill='x', padx=12, pady=6)
		ctk.CTkLabel(
			_cr, text='👤  Cliente:', font=FONT_SMALL_BOLD, text_color=TEXT_SECONDARY
		).pack(side='left', padx=(0, 8))

		self.customers_combo = ctk.CTkComboBox(
			_cr,
			fg_color=SURFACE2,
			border_color=BORDER,
			button_color=SURFACE4,
			button_hover_color=ACCENT,
			text_color=TEXT_PRIMARY,
			height=30,
			font=FONT_SMALL,
			command=self._on_customer_changed,
		)
		self.customers_combo.set('Cargando...')
		self.customers_combo.pack(side='left', fill='x', expand=True, padx=(0, 8))

		_list_a_name = _cfg_mgr.get('price_list_a_name', 'Minorista')
		self._btn_price_list = ctk.CTkButton(
			_cr,
			text=f'🏪 {_list_a_name}',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=30,
			width=120,
			corner_radius=6,
			font=FONT_SMALL_BOLD,
			command=self._toggle_price_list,
		)
		self._btn_price_list.pack(side='left', padx=(0, 8))

		self.banner_caja = ctk.CTkFrame(
			self.main_panel,
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

		cart_hdr = ctk.CTkFrame(self.main_panel, fg_color='transparent')
		cart_hdr.pack(fill='x', padx=12, pady=(4, 2))
		ctk.CTkLabel(
			cart_hdr,
			text='🛒  Carrito',
			font=FONT_SUBHEADING_BOLD,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')
		self._lbl_item_count = ctk.CTkLabel(
			cart_hdr, text='0 ítems', font=FONT_SMALL, text_color=TEXT_MUTED, anchor='w'
		)
		self._lbl_item_count.pack(side='left', padx=(8, 0))
		self.lbl_msg = ctk.CTkLabel(
			cart_hdr, text='', font=FONT_BODY_BOLD, text_color=GREEN_TEXT, anchor='e'
		)
		self.lbl_msg.pack(side='right', padx=(8, 0))
		ctk.CTkFrame(self.main_panel, height=1, fg_color=BORDER).pack(fill='x', padx=12)

		self._table_wrap = ctk.CTkFrame(self.main_panel, fg_color='transparent')
		self._table_wrap.pack(fill='both', expand=True, padx=10, pady=4)
		self.tree_scroll = ttk.Scrollbar(self._table_wrap, orient='vertical')
		self.tree = ttk.Treeview(
			self._table_wrap,
			columns=('Artículo', 'Cant', 'Precio', 'Subtotal'),
			show='headings',
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		self.tree.heading('Artículo', text='Artículo')
		self.tree.heading('Cant', text='Cant')
		self.tree.heading('Precio', text='Precio Unit.')
		self.tree.heading('Subtotal', text='Subtotal')
		self.tree.column('Artículo', width=220, anchor='w', stretch=True)
		self.tree.column('Cant', width=55, anchor='center', stretch=False)
		self.tree.column('Precio', width=100, anchor='e', stretch=False)
		self.tree.column('Subtotal', width=100, anchor='e', stretch=False)

		self.tree.tag_configure('odd', background=SURFACE2)
		self.tree.tag_configure('even', background=SURFACE3)
		self.tree.tag_configure('new_item', background=GREEN_MID)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)
		self.tree.bind('<Double-1>', self._on_cart_double_click)

		footer = ctk.CTkFrame(self.main_panel, fg_color='transparent')
		footer.pack(fill='x', padx=12, pady=(0, 4))
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
		ctk.CTkButton(
			footer,
			text='✕ Vaciar carrito',
			fg_color='transparent',
			hover_color=RED_DIM,
			text_color=TEXT_MUTED,
			font=FONT_SMALL,
			width=110,
			height=28,
			corner_radius=6,
			command=self.clear_entire_cart,
		).pack(side='right')

		self._build_discount_bar()
		self._build_total_block()

		self.btn_pay = ctk.CTkButton(
			self.main_panel,
			text='💰  COBRAR  [F5]',
			fg_color=GREEN,
			hover_color=GREEN_HOVER,
			text_color=TEXT_PRIMARY,
			height=56,
			corner_radius=10,
			font=FONT_XL_BOLD,
			cursor='hand2',
			command=self.process_sale,
		)
		self.btn_pay.pack(fill='x', padx=12, pady=(0, 10))

		self._vl = ctk.CTkFrame(self.main_panel, fg_color='transparent')
		self.entry_fast_desc = ctk.CTkEntry(self._vl)
		self.entry_fast_price = ctk.CTkEntry(self._vl)
		self.entry_fast_qty = ctk.CTkEntry(self._vl)
		self.entry_fast_qty.insert(0, '1')

	def _build_discount_bar(self):
		self._disc_expanded = True
		bar = ctk.CTkFrame(
			self.center_panel,
			fg_color=SURFACE3,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		bar.pack(fill='x', padx=12, pady=(0, 6))

		hdr = ctk.CTkFrame(bar, fg_color='transparent')
		hdr.pack(fill='x', padx=10, pady=(4, 0))

		self._btn_disc_toggle = ctk.CTkButton(
			hdr,
			text='🏷  DESCUENTO  ▾',
			fg_color='transparent',
			hover_color=SURFACE4,
			text_color=TEXT_MUTED,
			font=FONT_SMALL_BOLD,
			anchor='w',
			height=28,
			corner_radius=6,
			command=self._toggle_discount_bar,
		)
		self._btn_disc_toggle.pack(side='left', fill='x', expand=True)

		self._lbl_disc_preview = ctk.CTkLabel(
			hdr, text='', font=FONT_SMALL_BOLD, text_color=RED_TEXT
		)
		self._lbl_disc_preview.pack(side='right', padx=(0, 4))

		self._disc_inner = ctk.CTkFrame(bar, fg_color='transparent')
		self._disc_inner.pack(fill='x')  # expandido por defecto
		inner = ctk.CTkFrame(self._disc_inner, fg_color='transparent')
		inner.pack(fill='x', padx=10, pady=(2, 8))

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

	def has_unsaved_changes(self) -> bool:
		return bool(self.cart)

	def _toggle_discount_bar(self):
		self._disc_expanded = not self._disc_expanded
		if self._disc_expanded:
			self._disc_inner.pack(fill='x')
			self._btn_disc_toggle.configure(text='🏷  DESCUENTO  ▾')
		else:
			self._disc_inner.pack_forget()
			self._btn_disc_toggle.configure(text='🏷  DESCUENTO  ▸')

	def _build_total_block(self):
		total_block = ctk.CTkFrame(
			self.center_panel, fg_color=SURFACE3, corner_radius=10
		)
		total_block.pack(fill='x', padx=12, pady=(0, 6))

		inner = ctk.CTkFrame(total_block, fg_color='transparent')
		inner.pack(fill='x', padx=14, pady=(10, 4))

		sub_row = ctk.CTkFrame(inner, fg_color='transparent')
		sub_row.pack(fill='x')
		ctk.CTkLabel(
			sub_row, text='SUBTOTAL', font=FONT_SMALL, text_color=TEXT_MUTED, anchor='w'
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
			self._disc_row, text='', font=FONT_HEADING, text_color=RED_TEXT, anchor='e'
		)
		self._lbl_disc_value.pack(side='right')

		self._divider_total = ctk.CTkFrame(inner, height=1, fg_color=BORDER)
		ctk.CTkLabel(
			inner, text='TOTAL', font=FONT_BODY_BOLD, text_color=TEXT_MUTED, anchor='w'
		).pack(anchor='w', pady=(6, 0))
		self.lbl_total = ctk.CTkLabel(
			inner, text='$0', font=FONT_DISPLAY, text_color=GREEN_TEXT, anchor='w'
		)
		self.lbl_total.pack(anchor='w')

		self._lbl_wholesale_badge = ctk.CTkLabel(
			total_block,
			text='',
			font=FONT_SMALL_BOLD,
			text_color=ORANGE_TEXT,
			fg_color=ORANGE_DIM,
			corner_radius=6,
			anchor='w',
		)

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
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=(5, 10), pady=10)

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
			self.right_panel, fg_color='transparent', scrollbar_button_color=SURFACE3
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
					fg_color=ACCENT_DIM, text_color=ACCENT_TEXT, border_color=ACCENT
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
			self._set_msg('🏷  Descuento eliminado', TEXT_MUTED)
		else:
			self._btn_clear_disc.configure(text_color=RED_TEXT, border_color=RED)
			self._set_msg(f'🏷  Descuento del {pct}% aplicado', GREEN_TEXT)

		if hasattr(self, '_lbl_disc_preview'):
			self._lbl_disc_preview.configure(text=f'-{pct:.4g}%' if pct > 0 else '')
		if pct > 0 and hasattr(self, '_disc_expanded') and not self._disc_expanded:
			self._toggle_discount_bar()
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
			self._entry_custom_disc.configure(border_color=BORDER)
		except (ValueError, InvalidOperation):
			self._entry_custom_disc.configure(border_color=RED)
			if self._disc_border_timer:
				self.after_cancel(self._disc_border_timer)
			self._disc_border_timer = self.after(
				1200, lambda: self._entry_custom_disc.configure(border_color=BORDER)
			)

	def _set_msg(self, text: str, color: str = None):
		self.lbl_msg.configure(text=text, text_color=color or GREEN_TEXT)
		if self._msg_timer_id:
			try:
				self.after_cancel(self._msg_timer_id)
			except tkinter.TclError:
				pass
		self._msg_timer_id = self.after(3000, lambda: self.lbl_msg.configure(text=''))

	# =========================================================
	# CARGA DE DATOS (Optimizada con Batch Rendering Correcto)
	# =========================================================
	def _check_cash_status(self):
		try:
			session = self._cash_ctrl.get_active_session(
				self.ctx.tenant_id, self.ctx.user_id
			)
			self.banner_caja.pack_forget()
			if not session:
				self.banner_caja.pack(
					fill='x', padx=10, pady=(0, 4), before=self._table_wrap
				)
				self.btn_pay.configure(
					state='disabled',
					text='Abrí la Caja primero',
					fg_color=SURFACE3,
					text_color=TEXT_MUTED,
				)
			else:
				self.btn_pay.configure(
					state='normal',
					text='💰  COBRAR  [F5]',
					fg_color=GREEN,
					text_color=TEXT_PRIMARY,
				)
		except Exception as e:
			logging.warning(f'Cash status check failed: {e}')

	def load_data(self):
		self._is_loading_data = True
		try:
			# Si hay un render batch previo en curso, lo matamos
			if self._touch_batch_timer:
				self.after_cancel(self._touch_batch_timer)
				self._touch_batch_timer = None

			current_customer = (
				self.customers_combo.get() if hasattr(self, 'customers_combo') else None
			)
			tenant_id = self.ctx.tenant_id

			self.db_variants = self.sales_ctrl.get_articles_for_sale(tenant_id)
			customers = self.sales_ctrl.get_customers(tenant_id)
			self.customer_map = {c.get('name'): c for c in customers}

			customer_names = list(self.customer_map.keys())
			if 'Consumidor Final' not in customer_names:
				customer_names.insert(0, 'Consumidor Final')
			self.customers_combo.configure(values=customer_names)

			if current_customer and current_customer in customer_names:
				self.customers_combo.set(current_customer)
			else:
				self.customers_combo.set('Consumidor Final')

			for w in self.touch_scroll.winfo_children():
				w.destroy()
			self.touch_buttons.clear()

			self._touch_queue = [
				v
				for v in self.db_variants
				if v.get('is_combo') or v.get('show_on_touch')
			]
			self._touch_row, self._touch_col = 0, 0

			if not self._touch_queue:
				ctk.CTkLabel(
					self.touch_scroll,
					text='Sin combos\nasignados',
					font=FONT_BODY,
					text_color=TEXT_MUTED,
					justify='center',
				).pack(pady=40)
				self.grid_columnconfigure(1, weight=0)
				self.right_panel.grid_remove()
			else:
				self.grid_columnconfigure(1, weight=1)
				self.right_panel.grid()
				self._render_touch_batch()

			self.entry_barcode.focus()
			self._check_cash_status()

			if self._context_data and 'restore_sale' in self._context_data:
				self._load_restored_sale(self._context_data['restore_sale'])
				self._context_data = None
		finally:
			self._is_loading_data = False

	def _render_touch_batch(self):
		if not self.winfo_exists() or not self._touch_queue:
			return

		chunk = self._touch_queue[:15]
		self._touch_queue = self._touch_queue[15:]

		from utils.settings_manager import get as settings_get

		low_threshold = settings_get('low_stock_threshold', 5)

		for v in chunk:
			stock = Decimal(str(v.get('total_stock', 0)))
			price = Decimal(str(v.get('selling_price', 0)))
			name = v.get('name', 'Promo')
			is_disabled = stock <= 0
			stock_int = int(stock)

			if is_disabled:
				stock_label, stock_color = 'Sin stock', TEXT_MUTED
			elif stock_int <= low_threshold:
				stock_label, stock_color = f'Stock: {stock_int}', ORANGE_TEXT
			else:
				stock_label, stock_color = f'Stock: {stock_int}', TEXT_MUTED

			btn_frame = ctk.CTkFrame(
				self.touch_scroll,
				fg_color=SURFACE3 if is_disabled else ACCENT_DIM,
				corner_radius=8,
				border_width=1,
				border_color=BORDER,
				width=118,
				height=80,
			)
			btn_frame.grid(row=self._touch_row, column=self._touch_col, padx=4, pady=4)
			btn_frame.grid_propagate(False)

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
				inner, text=stock_label, font=FONT_LABEL, text_color=stock_color
			)
			lbl_stock.pack()

			if not is_disabled:
				action = lambda e, vid=v.get('variant_id'): self.add_from_touch(vid)
				for w in [btn_frame, inner, lbl_name, lbl_price, lbl_stock]:
					w.bind('<Button-1>', action)
					w.configure(cursor='hand2')

			self.touch_buttons.append(
				{
					'variant_id': v.get('variant_id'),
					'button': btn_frame,
					'price_label': lbl_price,
					'variant': v,
				}
			)

			self._touch_col += 1
			if self._touch_col > 1:
				self._touch_col = 0
				self._touch_row += 1

		if self._touch_queue:
			self._touch_batch_timer = self.after(20, self._render_touch_batch)

	def _load_restored_sale(self, sale_data):
		self._is_loading_data = True
		try:
			if (
				sale_data.get('customer_name')
				and sale_data['customer_name'] in self.customer_map
			):
				self.customers_combo.set(sale_data['customer_name'])

			for item in sale_data.get('items', []):
				variant_id = item.get('variant_id')
				qty = item.get('quantity', 1)

				if variant_id:
					variant = next(
						(v for v in self.db_variants if v['variant_id'] == variant_id),
						None,
					)
					if variant:
						self._add_variant_to_cart(variant, str(qty))
					else:
						self._set_msg(
							f'⚠ Producto {item.get("description")} no encontrado.',
							RED_TEXT,
						)
				else:
					self.entry_fast_desc.delete(0, 'end')
					self.entry_fast_desc.insert(
						0, item.get('description', 'Venta Libre')
					)
					self.entry_fast_price.delete(0, 'end')
					self.entry_fast_price.insert(0, str(item.get('unit_price', 0)))
					self.entry_fast_qty.delete(0, 'end')
					self.entry_fast_qty.insert(0, str(qty))
					self.add_fast_to_cart()

			self._set_msg('✏️ Ticket listo para modificar', ORANGE_TEXT)
		except Exception as e:
			logging.error(f'Error restoring ticket: {e}')
			self._set_msg('Error restaurando ticket', RED_TEXT)
		finally:
			self._is_loading_data = False

	# =========================================================
	# LÓGICA DEL CARRITO
	# =========================================================
	def _get_qty_in_cart(self, variant_id) -> Decimal:
		return sum(
			(
				Decimal(str(item.get('qty', 0)))
				for item in self.cart
				if item.get('variant_id') == variant_id
			),
			Decimal('0.0'),
		)

	def _apply_product_discount(self, variant: dict, base_price: Decimal):
		from datetime import datetime as _dt

		def _pct_active(pct, until):
			if not pct or pct <= 0:
				return Decimal('0')
			if until:
				if isinstance(until, str):
					try:
						until = _dt.fromisoformat(until)
					except Exception:
						return Decimal('0')
				if until < _dt.now():
					return Decimal('0')
			return Decimal(str(pct))

		prod_pct = _pct_active(
			variant.get('discount_pct', 0), variant.get('discount_until')
		)
		supp_pct = _pct_active(
			variant.get('supplier_discount_pct', 0),
			variant.get('supplier_discount_until'),
		)

		if prod_pct > Decimal('0'):
			factor = Decimal('1') - (prod_pct / Decimal('100'))
			return (base_price * factor).quantize(Decimal('0.01')), prod_pct, 'producto'
		if supp_pct > Decimal('0'):
			factor = Decimal('1') - (supp_pct / Decimal('100'))
			return (
				(base_price * factor).quantize(Decimal('0.01')),
				supp_pct,
				'distribuidor',
			)
		return base_price, Decimal('0'), ''

	def _get_list_price(self, variant: dict) -> Decimal:
		if self._active_price_list == 'B' and variant.get('selling_price_b'):
			return Decimal(str(variant.get('selling_price_b')))
		return Decimal(str(variant.get('selling_price', 0)))

	def _toggle_price_list(self):
		self._set_price_list('B' if self._active_price_list == 'A' else 'A')

	def _set_price_list(self, key: str):
		self._active_price_list = key
		list_a_name = _cfg_mgr.get('price_list_a_name', 'Minorista')
		list_b_name = _cfg_mgr.get('price_list_b_name', 'Mayorista')
		if key == 'B':
			self._btn_price_list.configure(
				text=f'💼 {list_b_name}',
				fg_color=ORANGE_DIM,
				hover_color=ORANGE_DIM,
				border_color=ORANGE,
				text_color=ORANGE_TEXT,
			)
		else:
			self._btn_price_list.configure(
				text=f'🏪 {list_a_name}',
				fg_color=SURFACE3,
				hover_color=SURFACE4,
				border_color=BORDER,
				text_color=TEXT_SECONDARY,
			)
		for tb in self.touch_buttons:
			variant, lbl = tb.get('variant'), tb.get('price_label')
			if variant and lbl:
				try:
					if lbl.winfo_exists():
						p = self._get_list_price(variant)
						lbl.configure(text=f'${p:.2f}')
				except Exception:
					pass

	def _on_customer_changed(self, name=None):
		name = name or self.customers_combo.get()
		customer = self.customer_map.get(name)
		self._set_price_list(
			'B' if customer and customer.get('price_list') == 'B' else 'A'
		)

	# =========================================================
	# Búsqueda Manual
	# =========================================================
	def _manual_search_on_key(self, event=None):
		if event and event.keysym in ('Return', 'KP_Enter'):
			return
		if (
			not self.entry_manual_search.get().strip()
			and getattr(self, '_search_popup', None)
			and self._search_popup.winfo_exists()
		):
			self._search_popup.destroy()
			self._search_popup = None

	def _manual_search_on_enter(self, event=None):
		q = self.entry_manual_search.get().lower().strip()
		if not q:
			if (
				getattr(self, '_search_popup', None)
				and self._search_popup.winfo_exists()
			):
				self._search_popup.destroy()
				self._search_popup = None
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
		if getattr(self, '_search_popup', None) and self._search_popup.winfo_exists():
			self._search_popup.destroy()

		popup = ctk.CTkToplevel(self)
		self._search_popup = popup
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

		def _make_cmd(var):
			return lambda: [
				self._add_variant_to_cart(var, self.qty_entry.get()),
				popup.destroy(),
			]

		for v in matches:
			btn = ctk.CTkButton(
				scroll,
				text=f'{v.get("name", "")}  |  ${v.get("selling_price", 0):.2f}  |  Stock: {v.get("total_stock", 0)}',
				font=FONT_BODY,
				height=36,
				fg_color=SURFACE3,
				hover_color=ACCENT_DIM,
				text_color=TEXT_PRIMARY,
				command=_make_cmd(v),
			)
			btn.pack(fill='x', pady=3)

	def _add_variant_to_cart(self, variant, qty_str):
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
		base_price = self._get_list_price(variant)
		desc = variant.get('name', 'Artículo')
		current_cart_qty = self._get_qty_in_cart(variant_id)
		total_qty = current_cart_qty + qty_to_add

		stock_warning = total_qty > total_stock

		price, product_disc_pct, _disc_src = self._apply_product_discount(
			variant, base_price
		)
		using_list_b = self._active_price_list == 'B' and variant.get('selling_price_b')

		display_desc = desc
		if product_disc_pct > Decimal('0'):
			display_desc = f'🏷️ -{product_disc_pct:.4g}% {desc}'
		elif using_list_b:
			display_desc = f'💼 {desc}'

		existing_item = next(
			(i for i in self.cart if i.get('variant_id') == variant_id), None
		)

		if existing_item:
			existing_item['qty'] = total_qty
			existing_item['price'] = price
			existing_item['product_disc_pct'] = product_disc_pct
			existing_item['subtotal'] = price * total_qty

			qty_visual = (
				f'{int(total_qty)}' if total_qty % 1 == 0 else f'{total_qty:.3f}'
			)
			self.tree.item(
				existing_item['tree_id'],
				values=(
					display_desc,
					qty_visual,
					f'${price:.2f}',
					f'${existing_item["subtotal"]:.2f}',
				),
			)
			self._flash_new_item(
				existing_item['tree_id'],
				self.tree.item(existing_item['tree_id'], 'tags')[0],
			)
		else:
			subtotal = price * qty_to_add
			qty_visual = (
				f'{int(qty_to_add)}' if qty_to_add % 1 == 0 else f'{qty_to_add:.3f}'
			)
			alt_tag = 'odd' if len(self.tree.get_children()) % 2 == 0 else 'even'
			item_id = self.tree.insert(
				'',
				'end',
				values=(display_desc, qty_visual, f'${price:.2f}', f'${subtotal:.2f}'),
				tags=(alt_tag,),
			)

			self.cart.append(
				{
					'tree_id': item_id,
					'variant_id': variant_id,
					'desc': display_desc,
					'base_price': base_price,
					'price': price,
					'product_disc_pct': product_disc_pct,
					'qty': qty_to_add,
					'subtotal': subtotal,
				}
			)
			self._flash_new_item(item_id, alt_tag)

		# Alertas suaves vs validaciones
		if stock_warning:
			self._set_msg(f'⚠ Stock de sistema superado ({desc})', ORANGE_TEXT)
		elif product_disc_pct > Decimal('0'):
			self._set_msg(
				f'🏷️ Descuento -{product_disc_pct:.4g}% aplicado en {desc}', ORANGE_TEXT
			)
		elif using_list_b:
			self._set_msg(f'💼 {desc} — Precio Mayorista', ORANGE_TEXT)
		else:
			self._set_msg(f'✓  Agregado: {desc}')

		self.update_total()
		self.qty_entry.delete(0, 'end')
		self.qty_entry.insert(0, '1')
		self.entry_barcode.focus()

	# =========================================================
	# Helpers de Timers e Interfaz (Treeview)
	# =========================================================
	def _flash_new_item(self, item_id, original_tag):
		try:
			if item_id in self._flash_timers:
				self.after_cancel(self._flash_timers[item_id])
			self.tree.item(item_id, tags=('new_item',))
			self._flash_timers[item_id] = self.after(
				900, lambda: self._restore_tag(item_id, original_tag)
			)
		except tkinter.TclError:
			pass

	def _restore_tag(self, item_id, tag):
		try:
			self._flash_timers.pop(item_id, None)
			if self.tree.exists(item_id):
				self.tree.item(item_id, tags=(tag,))
		except tkinter.TclError:
			pass

	# =========================================================
	# Barcode y Búsqueda Visual
	# =========================================================
	def _barcode_on_enter(self, event=None):
		if self._barcode_timer is not None:
			self.after_cancel(self._barcode_timer)
			self._barcode_timer = None
		if self._search_mode == 'search':
			self._select_first_dropdown_item()
		else:
			self.add_by_barcode()

	def _barcode_on_key(self, event=None):
		if event and event.keysym in ('Return', 'KP_Enter'):
			return
		if self._barcode_timer is not None:
			self.after_cancel(self._barcode_timer)
			self._barcode_timer = None

		raw = self.entry_barcode.get().strip()
		if self._search_mode == 'search':
			if len(raw) >= 1:
				self._barcode_timer = self.after(250, self._update_dropdown)
			else:
				self._close_dropdown()
		else:
			if len(raw) >= 4:
				self._barcode_timer = self.after(800, self._barcode_auto_add)

	def _barcode_auto_add(self):
		self._barcode_timer = None
		if self.entry_barcode.get().strip():
			self.add_by_barcode()

	def _set_search_mode(self, mode: str):
		self._search_mode = mode
		if mode == 'scan':
			self._btn_scan_mode.configure(
				fg_color=ACCENT, hover_color=ACCENT, text_color=TEXT_PRIMARY
			)
			self._btn_search_mode.configure(
				fg_color='transparent', hover_color=SURFACE3, text_color=TEXT_SECONDARY
			)
			self.entry_barcode.configure(placeholder_text='')
			self._close_dropdown()
		else:
			self._btn_search_mode.configure(
				fg_color=ACCENT, hover_color=ACCENT, text_color=TEXT_PRIMARY
			)
			self._btn_scan_mode.configure(
				fg_color='transparent', hover_color=SURFACE3, text_color=TEXT_SECONDARY
			)
			self.entry_barcode.configure(placeholder_text='')
		self.entry_barcode.focus()

	def _update_dropdown(self):
		self._barcode_timer = None
		q = self.entry_barcode.get().strip().lower()
		if not q:
			self._close_dropdown()
			return
		matches = [
			v
			for v in self.db_variants
			if q in (v.get('name') or '').lower() or q in str(v.get('barcode') or '')
		][:10]
		if matches:
			self._open_dropdown(matches)
		else:
			self._close_dropdown()

	def _open_dropdown(self, matches: list):
		for w in self._dropdown_frame.winfo_children():
			w.destroy()
		self._dropdown_items = matches

		for i, v in enumerate(matches):
			price_text = f'${float(v.get("selling_price", 0)):.2f}'
			if v.get('selling_price_b'):
				price_text += f'  💼 ${float(v.get("selling_price_b")):.2f}'
			row = ctk.CTkFrame(
				self._dropdown_frame,
				fg_color=SURFACE2 if i % 2 == 0 else SURFACE3,
				corner_radius=0,
			)
			row.pack(fill='x')
			ctk.CTkButton(
				row,
				text=f'{v.get("name", "")}   {price_text}   Stock: {v.get("total_stock", 0)}',
				fg_color='transparent',
				hover_color=ACCENT_DIM,
				text_color=TEXT_PRIMARY,
				font=FONT_BODY,
				height=34,
				anchor='w',
				corner_radius=0,
				command=lambda var=v: self._select_from_dropdown(var),
			).pack(fill='x', padx=4, pady=1)

		if not self._dropdown_frame.winfo_ismapped():
			self._dropdown_frame.pack(
				fill='x', padx=10, pady=(0, 2), before=self._customer_row_ref
			)

	def _close_dropdown(self):
		self._dropdown_items = []
		if hasattr(self, '_dropdown_frame') and self._dropdown_frame.winfo_ismapped():
			self._dropdown_frame.pack_forget()

	def _select_from_dropdown(self, variant):
		if self._barcode_timer is not None:
			self.after_cancel(self._barcode_timer)
			self._barcode_timer = None
		qty_str = self.qty_entry.get()
		self.entry_barcode.delete(0, 'end')
		self._close_dropdown()
		self._add_variant_to_cart(variant, qty_str)

	def _select_first_dropdown_item(self):
		if getattr(self, '_dropdown_items', []):
			self._select_from_dropdown(self._dropdown_items[0])
		else:
			self.add_by_barcode()

	def _on_search_entry_focus_out(self, event=None):
		if self._search_mode == 'search':
			self.after(150, self._close_dropdown)

	def add_by_barcode(self, event=None):
		if getattr(self, '_is_loading_data', False):
			self.after(100, self.add_by_barcode)
			return

		raw_code = self.entry_barcode.get().strip()
		if not raw_code:
			return

		is_scale_barcode = False
		scale_price = Decimal('0.0')
		search_code = raw_code.lstrip('0') or '0'

		if len(raw_code) == 13 and raw_code.startswith('20'):
			plu_code = str(int(raw_code[2:7]))
			scale_price = Decimal(raw_code[7:12])
			search_code = plu_code
			is_scale_barcode = True

		found_variant = next(
			(v for v in self.db_variants if str(v.get('barcode')) == search_code), None
		)

		if not found_variant and not is_scale_barcode and self._search_mode != 'scan':
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
		base_price = Decimal(str(found_variant.get('selling_price', 0.0)))
		total_stock = Decimal(str(found_variant.get('total_stock', 0)))
		current_cart_qty = self._get_qty_in_cart(variant_id)

		if is_scale_barcode:
			if base_price == Decimal('0'):
				self._set_msg('⚠ Producto de balanza con precio $0', RED_TEXT)
				self.entry_barcode.delete(0, 'end')
				return
			qty_to_add = scale_price / base_price
			unit_price = self._get_list_price(found_variant)
			subtotal = unit_price * qty_to_add
			product_disc_pct = Decimal('0')
			using_list_b = self._active_price_list == 'B' and found_variant.get(
				'selling_price_b'
			)
			total_qty = current_cart_qty + qty_to_add
		else:
			qty_to_add = Decimal('1')
			total_qty = current_cart_qty + qty_to_add
			list_base = self._get_list_price(found_variant)
			unit_price, product_disc_pct, _disc_src = self._apply_product_discount(
				found_variant, list_base
			)
			using_list_b = self._active_price_list == 'B' and found_variant.get(
				'selling_price_b'
			)
			subtotal = unit_price * total_qty

		stock_warning = total_qty > total_stock

		display_name = name
		if product_disc_pct > Decimal('0'):
			display_name = f'🏷️ -{product_disc_pct:.4g}% {name}'
		elif using_list_b:
			display_name = f'💼 {name}'

		existing_item = next(
			(i for i in self.cart if i.get('variant_id') == variant_id), None
		)

		if existing_item and not is_scale_barcode:
			existing_item['qty'] = total_qty
			existing_item['price'] = unit_price
			existing_item['product_disc_pct'] = product_disc_pct
			existing_item['subtotal'] = subtotal

			qty_visual = (
				f'{int(total_qty)}' if total_qty % 1 == 0 else f'{total_qty:.3f}'
			)
			self.tree.item(
				existing_item['tree_id'],
				values=(
					display_name,
					qty_visual,
					f'${unit_price:.2f}',
					f'${subtotal:.2f}',
				),
			)
			self._flash_new_item(
				existing_item['tree_id'],
				self.tree.item(existing_item['tree_id'], 'tags')[0],
			)
		else:
			subtotal = unit_price * qty_to_add
			qty_visual = (
				f'{int(qty_to_add)}' if qty_to_add % 1 == 0 else f'{qty_to_add:.3f}'
			)
			alt_tag = 'odd' if len(self.tree.get_children()) % 2 == 0 else 'even'

			item_id = self.tree.insert(
				'',
				'end',
				values=(
					display_name,
					qty_visual,
					f'${unit_price:.2f}',
					f'${subtotal:.2f}',
				),
				tags=(alt_tag,),
			)
			self.cart.append(
				{
					'tree_id': item_id,
					'variant_id': variant_id,
					'desc': display_name,
					'base_price': base_price,
					'price': unit_price,
					'product_disc_pct': product_disc_pct,
					'qty': qty_to_add,
					'subtotal': subtotal,
				}
			)
			self._flash_new_item(item_id, alt_tag)

		self.update_total()
		self.entry_barcode.delete(0, 'end')

		if stock_warning:
			self._set_msg(f'⚠ Stock superado ({name})', ORANGE_TEXT)
		elif product_disc_pct > Decimal('0'):
			self._set_msg(f'🏷️ {name} — Descuento -{product_disc_pct:.4g}%', ORANGE_TEXT)
		elif using_list_b:
			self._set_msg(f'💼 {name} — Precio Mayorista', ORANGE_TEXT)
		else:
			self._set_msg(f'✓  {name}')

	def add_from_touch(self, variant_id):
		if getattr(self, '_is_loading_data', False):
			return
		found = next(
			(v for v in self.db_variants if v['variant_id'] == variant_id), None
		)
		if not found:
			return

		qty_to_add = Decimal('1')
		total_stock = Decimal(str(found.get('total_stock', 0)))
		current_cart_qty = self._get_qty_in_cart(variant_id)
		total_qty = current_cart_qty + qty_to_add

		stock_warning = total_qty > total_stock

		base_price = self._get_list_price(found)
		name = found.get('name')
		price, product_disc_pct, _disc_src = self._apply_product_discount(
			found, base_price
		)
		using_list_b = self._active_price_list == 'B' and found.get('selling_price_b')

		display_name = name
		if product_disc_pct > Decimal('0'):
			display_name = f'🏷️ -{product_disc_pct:.4g}% {name}'
		elif using_list_b:
			display_name = f'💼 {name}'

		existing_item = next(
			(i for i in self.cart if i.get('variant_id') == variant_id), None
		)

		if existing_item:
			existing_item['qty'] = total_qty
			existing_item['price'] = price
			existing_item['product_disc_pct'] = product_disc_pct
			existing_item['subtotal'] = price * total_qty

			qty_visual = (
				f'{int(total_qty)}' if total_qty % 1 == 0 else f'{total_qty:.3f}'
			)
			self.tree.item(
				existing_item['tree_id'],
				values=(
					display_name,
					qty_visual,
					f'${price:.2f}',
					f'${existing_item["subtotal"]:.2f}',
				),
			)
			self._flash_new_item(
				existing_item['tree_id'],
				self.tree.item(existing_item['tree_id'], 'tags')[0],
			)
		else:
			subtotal = price * qty_to_add
			alt_tag = 'odd' if len(self.tree.get_children()) % 2 == 0 else 'even'
			item_id = self.tree.insert(
				'',
				'end',
				values=(display_name, '1', f'${price:.2f}', f'${subtotal:.2f}'),
				tags=(alt_tag,),
			)

			self.cart.append(
				{
					'tree_id': item_id,
					'variant_id': variant_id,
					'desc': display_name,
					'price': price,
					'base_price': base_price,
					'product_disc_pct': product_disc_pct,
					'qty': qty_to_add,
					'subtotal': subtotal,
				}
			)
			self._flash_new_item(item_id, alt_tag)

		self.update_total()

		if stock_warning:
			self._set_msg(f'⚠ Stock superado ({name})', ORANGE_TEXT)
		elif product_disc_pct > Decimal('0'):
			self._set_msg(f'🏷️ Descuento -{product_disc_pct:.4g}% · {name}', ORANGE_TEXT)
		elif using_list_b:
			self._set_msg(f'💼 {name} — Mayorista', ORANGE_TEXT)
		else:
			self._set_msg(f'✓ Agregado: {name}')

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
			self._set_msg('⚠ Ingresá números válidos', RED_TEXT)
			return

		subtotal = price * qty
		visual_desc = f'*(Libre)* {desc}'
		qty_visual = f'{int(qty)}' if qty % 1 == 0 else f'{qty:.2f}'
		alt_tag = 'odd' if len(self.tree.get_children()) % 2 == 0 else 'even'

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
				'price': price,
				'qty': qty,
				'subtotal': subtotal,
			}
		)

		self._flash_new_item(item_id, alt_tag)
		self.update_total()

		self.entry_fast_desc.delete(0, 'end')
		self.entry_fast_price.delete(0, 'end')
		self.entry_fast_qty.delete(0, 'end')
		self.entry_fast_qty.insert(0, '1')
		self.entry_barcode.focus()

	def remove_from_cart(self, event=None):
		self.lbl_msg.configure(text='')
		selected_item = self.tree.selection()
		if not selected_item:
			return

		for item_id in selected_item:
			if item_id in self._flash_timers:
				self.after_cancel(self._flash_timers.pop(item_id))
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

		if hasattr(self, '_lbl_item_count'):
			count = len(self.cart)
			self._lbl_item_count.configure(
				text=f'{count} ítem{"s" if count != 1 else ""}'
			)

		raw = sum(
			(item.get('subtotal', Decimal('0')) for item in self.cart), Decimal('0.0')
		)

		if self._discount_pct > Decimal('0') and raw > Decimal('0'):
			disc = (raw * self._discount_pct / Decimal('100')).quantize(Decimal('0.01'))
		else:
			disc = Decimal('0.0')

		self._discount_amount = disc
		final = raw - disc

		self._lbl_subtotal.configure(text=fmt_price(float(raw)))
		self.lbl_total.configure(text=fmt_price(float(final)))

		if disc > Decimal('0'):
			pct_str = f'{self._discount_pct:.4g}%'
			self._lbl_disc_label.configure(text=f'DESCUENTO  ({pct_str})')
			self._lbl_disc_value.configure(text=f'-{fmt_price(float(disc))}')
			self._disc_row.pack(fill='x', after=self._lbl_subtotal.master)
			self._divider_total.pack(fill='x', pady=(4, 0), after=self._disc_row)
		else:
			self._disc_row.pack_forget()
			self._divider_total.pack_forget()

		if hasattr(self, '_lbl_wholesale_badge'):
			disc_items = [
				i
				for i in self.cart
				if i.get('product_disc_pct', Decimal('0')) > Decimal('0')
			]
			list_b_items = [i for i in self.cart if i.get('desc', '').startswith('💼')]
			msgs = []
			if disc_items:
				ahorro_disc = sum(
					(i['base_price'] - i['price']) * i['qty'] for i in disc_items
				)
				msgs.append(
					f'🏷️ Desc. producto · Ahorro: {fmt_price(float(ahorro_disc))}'
				)
			if list_b_items:
				msgs.append('💼 Mayorista')
			if msgs:
				self._lbl_wholesale_badge.configure(text='  ·  '.join(msgs))
				self._lbl_wholesale_badge.pack(fill='x', padx=4, pady=(0, 4))
			else:
				self._lbl_wholesale_badge.pack_forget()

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
			for timer in self._flash_timers.values():
				self.after_cancel(timer)
			self._flash_timers.clear()
			for item in self.tree.get_children():
				self.tree.delete(item)
			self._set_discount_pct(Decimal('0'))
			self.update_total()
			self._set_msg('Venta anulada.', RED_TEXT)
			self.entry_barcode.focus()

	# =========================================================
	# POP-UP DE COBRO Y EVENTOS
	# =========================================================
	def process_sale(self):
		if (
			hasattr(self, 'popup')
			and self.popup is not None
			and self.popup.winfo_exists()
		):
			self.popup.focus()
			return

		if not self.cart:
			self._set_msg('⚠ Agregá productos antes de cobrar', RED_TEXT)
			return

		from utils.settings_manager import fmt_price

		raw_total = sum(
			(item.get('subtotal', Decimal('0')) for item in self.cart), Decimal('0.0')
		)
		self._discount_amount = (
			(raw_total * self._discount_pct / Decimal('100')).quantize(Decimal('0.01'))
			if self._discount_pct > Decimal('0')
			else Decimal('0.0')
		)
		self.current_total = raw_total - self._discount_amount
		self.customer_name = self.customers_combo.get()
		self._payment_method = 'Efectivo'

		self.popup = ctk.CTkToplevel(self)
		self.popup.title('Cobrar Venta')
		self.popup.configure(fg_color=SURFACE2)
		self.popup.attributes('-topmost', True)
		self.popup.grab_set()
		self.popup.update_idletasks()

		pw = 480
		self.popup.bind('<Escape>', lambda e: self.popup.destroy())
		self._render_popup_ui(pw, 0, raw_total, fmt_price)
		self.popup.update_idletasks()
		ph = min(
			self.popup.winfo_reqheight(),
			self.winfo_toplevel().winfo_screenheight() - 60,
		)
		rx = self.winfo_rootx() + (self.winfo_width() - pw) // 2
		ry = max(10, self.winfo_rooty() + (self.winfo_height() - ph) // 2)
		self.popup.geometry(f'{pw}x{ph}+{rx}+{ry}')

	def _render_popup_ui(self, pw, ph, raw_total, fmt_price):
		card = ctk.CTkFrame(
			self.popup,
			fg_color=SURFACE3,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		card.pack(fill='x', padx=20, pady=(16, 10))
		ci = ctk.CTkFrame(card, fg_color='transparent')
		ci.pack(fill='x', padx=14, pady=10)

		item_count, total_qty = (
			len(self.cart),
			sum(i.get('qty', Decimal('0')) for i in self.cart),
		)
		qty_str = f'{int(total_qty)}' if total_qty % 1 == 0 else f'{total_qty:.2f}'
		ctk.CTkLabel(
			ci,
			text=f'{item_count} prod.  ·  {qty_str} unid.',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', pady=(0, 6))

		if self._discount_amount > Decimal('0'):
			r = ctk.CTkFrame(ci, fg_color='transparent')
			r.pack(fill='x')
			ctk.CTkLabel(
				r, text='Subtotal', font=FONT_BODY, text_color=TEXT_MUTED, anchor='w'
			).pack(side='left')
			ctk.CTkLabel(
				r,
				text=fmt_price(float(raw_total)),
				font=FONT_BODY,
				text_color=TEXT_MUTED,
				anchor='e',
			).pack(side='right')

			rd = ctk.CTkFrame(ci, fg_color='transparent')
			rd.pack(fill='x')
			ctk.CTkLabel(
				rd,
				text=f'Descuento {self._discount_pct:.4g}%',
				font=FONT_BODY_BOLD,
				text_color=RED_TEXT,
				anchor='w',
			).pack(side='left')
			ctk.CTkLabel(
				rd,
				text=f'-{fmt_price(float(self._discount_amount))}',
				font=FONT_BODY_BOLD,
				text_color=RED_TEXT,
				anchor='e',
			).pack(side='right')
			ctk.CTkFrame(ci, height=1, fg_color=BORDER).pack(fill='x', pady=(6, 4))

		tr = ctk.CTkFrame(ci, fg_color='transparent')
		tr.pack(fill='x')
		ctk.CTkLabel(
			tr, text='TOTAL', font=FONT_BODY_BOLD, text_color=TEXT_SECONDARY, anchor='w'
		).pack(side='left')
		ctk.CTkLabel(
			tr,
			text=fmt_price(float(self.current_total)),
			font=FONT_TITLE,
			text_color=GREEN_TEXT,
			anchor='e',
		).pack(side='right')

		if self.customer_name and self.customer_name != 'Consumidor Final':
			ctk.CTkLabel(
				ci,
				text=f'📋  {self.customer_name}',
				font=FONT_BODY_BOLD,
				text_color=ACCENT_TEXT,
				anchor='w',
			).pack(anchor='w', pady=(6, 0))

		ctk.CTkLabel(
			self.popup,
			text='MÉTODO DE PAGO',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(2, 4))
		methods_grid = ctk.CTkFrame(self.popup, fg_color='transparent')
		methods_grid.pack(fill='x', padx=20, pady=(0, 10))
		methods_grid.grid_columnconfigure((0, 1), weight=1)

		self._pay_btns = {}
		for i, (icon, method) in enumerate([
			('💵', 'Efectivo'),
			('💳', 'Tarjeta'),
			('🏦', 'Transferencia'),
			('📱', 'QR'),
		]):
			row, col = divmod(i, 2)
			is_active = method == 'Efectivo'
			btn = ctk.CTkButton(
				methods_grid,
				text=f'{icon}  {method}',
				font=FONT_LABEL_BOLD,
				height=40,
				corner_radius=8,
				fg_color=ACCENT_DIM if is_active else SURFACE3,
				hover_color=ACCENT_DIM,
				text_color=ACCENT_TEXT if is_active else TEXT_SECONDARY,
				border_width=1,
				border_color=ACCENT if is_active else BORDER,
				command=lambda m=method: self._select_payment(m),
			)
			btn.grid(row=row, column=col, sticky='ew', padx=2, pady=2)
			self._pay_btns[method] = btn

		self._cash_section = ctk.CTkFrame(self.popup, fg_color='transparent')
		self._cash_section.pack(fill='x', padx=20, pady=(0, 6))
		ctk.CTkLabel(
			self._cash_section,
			text='Monto recibido ($)',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w')

		self.entry_paid = ctk.CTkEntry(
			self._cash_section,
			font=FONT_AMOUNT,
			justify='center',
			fg_color=SURFACE3,
			border_color=ACCENT,
			border_width=2,
			text_color=TEXT_PRIMARY,
			height=46,
		)
		self.entry_paid.pack(fill='x', pady=(4, 6))
		self.entry_paid.insert(0, f'{float(self.current_total):.2f}')
		self.entry_paid.select_range(0, 'end')
		self.entry_paid.bind('<KeyRelease>', self._calculate_change)
		self.entry_paid.bind('<FocusIn>', self._select_all_text)
		self.entry_paid.bind('<Return>', lambda e: self._confirm_and_save(False))

		self._vuelto_box = ctk.CTkFrame(
			self._cash_section,
			fg_color=SURFACE3,
			corner_radius=8,
			border_width=1,
			border_color=BORDER,
		)
		self._vuelto_box.pack(fill='x')
		self.lbl_change = ctk.CTkLabel(
			self._vuelto_box,
			text='VUELTO  $0,00',
			font=FONT_AMOUNT_BOLD,
			text_color=GREEN_TEXT,
		)
		self.lbl_change.pack(pady=10)
		self._calculate_change()

		mixto_frame = ctk.CTkFrame(
			self.popup,
			fg_color=SURFACE3,
			corner_radius=8,
			border_width=1,
			border_color=BORDER,
		)
		mixto_frame.pack(fill='x', padx=20, pady=(0, 8))
		mx = ctk.CTkFrame(mixto_frame, fg_color='transparent')
		mx.pack(fill='x', padx=10, pady=8)
		mx_top = ctk.CTkFrame(mx, fg_color='transparent')
		mx_top.pack(fill='x')

		self._mixto_var = ctk.BooleanVar(value=False)
		ctk.CTkSwitch(
			mx_top,
			text='Pago Mixto',
			variable=self._mixto_var,
			font=FONT_SMALL_BOLD,
			text_color=TEXT_MUTED,
			fg_color=SURFACE2,
			progress_color=ACCENT,
			command=self._toggle_mixto,
		).pack(side='left')

		self.combo_payment_2 = ctk.CTkComboBox(
			mx_top,
			values=['Transferencia', 'Tarjeta', 'QR Billetera', 'Efectivo'],
			fg_color=SURFACE2,
			border_color=BORDER,
			button_color=SURFACE4,
			button_hover_color=ACCENT,
			text_color=TEXT_MUTED,
			font=FONT_SMALL,
			height=28,
			width=140,
			state='disabled',
		)
		self.combo_payment_2.set('Transferencia')
		self.combo_payment_2.pack(side='left', padx=(8, 4))

		self.entry_amount_2 = ctk.CTkEntry(
			mx_top,
			placeholder_text='Monto ($)',
			font=FONT_SMALL,
			justify='center',
			fg_color=SURFACE2,
			border_color=BORDER,
			text_color=TEXT_MUTED,
			height=28,
			width=90,
			state='disabled',
		)
		self.entry_amount_2.pack(side='left')
		self.entry_amount_2.bind('<KeyRelease>', self._on_amount2_change)
		self.entry_amount_2.bind('<FocusIn>', self._select_all_text)

		self._lbl_amount_1_auto = ctk.CTkLabel(
			mx, text='', font=FONT_SMALL_BOLD, text_color=GREEN_TEXT, anchor='e'
		)
		self._lbl_amount_1_auto.pack(fill='x', pady=(4, 0))

		self.lbl_error_popup = ctk.CTkLabel(
			self.popup, text='', text_color=RED_TEXT, font=FONT_NAV
		)
		self.lbl_error_popup.pack(pady=(2, 0))

		self.btn_confirm_pay = ctk.CTkButton(
			self.popup,
			text='✅  CONFIRMAR COBRO  [Enter]',
			fg_color=GREEN,
			hover_color=GREEN_HOVER,
			text_color=TEXT_PRIMARY,
			height=50,
			font=FONT_TITLE_SM,
			corner_radius=10,
			command=lambda: self._confirm_and_save(False),
		)
		self.btn_confirm_pay.pack(fill='x', padx=20, pady=(4, 4))
		self.popup.bind('<Return>', lambda e: self._confirm_and_save(False))

		if self.customer_name != 'Consumidor Final':
			ctk.CTkButton(
				self.popup,
				text='📝  Anotar como Fiado',
				fg_color=SURFACE3,
				hover_color=SURFACE4,
				text_color=ORANGE_TEXT,
				font=FONT_BODY_BOLD,
				border_width=1,
				border_color=ORANGE,
				height=38,
				corner_radius=8,
				command=lambda: self._confirm_and_save(True),
			).pack(fill='x', padx=20, pady=(0, 4))

		ctk.CTkButton(
			self.popup,
			text='⬅  Volver  (Esc)',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			font=FONT_NAV,
			height=32,
			corner_radius=8,
			command=self.popup.destroy,
		).pack(fill='x', padx=20)
		self.entry_paid.focus()

	def _select_payment(self, method: str):
		self._payment_method = method
		for m, btn in self._pay_btns.items():
			active = m == method
			btn.configure(
				fg_color=ACCENT_DIM if active else SURFACE3,
				text_color=ACCENT_TEXT if active else TEXT_SECONDARY,
				border_color=ACCENT if active else BORDER,
			)
		is_cash = method == 'Efectivo'
		if not self._mixto_var.get():
			self.entry_paid.configure(
				state='normal' if is_cash else 'disabled',
				fg_color=SURFACE3 if is_cash else SURFACE2,
				border_color=ACCENT if is_cash else BORDER,
				border_width=2 if is_cash else 1,
			)
			self._calculate_change()

	def _calculate_change(self, event=None):
		is_cash = getattr(self, '_payment_method', 'Efectivo') == 'Efectivo'
		mixto_on = getattr(self, '_mixto_var', None) and self._mixto_var.get()

		if not is_cash and not mixto_on:
			if hasattr(self, 'lbl_change'):
				self.lbl_change.configure(text='Sin vuelto', text_color=TEXT_MUTED)
			if hasattr(self, '_vuelto_box'):
				self._vuelto_box.configure(fg_color=SURFACE2, border_color=BORDER)
			return

		paid_str = self.entry_paid.get().strip().replace(',', '.')
		if not paid_str:
			if hasattr(self, 'lbl_change'):
				self.lbl_change.configure(text='VUELTO  $0,00', text_color=GREEN_TEXT)
			if hasattr(self, '_vuelto_box'):
				self._vuelto_box.configure(fg_color=SURFACE3, border_color=BORDER)
			return

		try:
			paid = Decimal(paid_str)
			change = paid - self.current_total
			if change < Decimal('0.0'):
				if hasattr(self, 'lbl_change'):
					self.lbl_change.configure(
						text=f'⚠  FALTAN  ${abs(change):,.2f}', text_color=RED_TEXT
					)
				if hasattr(self, '_vuelto_box'):
					self._vuelto_box.configure(fg_color=RED_DIM, border_color=RED)
			else:
				if hasattr(self, 'lbl_change'):
					self.lbl_change.configure(
						text=f'VUELTO  ${change:,.2f}', text_color=GREEN_TEXT
					)
				if hasattr(self, '_vuelto_box'):
					self._vuelto_box.configure(fg_color=SURFACE3, border_color=BORDER)
		except (ValueError, InvalidOperation):
			if hasattr(self, 'lbl_change'):
				self.lbl_change.configure(text='Monto inválido', text_color=RED_TEXT)

	def _toggle_mixto(self):
		is_on = self._mixto_var.get()
		state = 'normal' if is_on else 'disabled'
		active_color = TEXT_PRIMARY if is_on else TEXT_MUTED

		self.combo_payment_2.configure(state=state, text_color=active_color)
		self.entry_amount_2.configure(state=state, text_color=active_color)

		if is_on:
			self.entry_paid.configure(
				state='disabled', fg_color=SURFACE2, border_color=BORDER, border_width=1
			)
			if hasattr(self, 'lbl_change'):
				self.lbl_change.configure(text='Sin vuelto', text_color=TEXT_MUTED)
			if hasattr(self, '_vuelto_box'):
				self._vuelto_box.configure(fg_color=SURFACE2, border_color=BORDER)
			self._on_amount2_change()
			try:
				self.entry_amount_2.focus()
			except tkinter.TclError:
				pass
		else:
			self._lbl_amount_1_auto.configure(text='')
			is_cash = getattr(self, '_payment_method', 'Efectivo') == 'Efectivo'
			self.entry_paid.configure(
				state='normal' if is_cash else 'disabled',
				fg_color=SURFACE3 if is_cash else SURFACE2,
				border_color=ACCENT if is_cash else BORDER,
				border_width=2 if is_cash else 1,
			)
			self._calculate_change()

	def _on_amount2_change(self, event=None):
		try:
			raw2 = self.entry_amount_2.get().strip().replace(',', '.')
			if not raw2:
				self.entry_amount_2.configure(border_color=BORDER)
				self._lbl_amount_1_auto.configure(text='')
				return

			amt2 = Decimal(raw2)
			amt1 = self.current_total - amt2
			method1 = getattr(self, '_payment_method', 'Efectivo')

			if amt1 < Decimal('0'):
				self.entry_amount_2.configure(border_color=RED)
				self._lbl_amount_1_auto.configure(
					text='⚠ El monto excede el total', text_color=RED_TEXT
				)
			else:
				self.entry_amount_2.configure(border_color=BORDER)
				self._lbl_amount_1_auto.configure(
					text=f'{method1}: ${amt1:,.2f}', text_color=GREEN_TEXT
				)
		except (ValueError, InvalidOperation):
			self.entry_amount_2.configure(border_color=RED)
			self._lbl_amount_1_auto.configure(
				text='⚠ Monto inválido', text_color=RED_TEXT
			)

	def _confirm_and_save(self, is_fiado=False):
		if (
			hasattr(self, 'btn_confirm_pay')
			and self.btn_confirm_pay.cget('state') == 'disabled'
		):
			return
		if hasattr(self, 'btn_confirm_pay'):
			self.btn_confirm_pay.configure(text='⏳ Procesando...', state='disabled')
			self.popup.update()

		payment_method = getattr(self, '_payment_method', 'Efectivo')
		payment_method_2, amount_method_2 = None, None

		if getattr(self, '_mixto_var', None) and self._mixto_var.get() and not is_fiado:
			payment_method_2 = self.combo_payment_2.get()
			raw2 = self.entry_amount_2.get().strip().replace(',', '.')
			try:
				amount_method_2 = Decimal(raw2) if raw2 else Decimal('0')
				limit = self.current_total - Decimal('0.01')
				if (
					amount_method_2 <= Decimal('0')
					or amount_method_2 >= self.current_total
				):
					self.lbl_error_popup.configure(
						text=f'El monto 2 debe ser entre $0.01 y ${limit:,.2f}'
					)
					if hasattr(self, 'btn_confirm_pay'):
						self.btn_confirm_pay.configure(
							text='✅  CONFIRMAR COBRO', state='normal'
						)
					return
			except (ValueError, InvalidOperation):
				self.lbl_error_popup.configure(
					text='Monto inválido para el segundo método'
				)
				if hasattr(self, 'btn_confirm_pay'):
					self.btn_confirm_pay.configure(
						text='✅  CONFIRMAR COBRO', state='normal'
					)
				return
			if payment_method_2.lower() == payment_method.lower():
				self.lbl_error_popup.configure(
					text='Los dos métodos no pueden ser iguales'
				)
				if hasattr(self, 'btn_confirm_pay'):
					self.btn_confirm_pay.configure(
						text='✅  CONFIRMAR COBRO', state='normal'
					)
				return
		elif not is_fiado and payment_method == 'Efectivo':
			try:
				paid_str = self.entry_paid.get().strip().replace(',', '.')
				paid = Decimal(paid_str) if paid_str else self.current_total
				if paid < self.current_total:
					self.lbl_error_popup.configure(text='El pago es menor al total')
					if hasattr(self, 'btn_confirm_pay'):
						self.btn_confirm_pay.configure(
							text='✅  CONFIRMAR COBRO', state='normal'
						)
					return
				self._paid_amount = paid
			except (ValueError, InvalidOperation):
				self.lbl_error_popup.configure(text='Monto inválido')
				if hasattr(self, 'btn_confirm_pay'):
					self.btn_confirm_pay.configure(
						text='✅  CONFIRMAR COBRO', state='normal'
					)
				return
		else:
			self._paid_amount = None

		customer_id = (
			self.customer_map.get(self.customer_name, {}).get('id')
			if self.customer_name in self.customer_map
			else None
		)

		amount_method_2_float = float(amount_method_2) if amount_method_2 else None
		paid_amount_float = float(self._paid_amount) if self._paid_amount else None

		self.finalize_sale(
			customer_id,
			is_fiado,
			payment_method,
			payment_method_2,
			amount_method_2_float,
			paid_amount_float,
		)

	def finalize_sale(
		self,
		customer_id,
		is_fiado,
		payment_method,
		payment_method_2=None,
		amount_method_2=None,
		paid_amount=None,
	):
		tenant_id, user_id = self.ctx.tenant_id, self.ctx.user_id

		# Limpiamos CUALQUIER Decimal antes de enviarlo al backend para prevenir TypeErrors en json.dumps
		clean_cart = []
		for i in self.cart:
			cleaned = i.copy()
			for key, val in cleaned.items():
				if isinstance(val, Decimal):
					cleaned[key] = float(val)
			clean_cart.append(cleaned)

		success, msg = self.sales_ctrl.process_sale(
			tenant_id,
			user_id,
			clean_cart,
			customer_id,
			is_fiado,
			payment_method,
			discount_amount=float(self._discount_amount),
			payment_method_2=payment_method_2,
			amount_method_2=amount_method_2,
			paid_amount=paid_amount,
		)

		if success:
			if hasattr(self, 'popup') and self.popup and self.popup.winfo_exists():
				self.popup.destroy()
			self.show_toast(f'✓  {msg}', 'success')
			self.cart.clear()
			for item in self.tree.get_children():
				self.tree.delete(item)
			self._set_discount_pct(Decimal('0'))
			self.update_total()
			self.load_data()
			self.entry_barcode.focus()
		else:
			self.show_toast(msg, 'error')
			if hasattr(self, 'btn_confirm_pay') and self.btn_confirm_pay.winfo_exists():
				self.btn_confirm_pay.configure(
					text='✅  CONFIRMAR COBRO  [Enter]', state='normal'
				)

	# =========================================================
	# EVENTOS DOBLE CLIC Y VENTA LIBRE
	# =========================================================
	def _on_cart_double_click(self, event=None):
		sel = self.tree.selection()
		if not sel:
			return
		item_id = sel[0]
		cart_item = next((i for i in self.cart if i.get('tree_id') == item_id), None)
		if not cart_item:
			return

		dlg = ctk.CTkToplevel(self)
		dlg.title('Editar cantidad')
		dlg.configure(fg_color=SURFACE2)
		dlg.attributes('-topmost', True)
		dlg.grab_set()
		dlg.geometry('300x170')
		dlg.bind('<Escape>', lambda e: dlg.destroy())

		ctk.CTkLabel(
			dlg,
			text=cart_item.get('desc', ''),
			font=FONT_BODY_BOLD,
			text_color=TEXT_PRIMARY,
			wraplength=260,
			justify='center',
		).pack(pady=(16, 6), padx=16)

		entry_qty = ctk.CTkEntry(
			dlg,
			font=FONT_INPUT_LG,
			justify='center',
			fg_color=SURFACE3,
			border_color=ACCENT,
			text_color=TEXT_PRIMARY,
			height=46,
			border_width=2,
		)
		entry_qty.pack(fill='x', padx=20)
		entry_qty.insert(
			0,
			str(
				int(cart_item['qty']) if cart_item['qty'] % 1 == 0 else cart_item['qty']
			),
		)
		entry_qty.select_range(0, 'end')
		entry_qty.focus()

		def _apply():
			try:
				new_qty = Decimal(entry_qty.get().strip().replace(',', '.'))
				if new_qty <= Decimal('0'):
					raise ValueError
			except (ValueError, InvalidOperation):
				entry_qty.configure(border_color=RED)
				return

			variant_id = cart_item.get('variant_id')
			if variant_id:
				stock = Decimal(
					str(
						next(
							(
								v
								for v in self.db_variants
								if v['variant_id'] == variant_id
							),
							{},
						).get('total_stock', 0)
					)
				)
				other_qty = self._get_qty_in_cart(variant_id) - cart_item.get(
					'qty', Decimal('0')
				)

				if new_qty + other_qty > stock:
					self._set_msg('⚠ Stock superado al editar', ORANGE_TEXT)

			cart_item['qty'] = new_qty
			cart_item['subtotal'] = cart_item['price'] * new_qty
			qty_visual = f'{int(new_qty)}' if new_qty % 1 == 0 else f'{new_qty:.3f}'

			self.tree.item(
				item_id,
				values=(
					cart_item['desc'],
					qty_visual,
					f'${cart_item["price"]:.2f}',
					f'${cart_item["subtotal"]:.2f}',
				),
			)
			self.update_total()
			dlg.destroy()
			self.entry_barcode.focus()

		entry_qty.bind('<Return>', lambda e: _apply())
		ctk.CTkButton(
			dlg,
			text='✓  Aplicar',
			command=_apply,
			fg_color=ACCENT,
			hover_color=ACCENT_DIM,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY_BOLD,
			height=36,
			corner_radius=8,
		).pack(fill='x', padx=20, pady=8)

	def _open_venta_libre_popup(self):
		popup = ctk.CTkToplevel(self)
		popup.title('Venta Libre')
		popup.configure(fg_color=SURFACE2)
		popup.attributes('-topmost', True)
		popup.grab_set()
		popup.geometry('340x240')
		popup.bind('<Escape>', lambda e: popup.destroy())

		ctk.CTkLabel(
			popup, text='⚡  Venta Libre', font=FONT_HEADING, text_color=ORANGE_TEXT
		).pack(pady=(16, 8))
		entry_desc = ctk.CTkEntry(
			popup,
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		entry_desc.pack(fill='x', padx=20, pady=(2, 8))
		entry_desc.focus()

		row = ctk.CTkFrame(popup, fg_color='transparent')
		row.pack(fill='x', padx=20)
		entry_price = ctk.CTkEntry(
			row,
			placeholder_text='Precio ($)',
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		entry_price.pack(side='left', fill='x', expand=True, padx=(0, 6))
		entry_qty_vl = ctk.CTkEntry(
			row,
			placeholder_text='Cant.',
			width=70,
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
			justify='center',
		)
		entry_qty_vl.pack(side='left')
		entry_qty_vl.insert(0, '1')

		def _do_add():
			self.entry_fast_desc.delete(0, 'end')
			self.entry_fast_desc.insert(0, entry_desc.get())
			self.entry_fast_price.delete(0, 'end')
			self.entry_fast_price.insert(0, entry_price.get())
			self.entry_fast_qty.delete(0, 'end')
			self.entry_fast_qty.insert(0, entry_qty_vl.get())
			self.add_fast_to_cart()
			popup.destroy()

		entry_desc.bind('<Return>', lambda e: entry_price.focus())
		entry_price.bind('<Return>', lambda e: entry_qty_vl.focus())
		entry_qty_vl.bind('<Return>', lambda e: _do_add())
		ctk.CTkButton(
			popup,
			text='⚡  Agregar al Carrito',
			command=_do_add,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			font=FONT_BODY_BOLD,
			height=40,
			corner_radius=8,
		).pack(fill='x', padx=20, pady=12)

	# =========================================================
	# ATAJOS DE TECLADO SEGUROS
	# =========================================================
	def setup_shortcuts(self):
		top = self.winfo_toplevel()
		# Forma estándar y segura de registrar eventos en Tkinter sin cruzar identificadores.
		top.bind(
			'<F5>', lambda e: self.process_sale() if self.winfo_ismapped() else None
		)
		top.bind(
			'<F6>',
			lambda e: (
				self.entry_barcode.focus()
				if self.winfo_ismapped() and self.entry_barcode.winfo_exists()
				else None
			),
		)
		top.bind(
			'<F7>',
			lambda e: self._open_venta_libre_popup() if self.winfo_ismapped() else None,
		)
		top.bind(
			'<Delete>',
			lambda e: self.remove_from_cart() if self.winfo_ismapped() else None,
		)
		top.bind(
			'<Control-Delete>',
			lambda e: self.clear_entire_cart() if self.winfo_ismapped() else None,
		)

		self.bind(
			'<Destroy>', lambda e: self.destroy_custom() if e.widget is self else None
		)

	def destroy_custom(self):
		top = self.winfo_toplevel()
		for key in ('<F5>', '<F6>', '<F7>', '<Delete>', '<Control-Delete>'):
			try:
				top.unbind(key)
			except tkinter.TclError:
				pass

		if hasattr(self, '_touch_batch_timer') and self._touch_batch_timer:
			self.after_cancel(self._touch_batch_timer)
		if hasattr(self, '_barcode_timer') and self._barcode_timer:
			self.after_cancel(self._barcode_timer)
		if hasattr(self, '_msg_timer_id') and self._msg_timer_id:
			self.after_cancel(self._msg_timer_id)
		if hasattr(self, '_disc_border_timer') and self._disc_border_timer:
			self.after_cancel(self._disc_border_timer)

		for timer in getattr(self, '_flash_timers', {}).values():
			try:
				self.after_cancel(timer)
			except tkinter.TclError:
				pass
