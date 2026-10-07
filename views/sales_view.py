"""
views/sales_view.py
====================
Módulo de Ventas (POS).
Optimizado para alto rendimiento en mostrador.
Solucionados errores de precisión Decimal, cierres de ciclos asíncronos y serialización.
"""

import logging
import queue
import sys
import threading
import tkinter
from datetime import datetime
from decimal import Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk

import utils.settings_manager as _cfg_mgr
from controllers.cash_controller import CashController
from controllers.promo_controller import PromoController
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
	GREEN_DIM,
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

_beep_sem = threading.Semaphore(1)
if sys.platform == 'win32':
	import winsound as _winsound

	def _do_beep(freq: int, dur: int) -> None:
		if _beep_sem.acquire(blocking=False):
			try:
				_winsound.Beep(freq, dur)
			except Exception:
				pass
			finally:
				_beep_sem.release()
else:

	def _do_beep(freq: int, dur: int) -> None:  # no-op on non-Windows
		pass


logger = logging.getLogger(__name__)

_DISCOUNT_PRESETS = [5, 10, 15, 20]


class SalesView(BaseView):
	def __init__(self, master, ctx: AppContext, context_data=None):
		super().__init__(master, ctx)
		self._context_data = context_data
		self.sales_ctrl = SalesController(ctx.db_engine)
		self._cash_ctrl = CashController(ctx.db_engine)
		self.promo_ctrl = PromoController(ctx.db_engine)
		self._active_promos = []
		self.cart = []

		self._discount_pct = Decimal(0)
		self._discount_amount = Decimal(0)
		self._preset_btns: list = []
		self._paid_amount = None
		self._active_price_list = 'A'
		self._max_global_discount = Decimal(100 if ctx.is_admin else 20)

		self._cash_ready = False
		self._catalog_ok = False
		self._is_loading_data = False
		self._search_popup = None
		self._search_mode = 'scan'
		self._muted = False
		self._search_results_queue: queue.Queue = queue.Queue()
		self._search_request_id = 0
		self._catalog_results_queue: queue.Queue = queue.Queue()
		self._catalog_request_id = 0

		# Timers unificados
		self._flash_timers = {}
		self._barcode_timer = None
		self._msg_timer_id = None
		self._touch_batch_timer = None
		self._disc_border_timer = None
		self._search_poll_job = None
		self._catalog_poll_job = None
		self._checkout_poll_job = None
		self._checkout_results_queue = queue.Queue()
		self._saving = False

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

		self.schedule(50, self.load_data)
		self.setup_shortcuts()
		self._search_poll_job = self.after(75, self._poll_search_results)
		self._catalog_poll_job = self.after(75, self._poll_catalog_results)

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
		self.entry_barcode.bind('<Down>', lambda e: self._move_dropdown_selection(1))
		self.entry_barcode.bind('<Up>', lambda e: self._move_dropdown_selection(-1))
		self.entry_barcode.bind('<KeyRelease>', self._barcode_on_key)
		self.entry_barcode.bind('<FocusOut>', self._on_search_entry_focus_out)
		# Escape sobre el campo de búsqueda: limpia sin afectar el binding global del dashboard
		self.entry_barcode.bind('<Escape>', self._on_search_escape)
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
		self.qty_entry.bind('<Return>', self._barcode_on_enter)
		self.qty_entry.bind('<FocusIn>', self._select_all_text)

		self._btn_free_sale = ctk.CTkButton(
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
		)
		self._btn_free_sale.pack(side='left')
		if not self.ctx.is_admin:
			self._btn_free_sale.configure(
				state='disabled',
				text='⚡  Venta Libre (solo admin)',
				text_color=TEXT_MUTED,
			)

		self._btn_mute = ctk.CTkButton(
			bottom_search,
			text='🔔',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_SECONDARY,
			font=FONT_BODY_BOLD,
			height=34,
			width=40,
			corner_radius=8,
			command=self._toggle_mute,
		)
		self._btn_mute.pack(side='right')

		customer_row = ctk.CTkFrame(
			self.main_panel,
			fg_color=SURFACE3,
			corner_radius=8,
			border_width=1,
			border_color=BORDER,
		)
		customer_row.pack(fill='x', padx=10, pady=(0, 5))
		self._customer_row_ref = customer_row

		self._dropdown_frame = ctk.CTkScrollableFrame(
			self.main_panel,
			height=145,
			fg_color=SURFACE3,
			corner_radius=8,
			border_width=1,
			border_color=BORDER,
		)
		self._dropdown_items = []
		self._dropdown_query = None
		self._dropdown_index = 0
		self._dropdown_buttons = []

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
			state='readonly',
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
			state='disabled',
			command=self.remove_from_cart,
		)
		self.btn_remove.pack(side='left')
		self.tree.bind('<<TreeviewSelect>>', self._on_cart_select)
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
			command=self._confirm_clear_cart,
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
			state='disabled',
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
			placeholder_text=f'máx. {self._max_global_discount:.0f}%',
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
			command=lambda: self._set_discount_pct(Decimal(0)),
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
			sub_row,
			text=_cfg_mgr.fmt_price(0),
			font=FONT_SUBHEADING,
			text_color=TEXT_MUTED,
			anchor='e',
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
			inner,
			text=_cfg_mgr.fmt_price(0),
			font=FONT_DISPLAY,
			text_color=GREEN_TEXT,
			anchor='w',
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
		if not pct.is_finite():
			self._set_msg('Descuento inválido.', RED_TEXT)
			return
		if pct < Decimal(0) or pct > self._max_global_discount:
			self._set_msg(
				f'El descuento máximo para tu perfil es {self._max_global_discount:.0f}%.',
				RED_TEXT,
			)
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
			if not pct.is_finite():
				raise ValueError
			if pct < 0 or pct > self._max_global_discount:
				raise ValueError
			self._set_discount_pct(pct)
			self._entry_custom_disc.configure(border_color=BORDER)
		except (ValueError, InvalidOperation):
			self._entry_custom_disc.configure(border_color=RED)
			self._set_msg(
				f'Ingresá un descuento entre 0 y {self._max_global_discount}%.',
				RED_TEXT,
			)
			if self._disc_border_timer:
				self.after_cancel(self._disc_border_timer)
			self._disc_border_timer = self.schedule(
				1200, lambda: self._entry_custom_disc.configure(border_color=BORDER)
			)

	def _set_msg(self, text: str, color: str | None = None, persistent=False):
		self.lbl_msg.configure(
			text=text, text_color=color or GREEN_TEXT, wraplength=360, justify='left'
		)
		if self._msg_timer_id:
			try:
				self.after_cancel(self._msg_timer_id)
			except tkinter.TclError:
				pass
		self._msg_timer_id = None
		if not persistent and color in (None, GREEN_TEXT):
			self._msg_timer_id = self.schedule(
				3000, lambda: self.lbl_msg.configure(text='')
			)

	def _refresh_pay_state(self):
		ready = (
			bool(self.cart)
			and not self._is_loading_data
			and self._cash_ready
			and self._catalog_ok
		)
		self.btn_pay.configure(state='normal' if ready else 'disabled')

	@staticmethod
	def _positive_decimal(raw, *, money=False):
		try:
			value = Decimal(str(raw).strip().replace(',', '.'))
			precision = Decimal('.01') if money else Decimal('.0001')
			limit = Decimal('99999999.99') if money else Decimal('99999999.9999')
			if (
				not value.is_finite()
				or not Decimal(0) < value <= limit
				or value != value.quantize(precision)
			):
				raise ValueError
			return value
		except (InvalidOperation, ValueError, TypeError) as exc:
			raise ValueError(
				'Valor positivo requerido: precios hasta 2 decimales y cantidades hasta 4.'
			) from exc

	@staticmethod
	def _payment_amount(raw):
		try:
			value = Decimal(str(raw).strip().replace(',', '.'))
			if (
				not value.is_finite()
				or not Decimal(0) <= value <= Decimal('99999999.99')
				or value != value.quantize(Decimal('.01'))
			):
				raise ValueError
			return value
		except (InvalidOperation, ValueError, TypeError) as exc:
			raise ValueError(
				'Monto inválido: ingresá un importe con hasta 2 decimales.'
			) from exc

	def _reprice_cart(self):
		variants = {v['variant_id']: v for v in self.db_variants}
		for item in self.cart:
			variant = variants.get(item.get('variant_id'))
			if variant:
				base = self._get_list_price(variant)
				promo = self._find_promo_for_variant(variant)
				if promo:
					price, desc = self._apply_promo_price(
						promo, base, self._get_qty_in_cart(item['variant_id'])
					)
					pct = Decimal(0)
				else:
					price, pct, _source = self._apply_product_discount(variant, base)
					name = variant.get('name', 'Artículo')
					desc = (
						f'🏷️ -{pct:.4g}% {name}'
						if pct > 0
						else (
							f'💼 {name}'
							if self._active_price_list == 'B'
							and variant.get('selling_price_b') is not None
							else name
						)
					)
				item.update(
					base_price=base, price=price, desc=desc, product_disc_pct=pct
				)
			item['subtotal'] = (item['price'] * item['qty']).quantize(Decimal('.01'))
			self._render_cart_item(item)
		self.update_total()

	def _render_cart_item(self, item):
		qty = item['qty']
		qty_text = (
			format(qty, 'f').rstrip('0').rstrip('.') if qty % 1 else str(int(qty))
		)
		self.tree.item(
			item['tree_id'],
			values=(
				item['desc'],
				qty_text,
				_cfg_mgr.fmt_price(item['price']),
				_cfg_mgr.fmt_price(item['subtotal']),
			),
		)

	def _prepare_checkout(self):
		try:
			lines, total = self.sales_ctrl.quote_cart(
				self.ctx.tenant_id,
				self.cart,
				self._active_price_list,
				self._discount_pct,
				validate_stock=True,
			)
		except Exception as exc:
			logger.exception('No se pudo validar el carrito')
			self._set_msg(str(exc), RED_TEXT)
			return False
		old_total = (
			sum((i['subtotal'] for i in self.cart), Decimal(0)) - self._discount_amount
		)
		self.cart[:] = lines
		for line in lines:
			self._render_cart_item(line)
		self.update_total()
		if total != old_total:
			return self.confirm(
				f'Los precios se actualizaron. Total actual: {_cfg_mgr.fmt_price(total)}. ¿Continuar al cobro?',
				'Precios actualizados',
			)
		return True

	def _check_cash_status(self):
		try:
			session = self._cash_ctrl.get_active_session(
				self.ctx.tenant_id, self.ctx.user_id
			)
			self._cash_ready = bool(session) and not getattr(
				self.ctx, 'offline_mode', False
			)
			self.banner_caja.pack_forget()

			if getattr(self.ctx, 'offline_mode', False):
				self.banner_caja.configure(fg_color='#7D3C00', border_color='#A04000')
				for w in self.banner_caja.winfo_children():
					if isinstance(w, ctk.CTkLabel):
						w.configure(
							text='📴 Modo sin conexión · Solo lectura de catálogo',
							text_color='#F5CBA7',
						)
				self.banner_caja.pack(
					fill='x', padx=10, pady=(0, 4), before=self._table_wrap
				)
				self.btn_pay.configure(
					state='disabled',
					text='Caja deshabilitada',
					fg_color=SURFACE3,
					text_color=TEXT_MUTED,
				)
			elif not session:
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
			logger.warning('Cash status check failed: %s', e)
			self._cash_ready = False
			self._set_msg(
				'No se pudo verificar la caja. Reintentá antes de cobrar.', RED_TEXT
			)
		finally:
			self._refresh_pay_state()

	def load_data(self):
		if not self.winfo_exists():  # BUG 19: guard contra callback post-destroy
			return
		self._is_loading_data = True
		self._refresh_pay_state()
		self._catalog_request_id += 1
		request_id = self._catalog_request_id
		current_customer = (
			self.customers_combo.get() if hasattr(self, 'customers_combo') else None
		)
		tenant_id = self.ctx.tenant_id
		sales_ctrl, promo_ctrl = self.sales_ctrl, self.promo_ctrl
		self._set_msg('Actualizando catálogo…', TEXT_MUTED)

		def fetch_catalog():
			try:
				payload = (
					sales_ctrl.get_articles_for_sale(tenant_id),
					promo_ctrl.get_active_promos_now(tenant_id),
					sales_ctrl.get_customers(tenant_id),
				)
				error = None
			except Exception as exc:
				logger.exception('No se pudo cargar el catálogo de ventas')
				payload, error = ([], [], []), str(exc)
			self._catalog_results_queue.put(
				(request_id, current_customer, payload, error)
			)

		threading.Thread(target=fetch_catalog, daemon=True, name='SalesCatalog').start()

	def _poll_catalog_results(self):
		"""Aplica el catálogo desde Tk y descarta respuestas de recargas obsoletas."""
		self._catalog_poll_job = None
		if not self.winfo_exists():
			return
		try:
			while True:
				request_id, current_customer, payload, error = (
					self._catalog_results_queue.get_nowait()
				)
				if request_id != self._catalog_request_id:
					continue
				self._apply_catalog_payload(current_customer, *payload, error=error)
		except queue.Empty:
			pass
		self._catalog_poll_job = self.after(75, self._poll_catalog_results)

	def _apply_catalog_payload(
		self, current_customer, variants, promos, customers, error=None
	):
		try:
			if error:
				self._catalog_ok = False
				self._set_msg(
					'No se pudo actualizar el catálogo. Se conservan los datos previos.',
					ORANGE_TEXT,
				)
				return
			if self._touch_batch_timer:
				self.after_cancel(self._touch_batch_timer)
				self._touch_batch_timer = None
			self._catalog_ok = True
			self.db_variants = variants
			self._active_promos = promos
			self.customer_map = {
				customer.get('name'): customer for customer in customers
			}
			customer_names = list(self.customer_map)
			if 'Consumidor Final' not in customer_names:
				customer_names.insert(0, 'Consumidor Final')
			self.customers_combo.configure(values=customer_names)
			current_customer = self.customers_combo.get()
			self.customers_combo.set(
				current_customer
				if current_customer in customer_names
				else 'Consumidor Final'
			)
			if self.customers_combo.get() != current_customer:
				self._on_customer_changed()
			else:
				self._reprice_cart()

			for widget in self.touch_scroll.winfo_children():
				widget.destroy()
			self.touch_buttons.clear()
			shortcuts_enabled = _cfg_mgr.get('show_shortcuts_bar', True)
			self._touch_queue = [
				variant
				for variant in self.db_variants
				if shortcuts_enabled
				and (variant.get('is_combo') or variant.get('show_on_touch'))
			]
			self._touch_row, self._touch_col = 0, 0
			if not self._touch_queue:
				ctk.CTkLabel(
					self.touch_scroll,
					text=(
						'Accesos táctiles desactivados en Configuración.'
						if not shortcuts_enabled
						else 'Sin combos\nasignados'
					),
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
			self._check_cash_status()
			if self._context_data and 'restore_sale' in self._context_data:
				if self._load_restored_sale(self._context_data['restore_sale']):
					self._context_data = None
			else:
				if getattr(self, '_restored_notice', None):
					self._set_msg(self._restored_notice, ORANGE_TEXT, persistent=True)
				else:
					self._set_msg(
						'Catálogo actualizado.'
						if variants
						else 'No hay artículos activos en el catálogo.',
						GREEN_TEXT,
					)
		except Exception:
			logger.exception('Error al aplicar el catálogo')
			self._catalog_ok = False
			self._set_msg(
				'No se pudo mostrar el catálogo. Volvé a abrir Ventas para reintentar.',
				RED_TEXT,
			)
		finally:
			self._is_loading_data = False
			self._refresh_pay_state()

	def _render_touch_batch(self):
		if not self.winfo_exists() or not self._touch_queue:
			return

		chunk = self._touch_queue[:15]
		self._touch_queue = self._touch_queue[15:]

		low_threshold = _cfg_mgr.get('low_stock_threshold', 5)

		for v in chunk:
			stock = Decimal(str(v.get('total_stock', 0)))
			base_price = self._get_list_price(v)
			promo = self._find_promo_for_variant(v)
			if promo:
				price, _description = self._apply_promo_price(
					promo, base_price, Decimal(1)
				)
			else:
				price, _pct, _source = self._apply_product_discount(v, base_price)
			name = v.get('name', 'Promo')
			is_disabled = stock <= 0
			stock_text = format(stock.normalize(), 'f').replace('.', ',')

			if is_disabled:
				stock_label, stock_color = 'Sin stock', TEXT_MUTED
			elif stock <= low_threshold:
				stock_label, stock_color = f'Stock: {stock_text}', ORANGE_TEXT
			else:
				stock_label, stock_color = f'Stock: {stock_text}', TEXT_MUTED

			btn_frame = ctk.CTkFrame(
				self.touch_scroll,
				fg_color=SURFACE3 if is_disabled else ACCENT_DIM,
				corner_radius=8,
				border_width=1,
				border_color=BORDER,
				width=118,
				height=112,
			)
			btn_frame.grid(row=self._touch_row, column=self._touch_col, padx=4, pady=4)
			btn_frame.grid_propagate(False)

			inner = ctk.CTkFrame(btn_frame, fg_color='transparent')
			inner.place(relx=0.5, rely=0.5, anchor='center')

			lbl_name = ctk.CTkLabel(
				inner,
				text=name if len(name) <= 46 else name[:43] + '…',
				font=FONT_BODY_BOLD,
				text_color=TEXT_MUTED if is_disabled else ACCENT_TEXT,
				wraplength=108,
				justify='center',
			)
			lbl_name.pack()
			lbl_price = ctk.CTkLabel(
				inner,
				text=_cfg_mgr.fmt_price(price),
				font=FONT_SMALL,
				text_color=TEXT_MUTED if is_disabled else ACCENT_TEXT,
			)
			lbl_price.pack()
			lbl_stock = ctk.CTkLabel(
				inner, text=stock_label, font=FONT_LABEL, text_color=stock_color
			)
			lbl_stock.pack()

			if not is_disabled:

				def action(e, vid=v.get('variant_id')):
					self.add_from_touch(vid)

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
		"""Prepare every line before cancelling the original; never restore partially."""
		prepared = []
		try:
			variants = {v['variant_id']: v for v in self.db_variants}
			items = sale_data.get('items', [])
			if not items:
				raise ValueError('El ticket no contiene líneas recuperables.')
			for item in items:
				self._positive_decimal(item.get('quantity', 1))
				vid = item.get('variant_id')
				if vid is not None and vid not in variants:
					raise ValueError(
						f'No se puede recuperar {item.get("description", vid)}. El ticket original no se anuló.'
					)
				if vid is None:
					if not self.ctx.is_admin:
						raise ValueError(
							'El ticket contiene una venta libre que requiere administrador.'
						)
					self._positive_decimal(item.get('unit_price'), money=True)
			name = sale_data.get('customer_name', 'Consumidor Final')
			if name != 'Consumidor Final' and name not in self.customer_map:
				raise ValueError(
					'El cliente original ya no está disponible. El ticket no se anuló.'
				)
			self.customers_combo.set(name)
			self._on_customer_changed(name)
			prepared = [
				dict(
					variant_id=i.get('variant_id'),
					qty=self._positive_decimal(i.get('quantity', 1)),
					price=i.get('unit_price', 0),
					desc=i.get('description', 'Artículo'),
				)
				for i in items
			]
			prepared, _total = self.sales_ctrl.quote_cart(
				self.ctx.tenant_id, prepared, self._active_price_list
			)
			# Render every line before cancelling the original sale.
			for line in prepared:
				tag = 'odd' if len(self.cart) % 2 == 0 else 'even'
				line['tree_id'] = self.tree.insert('', 'end', tags=(tag,))
				self.cart.append(line)
				self._render_cart_item(line)
			self.update_total()
			if (self._context_data or {}).get('cancel_original_sale'):
				from controllers.returns_controller import ReturnsController

				ok, message = ReturnsController(self.ctx.db_engine).cancel_sale(
					self.ctx.tenant_id, sale_data['id'], self.ctx.user_id
				)
				if not ok:
					raise ValueError(message)
				self._context_data['cancel_original_sale'] = False
				# Cancellation returned inventory; refresh touch stock in a separate load.
				self.schedule(0, self.load_data)
			self._restored_notice = 'Ticket recuperado completo. Se usan precios vigentes; revisá descuentos y total antes de cobrar.'
			self._set_msg(self._restored_notice, ORANGE_TEXT, persistent=True)
			return True
		except Exception as exc:
			logger.exception('No se pudo restaurar el ticket')
			for line in prepared:
				if line.get('tree_id'):
					self.tree.delete(line['tree_id'])
					if line in self.cart:
						self.cart.remove(line)
			self.update_total()
			self._set_msg(str(exc), RED_TEXT, persistent=True)
			return False

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
		def _pct_active(pct, until):
			if not pct or pct <= 0:
				return Decimal(0)
			if until:
				if isinstance(until, str):
					try:
						until = datetime.fromisoformat(until)
					except Exception:
						return Decimal(0)
				if until < datetime.now():
					return Decimal(0)
			return Decimal(str(pct))

		prod_pct = _pct_active(
			variant.get('discount_pct', 0), variant.get('discount_until')
		)
		supp_pct = _pct_active(
			variant.get('supplier_discount_pct', 0),
			variant.get('supplier_discount_until'),
		)

		if prod_pct > Decimal(0):
			factor = Decimal(1) - (prod_pct / Decimal(100))
			return (base_price * factor).quantize(Decimal('0.01')), prod_pct, 'producto'
		if supp_pct > Decimal(0):
			factor = Decimal(1) - (supp_pct / Decimal(100))
			return (
				(base_price * factor).quantize(Decimal('0.01')),
				supp_pct,
				'distribuidor',
			)
		return base_price, Decimal(0), ''

	def _find_promo_for_variant(self, variant: dict) -> dict | None:
		"""Prioriza producto sobre categoría y resuelve empates de forma estable."""
		variant_id = variant.get('variant_id')
		category_id = variant.get('category_id')
		matches = [
			promo
			for promo in self._active_promos
			if self.promo_ctrl._is_active_now(promo)
			and (
				promo.get('variant_id') == variant_id
				or (
					not promo.get('variant_id')
					and promo.get('category_id') == category_id
				)
			)
		]
		return max(
			matches,
			key=lambda promo: (
				promo.get('variant_id') == variant_id,
				promo.get('updated_at') or promo.get('date_from'),
				promo.get('id', ''),
			),
			default=None,
		)

	def _apply_promo_price(
		self, promo: dict, base_price: Decimal, total_qty: Decimal
	) -> tuple[Decimal, str]:
		"""
		Dado una promo activa, retorna (precio_efectivo_por_unidad, etiqueta_para_carrito).
		Para NxM el precio varía con la cantidad total en carrito.
		"""
		ptype = promo.get('promo_type', '')
		name = promo.get('name', 'Promo')

		if ptype == 'pct':
			pct = Decimal(str(promo.get('discount_value', 0)))
			factor = Decimal(1) - (pct / Decimal(100))
			price = (base_price * factor).quantize(Decimal('0.01'))
			return price, f'🎯 -{pct:.4g}% {name}'

		elif ptype == 'nxm':
			buy = promo.get('buy_qty', 2)
			pay = promo.get('pay_qty', 1)
			price = self.promo_ctrl.calc_nxm_price(base_price, buy, pay, total_qty)
			return price, f'🎯 {buy}×{pay} {name}'

		elif ptype == 'fixed':
			price = Decimal(str(promo.get('discount_value', base_price))).quantize(
				Decimal('0.01')
			)
			return price, f'🎯 {_cfg_mgr.fmt_price(price)} {name}'

		return base_price, ''

	def _get_list_price(self, variant: dict) -> Decimal:
		if (
			self._active_price_list == 'B'
			and variant.get('selling_price_b') is not None
		):
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
						base_price = self._get_list_price(variant)
						promo = self._find_promo_for_variant(variant)
						if promo:
							price, _description = self._apply_promo_price(
								promo, base_price, Decimal(1)
							)
						else:
							price, _pct, _source = self._apply_product_discount(
								variant, base_price
							)
						lbl.configure(text=_cfg_mgr.fmt_price(price))
				except Exception:
					pass

		self._reprice_cart()

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
			if self._add_variant_to_cart(matches[0], self.qty_entry.get()):
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
		self._center_dialog(popup, 450, 350)
		popup.attributes('-topmost', True)
		popup.grab_set()
		popup.bind('<Escape>', lambda e: self._close_dialog(popup))

		ctk.CTkLabel(popup, text='Seleccione el artículo', font=FONT_HEADING).pack(
			pady=10
		)
		scroll = ctk.CTkScrollableFrame(popup, fg_color='transparent')
		scroll.pack(fill='both', expand=True, padx=15, pady=5)

		def _make_cmd(var):
			def select():
				if self._add_variant_to_cart(var, self.qty_entry.get()):
					popup.destroy()
					self._restore_scan_focus(force=True)

			return select

		for v in matches:
			base_price = self._get_list_price(v)
			promo = self._find_promo_for_variant(v)
			if promo:
				price, _description = self._apply_promo_price(
					promo, base_price, Decimal(1)
				)
			else:
				price, _pct, _source = self._apply_product_discount(v, base_price)
			btn = ctk.CTkButton(
				scroll,
				text=(
					f'{v.get("name", "")}  |  {_cfg_mgr.fmt_price(price)}  '
					f'|  Stock: {v.get("total_stock", 0)}'
				),
				font=FONT_BODY,
				height=36,
				fg_color=SURFACE3,
				hover_color=ACCENT_DIM,
				text_color=TEXT_PRIMARY,
				command=_make_cmd(v),
			)
			btn.pack(fill='x', pady=3)

	def _beep_ok(self):
		if not self._muted:
			threading.Thread(target=_do_beep, args=(1000, 80), daemon=True).start()

	def _beep_err(self):
		if not self._muted:
			threading.Thread(target=_do_beep, args=(400, 200), daemon=True).start()

	def _toggle_mute(self):
		self._muted = not self._muted
		self._btn_mute.configure(text='🔇' if self._muted else '🔔')

	def _add_variant_to_cart(self, variant, qty_str):
		try:
			qty = self._positive_decimal(qty_str)
			vid = variant['variant_id']
			existing = next((i for i in self.cart if i.get('variant_id') == vid), None)
			total_qty = self._positive_decimal(
				qty + (existing['qty'] if existing else Decimal(0))
			)
		except ValueError as exc:
			self._set_msg(str(exc), RED_TEXT)
			return False
		if existing:
			existing['qty'] = total_qty
		else:
			tag = 'odd' if len(self.cart) % 2 == 0 else 'even'
			tree_id = self.tree.insert('', 'end', tags=(tag,))
			self.cart.append(
				dict(
					tree_id=tree_id,
					variant_id=vid,
					desc=variant.get('name', 'Artículo'),
					qty=qty,
					price=self._get_list_price(variant),
				)
			)
		self._reprice_cart()
		item = existing or self.cart[-1]
		self._flash_new_item(
			item['tree_id'], 'odd' if self.cart.index(item) % 2 == 0 else 'even'
		)
		self.tree.see(item['tree_id'])
		if total_qty > Decimal(str(variant.get('total_stock', 0))):
			self._set_msg(
				f'Stock insuficiente de {variant.get("name")}: disponible {variant.get("total_stock", 0)}. Ajustá la cantidad antes de cobrar.',
				ORANGE_TEXT,
			)
		else:
			self._set_msg(f'✓ Agregado: {variant.get("name", "Artículo")}')
		self._beep_ok()
		self.qty_entry.delete(0, 'end')
		self.qty_entry.insert(0, '1')
		self._restore_scan_focus(force=True)
		return True

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
		if event and event.keysym in ('Return', 'KP_Enter', 'Up', 'Down'):
			return
		if self._search_mode == 'scan':
			return  # En modo escáner solo el Enter (enviado por el escáner) dispara la acción
		if self._barcode_timer is not None:
			self.after_cancel(self._barcode_timer)
			self._barcode_timer = None
		raw = self.entry_barcode.get().strip()
		if raw != self._dropdown_query:
			self._close_dropdown()
		if len(raw) >= 1:
			self._barcode_timer = self.after(250, self._update_dropdown)
		else:
			self._close_dropdown()

	def _set_search_mode(self, mode: str):
		self._search_request_id += 1
		self._search_mode = mode
		if mode == 'scan':
			self._btn_scan_mode.configure(
				fg_color=ACCENT, hover_color=ACCENT, text_color=TEXT_PRIMARY
			)
			self._btn_search_mode.configure(
				fg_color='transparent', hover_color=SURFACE3, text_color=TEXT_SECONDARY
			)
			self.entry_barcode.configure(
				placeholder_text='Escaneá o ingresá un código y presioná Enter'
			)
			self._close_dropdown()
		else:
			self._btn_search_mode.configure(
				fg_color=ACCENT, hover_color=ACCENT, text_color=TEXT_PRIMARY
			)
			self._btn_scan_mode.configure(
				fg_color='transparent', hover_color=SURFACE3, text_color=TEXT_SECONDARY
			)
			self.entry_barcode.configure(
				placeholder_text='Buscá por nombre o código · ↑/↓ y Enter'
			)
		self.entry_barcode.focus()

	def _update_dropdown(self):
		self._barcode_timer = None
		q = self.entry_barcode.get().strip()
		if not q:
			self._close_dropdown()
			return

		if self._search_mode == 'search':
			self._set_msg('Buscando artículos…', TEXT_MUTED)
			# Búsqueda incremental en el backend — no filtra el catálogo completo en memoria
			tenant_id = self.ctx.tenant_id
			self._search_request_id += 1
			request_id = self._search_request_id
			controller = self.sales_ctrl

			def _fetch(query=q):
				try:
					matches = controller.search_articles(tenant_id, query, limit=50)
					error = None
				except Exception as exc:
					logger.warning('Error en búsqueda de artículos: %s', exc)
					matches, error = [], str(exc)
				self._search_results_queue.put((request_id, query, matches, error))

			threading.Thread(target=_fetch, daemon=True, name='ArtSearch').start()
		else:
			q_lower = q.lower()
			matches = [
				v
				for v in self.db_variants
				if q_lower in (v.get('name') or '').lower()
				or q_lower in str(v.get('barcode') or '')
			][:10]
			if matches:
				self._open_dropdown(matches)
			else:
				self._close_dropdown()

	def _poll_search_results(self):
		"""Consume resultados en el hilo Tk; los workers nunca tocan widgets."""
		self._search_poll_job = None
		if not self.winfo_exists():
			return
		try:
			while True:
				request_id, query, matches, error = (
					self._search_results_queue.get_nowait()
				)
				if request_id != self._search_request_id:
					continue
				if (
					self._search_mode != 'search'
					or self.entry_barcode.get().strip() != query
				):
					continue
				if error:
					self._set_msg(
						'No se pudo buscar el artículo. Intentá nuevamente.', RED_TEXT
					)
					self._close_dropdown()
				elif matches:
					self._open_dropdown(matches[:10])
				else:
					self._close_dropdown()
					self._set_msg('No hay resultados para esta búsqueda.', ORANGE_TEXT)
		except queue.Empty:
			pass
		except Exception:
			logger.exception('Error al mostrar resultados de búsqueda')
			self._close_dropdown()
			self._set_msg(
				'No se pudo mostrar la búsqueda. Intentá nuevamente.', RED_TEXT
			)
		self._search_poll_job = self.after(75, self._poll_search_results)

	def _open_dropdown(self, matches: list):
		if not matches:
			self._close_dropdown()
			return
		for w in self._dropdown_frame.winfo_children():
			w.destroy()
		self._dropdown_items = matches
		self._dropdown_query = self.entry_barcode.get().strip()
		self._dropdown_index = 0
		self._dropdown_buttons = []

		for i, v in enumerate(matches):
			base_price = self._get_list_price(v)
			promo = self._find_promo_for_variant(v)
			if promo:
				price, _description = self._apply_promo_price(
					promo, base_price, Decimal(1)
				)
			else:
				price, _pct, _source = self._apply_product_discount(v, base_price)
			price_text = _cfg_mgr.fmt_price(price)
			if self._active_price_list == 'B' and v.get('selling_price_b') is not None:
				price_text = f'💼 {price_text}'
			row = ctk.CTkFrame(
				self._dropdown_frame,
				fg_color=SURFACE2 if i % 2 == 0 else SURFACE3,
				corner_radius=0,
			)
			row.pack(fill='x')
			button = ctk.CTkButton(
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
			)
			button.pack(fill='x', padx=4, pady=1)
			self._dropdown_buttons.append(button)

		self._dropdown_buttons[0].configure(fg_color=ACCENT_DIM)
		self._set_msg(
			f'{len(matches)} resultados · ↑/↓ para elegir y Enter para agregar.'
		)
		if not self._dropdown_frame.winfo_ismapped():
			self._dropdown_frame.pack(
				fill='x', padx=10, pady=(0, 2), before=self._customer_row_ref
			)

	def _close_dropdown(self):
		self._dropdown_items = []
		self._dropdown_query = None
		if hasattr(self, '_dropdown_frame') and self._dropdown_frame.winfo_ismapped():
			self._dropdown_frame.pack_forget()

	def _select_from_dropdown(self, variant):
		if self._barcode_timer is not None:
			self.after_cancel(self._barcode_timer)
			self._barcode_timer = None
		qty_str = self.qty_entry.get()
		if self._add_variant_to_cart(variant, qty_str):
			self.entry_barcode.delete(0, 'end')
			self._close_dropdown()

	def _select_first_dropdown_item(self):
		query = self.entry_barcode.get().strip()
		if getattr(self, '_dropdown_query', None) == query and self._dropdown_items:
			self._select_from_dropdown(self._dropdown_items[self._dropdown_index])
		else:
			self._close_dropdown()
			self._update_dropdown()

	def _move_dropdown_selection(self, direction):
		if not self._dropdown_items:
			return 'break'
		self._dropdown_index = (self._dropdown_index + direction) % len(
			self._dropdown_items
		)
		for index, button in enumerate(self._dropdown_buttons):
			button.configure(
				fg_color=ACCENT_DIM if index == self._dropdown_index else 'transparent'
			)
		return 'break'

	def _on_search_entry_focus_out(self, event=None):
		if self._search_mode == 'search':
			self.schedule(150, self._close_dropdown)

	def add_by_barcode(self, event=None):
		if self._is_loading_data:
			self._set_msg('Esperá a que termine la carga del catálogo.', ORANGE_TEXT)
			return
		raw = self.entry_barcode.get().strip()
		if not raw:
			return
		# A registered exact EAN always wins over interpreting a scale prefix.
		variant = next(
			(v for v in self.db_variants if str(v.get('barcode')) == raw), None
		)
		scale = variant is None and len(raw) == 13 and raw.startswith('20')
		if scale and (not raw.isascii() or not raw.isdigit()):
			self._set_msg(
				'Código de balanza inválido: debe contener 13 dígitos.', RED_TEXT
			)
			return
		codes = (raw,)
		if scale:
			plu = raw[2:7]
			codes = (plu, str(int(plu)))
		if variant is None:
			variant = next(
				(v for v in self.db_variants if str(v.get('barcode')) in codes), None
			)
		if not variant and not scale:
			legacy = raw.lstrip('0') or '0'
			variant = next(
				(v for v in self.db_variants if str(v.get('barcode')) == legacy), None
			)
		if not variant and self._search_mode == 'search':
			self._manual_search_on_enter()
			return
		if not variant:
			self._beep_err()
			self._set_msg(f'Código no encontrado: {raw}', RED_TEXT)
			return
		qty = self.qty_entry.get()
		if scale:
			try:
				base = self._positive_decimal(variant.get('selling_price'), money=True)
				# Peso inferido a precio A; lista y promociones se aplican después.
				qty = str(
					(Decimal(raw[7:12]) / Decimal(100) / base).quantize(
						Decimal('.0001')
					)
				)
			except ValueError:
				self._set_msg(
					'El producto de balanza necesita un precio base positivo.', RED_TEXT
				)
				return
		if self._add_variant_to_cart(variant, qty):
			self.entry_barcode.delete(0, 'end')

	def add_from_touch(self, variant_id):
		if self._is_loading_data:
			return
		variant = next(
			(v for v in self.db_variants if v['variant_id'] == variant_id), None
		)
		if variant:
			self._add_variant_to_cart(variant, self.qty_entry.get())

	def add_fast_to_cart(self):
		if not self.ctx.is_admin:
			self._set_msg('La venta libre requiere administrador.', RED_TEXT)
			return False
		self.lbl_msg.configure(text='')
		desc = self.entry_fast_desc.get().strip()
		price_str = self.entry_fast_price.get().strip().replace(',', '.')
		qty_str = self.entry_fast_qty.get().strip().replace(',', '.')

		if not desc or not price_str or not qty_str:
			self._set_msg('Completá descripción, precio y cantidad.', RED_TEXT)
			return False

		try:
			price = self._positive_decimal(price_str, money=True)
			qty = self._positive_decimal(qty_str)
			if len(desc) > 480:
				raise ValueError
		except (ValueError, InvalidOperation):
			self._set_msg('⚠ Ingresá números válidos', RED_TEXT)
			return False

		subtotal = (price * qty).quantize(Decimal('.01'))
		visual_desc = f'*(Libre)* {desc}'
		qty_visual = f'{int(qty)}' if qty % 1 == 0 else format(qty.normalize(), 'f')
		alt_tag = 'odd' if len(self.tree.get_children()) % 2 == 0 else 'even'

		item_id = self.tree.insert(
			'',
			'end',
			values=(
				visual_desc,
				qty_visual,
				_cfg_mgr.fmt_price(price),
				_cfg_mgr.fmt_price(subtotal),
			),
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
		self._restore_scan_focus(force=True)
		return True

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
		fmt_price = _cfg_mgr.fmt_price
		self._refresh_pay_state()
		if hasattr(self, '_lbl_item_count'):
			count = len(self.cart)
			self._lbl_item_count.configure(
				text=f'{count} ítem{"s" if count != 1 else ""}'
			)

		raw = sum(
			(item.get('subtotal', Decimal(0)) for item in self.cart), Decimal('0.0')
		)

		if self._discount_pct > Decimal(0) and raw > Decimal(0):
			disc = (raw * self._discount_pct / Decimal(100)).quantize(Decimal('0.01'))
		else:
			disc = Decimal('0.0')

		self._discount_amount = disc
		final = raw - disc

		self._lbl_subtotal.configure(text=fmt_price(raw))
		self.lbl_total.configure(text=fmt_price(final))

		if disc > Decimal(0):
			pct_str = f'{self._discount_pct:.4g}%'
			self._lbl_disc_label.configure(text=f'DESCUENTO  ({pct_str})')
			self._lbl_disc_value.configure(text=f'-{fmt_price(disc)}')
			self._disc_row.pack(fill='x', after=self._lbl_subtotal.master)
			self._divider_total.pack(fill='x', pady=(4, 0), after=self._disc_row)
		else:
			self._disc_row.pack_forget()
			self._divider_total.pack_forget()

		if hasattr(self, '_lbl_wholesale_badge'):
			disc_items = [
				i
				for i in self.cart
				if i.get('product_disc_pct', Decimal(0)) > Decimal(0)
			]
			list_b_items = [i for i in self.cart if i.get('desc', '').startswith('💼')]
			msgs = []
			if disc_items:
				ahorro_disc = sum(
					(i['base_price'] - i['price']) * i['qty'] for i in disc_items
				)
				msgs.append(f'🏷️ Desc. producto · Ahorro: {fmt_price(ahorro_disc)}')
			if list_b_items:
				msgs.append(f'💼 {_cfg_mgr.get("price_list_b_name", "Mayorista")}')
			if msgs:
				self._lbl_wholesale_badge.configure(text='  ·  '.join(msgs))
				self._lbl_wholesale_badge.pack(fill='x', padx=4, pady=(0, 4))
			else:
				self._lbl_wholesale_badge.pack_forget()

	def _confirm_clear_cart(self):
		if not self.cart:
			return
		from CTkMessagebox import CTkMessagebox as _CMB

		r = _CMB(
			title='Vaciar carrito',
			message=f'¿Eliminar los {len(self.cart)} ítem(s) del carrito?',
			icon='warning',
			option_1='Cancelar',
			option_2='Vaciar',
		)
		if r.get() == 'Vaciar':
			self.clear_entire_cart()

	def _on_cart_select(self, event=None):
		state = 'normal' if self.tree.selection() else 'disabled'
		self.btn_remove.configure(state=state)

	def clear_entire_cart(self):
		self._restored_notice = None
		if not self.cart:
			return
		self.cart.clear()
		for timer in self._flash_timers.values():
			self.after_cancel(timer)
		self._flash_timers.clear()
		for item in self.tree.get_children():
			self.tree.delete(item)
		self.btn_remove.configure(state='disabled')
		self._set_discount_pct(Decimal(0))
		self._on_customer_changed()
		self.update_total()
		self._set_msg('Venta anulada.', RED_TEXT)
		self.entry_barcode.focus()

	# =========================================================
	# POP-UP DE COBRO Y EVENTOS
	# =========================================================
	def process_sale(self):
		if self._saving:
			return
		if self._is_loading_data or not self._catalog_ok:
			self._set_msg(
				'El catálogo debe cargarse correctamente antes de cobrar.', ORANGE_TEXT
			)
			return
		if getattr(self.ctx, 'offline_mode', False):
			self._set_msg(
				'Las ventas están deshabilitadas en modo sin conexión.', ORANGE_TEXT
			)
			return
		self._check_cash_status()
		if not self._cash_ready:
			self._check_cash_status()
			self._set_msg('⚠ Abrí la caja antes de cobrar.', ORANGE_TEXT)
			return
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

		if not self._prepare_checkout():
			return
		self._paid_amount = None
		fmt_price = _cfg_mgr.fmt_price
		raw_total = sum(
			(item.get('subtotal', Decimal(0)) for item in self.cart), Decimal('0.0')
		)
		self._discount_amount = (
			(raw_total * self._discount_pct / Decimal(100)).quantize(Decimal('0.01'))
			if self._discount_pct > Decimal(0)
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
		# Limpiar la referencia cuando el popup se destruya por cualquier medio (BUG 2)
		self.popup.bind(
			'<Destroy>',
			self._on_payment_destroy,
		)

		pw = 480
		self.popup.bind('<Escape>', lambda e: self._cancel_checkout())
		self.popup.protocol('WM_DELETE_WINDOW', self._cancel_checkout)
		self._popup_body = ctk.CTkScrollableFrame(
			self.popup,
			fg_color='transparent',
			scrollbar_button_color=SURFACE4,
			scrollbar_button_hover_color=ACCENT,
		)
		self._popup_body.pack(fill='both', expand=True)
		self._render_popup_ui(pw, 0, raw_total, fmt_price)
		self.popup.update_idletasks()
		ph = min(
			max(560, min(720, self._popup_body.winfo_reqheight() + 40)),
			self.winfo_toplevel().winfo_screenheight() - 60,
		)
		self._center_dialog(self.popup, pw, ph)

	def _render_popup_ui(self, pw, ph, raw_total, fmt_price):
		body = self._popup_body
		card = ctk.CTkFrame(
			body,
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
			sum(i.get('qty', Decimal(0)) for i in self.cart),
		)
		qty_str = f'{int(total_qty)}' if total_qty % 1 == 0 else f'{total_qty:.2f}'
		ctk.CTkLabel(
			ci,
			text=f'{item_count} prod.  ·  {qty_str} unid.',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', pady=(0, 6))

		if self._discount_amount > Decimal(0):
			r = ctk.CTkFrame(ci, fg_color='transparent')
			r.pack(fill='x')
			ctk.CTkLabel(
				r, text='Subtotal', font=FONT_BODY, text_color=TEXT_MUTED, anchor='w'
			).pack(side='left')
			ctk.CTkLabel(
				r,
				text=fmt_price(raw_total),
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
				text=f'-{fmt_price(self._discount_amount)}',
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
			text=fmt_price(self.current_total),
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
			body,
			text='MÉTODO DE PAGO',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(2, 4))
		methods_grid = ctk.CTkFrame(body, fg_color='transparent')
		methods_grid.pack(fill='x', padx=20, pady=(0, 10))
		methods_grid.grid_columnconfigure((0, 1), weight=1)

		self._pay_btns = {}
		for i, (icon, method) in enumerate(
			[
				('💵', 'Efectivo'),
				('💳', 'Tarjeta'),
				('🏦', 'Transferencia'),
				('📱', 'QR'),
			]
		):
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

		self._cash_section = ctk.CTkFrame(body, fg_color='transparent')
		self._cash_section.pack(fill='x', padx=20, pady=(0, 6))
		ctk.CTkLabel(
			self._cash_section,
			text='Monto recibido',
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
		self.entry_paid.insert(0, f'{self.current_total:.2f}')
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
			text=f'VUELTO  {fmt_price(0)}',
			font=FONT_AMOUNT_BOLD,
			text_color=GREEN_TEXT,
		)
		self.lbl_change.pack(pady=10)
		self._calculate_change()

		mixto_frame = ctk.CTkFrame(
			body,
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

		self._mixto_var = ctk.BooleanVar(master=self, value=False)
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
			values=['Transferencia', 'Tarjeta', 'QR', 'Efectivo'],
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
			placeholder_text='Monto',
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
		self.entry_amount_2.bind('<Return>', lambda e: self._confirm_and_save(False))
		self.entry_amount_2.bind('<FocusIn>', self._select_all_text)

		self._lbl_amount_1_auto = ctk.CTkLabel(
			mx, text='', font=FONT_SMALL_BOLD, text_color=GREEN_TEXT, anchor='e'
		)
		self._lbl_amount_1_auto.pack(fill='x', pady=(4, 0))

		self.lbl_error_popup = ctk.CTkLabel(
			body, text='', text_color=RED_TEXT, font=FONT_NAV
		)
		self.lbl_error_popup.pack(pady=(2, 0))

		self.btn_confirm_pay = ctk.CTkButton(
			body,
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

		if self.customer_name != 'Consumidor Final':
			ctk.CTkButton(
				body,
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
			body,
			text='⬅  Volver  (Esc)',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			font=FONT_NAV,
			height=32,
			corner_radius=8,
			command=self._cancel_checkout,
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
		if self._mixto_var.get():
			self._on_amount2_change()
		else:
			self.entry_paid.configure(
				state='normal' if is_cash else 'disabled',
				fg_color=SURFACE3 if is_cash else SURFACE2,
				border_color=ACCENT if is_cash else BORDER,
				border_width=2 if is_cash else 1,
			)
			self._calculate_change()

	def _calculate_change(self, event=None):
		fmt_price = _cfg_mgr.fmt_price
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
				self.lbl_change.configure(
					text=f'VUELTO  {fmt_price(0)}', text_color=GREEN_TEXT
				)
			if hasattr(self, '_vuelto_box'):
				self._vuelto_box.configure(fg_color=SURFACE3, border_color=BORDER)
			return

		try:
			paid = self._payment_amount(paid_str)
			change = paid - self.current_total
			if change < Decimal('0.0'):
				if hasattr(self, 'lbl_change'):
					self.lbl_change.configure(
						text=f'⚠  FALTAN  {fmt_price(abs(change))}',
						text_color=RED_TEXT,
						font=FONT_TITLE,
					)
				if hasattr(self, '_vuelto_box'):
					self._vuelto_box.configure(
						fg_color=RED_DIM, border_color=RED, height=100
					)
			elif change > Decimal('0.0'):
				if hasattr(self, 'lbl_change'):
					self.lbl_change.configure(
						text=f'VUELTO: {fmt_price(change)}',
						text_color=GREEN_TEXT,
						font=FONT_DISPLAY,
					)
				if hasattr(self, '_vuelto_box'):
					self._vuelto_box.configure(
						fg_color=GREEN_DIM, border_color=GREEN, height=120
					)
			else:
				if hasattr(self, 'lbl_change'):
					self.lbl_change.configure(
						text=f'VUELTO  {fmt_price(0)}',
						text_color=GREEN_TEXT,
						font=FONT_AMOUNT_BOLD,
					)
				if hasattr(self, '_vuelto_box'):
					self._vuelto_box.configure(
						fg_color=SURFACE3, border_color=BORDER, height=60
					)
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

			amt2 = self._positive_decimal(raw2, money=True)
			amt1 = self.current_total - amt2
			method1 = getattr(self, '_payment_method', 'Efectivo')

			if amt1 <= Decimal(0):
				self.entry_amount_2.configure(border_color=RED)
				self._lbl_amount_1_auto.configure(
					text='⚠ El monto excede el total', text_color=RED_TEXT
				)
			else:
				self.entry_amount_2.configure(border_color=BORDER)
				self._lbl_amount_1_auto.configure(
					text=f'{method1}: {_cfg_mgr.fmt_price(amt1)}',
					text_color=GREEN_TEXT,
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
			self.popup.update_idletasks()
		self._paid_amount = None

		payment_method = getattr(self, '_payment_method', 'Efectivo')
		payment_method_2, amount_method_2 = None, None

		if getattr(self, '_mixto_var', None) and self._mixto_var.get() and not is_fiado:
			payment_method_2 = self.combo_payment_2.get()
			raw2 = self.entry_amount_2.get().strip().replace(',', '.')
			try:
				amount_method_2 = self._positive_decimal(raw2, money=True)
				limit = self.current_total - Decimal('0.01')
				if (
					amount_method_2 <= Decimal(0)
					or amount_method_2 >= self.current_total
				):
					self.lbl_error_popup.configure(
						text=f'El monto 2 debe ser entre {_cfg_mgr.fmt_price(Decimal(".01"))} y {_cfg_mgr.fmt_price(limit)}'
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
				paid = (
					self._payment_amount(paid_str) if paid_str else self.current_total
				)
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

		amount_method_2_float = (
			str(amount_method_2) if amount_method_2 is not None else None
		)
		paid_amount_float = (
			str(self._paid_amount) if self._paid_amount is not None else None
		)

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

		# Convertimos Decimal a str para evitar TypeErrors en json.dumps y preservar precisión exacta
		clean_cart = []
		for i in self.cart:
			cleaned = i.copy()
			for key, val in cleaned.items():
				if isinstance(val, Decimal):
					cleaned[key] = str(val)
			clean_cart.append(cleaned)

		if self._saving:
			return
		self._saving = True
		controller = self.sales_ctrl
		discount, price_list, expected = (
			self._discount_pct,
			self._active_price_list,
			self.current_total,
		)

		def save():
			try:
				result = controller.process_sale(
					tenant_id,
					user_id,
					clean_cart,
					customer_id,
					is_fiado,
					payment_method,
					discount_pct=discount,
					price_list=price_list,
					payment_method_2=payment_method_2,
					amount_method_2=amount_method_2,
					paid_amount=paid_amount,
					expected_total=expected,
				)
			except Exception:
				logger.exception('Error al guardar venta')
				result = (
					False,
					'No se pudo completar el cobro. Revisá la caja antes de reintentar.',
				)
			self._checkout_results_queue.put(result)

		try:
			threading.Thread(target=save, daemon=True, name='SalesCheckout').start()
		except RuntimeError:
			logger.exception('No se pudo iniciar el cobro')
			self._saving = False
			self._finish_sale(False, 'No se pudo iniciar el cobro. Intentá nuevamente.')
			return
		self._checkout_poll_job = self.after(75, self._poll_checkout_results)

	def _cancel_checkout(self):
		if self._saving:
			self.lbl_error_popup.configure(text='Esperá a que termine el cobro.')
			return
		if getattr(self, 'popup', None):
			self._close_dialog(self.popup)

	def _poll_checkout_results(self):
		self._checkout_poll_job = None
		try:
			success, msg = self._checkout_results_queue.get_nowait()
		except queue.Empty:
			self._checkout_poll_job = self.after(75, self._poll_checkout_results)
			return
		self._saving = False
		self._finish_sale(success, msg)

	def _finish_sale(self, success, msg):
		if success:
			self._restored_notice = None
			if hasattr(self, 'popup') and self.popup and self.popup.winfo_exists():
				self.popup.destroy()
			self.show_toast(f'✓  {msg}', 'success')
			self.cart.clear()
			for item in self.tree.get_children():
				self.tree.delete(item)
			self._set_discount_pct(Decimal(0))
			self.update_total()
			self.load_data()
			self.entry_barcode.focus()
		else:
			self.show_toast(msg, 'error')
			if (
				getattr(self, 'lbl_error_popup', None)
				and self.lbl_error_popup.winfo_exists()
			):
				self.lbl_error_popup.configure(text=msg, wraplength=400)
			if hasattr(self, 'btn_confirm_pay') and self.btn_confirm_pay.winfo_exists():
				self.btn_confirm_pay.configure(
					text='✅  CONFIRMAR COBRO  [Enter]', state='normal'
				)

	# =========================================================
	# EVENTOS DOBLE CLIC Y VENTA LIBRE
	# =========================================================

	def _on_cart_double_click(self, event=None):
		selection = self.tree.selection()
		if not selection:
			return
		item = next((i for i in self.cart if i['tree_id'] == selection[0]), None)
		if item is None:
			return
		dlg = ctk.CTkToplevel(self)
		dlg.title('Editar cantidad')
		dlg.configure(fg_color=SURFACE2)
		dlg.grab_set()
		dlg.minsize(360, 280)
		dlg.bind('<Escape>', lambda e: self._close_dialog(dlg))
		dlg.protocol('WM_DELETE_WINDOW', lambda: self._close_dialog(dlg))
		ctk.CTkLabel(dlg, text=item['desc'], font=FONT_BODY_BOLD, wraplength=320).pack(
			padx=20, pady=16
		)
		entry = ctk.CTkEntry(dlg, justify='center', font=FONT_INPUT_LG, height=46)
		entry.pack(fill='x', padx=20)
		entry.insert(0, format(item['qty'], 'f'))
		entry.select_range(0, 'end')
		error = ctk.CTkLabel(dlg, text='', text_color=RED_TEXT, wraplength=320)
		error.pack(fill='x', padx=20, pady=4)

		def apply():
			try:
				qty = self._positive_decimal(entry.get())
				vid = item.get('variant_id')
				variant = next(
					(v for v in self.db_variants if v['variant_id'] == vid), None
				)
				if vid is not None and variant is None:
					raise ValueError(
						'El artículo ya no está disponible. Quitalo del carrito.'
					)
				item['qty'] = qty
				self._reprice_cart()
				self._close_dialog(dlg)
				if variant and qty > Decimal(str(variant.get('total_stock', 0))):
					self._set_msg(
						'Stock insuficiente. Ajustá la cantidad antes de cobrar.',
						ORANGE_TEXT,
					)
			except ValueError as exc:
				entry.configure(border_color=RED)
				error.configure(text=str(exc))

		entry.bind('<Return>', lambda e: apply())
		ctk.CTkButton(dlg, text='Aplicar', command=apply, height=36).pack(
			fill='x', padx=20, pady=8
		)
		self._center_dialog(dlg, 360, 280)
		entry.focus()

	def _center_dialog(self, dialog, width, height):
		dialog.update_idletasks()
		screen_w, screen_h = dialog.winfo_screenwidth(), dialog.winfo_screenheight()
		x = max(
			0,
			min(
				screen_w - width, self.winfo_rootx() + (self.winfo_width() - width) // 2
			),
		)
		y = max(
			0,
			min(
				screen_h - height,
				self.winfo_rooty() + (self.winfo_height() - height) // 2,
			),
		)
		dialog.geometry(f'{width}x{height}+{x}+{y}')

	def _close_dialog(self, dialog):
		dialog.destroy()
		self.schedule(0, lambda: self._restore_scan_focus(force=True))

	def _on_payment_destroy(self, event):
		if event.widget is getattr(self, 'popup', None):
			self.popup = None
			if self.winfo_exists():
				self.schedule(0, lambda: self._restore_scan_focus(force=True))

	def _open_venta_libre_popup(self):
		if not self.ctx.is_admin:
			self.show_toast(
				'La venta libre requiere una cuenta administradora.', 'error'
			)
			return
		popup = ctk.CTkToplevel(self)
		popup.title('Venta Libre')
		popup.configure(fg_color=SURFACE2)
		popup.attributes('-topmost', True)
		popup.grab_set()
		self._center_dialog(popup, 380, 320)
		popup.minsize(380, 320)
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
			placeholder_text=f'Precio ({_cfg_mgr.get("currency_symbol", "$")})',
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
		free_error = ctk.CTkLabel(popup, text='', text_color=RED_TEXT, wraplength=340)
		free_error.pack(fill='x', padx=20, pady=4)

		def _do_add():
			self.entry_fast_desc.delete(0, 'end')
			self.entry_fast_desc.insert(0, entry_desc.get())
			self.entry_fast_price.delete(0, 'end')
			self.entry_fast_price.insert(0, entry_price.get())
			self.entry_fast_qty.delete(0, 'end')
			self.entry_fast_qty.insert(0, entry_qty_vl.get())
			if self.add_fast_to_cart():
				popup.destroy()
				self._restore_scan_focus(force=True)
			else:
				free_error.configure(text=self.lbl_msg.cget('text'))

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

	@staticmethod
	def _is_text_input(widget):
		return isinstance(
			widget,
			(
				tkinter.Entry,
				tkinter.Text,
				tkinter.Spinbox,
				ttk.Entry,
				ttk.Combobox,
				ctk.CTkEntry,
				ctk.CTkComboBox,
				ctk.CTkTextbox,
			),
		)

	def _restore_scan_focus(self, force=False):
		if not self.winfo_ismapped() or not self.entry_barcode.winfo_exists():
			return
		top = self.winfo_toplevel()
		if top.grab_current() is not None:
			return
		focused = top.focus_get()
		if (
			not force
			and focused
			and (self._is_text_input(focused) or isinstance(focused, ttk.Treeview))
		):
			return
		self.entry_barcode.focus()

	def _maybe_restore_focus(self, event=None):
		"""Callback de Button-1: espera 60ms para que el click handler corra primero."""
		if self.winfo_ismapped():
			self.schedule(60, self._restore_scan_focus)

	def setup_shortcuts(self):
		top = self.winfo_toplevel()
		self._shortcut_ids = {}

		def run_when_visible(action, destructive=False):
			def handler(_event=None):
				if not self.winfo_ismapped() or top.grab_current() is not None:
					return None
				focused = top.focus_get()
				if destructive and focused and self._is_text_input(focused):
					return None
				action()
				return 'break'

			return handler

		# Forma estándar y segura de registrar eventos en Tkinter sin cruzar identificadores.
		self._shortcut_ids['<F5>'] = top.bind(
			'<F5>',
			run_when_visible(self.process_sale),
			add='+',
		)
		# F10 como alias de F5 para cobrar (más accesible en teclados estándar)
		self._shortcut_ids['<F10>'] = top.bind(
			'<F10>',
			run_when_visible(self.process_sale),
			add='+',
		)
		self._shortcut_ids['<F6>'] = top.bind(
			'<F6>',
			run_when_visible(lambda: self._restore_scan_focus(force=True)),
			add='+',
		)
		self._shortcut_ids['<F7>'] = top.bind(
			'<F7>',
			run_when_visible(self._open_venta_libre_popup),
			add='+',
		)
		self._shortcut_ids['<Delete>'] = top.bind(
			'<Delete>',
			run_when_visible(self.remove_from_cart, destructive=True),
			add='+',
		)
		self._shortcut_ids['<Control-Delete>'] = top.bind(
			'<Control-Delete>',
			run_when_visible(self._confirm_clear_cart, destructive=True),
			add='+',
		)
		# Auto-foco: devuelve el cursor al campo de barcode tras cualquier click
		self._focus_restore_cbid = top.bind(
			'<Button-1>', self._maybe_restore_focus, add='+'
		)
		# También al mostrarse la tab de ventas (cambio de pestaña)
		self.bind('<Map>', lambda e: self.schedule(150, self._restore_scan_focus))
		# Recarga el catálogo cuando label_view guarda un artículo manual
		self._manual_article_cbid = top.bind(
			'<<ManualArticleAdded>>',
			lambda e: self.schedule(0, self.load_data),
			add='+',
		)
		self.bind(
			'<Destroy>', lambda e: self.destroy_custom() if e.widget is self else None
		)

	def _on_search_escape(self, _event=None):
		self._clear_search()
		return 'break'

	def _clear_search(self):
		"""Limpia el campo de búsqueda y cierra el dropdown."""
		self._search_request_id += 1
		if hasattr(self, 'entry_barcode') and self.entry_barcode.winfo_exists():
			self.entry_barcode.delete(0, 'end')
		self._close_dropdown()

	def destroy_custom(self):
		if getattr(self, '_cleanup_done', False):
			return
		self._cleanup_done = True
		if getattr(self, '_checkout_poll_job', None):
			self.after_cancel(self._checkout_poll_job)
		top = self.winfo_toplevel()
		for key, funcid in getattr(self, '_shortcut_ids', {}).items():
			try:
				top.unbind(key, funcid)
			except tkinter.TclError:
				pass
		self._shortcut_ids = {}
		if getattr(self, '_focus_restore_cbid', None):
			try:
				top.unbind('<Button-1>', self._focus_restore_cbid)
			except tkinter.TclError:
				pass
		if getattr(self, '_manual_article_cbid', None):
			try:
				top.unbind('<<ManualArticleAdded>>', self._manual_article_cbid)
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
		if getattr(self, '_search_poll_job', None):
			self.after_cancel(self._search_poll_job)
		if getattr(self, '_catalog_poll_job', None):
			self.after_cancel(self._catalog_poll_job)

		for timer in getattr(self, '_flash_timers', {}).values():
			try:
				self.after_cancel(timer)
			except tkinter.TclError:
				pass
