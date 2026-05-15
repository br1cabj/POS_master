"""
views/batch_edit_view.py
========================
Vista para la edición masiva de atributos de artículos.
Permite cambiar proveedor, categoría, estado y descuentos de forma grupal.
"""

from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

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
	FONT_HEADING,
	FONT_SMALL_BOLD,
	ORANGE_TEXT,
	SURFACE2,
	SURFACE3,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	apply_treeview_style,
)


class BatchEditView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = ArticleController(ctx.db_engine)

		self.catalog = []
		self._display_list = []
		self.selected_ids = set()

		self.suppliers_map = {}
		self.categories_map = {}

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=3)
		self.grid_rowconfigure(0, weight=1)

		apply_treeview_style()
		self._build_left_panel()
		self._build_right_panel()

		self.after(100, self.load_data)

	def _build_left_panel(self):
		self.left_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)

		ctk.CTkLabel(
			self.left_panel,
			text='🛠️  Gestión Masiva',
			font=('Arial', 18, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(22, 10))

		ctk.CTkLabel(
			self.left_panel,
			text='MODIFICAR SELECCIONADOS',
			font=('Arial', 10, 'bold'),
			text_color=TEXT_MUTED,
		).pack(pady=(0, 20))

		# --- Campos de acción ---
		self._build_action_field('NUEVO PROVEEDOR', 'combo_new_supplier')
		self._build_action_field('NUEVA CATEGORÍA', 'combo_new_category')
		self._build_action_field('DESCUENTO (%)', 'entry_new_discount', is_entry=True)

		# Estado activo — solo se aplica si el checkbox está activo
		ctk.CTkFrame(self.left_panel, height=1, fg_color=BORDER).pack(
			fill='x', padx=20, pady=(14, 6)
		)
		ctk.CTkLabel(
			self.left_panel,
			text='ESTADO (opcional)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(0, 4))

		self.apply_status_var = ctk.BooleanVar(value=False)
		self.check_active_var = ctk.BooleanVar(value=True)
		row_status = ctk.CTkFrame(self.left_panel, fg_color='transparent')
		row_status.pack(fill='x', padx=20, pady=(0, 6))
		ctk.CTkCheckBox(
			row_status,
			text='Aplicar estado:',
			variable=self.apply_status_var,
			text_color=TEXT_SECONDARY,
		).pack(side='left')
		ctk.CTkRadioButton(
			row_status,
			text='Activo',
			variable=self.check_active_var,
			value=True,
			fg_color=ACCENT,
			font=('Arial', 11),
		).pack(side='left', padx=(10, 6))
		ctk.CTkRadioButton(
			row_status,
			text='Inactivo',
			variable=self.check_active_var,
			value=False,
			fg_color=ACCENT,
			font=('Arial', 11),
		).pack(side='left')

		self.apply_touch_var = ctk.BooleanVar(value=False)
		self.check_touch_var = ctk.BooleanVar(value=False)
		row_touch = ctk.CTkFrame(self.left_panel, fg_color='transparent')
		row_touch.pack(fill='x', padx=20, pady=(0, 8))
		ctk.CTkCheckBox(
			row_touch,
			text='Aplicar táctil:',
			variable=self.apply_touch_var,
			text_color=TEXT_SECONDARY,
		).pack(side='left')
		ctk.CTkRadioButton(
			row_touch,
			text='Sí',
			variable=self.check_touch_var,
			value=True,
			fg_color=ACCENT,
			font=('Arial', 11),
		).pack(side='left', padx=(10, 6))
		ctk.CTkRadioButton(
			row_touch,
			text='No',
			variable=self.check_touch_var,
			value=False,
			fg_color=ACCENT,
			font=('Arial', 11),
		).pack(side='left')

		ctk.CTkFrame(self.left_panel, height=1, fg_color=BORDER).pack(
			fill='x', padx=20, pady=(6, 12)
		)

		self.btn_apply = ctk.CTkButton(
			self.left_panel,
			text='🚀  APLICAR CAMBIOS',
			fg_color=ACCENT,
			hover_color=ACCENT_HOVER,
			text_color=TEXT_PRIMARY,
			height=45,
			font=FONT_HEADING,
			corner_radius=8,
			command=self.confirm_bulk_update,
		)
		self.btn_apply.pack(pady=(0, 10), padx=20, fill='x')

		self.lbl_selected_info = ctk.CTkLabel(
			self.left_panel,
			text='0 ítems seleccionados',
			font=FONT_SMALL_BOLD,
			text_color=ORANGE_TEXT,
		)
		self.lbl_selected_info.pack(pady=10)

	def _build_action_field(self, label, attr_name, is_entry=False):
		ctk.CTkLabel(
			self.left_panel,
			text=label,
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(10, 0))

		if is_entry:
			widget = ctk.CTkEntry(
				self.left_panel,
				placeholder_text='0',
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				height=34,
			)
		else:
			widget = ctk.CTkComboBox(
				self.left_panel,
				values=['Cargando...'],
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				height=34,
			)
		widget.pack(pady=(2, 5), padx=20, fill='x')
		setattr(self, attr_name, widget)

	def _build_right_panel(self):
		self.right_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=16)

		# Filtros superiores
		filter_bar = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		filter_bar.pack(fill='x', padx=16, pady=16)

		self.entry_search = ctk.CTkEntry(
			filter_bar,
			placeholder_text='🔍 Buscar por nombre o código...',
			height=38,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
		)
		self.entry_search.pack(side='left', fill='x', expand=True, padx=(0, 10))
		self.entry_search.bind('<KeyRelease>', lambda e: self.refresh_table())

		self.combo_filter_supplier = ctk.CTkComboBox(
			filter_bar,
			values=['Todos los proveedores'],
			width=180,
			height=38,
			command=lambda v: self.refresh_table(),
		)
		self.combo_filter_supplier.pack(side='left', padx=(0, 10))

		self.combo_filter_category = ctk.CTkComboBox(
			filter_bar,
			values=['Todas las categorías'],
			width=180,
			height=38,
			command=lambda v: self.refresh_table(),
		)
		self.combo_filter_category.pack(side='left', padx=(0, 10))

		self.show_inactive_var = ctk.BooleanVar(value=False)
		ctk.CTkCheckBox(
			filter_bar,
			text='Ver inactivos',
			variable=self.show_inactive_var,
			fg_color=ACCENT,
			font=('Arial', 11),
			text_color=TEXT_SECONDARY,
			command=self.load_data,
		).pack(side='left')

		# Botones de selección masiva
		sel_bar = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		sel_bar.pack(fill='x', padx=16, pady=(0, 10))

		ctk.CTkButton(
			sel_bar,
			text='Seleccionar Todos',
			width=130,
			height=28,
			font=FONT_SMALL_BOLD,
			fg_color=SURFACE3,
			command=self.select_all_visible,
		).pack(side='left', padx=(0, 8))

		ctk.CTkButton(
			sel_bar,
			text='Deseleccionar Todos',
			width=140,
			height=28,
			font=FONT_SMALL_BOLD,
			fg_color=SURFACE3,
			command=self.deselect_all,
		).pack(side='left')

		# Tabla
		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=16, pady=(0, 16))

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')
		columns = (
			'Sel',
			'Producto',
			'Proveedor',
			'Categoría',
			'Precio',
			'Stock',
			'Estado',
		)
		self.tree = ttk.Treeview(
			self.table_container,
			columns=columns,
			show='headings',
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		col_widths = {
			'Sel': (40, 'center'),
			'Producto': (230, 'w'),
			'Proveedor': (120, 'center'),
			'Categoría': (120, 'center'),
			'Precio': (90, 'center'),
			'Stock': (70, 'center'),
			'Estado': (75, 'center'),
		}
		for col in columns:
			w, anchor = col_widths[col]
			self.tree.heading(col, text=col)
			self.tree.column(col, width=w, anchor=anchor)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.tree.bind('<Button-1>', self.on_tree_click)

		self.tree.tag_configure(
			'selected', background=ACCENT_DIM, foreground=ACCENT_TEXT
		)

	def load_data(self):
		if not self.winfo_exists():
			return

		tenant_id = self.ctx.tenant_id
		include_inactive = self.show_inactive_var.get()
		self.catalog = self.controller.get_all_variants(
			tenant_id, include_inactive=include_inactive
		)

		suppliers = self.controller.get_suppliers_for_combo(tenant_id)
		self.suppliers_map = {s['name']: s['id'] for s in suppliers}

		categories = self.controller.get_categories_for_combo(tenant_id)
		self.categories_map = {c['name']: c['id'] for c in categories}

		# Actualizar Combos
		s_names = ['Todos los proveedores'] + list(self.suppliers_map.keys())
		self.combo_filter_supplier.configure(values=s_names)
		self.combo_new_supplier.configure(
			values=['(No cambiar)'] + list(self.suppliers_map.keys())
		)
		self.combo_new_supplier.set('(No cambiar)')

		c_names = ['Todas las categorías'] + list(self.categories_map.keys())
		self.combo_filter_category.configure(values=c_names)
		self.combo_new_category.configure(
			values=['(No cambiar)'] + list(self.categories_map.keys())
		)
		self.combo_new_category.set('(No cambiar)')

		self.refresh_table()

	def refresh_table(self):
		search = self.entry_search.get().lower()
		sup_filter = self.combo_filter_supplier.get()
		cat_filter = self.combo_filter_category.get()

		for item in self.tree.get_children():
			self.tree.delete(item)

		self._display_list = []
		for item in self.catalog:
			# Filtrado
			if (
				search
				and search not in item['name'].lower()
				and search not in (item['barcode'] or '').lower()
			):
				continue
			if (
				sup_filter != 'Todos los proveedores'
				and item['supplier_name'] != sup_filter
			):
				continue
			if (
				cat_filter != 'Todas las categorías'
				and item['category_name'] != cat_filter
			):
				continue

			self._display_list.append(item)

			vid = item['variant_id']
			is_sel = vid in self.selected_ids
			sel_mark = '●' if is_sel else '○'
			tags = ('selected',) if is_sel else ()

			estado = '✔ Activo' if item.get('is_active', True) else '✕ Inactivo'
			self.tree.insert(
				'',
				'end',
				values=(
					sel_mark,
					item['name'],
					item['supplier_name'],
					item['category_name'],
					f'${item["selling_price"]:,.2f}',
					item['total_stock'],
					estado,
				),
				iid=vid,
				tags=tags,
			)

		self.update_selection_label()

	def on_tree_click(self, event):
		region = self.tree.identify_region(event.x, event.y)
		if region != 'cell':
			return
		item_id = self.tree.identify_row(event.y)
		if not item_id:
			return
		# Toggle selección al hacer clic en cualquier celda de la fila
		if item_id in self.selected_ids:
			self.selected_ids.remove(item_id)
		else:
			self.selected_ids.add(item_id)
		self.refresh_table()

	def select_all_visible(self):
		for item in self._display_list:
			self.selected_ids.add(item['variant_id'])
		self.refresh_table()

	def deselect_all(self):
		self.selected_ids.clear()
		self.refresh_table()

	def update_selection_label(self):
		count = len(self.selected_ids)
		self.lbl_selected_info.configure(
			text=f'{count} ítems seleccionados',
			text_color=ORANGE_TEXT if count > 0 else TEXT_MUTED,
		)

	def confirm_bulk_update(self):
		if not self.selected_ids:
			CTkMessagebox(
				title='Aviso',
				message='Primero seleccioná algunos artículos de la lista.',
				icon='info',
			)
			return

		updates = {}

		# Proveedor
		new_sup = self.combo_new_supplier.get()
		if new_sup and new_sup != '(No cambiar)':
			sup_id = self.suppliers_map.get(new_sup)
			if sup_id is None:
				CTkMessagebox(
					title='Error', message='Proveedor inválido.', icon='cancel'
				)
				return
			updates['supplier_id'] = sup_id

		# Categoría
		new_cat = self.combo_new_category.get()
		if new_cat and new_cat != '(No cambiar)':
			cat_id = self.categories_map.get(new_cat)
			if cat_id is None:
				CTkMessagebox(
					title='Error', message='Categoría inválida.', icon='cancel'
				)
				return
			updates['category_id'] = cat_id

		# Descuento — solo si el campo tiene valor y en rango [0, 100]
		disc_str = self.entry_new_discount.get().strip()
		if disc_str:
			try:
				disc_val = float(disc_str.replace(',', '.'))
			except ValueError:
				CTkMessagebox(
					title='Error',
					message='El descuento debe ser un número (ej: 15 o 15.5).',
					icon='cancel',
				)
				return
			if not (0 <= disc_val <= 100):
				CTkMessagebox(
					title='Error',
					message='El descuento debe estar entre 0 y 100.',
					icon='cancel',
				)
				return
			updates['discount_pct'] = disc_val

		# Estado activo — solo si el checkbox "Aplicar estado" está tildado
		if self.apply_status_var.get():
			updates['is_active'] = self.check_active_var.get()

		# Pantalla táctil — solo si el checkbox "Aplicar táctil" está tildado
		if self.apply_touch_var.get():
			updates['show_on_touch'] = self.check_touch_var.get()

		if not updates:
			CTkMessagebox(
				title='Sin cambios',
				message='No seleccionaste ningún campo para modificar.\n'
				'Completá al menos un campo o activá un checkbox de estado.',
				icon='info',
			)
			return

		# Resumen de lo que se va a aplicar
		summary_lines = []
		if 'supplier_id' in updates:
			summary_lines.append(f'• Proveedor → {new_sup}')
		if 'category_id' in updates:
			summary_lines.append(f'• Categoría → {new_cat}')
		if 'discount_pct' in updates:
			summary_lines.append(f'• Descuento → {disc_val:.1f}%')
		if 'is_active' in updates:
			summary_lines.append(
				f'• Estado → {"Activo" if updates["is_active"] else "Inactivo"}'
			)
		if 'show_on_touch' in updates:
			summary_lines.append(
				f'• Táctil → {"Sí" if updates["show_on_touch"] else "No"}'
			)

		count = len(self.selected_ids)
		msg = f'Se modificarán {count} artículo(s):\n\n' + '\n'.join(summary_lines)

		if (
			CTkMessagebox(
				title='Confirmar cambios',
				message=msg,
				icon='warning',
				option_1='Cancelar',
				option_2='Confirmar',
			).get()
			!= 'Confirmar'
		):
			return

		success, message = self.controller.bulk_update_variants(
			self.ctx.tenant_id, self.ctx.user_id, list(self.selected_ids), updates
		)
		if success:
			self.show_toast(message, 'success')
			self.selected_ids.clear()
			self.load_data()
		else:
			self.show_toast(message, 'error')
