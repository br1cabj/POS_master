import random
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

import utils.settings_manager as cfg
from controllers.article_controller import ArticleController
from controllers.label_controller import LabelController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	GREEN,
	GREEN_DIM,
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


class ArticlesView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = ArticleController(ctx.db_engine)

		self.editing_variant_id = None
		self.current_variants = []
		self.suppliers_map = {}
		self._search_timer = None

		# ── Leer IVA desde configuración ─────────────────────────────────────
		tax_pct = cfg.get('tax_rate', 0.0)
		self._iva_rate = Decimal(str(tax_pct)) / Decimal('100')
		self._iva_pct_str = f'{float(tax_pct):.4g}%'
		self._iva_enabled = self._iva_rate > 0

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		apply_treeview_style()
		ttk.Style().map('Treeview.Heading', background=[('active', SURFACE4)])

		# ── Estado de la calculadora ─────────────────────────────────────────
		self._var_iva_included = ctk.BooleanVar(value=False)
		self._var_price_mode = ctk.StringVar(value='manual')
		self._var_margin = ctk.StringVar(value='')
		self._var_cost_str = ctk.StringVar(value='')
		self._var_price_str = ctk.StringVar(value='')

		self._var_cost_str.trace_add('write', self._on_calc_change)
		self._var_margin.trace_add('write', self._on_calc_change)
		self._var_iva_included.trace_add('write', self._on_calc_change)

		self._build_left_panel()
		self._build_right_panel()

		self.after(100, self.load_data)
		self.entry_barcode.focus()

	# =========================================================
	# CONSTRUCCIÓN DE UI
	# =========================================================
	def _build_left_panel(self):
		self.left_panel = ctk.CTkScrollableFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
			scrollbar_button_color=SURFACE3,
		)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)
		self.left_panel.grid_columnconfigure(0, weight=1)

		self.lbl_form_title = ctk.CTkLabel(
			self.left_panel,
			text='📦 Nuevo Producto',
			font=('Arial', 17, 'bold'),
			text_color=TEXT_PRIMARY,
		)
		self.lbl_form_title.pack(pady=(22, 6))

		# ── Barcode ──
		ctk.CTkLabel(
			self.left_panel,
			text='CÓDIGO DE BARRAS',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(6, 2))
		self.entry_barcode = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Escanear o escribir  (Enter para buscar)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_barcode.pack(pady=(0, 4), padx=20, fill='x')
		self.entry_barcode.bind('<Return>', self.on_barcode_scanned)

		# ── Nombre ──
		ctk.CTkLabel(
			self.left_panel,
			text='NOMBRE DEL PRODUCTO',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(4, 2))
		self.entry_name = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Nombre del producto',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_name.pack(pady=(0, 4), padx=20, fill='x')

		# ── Proveedor ──
		ctk.CTkLabel(
			self.left_panel,
			text='PROVEEDOR ASOCIADO',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(8, 2))
		self.combo_supplier = ctk.CTkComboBox(
			self.left_panel,
			values=['Cargando...'],
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			button_color=SURFACE3,
			button_hover_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			dropdown_text_color=TEXT_PRIMARY,
		)
		self.combo_supplier.pack(pady=(0, 8), padx=20, fill='x')

		# ── Precio de costo ──
		ctk.CTkLabel(
			self.left_panel,
			text='PRECIO DE COSTO ($)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(4, 2))
		self.entry_cost = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='0.00',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			textvariable=self._var_cost_str,
		)
		self.entry_cost.pack(pady=(0, 4), padx=20, fill='x')

		# ── Toggle IVA ──
		iva_bg, iva_border, iva_txt = (
			(ORANGE_DIM, ORANGE, ORANGE_TEXT)
			if self._iva_enabled
			else (SURFACE3, BORDER, TEXT_MUTED)
		)
		chk_text = (
			f'El precio del proveedor ya incluye IVA ({self._iva_pct_str})'
			if self._iva_enabled
			else 'IVA no configurado  (ver Configuración → Ventas)'
		)

		iva_frame = ctk.CTkFrame(
			self.left_panel,
			fg_color=iva_bg,
			corner_radius=8,
			border_width=1,
			border_color=iva_border,
		)
		iva_frame.pack(padx=20, fill='x', pady=(0, 10))

		self.chk_iva = ctk.CTkCheckBox(
			iva_frame,
			text=chk_text,
			variable=self._var_iva_included,
			onvalue=True,
			offvalue=False,
			font=('Arial', 11),
			text_color=iva_txt,
			fg_color=ORANGE if self._iva_enabled else SURFACE4,
			hover_color=ORANGE if self._iva_enabled else SURFACE4,
			checkmark_color='white',
			border_color=iva_border,
			state='normal' if self._iva_enabled else 'disabled',
		)
		self.chk_iva.pack(padx=12, pady=10, anchor='w')

		self._lbl_iva_hint = ctk.CTkLabel(
			iva_frame,
			text='→ Se usará el costo tal cual para calcular el margen'
			if self._iva_enabled
			else '→ Configurá el IVA en ⚙ Configuración → Ventas y Alertas',
			font=('Arial', 9),
			text_color=iva_txt,
		)
		self._lbl_iva_hint.pack(padx=12, pady=(0, 8), anchor='w')

		# ── Modo de precio ──
		ctk.CTkLabel(
			self.left_panel,
			text='PRECIO DE VENTA',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(4, 2))

		mode_row = ctk.CTkFrame(self.left_panel, fg_color='transparent')
		mode_row.pack(padx=20, fill='x', pady=(0, 6))

		self._btn_mode_manual = ctk.CTkButton(
			mode_row,
			text='$ Precio Fijo',
			height=30,
			fg_color=ACCENT,
			hover_color=ACCENT,
			text_color='white',
			font=('Arial', 11, 'bold'),
			corner_radius=6,
			command=lambda: self._set_price_mode('manual'),
		)
		self._btn_mode_manual.pack(side='left', fill='x', expand=True, padx=(0, 4))

		self._btn_mode_margen = ctk.CTkButton(
			mode_row,
			text='% Por Margen',
			height=30,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			font=('Arial', 11),
			corner_radius=6,
			command=lambda: self._set_price_mode('margen'),
		)
		self._btn_mode_margen.pack(side='left', fill='x', expand=True, padx=(4, 0))

		self.entry_price = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='0.00',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			textvariable=self._var_price_str,
		)
		self.entry_price.pack(pady=(0, 4), padx=20, fill='x')

		self._frame_margen = ctk.CTkFrame(self.left_panel, fg_color='transparent')
		ctk.CTkLabel(
			self._frame_margen,
			text='MARGEN DE GANANCIA (%)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', pady=(0, 2))
		self.entry_margin = ctk.CTkEntry(
			self._frame_margen,
			placeholder_text='Ej: 30  (para 30%)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=GREEN_TEXT,
			height=36,
			textvariable=self._var_margin,
		)
		self.entry_margin.pack(fill='x')

		# ── Panel fórmula live ──
		self._formula_frame = ctk.CTkFrame(
			self.left_panel,
			fg_color=ACCENT_DIM,
			corner_radius=10,
			border_width=1,
			border_color=ACCENT,
		)
		self._formula_frame.pack(padx=20, fill='x', pady=(6, 10))

		ctk.CTkLabel(
			self._formula_frame,
			text='📐  CÓMO SE CALCULA EL PRECIO',
			font=('Arial', 9, 'bold'),
			text_color=ACCENT_TEXT,
		).pack(anchor='w', padx=12, pady=(10, 4))

		self._lbl_f_costo_neto = self._formula_row('Costo ingresado')
		_iva_row_label = (
			f'+ IVA {self._iva_pct_str}' if self._iva_enabled else '+ IVA (no config.)'
		)
		self._lbl_f_iva = self._formula_row(_iva_row_label)
		self._lbl_f_costo_real = self._formula_row('= Costo real')

		ctk.CTkFrame(self._formula_frame, height=1, fg_color=ACCENT).pack(
			fill='x', padx=12, pady=4
		)

		self._lbl_f_margen = self._formula_row('+ Ganancia')
		self._lbl_f_precio = self._formula_row(
			'= Precio de Venta', bold=True, color=ACCENT_TEXT
		)

		ctk.CTkLabel(
			self._formula_frame, text='', font=('Arial', 9), text_color=TEXT_MUTED
		).pack(padx=12, pady=(0, 2))

		self._lbl_formula_expr = ctk.CTkLabel(
			self._formula_frame,
			text='Fórmula:  PV = Costo_real × (1 + margen%)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			wraplength=260,
			justify='left',
		)
		self._lbl_formula_expr.pack(anchor='w', padx=12, pady=(0, 10))

		# ── Stock inicial ──
		ctk.CTkLabel(
			self.left_panel,
			text='STOCK INICIAL',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(4, 2))
		self.entry_stock = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='0',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_stock.pack(pady=(0, 10), padx=20, fill='x')

		# ── Botones ──
		self.btn_add = ctk.CTkButton(
			self.left_panel,
			text='➕  Agregar al Inventario',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=38,
			corner_radius=8,
			cursor='hand2',
			command=self.save_article,
		)
		self.btn_add.pack(pady=(0, 6), padx=20, fill='x')

		self.btn_cancel = ctk.CTkButton(
			self.left_panel,
			text='↺  Limpiar Formulario',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=36,
			corner_radius=8,
			cursor='hand2',
			command=self.reset_form,
		)
		self.btn_cancel.pack(pady=(0, 6), padx=20, fill='x')

		# ── Panel de Presentaciones (cajón, pallet, etc.) ──
		# Solo visible al editar un artículo existente
		sep = ctk.CTkFrame(self.left_panel, height=1, fg_color=BORDER)
		sep.pack(fill='x', padx=20, pady=(10, 8))

		self.frame_packaging = ctk.CTkFrame(self.left_panel, fg_color='transparent')
		self.frame_packaging.pack(fill='x', padx=20, pady=(0, 16))

		packaging_header = ctk.CTkFrame(self.frame_packaging, fg_color='transparent')
		packaging_header.pack(fill='x')

		ctk.CTkLabel(
			packaging_header,
			text='Presentaciones',
			font=('Arial', 12, 'bold'),
			text_color=TEXT_SECONDARY,
			anchor='w',
		).pack(side='left')

		self.btn_add_pack = ctk.CTkButton(
			packaging_header,
			text='+ Agregar',
			width=80,
			height=26,
			font=('Arial', 10, 'bold'),
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			corner_radius=6,
			cursor='hand2',
			command=self._open_add_packaging_dialog,
		)
		self.btn_add_pack.pack(side='right')

		self.lbl_pack_hint = ctk.CTkLabel(
			self.frame_packaging,
			text='(Guarda el producto primero para agregar presentaciones)',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
			anchor='w',
			wraplength=230,
		)
		self.lbl_pack_hint.pack(anchor='w', pady=(4, 0))

		self.frame_pack_list = ctk.CTkFrame(
			self.frame_packaging, fg_color='transparent'
		)
		self.frame_pack_list.pack(fill='x', pady=(4, 0))

		self.frame_packaging.pack_forget()  # Oculto hasta editar

	def _build_right_panel(self):
		self.right_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=16)

		hdr = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		hdr.pack(fill='x', padx=16, pady=(16, 4))
		ctk.CTkLabel(
			hdr,
			text='Catálogo de Productos',
			font=('Arial', 15, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		ctk.CTkLabel(
			self.right_panel,
			text='Doble clic en un producto para editarlo',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=16, pady=(0, 6))

		search_row = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		search_row.pack(fill='x', padx=14, pady=(0, 6))

		self.entry_search = ctk.CTkEntry(
			search_row,
			placeholder_text='🔍 Buscar por nombre, código o proveedor...',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
		)
		self.entry_search.pack(side='left', fill='x', expand=True)
		# MEJORA: Debounce en la búsqueda
		self.entry_search.bind('<KeyRelease>', self._debounced_search)

		self.lbl_count = ctk.CTkLabel(
			search_row,
			text='',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
			width=100,
			anchor='e',
		)
		self.lbl_count.pack(side='right', padx=(8, 0))

		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=14, pady=(0, 8))

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		columns = ('ID', 'Código', 'Nombre', 'Proveedor', 'Costo', 'Venta', 'Stock')
		self.tree = ttk.Treeview(
			self.table_container,
			columns=columns,
			show='headings',
			height=15,
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		for col in columns:
			self.tree.heading(col, text=col)
			width = 150 if col == 'Nombre' else 80
			anchor = 'w' if col == 'Nombre' else 'center'
			self.tree.column(col, anchor=anchor, width=width)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)
		self.tree.bind('<Double-1>', self.on_tree_double_click)

		btns = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		btns.pack(fill='x', padx=14, pady=(4, 14))

		self.btn_edit_sel = ctk.CTkButton(
			btns,
			text='✏️  Editar Seleccionado',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=36,
			corner_radius=8,
			cursor='hand2',
			command=lambda: self.on_tree_double_click(None),
		)
		self.btn_edit_sel.pack(side='left', expand=True, fill='x', padx=(0, 6))

		self.btn_delete = ctk.CTkButton(
			btns,
			text='🗑  Eliminar',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
			height=36,
			corner_radius=8,
			cursor='hand2',
			command=self.delete_article,
		)
		self.btn_delete.pack(side='left', expand=True, fill='x', padx=(0, 6))

		self.btn_print_labels = ctk.CTkButton(
			btns,
			text='🖨  Imprimir Etiquetas PDF',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=36,
			corner_radius=8,
			cursor='hand2',
			command=self.print_labels,
		)
		self.btn_print_labels.pack(side='left', expand=True, fill='x')

	# =========================================================
	# CALCULADORA DE PRECIOS (Optimizada con Decimal)
	# =========================================================
	def _formula_row(self, label: str, bold=False, color=None):
		row = ctk.CTkFrame(self._formula_frame, fg_color='transparent')
		row.pack(fill='x', padx=12, pady=1)
		ctk.CTkLabel(
			row,
			text=label,
			font=('Arial', 10, 'bold') if bold else ('Arial', 10),
			text_color=color or TEXT_SECONDARY,
			width=130,
			anchor='w',
		).pack(side='left')
		lbl_val = ctk.CTkLabel(
			row,
			text='—',
			font=('Arial', 10, 'bold') if bold else ('Arial', 10),
			text_color=color or TEXT_PRIMARY,
			anchor='e',
		)
		lbl_val.pack(side='right')
		return lbl_val

	def _set_price_mode(self, mode: str):
		self._var_price_mode.set(mode)
		if mode == 'manual':
			self._btn_mode_manual.configure(
				fg_color=ACCENT, text_color='white', font=('Arial', 11, 'bold')
			)
			self._btn_mode_margen.configure(
				fg_color=SURFACE3, text_color=TEXT_SECONDARY, font=('Arial', 11)
			)
			self._frame_margen.pack_forget()
			self.entry_price.configure(state='normal', text_color=TEXT_PRIMARY)
		else:
			self._btn_mode_margen.configure(
				fg_color=GREEN, text_color='white', font=('Arial', 11, 'bold')
			)
			self._btn_mode_manual.configure(
				fg_color=SURFACE3, text_color=TEXT_SECONDARY, font=('Arial', 11)
			)
			self._frame_margen.pack(
				padx=20, fill='x', pady=(0, 4), before=self._formula_frame
			)
			self.entry_price.configure(state='readonly', text_color=GREEN_TEXT)
		self._update_formula_panel()

	def _on_calc_change(self, *_):
		self._update_formula_panel()
		if self._var_price_mode.get() == 'margen':
			self._apply_margin_to_price()

	def _get_cost_real(self) -> Decimal | None:
		try:
			cost = Decimal(self._var_cost_str.get().replace(',', '.'))
		except (ValueError, InvalidOperation):
			return None

		if not self._iva_enabled or self._var_iva_included.get():
			return cost
		else:
			return cost * (Decimal('1') + self._iva_rate)

	def _apply_margin_to_price(self):
		cost_real = self._get_cost_real()
		try:
			margin_pct = Decimal(self._var_margin.get().replace(',', '.'))
		except (ValueError, InvalidOperation):
			self._var_price_str.set('')
			return

		if cost_real is None or cost_real <= 0:
			self._var_price_str.set('')
			return

		price = (cost_real * (Decimal('1') + margin_pct / Decimal('100'))).quantize(
			Decimal('0.01'), ROUND_HALF_UP
		)
		self._var_price_str.set(str(price))

	def _update_formula_panel(self):
		try:
			cost_raw = Decimal(self._var_cost_str.get().replace(',', '.'))
		except (ValueError, InvalidOperation):
			cost_raw = None

		iva_included = self._var_iva_included.get()

		if self._iva_enabled:
			if iva_included:
				self._lbl_iva_hint.configure(
					text='→ Se usará el costo tal cual para calcular el margen'
				)
			else:
				self._lbl_iva_hint.configure(
					text=f'→ Se sumará {self._iva_pct_str} al costo para calcular el margen'
				)

		if cost_raw is None:
			for lbl in (
				self._lbl_f_costo_neto,
				self._lbl_f_iva,
				self._lbl_f_costo_real,
				self._lbl_f_margen,
				self._lbl_f_precio,
			):
				lbl.configure(text='—')
			return

		if not self._iva_enabled:
			cost_real = cost_raw
			self._lbl_f_costo_neto.configure(text=f'${cost_raw:.2f}')
			self._lbl_f_iva.configure(text='Sin IVA configurado')
			self._lbl_f_costo_real.configure(text=f'${cost_real:.2f}')
		elif iva_included:
			cost_sin_iva = cost_raw / (Decimal('1') + self._iva_rate)
			iva_amount = cost_raw - cost_sin_iva
			cost_real = cost_raw
			self._lbl_f_costo_neto.configure(
				text=f'${cost_sin_iva:.2f}  (neto estimado)'
			)
			self._lbl_f_iva.configure(text=f'+${iva_amount:.2f}')
			self._lbl_f_costo_real.configure(text=f'${cost_real:.2f}')
		else:
			iva_amount = cost_raw * self._iva_rate
			cost_real = cost_raw + iva_amount
			self._lbl_f_costo_neto.configure(text=f'${cost_raw:.2f}')
			self._lbl_f_iva.configure(text=f'+${iva_amount:.2f}')
			self._lbl_f_costo_real.configure(text=f'${cost_real:.2f}')

		mode = self._var_price_mode.get()
		try:
			margin_pct = Decimal(self._var_margin.get().replace(',', '.'))
		except (ValueError, InvalidOperation):
			margin_pct = None

		if mode == 'margen' and margin_pct is not None:
			ganancia = cost_real * (margin_pct / Decimal('100'))
			precio = cost_real + ganancia
			self._lbl_f_margen.configure(text=f'+${ganancia:.2f}  ({margin_pct:.1f}%)')
			self._lbl_f_precio.configure(text=f'${precio:.2f}')
			self._lbl_formula_expr.configure(
				text=f'PV = ${cost_real:.2f} × (1 + {margin_pct:.1f}%)'
			)
		elif mode == 'manual':
			try:
				precio = Decimal(self._var_price_str.get().replace(',', '.'))
				if cost_real > 0:
					real_margin = (precio - cost_real) / cost_real * Decimal('100')
					ganancia = precio - cost_real
					self._lbl_f_margen.configure(
						text=f'+${ganancia:.2f}  ({real_margin:.1f}%)'
					)
					self._lbl_f_precio.configure(text=f'${precio:.2f}')
					self._lbl_formula_expr.configure(
						text=f'Margen real: {real_margin:.1f}%  sobre costo c/IVA'
					)
				else:
					self._lbl_f_margen.configure(text='—')
					self._lbl_f_precio.configure(text='—')
			except (ValueError, InvalidOperation):
				self._lbl_f_margen.configure(text='—')
				self._lbl_f_precio.configure(text='—')
				self._lbl_formula_expr.configure(
					text='Fórmula:  PV = Costo_real × (1 + margen%)'
				)
		else:
			self._lbl_f_margen.configure(text='—')
			self._lbl_f_precio.configure(text='—')
			self._lbl_formula_expr.configure(
				text='Fórmula:  PV = Costo_real × (1 + margen%)'
			)

	# =========================================================
	# DATOS Y EVENTOS
	# =========================================================
	def load_data(self):
		tenant_id = self.ctx.tenant_id
		suppliers = self.controller.get_suppliers_for_combo(tenant_id)
		self.suppliers_map = {s['name']: s['id'] for s in suppliers}

		if self.suppliers_map:
			combo_vals = ['Sin Proveedor'] + list(self.suppliers_map.keys())
			self.combo_supplier.configure(values=combo_vals)
		else:
			self.combo_supplier.configure(values=['Sin Proveedor'])
		self.combo_supplier.set('Sin Proveedor')

		self.current_variants = self.controller.get_all_variants(tenant_id)
		self._filter_tree()

	def _debounced_search(self, event=None):
		if self._search_timer:
			self.after_cancel(self._search_timer)
		self._search_timer = self.after(300, self._filter_tree)

	def _filter_tree(self):
		if not self.winfo_exists():
			return

		q = self.entry_search.get().lower().strip()
		if q:
			matches = [
				v
				for v in self.current_variants
				if q in (v.get('name') or '').lower()
				or q in str(v.get('barcode') or '').lower()
				or q in (v.get('supplier_name') or '').lower()
			]
		else:
			matches = self.current_variants

		for item in self.tree.get_children():
			self.tree.delete(item)

		for variant in matches:
			stock_actual = variant.get('total_stock', 0)
			stock_format = (
				f'{int(stock_actual)}'
				if float(stock_actual).is_integer()
				else f'{float(stock_actual):.2f}'
			)
			self.tree.insert(
				'',
				'end',
				values=(
					variant.get('variant_id'),
					variant.get('barcode') or 'N/A',
					variant.get('name'),
					variant.get('supplier_name') or '-',
					f'${variant.get("cost_price", 0):.2f}',
					f'${variant.get("selling_price", 0):.2f}',
					stock_format,
				),
			)

		total = len(self.current_variants)
		shown = len(matches)
		if hasattr(self, 'lbl_count') and self.lbl_count.winfo_exists():
			self.lbl_count.configure(
				text=f'{shown} de {total}' if q else f'{total} productos'
			)

	def on_barcode_scanned(self, event):
		barcode = self.entry_barcode.get().strip().lstrip('0') or '0'
		if not barcode:
			return

		found = next(
			(v for v in self.current_variants if str(v.get('barcode')) == barcode), None
		)
		if found:
			self.load_variant_into_form(found)
			self.entry_price.focus()
		else:
			self.reset_form(keep_barcode=True)
			self.entry_name.focus()  # Salto inteligente para cargar rápido

	def on_tree_double_click(self, event):
		selected = self.tree.selection()
		if not selected:
			return
		variant_id = self.tree.item(selected[0], 'values')[0]
		found = next(
			(
				v
				for v in self.current_variants
				if str(v.get('variant_id')) == str(variant_id)
			),
			None,
		)
		if found:
			self.load_variant_into_form(found)

	def load_variant_into_form(self, variant):
		self.reset_form()
		self.editing_variant_id = variant['variant_id']

		self.entry_barcode.insert(0, variant.get('barcode', ''))
		self.entry_name.insert(0, variant.get('name', ''))
		self._var_cost_str.set(f'{variant.get("cost_price", 0):.2f}')

		self._set_price_mode('manual')
		self.entry_price.configure(state='normal')
		self._var_price_str.set(f'{variant.get("selling_price", 0):.2f}')

		supplier_name = variant.get('supplier_name', 'Sin Proveedor')
		self.combo_supplier.set(
			supplier_name if supplier_name in self.suppliers_map else 'Sin Proveedor'
		)

		stock_val = variant.get('total_stock', 0)
		try:
			stock_str = (
				f'{int(stock_val)}'
				if float(stock_val).is_integer()
				else f'{float(stock_val):.2f}'
			)
		except (TypeError, ValueError):
			stock_str = str(stock_val)

		self.entry_stock.insert(
			0, f'Stock actual: {stock_str} u  ·  Ajustar desde Compras'
		)
		self.entry_stock.configure(state='disabled', text_color=TEXT_MUTED)

		self.lbl_form_title.configure(
			text='✏️ Editando Producto', text_color=ACCENT_TEXT
		)
		self.btn_add.configure(text='💾  Actualizar Precios / Datos')
		self._update_formula_panel()
		self._show_packaging_panel(variant['variant_id'])

	def reset_form(self, keep_barcode=False):
		self.editing_variant_id = None

		barcode_temp = self.entry_barcode.get() if keep_barcode else ''
		self.entry_barcode.delete(0, 'end')
		if keep_barcode:
			self.entry_barcode.insert(0, barcode_temp)

		self.entry_name.delete(0, 'end')
		self._var_cost_str.set('')
		self._var_price_str.set('')
		self._var_margin.set('')
		self._var_iva_included.set(False)

		self.entry_stock.configure(state='normal', text_color=TEXT_PRIMARY)
		self.entry_stock.delete(0, 'end')
		self.combo_supplier.set('Sin Proveedor')

		self._set_price_mode('manual')
		self.lbl_form_title.configure(text='📦 Nuevo Producto', text_color=TEXT_PRIMARY)
		self.btn_add.configure(text='➕  Agregar al Inventario')
		self.frame_packaging.pack_forget()

		if not keep_barcode:
			self.entry_barcode.focus()

	# =========================================================
	# GUARDAR Y ELIMINAR
	# =========================================================
	def save_article(self):
		name = self.entry_name.get().strip()
		raw_barcode = self.entry_barcode.get().strip().lstrip('0')
		barcode = (
			raw_barcode
			if raw_barcode
			else f'99{random.randint(1000000000, 9999999999)}'
		)

		cost_str = self._var_cost_str.get().strip().replace(',', '.')
		price_str = self._var_price_str.get().strip().replace(',', '.')
		supplier_name = self.combo_supplier.get()
		supplier_id = self.suppliers_map.get(supplier_name)

		if not name or not cost_str or not price_str:
			CTkMessagebox(
				title='Faltan Datos',
				message='Nombre, costo y precio son obligatorios.',
				icon='warning',
			)
			return

		try:
			cost = float(cost_str)
			price = float(price_str)
			initial_stock = 0.0
			if not self.editing_variant_id:
				stock_str = self.entry_stock.get().strip().replace(',', '.')
				initial_stock = float(stock_str) if stock_str else 0.0
		except ValueError:
			CTkMessagebox(
				title='Error',
				message='Precios o stock deben ser números.',
				icon='cancel',
			)
			return

		tenant_id = self.ctx.tenant_id

		if self.editing_variant_id:
			user_id = self.ctx.user_id
			success, msg = self.controller.update_article(
				tenant_id,
				user_id,
				self.editing_variant_id,
				name,
				barcode,
				cost,
				price,
				supplier_id,
			)
		else:
			user_id = self.ctx.user_id
			success, msg = self.controller.add_simple_article(
				tenant_id,
				user_id,
				name,
				barcode,
				cost,
				price,
				initial_stock,
				supplier_id,
			)

		if success:
			self.show_success(msg)
			self.reset_form()
			self.load_data()
		else:
			self.show_error(msg)

	def delete_article(self):
		selected = self.tree.selection()
		if not selected:
			return

		msg = CTkMessagebox(
			title='Confirmar',
			message='¿Seguro que deseas eliminar este producto?',
			icon='question',
			option_1='No',
			option_2='Sí',
		)
		if msg.get() == 'Sí':
			variant_id = self.tree.item(selected[0], 'values')[0]
			tenant_id = self.ctx.tenant_id
			success, msg_response = self.controller.delete_variant(
				tenant_id, variant_id
			)
			if success:
				self.load_data()
				self.reset_form()
				self.show_success(msg_response)
			else:
				self.show_error(msg_response)

	# =========================================================
	# ETIQUETAS PDF (Delegado al nuevo LabelController)
	# =========================================================
	def print_labels(self):
		selected_items = self.tree.selection()
		if not selected_items:
			CTkMessagebox(
				title='Atención',
				message='Selecciona al menos un artículo de la tabla.\n(Podés usar Shift o Ctrl para seleccionar varios)',
				icon='info',
			)
			return

		products_to_print = []
		for item_id in selected_items:
			values = self.tree.item(item_id, 'values')
			barcode = values[1] if values[1] != 'N/A' else ''
			price_str = values[5].replace('$', '').replace(',', '.')
			products_to_print.append(
				{
					'name': values[2],
					'barcode': barcode,
					'price': float(price_str),
					'copies': 1,
				}
			)

		try:
			lbl_ctrl = LabelController()
			# Genera etiquetas usando el template "supermercado" por defecto
			ok, result = lbl_ctrl.generate_pdf(
				products_to_print, template_key='supermercado'
			)
			if ok:
				CTkMessagebox(
					title='¡Éxito!',
					message='Etiquetas generadas correctamente.',
					icon='check',
				)
			else:
				CTkMessagebox(
					title='Error',
					message=f'No se pudo generar el PDF: {result}',
					icon='cancel',
				)
		except Exception as e:
			CTkMessagebox(
				title='Error',
				message=f'Excepción al generar etiquetas: {e}',
				icon='cancel',
			)

	# =========================================================
	# PRESENTACIONES / EMPAQUE
	# =========================================================
	def _show_packaging_panel(self, base_variant_id):
		"""Muestra y refresca el panel de presentaciones para la variante en edicion."""
		# Limpiar lista anterior
		for w in self.frame_pack_list.winfo_children():
			w.destroy()

		packs = self.controller.get_packaging_variants(base_variant_id)

		if packs:
			self.lbl_pack_hint.pack_forget()
			for p in packs:
				self._build_pack_row(p, base_variant_id)
		else:
			self.lbl_pack_hint.configure(
				text='Sin presentaciones. Usa + Agregar para definir cajon, pallet, etc.'
			)
			self.lbl_pack_hint.pack(anchor='w', pady=(4, 0))

		self.btn_add_pack.configure(
			command=lambda vid=base_variant_id: self._open_add_packaging_dialog(vid)
		)
		self.frame_packaging.pack(fill='x', padx=20, pady=(0, 16))

	def _build_pack_row(self, pack, base_variant_id):
		row = ctk.CTkFrame(
			self.frame_pack_list,
			fg_color=SURFACE1,
			corner_radius=6,
			border_width=1,
			border_color=BORDER,
		)
		row.pack(fill='x', pady=(0, 4))
		row.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(
			row,
			text=pack['pack_label'],
			font=('Arial', 11, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).grid(row=0, column=0, sticky='w', padx=(10, 6), pady=6)

		ctk.CTkLabel(
			row,
			text=f'{pack["units_per_pack"]}u  |  ${pack["selling_price"]:,.2f}',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=0, column=1, sticky='w', pady=6)

		btn_frame = ctk.CTkFrame(row, fg_color='transparent')
		btn_frame.grid(row=0, column=2, padx=(4, 8), pady=6)

		ctk.CTkButton(
			btn_frame,
			text='✏',
			width=28,
			height=24,
			font=('Arial', 11),
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=0,
			corner_radius=4,
			command=lambda p=pack, bvid=base_variant_id: (
				self._open_edit_packaging_dialog(p, bvid)
			),
		).pack(side='left', padx=(0, 3))

		ctk.CTkButton(
			btn_frame,
			text='X',
			width=28,
			height=24,
			font=('Arial', 10, 'bold'),
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=0,
			corner_radius=4,
			command=lambda vid=pack['variant_id'], bvid=base_variant_id: (
				self._delete_pack(vid, bvid)
			),
		).pack(side='left')

	def _delete_pack(self, variant_id, base_variant_id):
		tenant_id = self.ctx.tenant_id
		success, msg = self.controller.delete_packaging_variant(tenant_id, variant_id)
		if success:
			self._show_packaging_panel(base_variant_id)
		else:
			self.show_error(msg)

	def _open_add_packaging_dialog(self, base_variant_id=None):
		if base_variant_id is None:
			base_variant_id = self.editing_variant_id
		if not base_variant_id:
			self.show_warning(
				'Guarda el producto primero antes de agregar presentaciones.'
			)
			return
		self._packaging_dialog(
			title='Nueva Presentacion',
			base_variant_id=base_variant_id,
			existing_pack=None,
		)

	def _open_edit_packaging_dialog(self, pack, base_variant_id):
		self._packaging_dialog(
			title='Editar Presentacion',
			base_variant_id=base_variant_id,
			existing_pack=pack,
		)

	def _packaging_dialog(self, title, base_variant_id, existing_pack):
		"""Dialog reutilizable para crear o editar una presentacion (cajon, caja, pallet, etc.)."""
		is_edit = existing_pack is not None

		dialog = ctk.CTkToplevel(self)
		dialog.title(title)
		dialog.geometry('400x430')
		dialog.resizable(False, False)
		dialog.grab_set()
		dialog.focus()
		dialog.attributes('-topmost', True)

		ctk.CTkLabel(
			dialog,
			text=title,
			font=('Arial', 18, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(20, 2))

		ctk.CTkLabel(
			dialog,
			text='Definí nombre, cantidad y precio de venta del paquete.',
			font=('Arial', 11),
			text_color=TEXT_MUTED,
		).pack(pady=(0, 12))

		# ── Nombre ──
		ctk.CTkLabel(
			dialog,
			text='NOMBRE  (ej: Cajon 12u, Caja x6, Pallet 200u)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=28, anchor='w', pady=(0, 2))
		entry_label = ctk.CTkEntry(
			dialog,
			placeholder_text='Cajon 12 unidades',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		entry_label.pack(padx=28, fill='x', pady=(0, 10))
		if is_edit:
			entry_label.insert(0, existing_pack.get('pack_label', ''))
		entry_label.focus()

		# ── Unidades por paquete con presets rapidos ──
		ctk.CTkLabel(
			dialog,
			text='UNIDADES POR PAQUETE',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=28, anchor='w', pady=(0, 2))

		presets_row = ctk.CTkFrame(dialog, fg_color='transparent')
		presets_row.pack(padx=28, fill='x', pady=(0, 4))
		entry_units = ctk.CTkEntry(
			dialog,
			placeholder_text='Ej: 6, 12, 24, 200',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)

		def _set_units(val):
			entry_units.delete(0, 'end')
			entry_units.insert(0, str(val))

		for qty in [4, 6, 12, 24, 48]:
			ctk.CTkButton(
				presets_row,
				text=str(qty),
				width=44,
				height=28,
				font=('Arial', 11),
				fg_color=SURFACE3,
				hover_color=SURFACE4,
				text_color=TEXT_SECONDARY,
				border_width=1,
				border_color=BORDER,
				corner_radius=6,
				command=lambda v=qty: _set_units(v),
			).pack(side='left', padx=(0, 4))

		entry_units.pack(padx=28, fill='x', pady=(0, 10))
		if is_edit:
			entry_units.insert(0, str(existing_pack.get('units_per_pack', '')))

		# ── Precio ──
		ctk.CTkLabel(
			dialog,
			text='PRECIO DE VENTA DEL PAQUETE ($)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=28, anchor='w', pady=(0, 2))
		entry_price = ctk.CTkEntry(
			dialog,
			placeholder_text='Ej: 5000',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		entry_price.pack(padx=28, fill='x', pady=(0, 10))
		if is_edit:
			entry_price.insert(0, f'{existing_pack.get("selling_price", ""):.2f}')

		# ── Barcode ──
		ctk.CTkLabel(
			dialog,
			text='CODIGO DE BARRAS  (opcional)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=28, anchor='w', pady=(0, 2))
		entry_barcode = ctk.CTkEntry(
			dialog,
			placeholder_text='Dejar vacio si no tiene',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		entry_barcode.pack(padx=28, fill='x', pady=(0, 6))
		if is_edit and existing_pack.get('barcode'):
			entry_barcode.insert(0, existing_pack['barcode'])

		lbl_err = ctk.CTkLabel(
			dialog, text='', font=('Arial', 11, 'bold'), text_color=RED_TEXT
		)
		lbl_err.pack(pady=(0, 4))

		def _do_save():
			label = entry_label.get().strip()
			units_str = entry_units.get().strip()
			price_str = entry_price.get().strip().replace(',', '.')
			barcode = entry_barcode.get().strip() or None

			if not label or not units_str or not price_str:
				lbl_err.configure(text='Nombre, unidades y precio son obligatorios.')
				return
			try:
				units = int(units_str)
				price = float(price_str)
			except ValueError:
				lbl_err.configure(text='Unidades debe ser entero y precio un numero.')
				return

			tenant_id = self.ctx.tenant_id
			if is_edit:
				success, msg = self.controller.update_packaging_variant(
					tenant_id, existing_pack['variant_id'], label, units, price, barcode
				)
			else:
				success, msg = self.controller.add_packaging_variant(
					tenant_id, base_variant_id, label, units, price, barcode
				)

			if success:
				dialog.destroy()
				self._show_packaging_panel(base_variant_id)
			else:
				lbl_err.configure(text=msg)

		ctk.CTkButton(
			dialog,
			text='Guardar Cambios' if is_edit else 'Agregar Presentacion',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=40,
			corner_radius=8,
			command=_do_save,
		).pack(padx=28, fill='x')

		entry_barcode.bind('<Return>', lambda e: _do_save())
