"""
views/batch_edit_view.py
========================
Gestión masiva de atributos y precios.
Layout vertical: filtros → tabla → barra de acción fija al fondo.
"""

import threading
from decimal import Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk

from controllers.article_controller import ArticleController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_HOVER,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_BODY_BOLD,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	GREEN_DIM,
	GREEN_TEXT,
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


class BatchEditView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = ArticleController(ctx.db_engine)

		self.catalog: list = []
		self._display_list: list = []
		self.selected_ids: set = set()
		self._last_clicked_idx: int | None = None
		self._search_after_id = None
		self._sort_col: str | None = None
		self._sort_reverse: bool = False

		self.suppliers_map: dict = {}
		self.categories_map: dict = {}

		self.grid_columnconfigure(0, weight=1)  # panel izquierdo (filtros + tabla)
		self.grid_columnconfigure(1, weight=0, minsize=320)  # panel derecho (edición masiva)
		self.grid_rowconfigure(0, weight=0)  # filtros
		self.grid_rowconfigure(1, weight=1)  # tabla

		apply_treeview_style()
		self._build_filter_bar()
		self._build_table()
		self._build_action_bar()

		self.after(100, self.load_data)

	# =========================================================
	# BARRA DE FILTROS
	# =========================================================
	def _build_filter_bar(self):
		bar = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		bar.grid(row=0, column=0, sticky='ew', padx=(16, 8), pady=(14, 6))
		bar.grid_columnconfigure(0, weight=1)

		inner = ctk.CTkFrame(bar, fg_color='transparent')
		inner.pack(fill='x', padx=14, pady=10)

		# Búsqueda
		self.entry_search = ctk.CTkEntry(
			inner,
			placeholder_text='🔍  Buscar por nombre o código...',
			height=36,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
		)
		self.entry_search.pack(side='left', fill='x', expand=True, padx=(0, 10))
		self.entry_search.bind('<KeyRelease>', self._on_search_key)

		# Proveedor
		self.combo_filter_supplier = ctk.CTkComboBox(
			inner,
			values=['Todos los proveedores'],
			width=170,
			height=36,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			button_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			text_color=TEXT_PRIMARY,
			command=lambda v: self.refresh_table(),
		)
		self.combo_filter_supplier.pack(side='left', padx=(0, 8))

		# Categoría
		self.combo_filter_category = ctk.CTkComboBox(
			inner,
			values=['Todas las categorías'],
			width=160,
			height=36,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			button_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			text_color=TEXT_PRIMARY,
			command=lambda v: self.refresh_table(),
		)
		self.combo_filter_category.pack(side='left', padx=(0, 10))

		# Inactivos
		self.show_inactive_var = ctk.BooleanVar(master=self, value=False)
		ctk.CTkCheckBox(
			inner,
			text='Ver inactivos',
			variable=self.show_inactive_var,
			fg_color=ACCENT,
			font=FONT_LABEL,
			text_color=TEXT_SECONDARY,
			command=self.load_data,
		).pack(side='left', padx=(0, 10))

		# Botones selección
		ctk.CTkFrame(inner, width=1, fg_color=BORDER).pack(
			side='left', fill='y', padx=(0, 10)
		)

		ctk.CTkButton(
			inner,
			text='☑ Todos',
			width=80,
			height=30,
			font=FONT_LABEL_BOLD,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			command=self.select_all_visible,
		).pack(side='left', padx=(0, 6))

		ctk.CTkButton(
			inner,
			text='☐ Ninguno',
			width=90,
			height=30,
			font=FONT_LABEL_BOLD,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			command=self.deselect_all,
		).pack(side='left')

		self.lbl_count = ctk.CTkLabel(
			inner,
			text='',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		)
		self.lbl_count.pack(side='right')

	# =========================================================
	# TABLA
	# =========================================================
	def _build_table(self):
		wrap = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		wrap.grid(row=1, column=0, sticky='nsew', padx=(16, 8), pady=(4, 14))
		wrap.grid_rowconfigure(0, weight=1)
		wrap.grid_columnconfigure(0, weight=1)

		tree_wrap = ctk.CTkFrame(wrap, fg_color='transparent')
		tree_wrap.pack(fill='both', expand=True, padx=12, pady=10)
		tree_wrap.grid_rowconfigure(0, weight=1)
		tree_wrap.grid_columnconfigure(0, weight=1)

		vsb = ttk.Scrollbar(tree_wrap, orient='vertical')
		columns = (
			'Sel',
			'Producto',
			'Proveedor',
			'Categoría',
			'P.Venta',
			'P.Costo',
			'Stock',
			'Estado',
			'Táctil',
		)
		self.tree = ttk.Treeview(
			tree_wrap,
			columns=columns,
			show='headings',
			yscrollcommand=vsb.set,
			selectmode='none',
		)
		vsb.configure(command=self.tree.yview)

		col_cfg = {
			'Sel': (36, 'center'),
			'Producto': (220, 'w'),
			'Proveedor': (110, 'center'),
			'Categoría': (110, 'center'),
			'P.Venta': (85, 'center'),
			'P.Costo': (85, 'center'),
			'Stock': (55, 'center'),
			'Estado': (72, 'center'),
			'Táctil': (60, 'center'),
		}
		for col in columns:
			w, anchor = col_cfg[col]
			self.tree.heading(col, text=col, command=lambda c=col: self._sort(c, False))
			self.tree.column(col, width=w, anchor=anchor, minwidth=w)

		self.tree.tag_configure(
			'selected', background=ACCENT_DIM, foreground=ACCENT_TEXT
		)
		self.tree.tag_configure('odd', background=SURFACE2)
		self.tree.tag_configure('even', background=SURFACE3)

		vsb.grid(row=0, column=1, sticky='ns')
		self.tree.grid(row=0, column=0, sticky='nsew')

		self.tree.bind('<Button-1>', self._on_click)
		self.tree.bind('<Shift-Button-1>', self._on_shift_click)

	# =========================================================
	# BARRA DE ACCIÓN (fondo fijo)
	# =========================================================
	def _build_action_bar(self):
		self.action_bar = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.action_bar.grid(row=0, column=1, rowspan=2, sticky='nsew', padx=(8, 16), pady=(14, 14))

		inner = ctk.CTkFrame(self.action_bar, fg_color='transparent')
		inner.pack(fill='both', expand=True, padx=16, pady=16)

		# Título del panel
		ctk.CTkLabel(
			inner,
			text='EDICIÓN MASIVA',
			font=FONT_BODY_BOLD,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(fill='x', pady=(0, 12))

		# Badge de selección
		self.lbl_sel_badge = ctk.CTkLabel(
			inner,
			text='Seleccioná productos para editar',
			font=FONT_LABEL_BOLD,
			fg_color=SURFACE3,
			text_color=TEXT_MUTED,
			corner_radius=8,
			padx=12,
			pady=6,
			height=36,
		)
		self.lbl_sel_badge.pack(fill='x', pady=(0, 16))

		# Separador
		ctk.CTkFrame(inner, height=1, fg_color=BORDER).pack(fill='x', pady=(0, 14))

		# ── Sección: Precios ───────────────────────────────────────
		ctk.CTkLabel(
			inner, text='Precio Venta ($)', font=FONT_LABEL_BOLD, text_color=TEXT_MUTED, anchor='w'
		).pack(fill='x', pady=(0, 4))
		self.entry_selling_price = ctk.CTkEntry(
			inner,
			placeholder_text='Sin cambio',
			height=32,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
		)
		self.entry_selling_price.pack(fill='x', pady=(0, 12))
		self.entry_selling_price.bind(
			'<KeyRelease>', lambda e: self._update_action_bar()
		)

		ctk.CTkLabel(
			inner, text='Precio Costo ($)', font=FONT_LABEL_BOLD, text_color=TEXT_MUTED, anchor='w'
		).pack(fill='x', pady=(0, 4))
		self.entry_cost_price = ctk.CTkEntry(
			inner,
			placeholder_text='Sin cambio',
			height=32,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
		)
		self.entry_cost_price.pack(fill='x', pady=(0, 16))
		self.entry_cost_price.bind('<KeyRelease>', lambda e: self._update_action_bar())

		# ── Sección: Clasificación ─────────────────────────────────
		ctk.CTkLabel(
			inner, text='Proveedor', font=FONT_LABEL_BOLD, text_color=TEXT_MUTED, anchor='w'
		).pack(fill='x', pady=(0, 4))
		self.combo_new_supplier = ctk.CTkComboBox(
			inner,
			values=['(Sin cambio)'],
			height=32,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			button_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			text_color=TEXT_PRIMARY,
			command=lambda v: self._update_action_bar(),
		)
		self.combo_new_supplier.pack(fill='x', pady=(0, 12))

		ctk.CTkLabel(
			inner, text='Categoría', font=FONT_LABEL_BOLD, text_color=TEXT_MUTED, anchor='w'
		).pack(fill='x', pady=(0, 4))
		self.combo_new_category = ctk.CTkComboBox(
			inner,
			values=['(Sin cambio)'],
			height=32,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			button_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			text_color=TEXT_PRIMARY,
			command=lambda v: self._update_action_bar(),
		)
		self.combo_new_category.pack(fill='x', pady=(0, 16))

		# ── Sección: Propiedades ───────────────────────────────────
		ctk.CTkLabel(
			inner, text='Estado', font=FONT_LABEL_BOLD, text_color=TEXT_MUTED, anchor='w'
		).pack(fill='x', pady=(0, 4))
		self.seg_estado = ctk.CTkSegmentedButton(
			inner,
			values=['—', 'Activo', 'Inactivo'],
			fg_color=SURFACE3,
			selected_color=ACCENT_DIM,
			selected_hover_color=ACCENT,
			unselected_color=SURFACE3,
			unselected_hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			font=FONT_LABEL_BOLD,
			height=30,
			command=lambda v: self._update_action_bar(),
		)
		self.seg_estado.set('—')
		self.seg_estado.pack(fill='x', pady=(0, 12))

		ctk.CTkLabel(
			inner, text='Táctil', font=FONT_LABEL_BOLD, text_color=TEXT_MUTED, anchor='w'
		).pack(fill='x', pady=(0, 4))
		self.seg_tactil = ctk.CTkSegmentedButton(
			inner,
			values=['—', 'Sí', 'No'],
			fg_color=SURFACE3,
			selected_color=ACCENT_DIM,
			selected_hover_color=ACCENT,
			unselected_color=SURFACE3,
			unselected_hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			font=FONT_LABEL_BOLD,
			height=30,
			command=lambda v: self._update_action_bar(),
		)
		self.seg_tactil.set('—')
		self.seg_tactil.pack(fill='x', pady=(0, 16))

		# Espacio flexible para empujar los botones de acción al fondo
		spacer = ctk.CTkFrame(inner, fg_color='transparent', height=0)
		spacer.pack(fill='both', expand=True)

		# Botones de Acción al fondo
		self.btn_apply = ctk.CTkButton(
			inner,
			text='🚀  APLICAR CAMBIOS',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT_HOVER,
			text_color=TEXT_MUTED,
			height=38,
			font=FONT_BODY_BOLD,
			corner_radius=8,
			state='disabled',
			command=self.confirm_bulk_update,
		)
		self.btn_apply.pack(side='bottom', fill='x', pady=(8, 0))

		ctk.CTkButton(
			inner,
			text='✕  Limpiar',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			height=34,
			font=FONT_LABEL_BOLD,
			corner_radius=8,
			command=self._clear_fields,
		).pack(side='bottom', fill='x')

	# =========================================================
	# ESTADO DE LA BARRA DE ACCIÓN
	# =========================================================
	def _has_any_change(self) -> bool:
		return bool(
			self.entry_selling_price.get().strip()
			or self.entry_cost_price.get().strip()
			or self.combo_new_supplier.get() not in ('(Sin cambio)', '')
			or self.combo_new_category.get() not in ('(Sin cambio)', '')
			or self.seg_estado.get() != '—'
			or self.seg_tactil.get() != '—'
		)

	def _update_action_bar(self):
		count = len(self.selected_ids)
		has_change = self._has_any_change()

		if count == 0:
			self.lbl_sel_badge.configure(
				text='Seleccioná productos para editar',
				fg_color=SURFACE3,
				text_color=TEXT_MUTED,
			)
			self.btn_apply.configure(
				state='disabled',
				fg_color=ACCENT_DIM,
				text_color=TEXT_MUTED,
				text='🚀  APLICAR CAMBIOS',
			)
		elif has_change:
			self.lbl_sel_badge.configure(
				text=f'✓  {count} producto{"s" if count > 1 else ""} listo{"s" if count > 1 else ""}',
				fg_color=GREEN_DIM,
				text_color=GREEN_TEXT,
			)
			self.btn_apply.configure(
				state='normal',
				fg_color=ACCENT,
				text_color=TEXT_PRIMARY,
				text='🚀  APLICAR CAMBIOS',
			)
		else:
			self.lbl_sel_badge.configure(
				text=f'{count} seleccionado{"s" if count > 1 else ""}  ·  completá un campo',
				fg_color=ORANGE_DIM,
				text_color=ORANGE_TEXT,
			)
			self.btn_apply.configure(
				state='disabled',
				fg_color=ACCENT_DIM,
				text_color=TEXT_MUTED,
				text='🚀  APLICAR CAMBIOS',
			)

	def _clear_fields(self):
		self.entry_selling_price.delete(0, 'end')
		self.entry_cost_price.delete(0, 'end')
		self.combo_new_supplier.set('(Sin cambio)')
		self.combo_new_category.set('(Sin cambio)')
		self.seg_estado.set('—')
		self.seg_tactil.set('—')
		self._update_action_bar()

	# =========================================================
	# CARGA Y FILTRADO
	# =========================================================
	def load_data(self):
		if not self.winfo_exists():
			return
		tid = self.ctx.tenant_id
		self.catalog = self.controller.get_all_variants(
			tid, include_inactive=self.show_inactive_var.get()
		)

		suppliers = self.controller.get_suppliers_for_combo(tid)
		self.suppliers_map = {s['name']: s['id'] for s in suppliers}

		categories = self.controller.get_categories_for_combo(tid)
		self.categories_map = {c['name']: c['id'] for c in categories}

		s_vals = ['Todos los proveedores'] + list(self.suppliers_map.keys())
		c_vals = ['Todas las categorías'] + list(self.categories_map.keys())
		self.combo_filter_supplier.configure(values=s_vals)
		self.combo_filter_category.configure(values=c_vals)
		self.combo_new_supplier.configure(
			values=['(Sin cambio)'] + list(self.suppliers_map.keys())
		)
		self.combo_new_category.configure(
			values=['(Sin cambio)'] + list(self.categories_map.keys())
		)

		self.refresh_table()

	def refresh_table(self):
		if not self.winfo_exists():
			return
		search = self.entry_search.get().lower().strip()
		sup_f = self.combo_filter_supplier.get()
		cat_f = self.combo_filter_category.get()

		for row in self.tree.get_children():
			self.tree.delete(row)

		self._display_list = []
		for item in self.catalog:
			if (
				search
				and search not in item['name'].lower()
				and search not in (item.get('barcode') or '').lower()
			):
				continue
			if sup_f != 'Todos los proveedores' and item.get('supplier_name') != sup_f:
				continue
			if cat_f != 'Todas las categorías' and item.get('category_name') != cat_f:
				continue
			self._display_list.append(item)

		for i, item in enumerate(self._display_list):
			vid = item['variant_id']
			is_sel = vid in self.selected_ids
			sel = '☑' if is_sel else '☐'
			tags = ('selected',) if is_sel else ('odd' if i % 2 == 0 else 'even',)
			venta = f'${float(item.get("selling_price") or 0):,.2f}'
			costo = f'${float(item.get("cost_price") or 0):,.2f}'
			estado = '✔ Activo' if item.get('is_active', True) else '✕ Inactivo'
			tactil = '✔' if item.get('show_on_touch') else '—'

			self.tree.insert(
				'',
				'end',
				iid=str(vid),
				values=(
					sel,
					item['name'],
					item.get('supplier_name', '—'),
					item.get('category_name', '—'),
					venta,
					costo,
					item.get('total_stock', 0),
					estado,
					tactil,
				),
				tags=tags,
			)

		total = len(self._display_list)
		sel = len(self.selected_ids)
		txt = f'{total} producto{"s" if total != 1 else ""}'
		if sel:
			txt += f'  ·  {sel} seleccionado{"s" if sel != 1 else ""}'
		self.lbl_count.configure(text=txt)

	# =========================================================
	# SELECCIÓN
	# =========================================================
	def _row_index(self, iid: str) -> int:
		for i, item in enumerate(self._display_list):
			if str(item['variant_id']) == iid:
				return i
		return -1

	def _on_click(self, event):
		if self.tree.identify_region(event.x, event.y) != 'cell':
			return
		iid = self.tree.identify_row(event.y)
		if not iid:
			return
		self._toggle(iid)
		self._last_clicked_idx = self._row_index(iid)

	def _on_shift_click(self, event):
		if self.tree.identify_region(event.x, event.y) != 'cell':
			return
		iid = self.tree.identify_row(event.y)
		if not iid:
			return
		cur = self._row_index(iid)
		if cur == -1:
			return
		if self._last_clicked_idx is None:
			self._toggle(iid)
			self._last_clicked_idx = cur
			return
		lo, hi = min(self._last_clicked_idx, cur), max(self._last_clicked_idx, cur)
		for item in self._display_list[lo : hi + 1]:
			self.selected_ids.add(item['variant_id'])
		self.refresh_table()
		self._update_action_bar()

	def _toggle(self, iid: str):
		match = next(
			(
				item['variant_id']
				for item in self._display_list
				if str(item['variant_id']) == iid
			),
			None,
		)
		if match is None:
			return
		if match in self.selected_ids:
			self.selected_ids.discard(match)
		else:
			self.selected_ids.add(match)
		self.refresh_table()
		self._update_action_bar()

	def select_all_visible(self):
		for item in self._display_list:
			self.selected_ids.add(item['variant_id'])
		self.refresh_table()
		self._update_action_bar()

	def deselect_all(self):
		self.selected_ids.clear()
		self._last_clicked_idx = None
		self.refresh_table()
		self._update_action_bar()

	def destroy(self):
		if getattr(self, '_search_after_id', None):
			try:
				self.after_cancel(self._search_after_id)
			except Exception:
				pass
			self._search_after_id = None
		super().destroy()

	# =========================================================
	# BÚSQUEDA CON DEBOUNCE
	# =========================================================
	def _on_search_key(self, _event=None):
		if self._search_after_id:
			self.after_cancel(self._search_after_id)
		self._search_after_id = self.after(250, self.refresh_table)

	# =========================================================
	# ORDENAMIENTO
	# =========================================================
	def _sort(self, col: str, reverse: bool):
		rows = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]

		def key(tup):
			val = tup[0]
			if val in ('—', '☐', '☑', ''):
				return 999999 if not reverse else -999999
			if val.startswith('$'):
				try:
					return float(val.replace('$', '').replace(',', ''))
				except ValueError:
					return 0.0
			return val.lower()

		rows.sort(key=key, reverse=reverse)
		for idx, (_, k) in enumerate(rows):
			self.tree.move(k, '', idx)

		self._sort_col = col
		self._sort_reverse = reverse
		self._refresh_sort_indicators()
		self.tree.heading(col, command=lambda: self._sort(col, not reverse))

	def _refresh_sort_indicators(self):
		columns = (
			'Sel',
			'Producto',
			'Proveedor',
			'Categoría',
			'P.Venta',
			'P.Costo',
			'Stock',
			'Estado',
			'Táctil',
		)
		for c in columns:
			if c == self._sort_col:
				arrow = ' ▲' if not self._sort_reverse else ' ▼'
				self.tree.heading(c, text=c + arrow)
			else:
				self.tree.heading(c, text=c)

	# =========================================================
	# APLICAR CAMBIOS
	# =========================================================
	def confirm_bulk_update(self):
		if not self.selected_ids:
			self.show_warning('Seleccioná productos de la lista primero.')
			return

		updates: dict = {}

		venta_str = self.entry_selling_price.get().strip().replace(',', '.')
		if venta_str:
			try:
				val = Decimal(venta_str)
				if val < 0:
					raise ValueError
				updates['selling_price'] = val
			except (InvalidOperation, ValueError):
				self.show_error('El precio de venta debe ser un número positivo.')
				return

		costo_str = self.entry_cost_price.get().strip().replace(',', '.')
		if costo_str:
			try:
				val = Decimal(costo_str)
				if val < 0:
					raise ValueError
				updates['cost_price'] = val
			except (InvalidOperation, ValueError):
				self.show_error('El precio de costo debe ser un número positivo.')
				return

		new_sup = self.combo_new_supplier.get()
		if new_sup and new_sup != '(Sin cambio)':
			sup_id = self.suppliers_map.get(new_sup)
			if not sup_id:
				self.show_error('Proveedor inválido.')
				return
			updates['supplier_id'] = sup_id

		new_cat = self.combo_new_category.get()
		if new_cat and new_cat != '(Sin cambio)':
			cat_id = self.categories_map.get(new_cat)
			if not cat_id:
				self.show_error('Categoría inválida.')
				return
			updates['category_id'] = cat_id

		estado_val = self.seg_estado.get()
		if estado_val != '—':
			updates['is_active'] = estado_val == 'Activo'

		tactil_val = self.seg_tactil.get()
		if tactil_val != '—':
			updates['show_on_touch'] = tactil_val == 'Sí'

		if not updates:
			self.show_warning('Completá al menos un campo para aplicar.')
			return

		count = len(self.selected_ids)
		lines = [f'Se modificarán {count} producto{"s" if count > 1 else ""}:\n']
		if 'selling_price' in updates:
			lines.append(f'• Precio de Venta → ${float(updates["selling_price"]):,.2f}')
		if 'cost_price' in updates:
			lines.append(f'• Precio de Costo → ${float(updates["cost_price"]):,.2f}')
		if 'supplier_id' in updates:
			lines.append(f'• Proveedor → {new_sup}')
		if 'category_id' in updates:
			lines.append(f'• Categoría → {new_cat}')
		if 'is_active' in updates:
			lines.append(
				f'• Estado → {"Activo" if updates["is_active"] else "Inactivo"}'
			)
		if 'show_on_touch' in updates:
			lines.append(f'• Táctil → {"Sí" if updates["show_on_touch"] else "No"}')

		if not self.confirm('\n'.join(lines)):
			return

		orig = self.btn_apply.cget('text')
		self.set_loading(self.btn_apply, True)

		_tenant = self.ctx.tenant_id
		_user = self.ctx.user_id
		_ids = list(self.selected_ids)

		def _run():
			try:
				ok, msg = self.controller.bulk_update_variants(
					_tenant, _user, _ids, updates
				)
			except Exception as exc:
				ok, msg = False, str(exc)
			if self.winfo_exists():
				self.after(0, lambda: _done(ok, msg))

		def _done(ok, msg):
			self.set_loading(self.btn_apply, False, orig)
			if ok:
				self.show_success(msg)
				self.selected_ids.clear()
				self._last_clicked_idx = None
				self._clear_fields()
				self.load_data()
			else:
				self.show_error(msg)

		threading.Thread(target=_run, daemon=True).start()
