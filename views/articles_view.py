import random
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk

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
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_HEADING,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	FONT_TITLE,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	PAD_LG,
	PAD_MD,
	PAD_SM,
	PAD_XS,
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
	make_form_label,
)


class ArticlesView(BaseView):
	"""
	Vista principal para la gestión del catálogo de artículos, definición de precios
	y configuración de presentaciones (empaques).
	"""

	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = ArticleController(ctx.db_engine)

		self.editing_variant_id = None
		self.current_variants = []
		self.suppliers_map = {}
		self._search_timer = None
		self._calc_lock = False

		tax_pct = cfg.get('tax_rate', 0.0)
		self._iva_rate = Decimal(str(tax_pct)) / Decimal('100')
		self._iva_pct_str = f'{float(tax_pct):.4g}%'
		self._iva_enabled = self._iva_rate > 0

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		self._var_iva_included = ctk.BooleanVar(value=False)
		self._var_margin = ctk.StringVar(value='')
		self._var_cost_str = ctk.StringVar(value='')
		self._var_price_str = ctk.StringVar(value='')

		self._var_discount_enabled = ctk.BooleanVar(value=False)
		self._var_discount_pct = ctk.StringVar(value='')
		self._var_discount_until = ctk.StringVar(value='')

		self._var_cost_str.trace_add('write', self._on_cost_or_margin_changed)
		self._var_margin.trace_add('write', self._on_cost_or_margin_changed)
		self._var_iva_included.trace_add('write', self._on_cost_or_margin_changed)
		self._var_price_str.trace_add('write', self._on_price_changed)

		self._build_left_panel()
		self._build_right_panel()

		self.bind('<Control-g>', lambda e: self.save_article())
		self.bind('<Escape>', lambda e: self.reset_form())

		self.after(100, self.load_data)
		self.entry_barcode.focus()

	# ─────────────────────────────────────────────────────────────────────────
	# CONSTRUCCIÓN DE LA INTERFAZ
	# ─────────────────────────────────────────────────────────────────────────

	def _build_left_panel(self):
		self.left_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.left_panel.grid(
			row=0, column=0, sticky='nsew', padx=(PAD_LG, PAD_SM), pady=PAD_LG
		)
		self.left_panel.grid_columnconfigure(0, weight=1)
		self.left_panel.grid_rowconfigure(1, weight=1)

		self.lbl_form_title = ctk.CTkLabel(
			self.left_panel,
			text='📦 Nuevo Producto',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
		)
		self.lbl_form_title.grid(
			row=0, column=0, pady=(PAD_LG, PAD_SM), padx=PAD_LG, sticky='w'
		)

		self.tabview = ctk.CTkTabview(
			self.left_panel,
			fg_color=SURFACE1,
			segmented_button_fg_color=SURFACE3,
			segmented_button_selected_color=ACCENT,
			segmented_button_selected_hover_color=ACCENT_DIM,
			text_color=TEXT_PRIMARY,
		)
		self.tabview.grid(row=1, column=0, sticky='nsew', padx=PAD_MD, pady=(0, PAD_MD))

		tab_gen = self.tabview.add('General')
		tab_pre = self.tabview.add('Precios')
		tab_emp = self.tabview.add('Empaque')

		self._build_tab_general(tab_gen)
		self._build_tab_precios(tab_pre)
		self._build_tab_empaque(tab_emp)

		footer = ctk.CTkFrame(self.left_panel, fg_color='transparent')
		footer.grid(row=2, column=0, sticky='ew', padx=PAD_MD, pady=(0, PAD_MD))

		self.btn_add = ctk.CTkButton(
			footer,
			text='💾 Guardar Producto (Ctrl+G)',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			font=FONT_BODY_BOLD,
			height=45,
			corner_radius=8,
			cursor='hand2',
			command=self.save_article,
		)
		self.btn_add.pack(side='left', expand=True, fill='x', padx=(0, PAD_SM))

		self.btn_cancel = ctk.CTkButton(
			footer,
			text='↺ Limpiar (Esc)',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			font=FONT_BODY,
			height=45,
			corner_radius=8,
			cursor='hand2',
			command=self.reset_form,
		)
		self.btn_cancel.pack(side='right', expand=False, fill='x')

	def _build_tab_general(self, parent):
		make_form_label(parent, 'CÓDIGO DE BARRAS', required=False)[0].pack(
			anchor='w', pady=(PAD_MD, PAD_XS)
		)
		self.entry_barcode = ctk.CTkEntry(
			parent,
			placeholder_text='Escanear o escribir (Enter)',
			height=40,
			font=FONT_BODY,
		)
		self.entry_barcode.pack(fill='x', pady=(0, PAD_SM))
		self.entry_barcode.bind('<Return>', self.on_barcode_scanned)

		self.lbl_barcode_msg = ctk.CTkLabel(
			parent, text='', font=FONT_LABEL, text_color=GREEN_TEXT
		)
		self.lbl_barcode_msg.pack(anchor='w', pady=(0, PAD_SM))
		self.lbl_barcode_msg.pack_forget()

		make_form_label(parent, 'NOMBRE DEL PRODUCTO', required=True)[0].pack(
			anchor='w', pady=(PAD_SM, PAD_XS)
		)
		self.entry_name = ctk.CTkEntry(
			parent,
			placeholder_text='Ej: Gaseosa Cola 1.5L',
			height=40,
			font=FONT_HEADING,
		)
		self.entry_name.pack(fill='x', pady=(0, PAD_SM))

		make_form_label(parent, 'PROVEEDOR / DISTRIBUIDOR', required=False)[0].pack(
			anchor='w', pady=(PAD_SM, PAD_XS)
		)
		self.combo_supplier = ctk.CTkComboBox(
			parent, values=['Cargando...'], height=40, font=FONT_BODY,
			command=self._on_supplier_changed,
		)
		self.combo_supplier.pack(fill='x', pady=(0, PAD_XS))

		# Descuento activo del distribuidor seleccionado
		self._lbl_supplier_discount = ctk.CTkLabel(
			parent,
			text='',
			font=FONT_LABEL_BOLD,
			text_color=ORANGE_TEXT,
			anchor='w',
		)
		self._lbl_supplier_discount.pack(anchor='w', pady=(0, PAD_XS))

		# Botón para configurar descuento del distribuidor
		self._btn_supplier_discount = ctk.CTkButton(
			parent,
			text='🏷️  Configurar descuento del distribuidor',
			fg_color='transparent',
			hover_color=ORANGE_DIM,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			height=30,
			corner_radius=6,
			font=FONT_LABEL_BOLD,
			command=self._open_supplier_discount_dialog,
		)
		self._btn_supplier_discount.pack(fill='x', pady=(0, PAD_SM))

		self.lbl_stock = make_form_label(parent, 'STOCK INICIAL', required=False)[0]
		self.lbl_stock.pack(anchor='w', pady=(PAD_SM, PAD_XS))
		self.entry_stock = ctk.CTkEntry(
			parent, placeholder_text='0', height=40, font=FONT_BODY_BOLD
		)
		self.entry_stock.pack(fill='x', pady=(0, PAD_SM))

	def _build_tab_precios(self, parent):
		make_form_label(parent, 'PRECIO DE COSTO ($)', required=True)[0].pack(
			anchor='w', pady=(PAD_MD, PAD_XS)
		)
		self.entry_cost = ctk.CTkEntry(
			parent,
			placeholder_text='0.00',
			height=45,
			font=FONT_TITLE,
			textvariable=self._var_cost_str,
		)
		self.entry_cost.pack(fill='x', pady=(0, PAD_SM))

		chk_text = (
			f'Proveedor incluye IVA ({self._iva_pct_str})'
			if self._iva_enabled
			else 'IVA no configurado'
		)
		self.chk_iva = ctk.CTkCheckBox(
			parent,
			text=chk_text,
			variable=self._var_iva_included,
			font=FONT_BODY,
			state='normal' if self._iva_enabled else 'disabled',
		)
		self.chk_iva.pack(anchor='w', pady=(0, PAD_MD), padx=PAD_XS)

		row_precios = ctk.CTkFrame(parent, fg_color='transparent')
		row_precios.pack(fill='x', pady=(0, PAD_MD))
		row_precios.grid_columnconfigure(0, weight=1)
		row_precios.grid_columnconfigure(1, weight=1)

		frame_margen = ctk.CTkFrame(row_precios, fg_color='transparent')
		frame_margen.grid(row=0, column=0, sticky='nsew', padx=(0, PAD_XS))
		make_form_label(frame_margen, 'MARGEN (%)')[0].pack(
			anchor='w', pady=(0, PAD_XS)
		)
		self.entry_margin = ctk.CTkEntry(
			frame_margen,
			placeholder_text='Ej: 30',
			height=45,
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
			textvariable=self._var_margin,
		)
		self.entry_margin.pack(fill='x')

		frame_venta = ctk.CTkFrame(row_precios, fg_color='transparent')
		frame_venta.grid(row=0, column=1, sticky='nsew', padx=(PAD_XS, 0))
		make_form_label(frame_venta, 'PRECIO VENTA ($)', required=True)[0].pack(
			anchor='w', pady=(0, PAD_XS)
		)
		self.entry_price = ctk.CTkEntry(
			frame_venta,
			placeholder_text='0.00',
			height=45,
			font=FONT_TITLE,
			text_color=GREEN_TEXT,
			textvariable=self._var_price_str,
		)
		self.entry_price.pack(fill='x')

		self._formula_frame = ctk.CTkFrame(
			parent,
			fg_color=ACCENT_DIM,
			corner_radius=10,
			border_width=1,
			border_color=ACCENT,
		)
		self._formula_frame.pack(fill='x', pady=(PAD_SM, 0))

		self._lbl_formula_expr = ctk.CTkLabel(
			self._formula_frame,
			text='Costo Real: $0.00 | Ganancia: $0.00',
			font=FONT_LABEL_BOLD,
			text_color=ACCENT_TEXT,
		)
		self._lbl_formula_expr.pack(padx=PAD_MD, pady=PAD_MD)

		# ── Sección Descuento ──────────────────────────────────────────────
		ctk.CTkFrame(parent, height=1, fg_color=BORDER, corner_radius=0).pack(
			fill='x', pady=(PAD_MD, PAD_SM)
		)

		self._chk_discount = ctk.CTkCheckBox(
			parent,
			text='🏷️  Activar descuento en este producto',
			variable=self._var_discount_enabled,
			font=FONT_BODY_BOLD,
			text_color=ORANGE_TEXT,
			fg_color=ORANGE,
			hover_color=ORANGE_DIM,
			command=self._toggle_discount_section,
		)
		self._chk_discount.pack(anchor='w', pady=(0, PAD_XS))

		self._frame_discount_fields = ctk.CTkFrame(
			parent,
			fg_color=ORANGE_DIM,
			corner_radius=8,
			border_width=1,
			border_color=ORANGE,
		)

		disc_inner = ctk.CTkFrame(self._frame_discount_fields, fg_color='transparent')
		disc_inner.pack(fill='x', padx=PAD_SM, pady=PAD_SM)
		disc_inner.grid_columnconfigure(0, weight=1)
		disc_inner.grid_columnconfigure(1, weight=1)

		frame_dpct = ctk.CTkFrame(disc_inner, fg_color='transparent')
		frame_dpct.grid(row=0, column=0, sticky='nsew', padx=(0, PAD_XS))
		make_form_label(frame_dpct, 'DESCUENTO (%)')[0].pack(anchor='w', pady=(0, PAD_XS))
		self.entry_discount_pct = ctk.CTkEntry(
			frame_dpct,
			placeholder_text='Ej: 15',
			height=40,
			font=FONT_HEADING,
			text_color=ORANGE_TEXT,
			textvariable=self._var_discount_pct,
		)
		self.entry_discount_pct.pack(fill='x')

		frame_duntil = ctk.CTkFrame(disc_inner, fg_color='transparent')
		frame_duntil.grid(row=0, column=1, sticky='nsew', padx=(PAD_XS, 0))
		make_form_label(frame_duntil, 'VÁLIDO HASTA (opcional)')[0].pack(
			anchor='w', pady=(0, PAD_XS)
		)
		self.entry_discount_until = ctk.CTkEntry(
			frame_duntil,
			placeholder_text='DD/MM/AAAA',
			height=40,
			font=FONT_BODY,
			textvariable=self._var_discount_until,
		)
		self.entry_discount_until.pack(fill='x')

		self._lbl_disc_preview = ctk.CTkLabel(
			self._frame_discount_fields,
			text='',
			font=FONT_LABEL_BOLD,
			text_color=ORANGE_TEXT,
			anchor='w',
		)
		self._lbl_disc_preview.pack(padx=PAD_SM, anchor='w', pady=(0, PAD_SM))

	def _build_tab_empaque(self, parent):
		self.frame_packaging = ctk.CTkFrame(parent, fg_color='transparent')
		self.frame_packaging.pack(fill='both', expand=True, pady=PAD_SM)

		packaging_header = ctk.CTkFrame(self.frame_packaging, fg_color='transparent')
		packaging_header.pack(fill='x')

		self.btn_add_pack = ctk.CTkButton(
			packaging_header,
			text='+ Agregar Presentación',
			font=FONT_LABEL_BOLD,
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			height=32,
			corner_radius=6,
			cursor='hand2',
			command=self._open_add_packaging_dialog,
		)
		self.btn_add_pack.pack(side='right')

		self.lbl_pack_hint = ctk.CTkLabel(
			self.frame_packaging,
			text='(Guarda el producto base primero)',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
		)
		self.lbl_pack_hint.pack(pady=PAD_LG)

		self.frame_pack_list = ctk.CTkScrollableFrame(
			self.frame_packaging, fg_color='transparent'
		)
		self.frame_pack_list.pack(fill='both', expand=True, pady=(PAD_SM, 0))
		self.frame_pack_list.pack_forget()

	def _build_right_panel(self):
		self.right_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.right_panel.grid(
			row=0, column=1, sticky='nsew', padx=(PAD_SM, PAD_LG), pady=PAD_LG
		)

		hdr = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		hdr.pack(fill='x', padx=PAD_MD, pady=(PAD_MD, PAD_XS))
		ctk.CTkLabel(
			hdr,
			text='Catálogo de Productos',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		ctk.CTkLabel(
			self.right_panel,
			text='Doble clic en un producto para editarlo',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		search_row = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		search_row.pack(fill='x', padx=PAD_SM, pady=(0, PAD_SM))

		self.entry_search = ctk.CTkEntry(
			search_row,
			placeholder_text='🔍 Buscar por nombre, código o proveedor...',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
		)
		self.entry_search.pack(side='left', fill='x', expand=True)
		self.entry_search.bind('<KeyRelease>', self._debounced_search)

		self.lbl_count = ctk.CTkLabel(
			search_row,
			text='',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			width=100,
			anchor='e',
		)
		self.lbl_count.pack(side='right', padx=(PAD_SM, 0))

		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(
			fill='both', expand=True, padx=PAD_SM, pady=(0, PAD_SM)
		)

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		columns = ('ID', 'Código', 'Nombre', 'Proveedor', 'Costo', 'Venta', 'Stock')
		self.tree = ttk.Treeview(
			self.table_container,
			columns=columns,
			show='headings',
			height=15,
			yscrollcommand=self.tree_scroll.set,
		)
		self.init_treeview(self.tree)
		self.tree_scroll.configure(command=self.tree.yview)

		for col in columns:
			self.tree.heading(col, text=col)
			width = 150 if col == 'Nombre' else 80
			anchor = 'w' if col == 'Nombre' else 'center'
			self.tree.column(col, anchor=anchor, width=width)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)
		self.tree.bind('<Double-1>', self.on_tree_double_click)

		self.lbl_empty_tree = ctk.CTkLabel(
			self.table_container,
			text='📦\nNo hay productos en el catálogo.\nUsá el formulario de la izquierda para agregar el primero.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			justify='center',
		)

		btns = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		btns.pack(fill='x', padx=PAD_SM, pady=(PAD_XS, PAD_SM))

		self.btn_edit_sel = ctk.CTkButton(
			btns,
			text='✏️ Editar Seleccionado',
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
		self.btn_edit_sel.pack(side='left', expand=True, fill='x', padx=(0, PAD_SM))

		self.btn_delete = ctk.CTkButton(
			btns,
			text='🗑 Eliminar',
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
		self.btn_delete.pack(side='left', expand=True, fill='x', padx=(0, PAD_SM))

		self.btn_print_labels = ctk.CTkButton(
			btns,
			text='🖨 Imprimir Etiquetas',
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

	# ─────────────────────────────────────────────────────────────────────────
	# LÓGICA DE NEGOCIO Y EVENTOS
	# ─────────────────────────────────────────────────────────────────────────

	def _toggle_discount_section(self):
		if self._var_discount_enabled.get():
			self._frame_discount_fields.pack(fill='x', pady=(PAD_XS, PAD_SM))
		else:
			self._frame_discount_fields.pack_forget()
			self._var_discount_pct.set('')
			self._var_discount_until.set('')

	def _on_supplier_changed(self, value=None):
		"""Actualiza el label con el descuento activo del proveedor seleccionado."""
		from datetime import datetime as _dt
		supplier_id = self.suppliers_map.get(self.combo_supplier.get())
		if not supplier_id:
			self._lbl_supplier_discount.configure(text='')
			return
		pct, until = self.controller.get_supplier_discount(self.ctx.tenant_id, supplier_id)
		if pct and pct > 0:
			if until and until < _dt.now():
				self._lbl_supplier_discount.configure(
					text=f'⚠️  Descuento {pct:.4g}% VENCIDO', text_color=RED_TEXT
				)
			elif until:
				self._lbl_supplier_discount.configure(
					text=f'🏷️  Descuento activo: -{pct:.4g}%  (hasta {until.strftime("%d/%m/%Y")})',
					text_color=ORANGE_TEXT,
				)
			else:
				self._lbl_supplier_discount.configure(
					text=f'🏷️  Descuento activo: -{pct:.4g}%  (sin vencimiento)',
					text_color=ORANGE_TEXT,
				)
		else:
			self._lbl_supplier_discount.configure(text='Sin descuento configurado', text_color=TEXT_MUTED)

	def _open_supplier_discount_dialog(self):
		"""Abre un diálogo para configurar el descuento de un distribuidor."""
		from datetime import datetime as _dt
		supplier_name = self.combo_supplier.get()
		supplier_id = self.suppliers_map.get(supplier_name)
		if not supplier_id:
			self.show_warning('Seleccioná un proveedor primero.', 'Sin proveedor')
			return

		current_pct, current_until = self.controller.get_supplier_discount(
			self.ctx.tenant_id, supplier_id
		)

		dialog = ctk.CTkToplevel(self)
		dialog.title(f'Descuento de Distribuidor — {supplier_name}')
		dialog.geometry('420x320')
		dialog.resizable(False, False)
		dialog.grab_set()
		dialog.focus()
		dialog.attributes('-topmost', True)

		ctk.CTkLabel(
			dialog, text=f'🏷️  {supplier_name}', font=FONT_TITLE, text_color=ORANGE_TEXT
		).pack(pady=(PAD_LG, PAD_XS))
		ctk.CTkLabel(
			dialog,
			text='Este descuento aplica automáticamente a todos los productos de este distribuidor.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			wraplength=370,
			justify='center',
		).pack(pady=(0, PAD_MD))

		make_form_label(dialog, 'DESCUENTO (%) — 0 para eliminar')[0].pack(
			padx=PAD_LG, anchor='w'
		)
		var_pct = ctk.StringVar(value=f'{current_pct:.4g}' if current_pct else '')
		entry_pct = ctk.CTkEntry(
			dialog, placeholder_text='Ej: 15', height=40, font=FONT_HEADING,
			text_color=ORANGE_TEXT, textvariable=var_pct,
		)
		entry_pct.pack(padx=PAD_LG, fill='x', pady=(0, PAD_SM))
		entry_pct.focus()

		make_form_label(dialog, 'VÁLIDO HASTA (opcional — dejar vacío = sin vencimiento)')[0].pack(
			padx=PAD_LG, anchor='w'
		)
		var_until = ctk.StringVar(
			value=current_until.strftime('%d/%m/%Y') if current_until else ''
		)
		entry_until = ctk.CTkEntry(
			dialog, placeholder_text='DD/MM/AAAA', height=36, font=FONT_BODY,
			textvariable=var_until,
		)
		entry_until.pack(padx=PAD_LG, fill='x', pady=(0, PAD_SM))

		lbl_err = ctk.CTkLabel(dialog, text='', font=FONT_LABEL_BOLD, text_color=RED_TEXT)
		lbl_err.pack(pady=(0, PAD_XS))

		def _do_save():
			raw_pct = var_pct.get().strip().replace(',', '.')
			raw_until = var_until.get().strip()
			try:
				pct = float(raw_pct) if raw_pct else 0.0
				if pct < 0 or pct >= 100:
					raise ValueError
			except ValueError:
				lbl_err.configure(text='Porcentaje inválido (0-99).')
				return

			until = None
			if raw_until:
				for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
					try:
						until = _dt.strptime(raw_until, fmt).replace(hour=23, minute=59, second=59)
						break
					except ValueError:
						continue
				if until is None:
					lbl_err.configure(text='Fecha inválida. Usá DD/MM/AAAA.')
					return

			success, msg = self.controller.set_supplier_discount(
				self.ctx.tenant_id, supplier_id, pct if pct > 0 else None, until
			)
			if success:
				dialog.destroy()
				self._on_supplier_changed()
				self.show_success(msg)
			else:
				lbl_err.configure(text=msg)

		ctk.CTkButton(
			dialog,
			text='Guardar Descuento',
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			height=40,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=_do_save,
		).pack(padx=PAD_LG, fill='x')
		entry_until.bind('<Return>', lambda e: _do_save())

	def _get_cost_real(self) -> Decimal | None:
		try:
			cost = Decimal(self._var_cost_str.get().replace(',', '.'))
			if cost < 0:
				return None
		except (ValueError, InvalidOperation):
			return None

		if not self._iva_enabled or self._var_iva_included.get():
			return cost
		else:
			return cost * (Decimal('1') + self._iva_rate)

	def _on_cost_or_margin_changed(self, *_):
		if self._calc_lock:
			return
		self._calc_lock = True

		cost_real = self._get_cost_real()
		try:
			margin_pct = Decimal(self._var_margin.get().replace(',', '.'))
		except (ValueError, InvalidOperation):
			margin_pct = None

		if cost_real is not None and margin_pct is not None:
			precio = (
				cost_real * (Decimal('1') + margin_pct / Decimal('100'))
			).quantize(Decimal('0.01'), ROUND_HALF_UP)
			self._var_price_str.set(str(precio))
			ganancia = precio - cost_real
			self._lbl_formula_expr.configure(
				text=f'Costo con IVA: ${cost_real:.2f} | Ganancia: ${ganancia:.2f}'
			)
		else:
			self._lbl_formula_expr.configure(text='Faltan datos para calcular margen')

		self._calc_lock = False

	def _on_price_changed(self, *_):
		if self._calc_lock:
			return
		self._calc_lock = True

		cost_real = self._get_cost_real()
		try:
			precio = Decimal(self._var_price_str.get().replace(',', '.'))
		except (ValueError, InvalidOperation):
			precio = None

		if cost_real is not None and cost_real > 0 and precio is not None:
			real_margin = ((precio - cost_real) / cost_real * Decimal('100')).quantize(
				Decimal('0.01'), ROUND_HALF_UP
			)
			self._var_margin.set(str(real_margin))
			ganancia = precio - cost_real
			self._lbl_formula_expr.configure(
				text=f'Costo con IVA: ${cost_real:.2f} | Ganancia: ${ganancia:.2f}'
			)
		elif cost_real is not None and cost_real == 0 and precio is not None:
			self._var_margin.set('100.00')
			self._lbl_formula_expr.configure(
				text=f'Costo con IVA: $0.00 | Ganancia: ${precio:.2f}'
			)

		self._calc_lock = False

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
		self._on_supplier_changed()

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

		for i, variant in enumerate(matches):
			stock_actual = variant.get('total_stock', 0)
			stock_format = (
				f'{int(stock_actual)}'
				if float(stock_actual).is_integer()
				else f'{float(stock_actual):.2f}'
			)
			self.insert_tree_row(
				tree=self.tree,
				index=i,
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

		if hasattr(self, 'lbl_empty_tree'):
			if not matches:
				self.tree.pack_forget()
				self.tree_scroll.pack_forget()
				msg = (
					'🔍\nNo se encontraron productos con ese criterio.'
					if q
					else '📦\nNo hay productos en el catálogo.\nUsá el formulario de la izquierda para agregar el primero.'
				)
				self.lbl_empty_tree.configure(text=msg)
				self.lbl_empty_tree.pack(expand=True)
			else:
				self.lbl_empty_tree.pack_forget()
				if not self.tree.winfo_ismapped():
					self.tree_scroll.pack(side='right', fill='y')
					self.tree.pack(side='left', fill='both', expand=True)

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
			self.tabview.set('Precios')
			self.entry_price.focus()
		else:
			self.reset_form(keep_barcode=True)
			self.entry_name.focus()

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

		self._calc_lock = True
		self._var_cost_str.set(f'{variant.get("cost_price", 0):.2f}')
		self._var_price_str.set(f'{variant.get("selling_price", 0):.2f}')
		self._calc_lock = False
		self._on_price_changed()

		supplier_name = variant.get('supplier_name', 'Sin Proveedor')
		self.combo_supplier.set(
			supplier_name if supplier_name in self.suppliers_map else 'Sin Proveedor'
		)
		self._on_supplier_changed()

		self.lbl_stock.configure(text='STOCK ACTUAL')
		self.entry_stock.insert(0, f'Stock actual: {variant.get("total_stock", 0)} u')
		self.entry_stock.configure(state='disabled')

		# Descuento
		disc_pct = variant.get('discount_pct', 0) or 0
		if disc_pct > 0:
			self._var_discount_enabled.set(True)
			self._var_discount_pct.set(f'{disc_pct:.4g}')
			disc_until = variant.get('discount_until')
			if disc_until:
				from datetime import datetime as _dt
				if isinstance(disc_until, str):
					try:
						disc_until = _dt.fromisoformat(disc_until)
					except Exception:
						disc_until = None
				if disc_until:
					self._var_discount_until.set(disc_until.strftime('%d/%m/%Y'))
			else:
				self._var_discount_until.set('')
			self._frame_discount_fields.pack(fill='x', pady=(PAD_XS, PAD_SM))
		else:
			self._var_discount_enabled.set(False)
			self._var_discount_pct.set('')
			self._var_discount_until.set('')
			self._frame_discount_fields.pack_forget()

		self.lbl_form_title.configure(
			text='✏️ Editando Producto', text_color=ACCENT_TEXT
		)
		self.btn_add.configure(text='💾 Actualizar (Ctrl+G)')

		self.tabview.set('General')
		self._show_packaging_panel(variant['variant_id'])
		self.lbl_pack_hint.pack_forget()

	def reset_form(self, keep_barcode=False):
		self.editing_variant_id = None
		barcode_temp = self.entry_barcode.get() if keep_barcode else ''

		self.entry_barcode.delete(0, 'end')
		if keep_barcode:
			self.entry_barcode.insert(0, barcode_temp)

		self.lbl_barcode_msg.pack_forget()
		self.lbl_barcode_msg.configure(text='')

		self.entry_name.delete(0, 'end')

		self._calc_lock = True
		self._var_cost_str.set('')
		self._var_price_str.set('')
		self._var_margin.set('')
		self._var_iva_included.set(False)
		self._lbl_formula_expr.configure(text='Costo Real: $0.00 | Ganancia: $0.00')
		self._calc_lock = False

		self.lbl_stock.configure(text='STOCK INICIAL')
		self.entry_stock.configure(state='normal')
		self.entry_stock.delete(0, 'end')
		self.combo_supplier.set('Sin Proveedor')

		self.lbl_form_title.configure(text='📦 Nuevo Producto', text_color=TEXT_PRIMARY)
		self.btn_add.configure(text='💾 Guardar Producto (Ctrl+G)')

		# Descuento por producto
		self._var_discount_enabled.set(False)
		self._var_discount_pct.set('')
		self._var_discount_until.set('')
		self._frame_discount_fields.pack_forget()
		self.combo_supplier.set('Sin Proveedor')
		self._on_supplier_changed()

		self.lbl_pack_hint.configure(text='(Guarda el producto base primero)')
		self.lbl_pack_hint.pack(pady=PAD_LG)
		self.frame_pack_list.pack_forget()

		self.tabview.set('General')
		if not keep_barcode:
			self.entry_barcode.focus()

	def has_unsaved_changes(self) -> bool:
		return bool(self.entry_name.get().strip())

	def _generate_unique_barcode(self):
		while True:
			new_code = f'99{random.randint(1000000000, 9999999999)}'
			found = next(
				(v for v in self.current_variants if str(v.get('barcode')) == new_code),
				None,
			)
			if not found:
				return new_code

	def save_article(self):
		self.clear_field_errors(self.entry_name, self.entry_barcode)

		name = self.entry_name.get().strip()
		raw_barcode = self.entry_barcode.get().strip().lstrip('0')

		assigned_random_code = False
		if raw_barcode:
			barcode = raw_barcode
		else:
			barcode = self._generate_unique_barcode()
			assigned_random_code = True

		supplier_name = self.combo_supplier.get()
		supplier_id = self.suppliers_map.get(supplier_name)

		if not name:
			self.mark_field_error(self.entry_name, 'El nombre es obligatorio.')
			return

		if not self._var_cost_str.get() or not self._var_price_str.get():
			self.show_warning('Completá el costo y el precio de venta.')
			return

		try:
			cost_dec = Decimal(self._var_cost_str.get().replace(',', '.'))
			price_dec = Decimal(self._var_price_str.get().replace(',', '.'))

			if cost_dec < 0 or price_dec < 0:
				raise ValueError('No se admiten precios negativos.')

			cost = float(cost_dec)
			price = float(price_dec)

			initial_stock = 0.0
			if not self.editing_variant_id:
				stock_str = self.entry_stock.get().strip().replace(',', '.')
				initial_stock = float(stock_str) if stock_str else 0.0
				if initial_stock < 0:
					raise ValueError('El stock no puede ser negativo.')

		except (ValueError, InvalidOperation) as e:
			msg = (
				str(e)
				if 'negativo' in str(e)
				else 'Los precios y el stock deben ser números válidos.'
			)
			self.show_error(msg)
			return

		# Leer campos de descuento
		discount_pct = None
		discount_until = None
		if self._var_discount_enabled.get():
			raw_dpct = self._var_discount_pct.get().strip().replace(',', '.')
			try:
				discount_pct = float(raw_dpct) if raw_dpct else None
				if discount_pct is not None and (discount_pct <= 0 or discount_pct >= 100):
					self.show_warning('El descuento debe ser entre 0 y 100%.', 'Dato inválido')
					return
			except ValueError:
				self.show_warning('El porcentaje de descuento no es válido.', 'Dato inválido')
				return

			raw_duntil = self._var_discount_until.get().strip()
			if raw_duntil:
				from datetime import datetime as _dt
				for fmt in ('%d/%m/%Y', '%d/%m/%y', '%Y-%m-%d'):
					try:
						discount_until = _dt.strptime(raw_duntil, fmt).replace(
							hour=23, minute=59, second=59
						)
						break
					except ValueError:
						continue
				if discount_until is None:
					self.show_warning(
						'Fecha de vencimiento inválida. Usá DD/MM/AAAA.', 'Dato inválido'
					)
					return

		tenant_id = self.ctx.tenant_id
		user_id = self.ctx.user_id

		original_text = self.btn_add.cget('text')
		self.set_loading(self.btn_add, True)
		self.update_idletasks()

		try:
			if self.editing_variant_id:
				success, msg = self.controller.update_article(
					tenant_id,
					user_id,
					self.editing_variant_id,
					name,
					barcode,
					cost,
					price,
					supplier_id,
					discount_pct=discount_pct,
					discount_until=discount_until,
				)
			else:
				success, msg = self.controller.add_simple_article(
					tenant_id,
					user_id,
					name,
					barcode,
					cost,
					price,
					initial_stock,
					supplier_id,
					discount_pct=discount_pct,
					discount_until=discount_until,
				)
		finally:
			self.set_loading(self.btn_add, False, original_text)

		if success:
			self.show_success(msg)
			self.reset_form()
			if assigned_random_code:
				self.lbl_barcode_msg.configure(text=f'Código asignado: {barcode}')
				self.lbl_barcode_msg.pack(
					anchor='w',
					pady=(0, PAD_SM),
					before=self.entry_name.master.winfo_children()[2],
				)
			self.load_data()
			self.entry_barcode.focus()
		else:
			self.show_error(msg)

	def delete_article(self):
		selected_items = self.tree.selection()
		if not selected_items:
			return

		count = len(selected_items)
		item_text = 'este producto' if count == 1 else f'estos {count} productos'

		if self.confirm(f'¿Seguro que deseas eliminar {item_text}?', 'Confirmar'):
			success_count = 0
			error_msg = ''
			for item in selected_items:
				variant_id = self.tree.item(item, 'values')[0]
				success, msg_response = self.controller.delete_variant(
					self.ctx.tenant_id, variant_id
				)
				if success:
					success_count += 1
				else:
					error_msg = msg_response

			if success_count > 0:
				self.load_data()
				self.reset_form()
				msg = f'{success_count} producto(s) eliminado(s) correctamente.'
				if error_msg:
					msg += f' Hubo un error con al menos uno: {error_msg}'
				self.show_success(msg)
			else:
				self.show_error(error_msg or 'Error al eliminar productos.')

	def print_labels(self):
		selected_items = self.tree.selection()
		if not selected_items:
			self.show_warning('Selecciona al menos un artículo de la tabla.')
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
			ok, result = lbl_ctrl.generate_pdf(
				products_to_print, template_key='supermercado'
			)
			if ok:
				self.show_success('Etiquetas generadas correctamente.')
			else:
				self.show_error(f'No se pudo generar el PDF: {result}')
		except Exception as e:
			self.show_error(f'Excepción al generar etiquetas: {e}')

	def _show_packaging_panel(self, base_variant_id):
		for w in self.frame_pack_list.winfo_children():
			w.destroy()

		packs = self.controller.get_packaging_variants(base_variant_id)

		if packs:
			self.lbl_pack_hint.pack_forget()
			for p in packs:
				self._build_pack_row(p, base_variant_id)
			self.frame_pack_list.pack(fill='both', expand=True, pady=(PAD_SM, 0))
		else:
			self.frame_pack_list.pack_forget()
			self.lbl_pack_hint.configure(
				text='Sin presentaciones. Usa + Agregar para definir cajon, pallet, etc.'
			)
			self.lbl_pack_hint.pack(pady=PAD_LG)

		self.btn_add_pack.configure(
			command=lambda vid=base_variant_id: self._open_add_packaging_dialog(vid)
		)

	def _build_pack_row(self, pack, base_variant_id):
		row = ctk.CTkFrame(
			self.frame_pack_list,
			fg_color=SURFACE1,
			corner_radius=6,
			border_width=1,
			border_color=BORDER,
		)
		row.pack(fill='x', pady=(0, PAD_XS))
		row.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(
			row,
			text=pack['pack_label'],
			font=FONT_LABEL_BOLD,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).grid(row=0, column=0, sticky='w', padx=(PAD_SM, PAD_XS), pady=PAD_XS)

		ctk.CTkLabel(
			row,
			text=f'{pack["units_per_pack"]}u  |  ${pack["selling_price"]:,.2f}',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=0, column=1, sticky='w', pady=PAD_XS)

		btn_frame = ctk.CTkFrame(row, fg_color='transparent')
		btn_frame.grid(row=0, column=2, padx=(PAD_XS, PAD_SM), pady=PAD_XS)

		ctk.CTkButton(
			btn_frame,
			text='✏',
			width=28,
			height=24,
			font=FONT_LABEL,
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
			font=FONT_LABEL_BOLD,
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
		success, msg = self.controller.delete_packaging_variant(
			self.ctx.tenant_id, variant_id
		)
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
			title='Nueva Presentación',
			base_variant_id=base_variant_id,
			existing_pack=None,
		)

	def _open_edit_packaging_dialog(self, pack, base_variant_id):
		self._packaging_dialog(
			title='Editar Presentación',
			base_variant_id=base_variant_id,
			existing_pack=pack,
		)

	def _packaging_dialog(self, title, base_variant_id, existing_pack):
		is_edit = existing_pack is not None

		dialog = ctk.CTkToplevel(self)
		dialog.title(title)
		dialog.geometry('400x480')
		dialog.resizable(False, False)
		dialog.grab_set()
		dialog.focus()
		dialog.attributes('-topmost', True)

		ctk.CTkLabel(dialog, text=title, font=FONT_TITLE, text_color=TEXT_PRIMARY).pack(
			pady=(PAD_LG, PAD_XS)
		)

		ctk.CTkLabel(
			dialog,
			text='Definí nombre, cantidad y precio de venta del paquete.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
		).pack(pady=(0, PAD_MD))

		make_form_label(dialog, 'NOMBRE  (ej: Cajón 12u, Caja x6)', required=True)[
			0
		].pack(padx=PAD_LG, anchor='w')

		entry_label = ctk.CTkEntry(
			dialog,
			placeholder_text='Cajón 12 unidades',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		entry_label.pack(padx=PAD_LG, fill='x', pady=(0, PAD_SM))
		if is_edit:
			entry_label.insert(0, existing_pack.get('pack_label', ''))
		entry_label.focus()

		make_form_label(dialog, 'UNIDADES POR PAQUETE', required=True)[0].pack(
			padx=PAD_LG, anchor='w'
		)

		presets_row = ctk.CTkFrame(dialog, fg_color='transparent')
		presets_row.pack(padx=PAD_LG, fill='x', pady=(0, PAD_XS))
		entry_units = ctk.CTkEntry(
			dialog,
			placeholder_text='Ej: 6, 12, 24, 200',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
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
				font=FONT_BODY,
				fg_color=SURFACE3,
				hover_color=SURFACE4,
				text_color=TEXT_SECONDARY,
				border_width=1,
				border_color=BORDER,
				corner_radius=6,
				command=lambda v=qty: _set_units(v),
			).pack(side='left', padx=(0, PAD_XS))

		entry_units.pack(padx=PAD_LG, fill='x', pady=(0, PAD_SM))
		if is_edit:
			entry_units.insert(0, str(existing_pack.get('units_per_pack', '')))

		make_form_label(dialog, 'PRECIO DE VENTA DEL PAQUETE ($)', required=True)[
			0
		].pack(padx=PAD_LG, anchor='w')

		entry_price = ctk.CTkEntry(
			dialog,
			placeholder_text='Ej: 5000',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		entry_price.pack(padx=PAD_LG, fill='x', pady=(0, PAD_SM))
		if is_edit:
			entry_price.insert(0, f'{existing_pack.get("selling_price", ""):.2f}')

		make_form_label(dialog, 'CÓDIGO DE BARRAS  (opcional)', required=False)[0].pack(
			padx=PAD_LG, anchor='w'
		)

		entry_barcode = ctk.CTkEntry(
			dialog,
			placeholder_text='Dejar vacío si no tiene',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		entry_barcode.pack(padx=PAD_LG, fill='x', pady=(0, PAD_XS))
		if is_edit and existing_pack.get('barcode'):
			entry_barcode.insert(0, existing_pack['barcode'])

		lbl_err = ctk.CTkLabel(
			dialog, text='', font=FONT_LABEL_BOLD, text_color=RED_TEXT
		)
		lbl_err.pack(pady=(0, PAD_XS))

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
				lbl_err.configure(text='Unidades debe ser entero y precio un número.')
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
			text='Guardar Cambios' if is_edit else 'Agregar Presentación',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=40,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=_do_save,
		).pack(padx=PAD_LG, fill='x')

		entry_barcode.bind('<Return>', lambda e: _do_save())
