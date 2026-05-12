import logging
from decimal import Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk

from controllers.article_controller import ArticleController
from controllers.combo_controller import ComboController
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
	PURPLE_DIM,
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
	make_form_label,
)

logger = logging.getLogger(__name__)


class ComboMakerView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.combo_ctrl = ComboController(ctx.db_engine)
		self.article_ctrl = ArticleController(ctx.db_engine)

		self.db_variants = []
		self.variant_map = {}
		self.ingredients_cart = []
		self.editing_combo_id = None

		self.color_map = {
			'🔵 Azul Marino': ACCENT_DIM,
			'🟢 Verde Éxito': GREEN_DIM,
			'🔴 Rojo Alerta': RED_DIM,
			'🟠 Naranja Promo': ORANGE_DIM,
			'🟣 Púrpura Premium': PURPLE_DIM,
			'⚫ Gris Neutro': SURFACE3,
		}

		self.tabs = ctk.CTkTabview(
			self,
			fg_color=SURFACE2,
			border_color=BORDER,
			border_width=1,
			segmented_button_fg_color=SURFACE3,
			segmented_button_selected_color=ACCENT_DIM,
			segmented_button_selected_hover_color=ACCENT,
			segmented_button_unselected_color=SURFACE3,
			segmented_button_unselected_hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			text_color_disabled=TEXT_MUTED,
		)
		self.tabs.pack(fill='both', expand=True)

		self.tab_combos = self.tabs.add('🍔  Crear Combos y Promos')
		self.tab_sueltos = self.tabs.add('👆  Botones Rápidos')

		self._setup_tab_combos()
		self._setup_tab_sueltos()

		self.winfo_toplevel().bind(
			'<Control-g>',
			lambda e: (
				(
					self.save_combo()
					if self.tabs.get() == '🍔  Crear Combos y Promos'
					else self.save_suelto()
				)
				if self.winfo_exists()
				else None
			),
		)

		self.after(100, self.load_data)

	def destroy_custom(self):
		try:
			self.winfo_toplevel().unbind('<Control-g>')
		except Exception:
			pass

	def load_data(self):
		tenant_id = self.ctx.tenant_id
		self.db_variants = self.article_ctrl.get_all_variants(tenant_id)

		normal_items = [v for v in self.db_variants if not v.get('is_combo')]
		self.variant_map = {}
		for v in normal_items:
			if v.get('name'):
				# Prevención de colisiones: Clave única con ID
				display_name = f'{v["name"]} | Cód: {v.get("barcode", "S/N")} (ID: {v["variant_id"]})'
				self.variant_map[display_name] = v

		if self.variant_map:
			vals = list(self.variant_map.keys())
			self.combo_ingredient.configure(values=vals)
			self.combo_sueltos.configure(values=vals)
			self.combo_ingredient.set('Seleccionar Ingrediente...')
			self.combo_sueltos.set('Seleccionar Producto...')
		else:
			self.combo_ingredient.configure(values=['Sin productos'])
			self.combo_sueltos.configure(values=['Sin productos'])

		# Cargar Directorio de Combos Existentes
		for item in self.tree_directory.get_children():
			self.tree_directory.delete(item)

		combos = [v for v in self.db_variants if v.get('is_combo')]
		for c in combos:
			self.tree_directory.insert(
				'',
				'end',
				values=(
					c['variant_id'],
					c['name'],
					f'${float(c.get("selling_price", 0)):.2f}',
				),
			)

		# Cargar Directorio de Botones Rápidos (tab 2)
		if hasattr(self, 'tree_sueltos_list'):
			for item in self.tree_sueltos_list.get_children():
				self.tree_sueltos_list.delete(item)
			sueltos = [
				v for v in self.db_variants
				if v.get('show_on_touch') and not v.get('is_combo')
			]
			for s in sueltos:
				color_key = next(
					(k for k, val in self.color_map.items() if val == s.get('btn_color')),
					'—',
				)
				self.tree_sueltos_list.insert(
					'', 'end',
					iid=str(s['variant_id']),
					values=(s['name'], color_key),
				)

	# =========================================================
	# PESTAÑA 1: CREADOR DE COMBOS
	# =========================================================
	def _setup_tab_combos(self):
		self.tab_combos.grid_columnconfigure(0, weight=1)
		self.tab_combos.grid_columnconfigure(1, weight=1)

		# ── PANEL IZQUIERDO ──
		left = ctk.CTkFrame(
			self.tab_combos,
			fg_color=SURFACE2,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		left.grid(row=0, column=0, sticky='nsew', padx=(0, PAD_SM), pady=PAD_SM)

		self.lbl_form_title = ctk.CTkLabel(
			left,
			text='1.  Datos de la Promo',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
		)
		self.lbl_form_title.pack(pady=(PAD_LG, PAD_MD))

		self.entry_combo_name = ctk.CTkEntry(
			left,
			placeholder_text='Nombre  (Ej: Promo Panchos)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
			font=FONT_BODY,
		)
		self.entry_combo_name.pack(pady=(0, PAD_SM), padx=PAD_LG, fill='x')

		self.entry_combo_price = ctk.CTkEntry(
			left,
			placeholder_text='Precio Total de Venta ($)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=GREEN_TEXT,
			height=40,
			font=FONT_BODY_BOLD,
		)
		self.entry_combo_price.pack(pady=(0, PAD_MD), padx=PAD_LG, fill='x')

		make_form_label(left, 'COLOR DEL BOTÓN TÁCTIL')[0].pack(padx=PAD_LG, anchor='w')

		self.combo_color = ctk.CTkComboBox(
			left,
			values=list(self.color_map.keys()),
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
			state='readonly',
		)
		self.combo_color.pack(pady=(PAD_XS, PAD_MD), padx=PAD_LG, fill='x')

		ctk.CTkFrame(left, height=1, fg_color=BORDER).pack(
			fill='x', padx=PAD_MD, pady=(0, PAD_MD)
		)

		ctk.CTkLabel(
			left,
			text='2.  Agregar Ingredientes (Receta)',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
		).pack(pady=(0, PAD_SM))

		self.combo_ingredient = ctk.CTkComboBox(
			left,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
		)
		self.combo_ingredient.pack(pady=(0, PAD_SM), padx=PAD_LG, fill='x')
		self.combo_ingredient.bind('<KeyRelease>', self._filter_ingredients)

		self.entry_ingredient_qty = ctk.CTkEntry(
			left,
			placeholder_text='Cantidad que descuenta  (Ej: 2)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
			font=FONT_BODY,
		)
		self.entry_ingredient_qty.pack(pady=(0, PAD_SM), padx=PAD_LG, fill='x')
		self.entry_ingredient_qty.bind('<Return>', lambda e: self.add_ingredient())
		self.entry_ingredient_qty.bind(
			'<FocusIn>', lambda e: self.entry_ingredient_qty.select_range(0, 'end')
		)

		ctk.CTkButton(
			left,
			text='👇  Añadir Ingrediente (Enter)',
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			height=40,
			corner_radius=8,
			command=self.add_ingredient,
			font=FONT_BODY_BOLD,
		).pack(pady=(0, PAD_LG), padx=PAD_LG, fill='x')

		# ── CONTENEDOR DERECHO ──
		right_container = ctk.CTkFrame(self.tab_combos, fg_color='transparent')
		right_container.grid(
			row=0, column=1, sticky='nsew', padx=(PAD_SM, 0), pady=PAD_SM
		)
		right_container.grid_rowconfigure(0, weight=3)  # Receta
		right_container.grid_rowconfigure(1, weight=2)  # Directorio
		right_container.grid_columnconfigure(0, weight=1)

		# ── RECETA ──
		right = ctk.CTkFrame(
			right_container,
			fg_color=SURFACE2,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		right.grid(row=0, column=0, sticky='nsew', pady=(0, PAD_SM))

		ctk.CTkLabel(
			right,
			text='Ingredientes de esta Promo',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
		).pack(pady=(PAD_LG, PAD_SM))

		apply_treeview_style()
		self.tree_recipe = ttk.Treeview(
			right,
			columns=('Producto', 'Cantidad', 'Costo Parcial'),
			show='headings',
			height=6,
		)
		self.init_treeview(self.tree_recipe)

		self.tree_recipe.heading('Producto', text='Producto')
		self.tree_recipe.heading('Cantidad', text='Cant.')
		self.tree_recipe.heading('Costo Parcial', text='Costo')

		self.tree_recipe.column('Producto', width=200, anchor='w')
		self.tree_recipe.column('Cantidad', width=60, anchor='center')
		self.tree_recipe.column('Costo Parcial', width=80, anchor='center')
		self.tree_recipe.pack(fill='both', expand=True, padx=PAD_MD, pady=PAD_XS)

		self.lbl_recipe_cost = ctk.CTkLabel(
			right,
			text='Costo de Producción: $0.00',
			font=FONT_BODY_BOLD,
			text_color=ORANGE_TEXT,
		)
		self.lbl_recipe_cost.pack(pady=(PAD_XS, PAD_SM), padx=PAD_MD, anchor='e')

		ctk.CTkButton(
			right,
			text='🗑  Quitar Ingrediente',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
			height=36,
			corner_radius=8,
			command=self.remove_ingredient,
		).pack(pady=(PAD_XS, PAD_SM), padx=PAD_MD, fill='x')

		btn_row = ctk.CTkFrame(right, fg_color='transparent')
		btn_row.pack(pady=(0, PAD_MD), padx=PAD_MD, fill='x')

		self.btn_save_combo = ctk.CTkButton(
			btn_row,
			text='💾  GUARDAR COMBO Y CREAR BOTÓN (Ctrl+G)',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			height=50,
			font=FONT_BODY_BOLD,
			corner_radius=8,
			command=self.save_combo,
		)
		self.btn_save_combo.pack(side='left', expand=True, fill='x', padx=(0, PAD_SM))

		ctk.CTkButton(
			btn_row,
			text='✕ Cancelar',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=50,
			corner_radius=8,
			command=self.reset_form,
		).pack(side='left', fill='x')

		# ── DIRECTORIO DE COMBOS EXISTENTES ──
		dir_panel = ctk.CTkFrame(
			right_container,
			fg_color=SURFACE2,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		dir_panel.grid(row=1, column=0, sticky='nsew')

		ctk.CTkLabel(
			dir_panel,
			text='Directorio de Combos',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
		).pack(pady=(PAD_LG, PAD_SM))

		self.tree_directory = ttk.Treeview(
			dir_panel, columns=('ID', 'Nombre', 'Precio'), show='headings', height=5
		)
		self.tree_directory.heading('ID', text='ID')
		self.tree_directory.heading('Nombre', text='Nombre Promo')
		self.tree_directory.heading('Precio', text='Precio')
		self.tree_directory.column('ID', width=40, anchor='center')
		self.tree_directory.column('Nombre', width=200, anchor='w')
		self.tree_directory.column('Precio', width=80, anchor='e')
		self.tree_directory.pack(fill='both', expand=True, padx=PAD_MD, pady=PAD_XS)
		self.tree_directory.bind('<Double-1>', self.edit_combo)

		dir_btn_row = ctk.CTkFrame(dir_panel, fg_color='transparent')
		dir_btn_row.pack(fill='x', padx=PAD_MD, pady=(PAD_XS, PAD_MD))

		ctk.CTkButton(
			dir_btn_row,
			text='✏️ Editar',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=32,
			command=self.edit_combo,
		).pack(side='left', expand=True, fill='x', padx=(0, PAD_SM))

		ctk.CTkButton(
			dir_btn_row,
			text='🗑 Eliminar',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
			height=32,
			command=self.delete_combo,
		).pack(side='left', expand=True, fill='x')

	def reset_form(self):
		"""Purga el formulario y el carrito asegurando limpieza entre creaciones."""
		self.editing_combo_id = None
		self.entry_combo_name.delete(0, 'end')
		self.entry_combo_price.delete(0, 'end')
		self.combo_color.set(list(self.color_map.keys())[0])

		for item in self.tree_recipe.get_children():
			self.tree_recipe.delete(item)
		self.ingredients_cart.clear()
		self._update_recipe_cost()

		if self.variant_map:
			self.combo_ingredient.set('Seleccionar Ingrediente...')

		self.lbl_form_title.configure(text='1.  Datos de la Promo')
		self.btn_save_combo.configure(text='💾  GUARDAR COMBO Y CREAR BOTÓN (Ctrl+G)')

	def edit_combo(self, event=None):
		selected = self.tree_directory.selection()
		if not selected:
			return

		combo_id = self.tree_directory.item(selected[0], 'values')[0]
		combo = next(
			(c for c in self.db_variants if str(c.get('variant_id')) == str(combo_id)),
			None,
		)

		if not combo:
			return

		self.reset_form()
		self.editing_combo_id = combo['variant_id']
		self.lbl_form_title.configure(text='✏️ Editando Promo')
		self.btn_save_combo.configure(text='💾  ACTUALIZAR COMBO (Ctrl+G)')

		self.entry_combo_name.insert(0, combo.get('name', ''))
		self.entry_combo_price.insert(0, f'{combo.get("selling_price", 0):.2f}')

		stored_color = combo.get('btn_color', '')
		color_key = next(
			(k for k, v in self.color_map.items() if v == stored_color),
			list(self.color_map.keys())[0],
		)
		self.combo_color.set(color_key)

		try:
			ingredients = self.combo_ctrl.get_combo_ingredients(
				self.ctx.tenant_id, combo['variant_id']
			)
			for ing in ingredients:
				vid = ing.get('variant_id') or ing.get('ingredient_id')
				qty = Decimal(str(ing.get('quantity', 1)))

				orig_v = next(
					(v for v in self.db_variants if v.get('variant_id') == vid), None
				)
				if orig_v:
					desc = orig_v.get('name', 'Desconocido')
					# Formatear el display para match con la UI
					display_desc = (
						f'{desc} | Cód: {orig_v.get("barcode", "S/N")} (ID: {vid})'
					)

					cost = Decimal(str(orig_v.get('cost_price', 0)))
					subtotal = cost * qty

					item_id = self.insert_tree_row(
						self.tree_recipe,
						len(self.tree_recipe.get_children()),
						values=(display_desc, f'{qty:g}', f'${subtotal:,.2f}'),
					)
					self.ingredients_cart.append(
						{
							'tree_id': item_id,
							'variant_id': vid,
							'qty': qty,
							'cost_price': cost,
						}
					)
		except Exception as e:
			logger.error(f'Error cargando ingredientes del combo: {e}')
			self.show_warning('Ocurrió un error al cargar la receta completa.')

		self._update_recipe_cost()

	def delete_combo(self):
		selected = self.tree_directory.selection()
		if not selected:
			self.show_warning('Seleccioná un combo de la lista para eliminarlo.')
			return

		combo_id = self.tree_directory.item(selected[0], 'values')[0]
		combo_name = self.tree_directory.item(selected[0], 'values')[1]

		if not self.confirm(f'¿Seguro que deseás eliminar el combo "{combo_name}"?'):
			return

		try:
			# Fallback seguro: un combo es una variante en db
			success, msg = self.article_ctrl.delete_variant(
				self.ctx.tenant_id, combo_id
			)
		except Exception as e:
			success, msg = False, str(e)

		if success:
			self.show_success('Combo eliminado correctamente.')
			if str(self.editing_combo_id) == str(combo_id):
				self.reset_form()
			self.load_data()
		else:
			self.show_error(msg)

	def _filter_ingredients(self, event):
		if event.keysym in ('Up', 'Down', 'Return', 'Tab', 'Shift_L', 'Shift_R'):
			return
		typed = self.combo_ingredient.get().lower()
		if not typed:
			self.combo_ingredient.configure(values=list(self.variant_map.keys()))
			return
		filtered = [k for k in self.variant_map.keys() if typed in k.lower()]
		self.combo_ingredient.configure(
			values=filtered if filtered else ['Sin coincidencias']
		)

	def _update_recipe_cost(self):
		total_cost = Decimal('0')
		for item in self.ingredients_cart:
			cost_unitario = item.get('cost_price', Decimal('0'))
			total_cost += cost_unitario * item['qty']
		self.lbl_recipe_cost.configure(text=f'Costo de Producción: ${total_cost:,.2f}')

	def add_ingredient(self):
		desc = self.combo_ingredient.get()
		qty_str = self.entry_ingredient_qty.get().replace(',', '.')

		if desc not in self.variant_map:
			self.show_warning('Seleccioná un producto de la lista válida.')
			return

		try:
			qty = Decimal(qty_str)
			if qty <= 0:
				raise ValueError
		except (ValueError, InvalidOperation):
			self.show_error('La cantidad debe ser un número mayor a cero.')
			return

		variant = self.variant_map[desc]
		variant_id = variant['variant_id']
		cost_unitario = Decimal(str(variant.get('cost_price', 0)))

		existing_item = next(
			(
				item
				for item in self.ingredients_cart
				if item['variant_id'] == variant_id
			),
			None,
		)

		if existing_item:
			existing_item['qty'] += qty
			costo_parcial = cost_unitario * existing_item['qty']
			self.tree_recipe.item(
				existing_item['tree_id'],
				values=(desc, f'{existing_item["qty"]:g}', f'${costo_parcial:,.2f}'),
			)
		else:
			costo_parcial = cost_unitario * qty
			row_idx = len(self.tree_recipe.get_children())
			item_id = self.insert_tree_row(
				self.tree_recipe,
				row_idx,
				values=(desc, f'{qty:g}', f'${costo_parcial:,.2f}'),
			)
			self.ingredients_cart.append(
				{
					'tree_id': item_id,
					'variant_id': variant_id,
					'qty': qty,
					'cost_price': cost_unitario,
				}
			)

		self.entry_ingredient_qty.delete(0, 'end')
		self.combo_ingredient.set('Seleccionar Ingrediente...')
		self.combo_ingredient.focus()
		self._update_recipe_cost()

	def remove_ingredient(self):
		selected = self.tree_recipe.selection()
		if not selected:
			self.show_warning('Seleccioná un ingrediente de la tabla para quitarlo.')
			return

		self.ingredients_cart = [
			item for item in self.ingredients_cart if item['tree_id'] not in selected
		]

		for item_id in selected:
			self.tree_recipe.delete(item_id)

		self._update_recipe_cost()

	def save_combo(self):
		name = self.entry_combo_name.get().strip()
		price_str = self.entry_combo_price.get().replace(',', '.')
		color_key = self.combo_color.get()
		btn_color = self.color_map.get(color_key, ACCENT_DIM)

		if not name or not price_str or not self.ingredients_cart:
			self.show_warning(
				'Debés ingresar un nombre, precio de venta y al menos 1 ingrediente.',
				'Faltan Datos',
			)
			return

		tenant_id = self.ctx.tenant_id
		cart_for_ctrl = [
			{'variant_id': i['variant_id'], 'qty': float(i['qty'])}
			for i in self.ingredients_cart
		]

		orig_text = self.btn_save_combo.cget('text')
		self.set_loading(self.btn_save_combo, True)
		self.update_idletasks()

		try:
			if self.editing_combo_id:
				success, msg = self.combo_ctrl.update_combo(
					tenant_id,
					self.editing_combo_id,
					name,
					price_str,
					btn_color,
					cart_for_ctrl,
				)
			else:
				success, msg = self.combo_ctrl.create_combo(
					tenant_id, name, price_str, btn_color, cart_for_ctrl
				)
		except AttributeError:
			if self.editing_combo_id:
				success, msg = (
					False,
					'La función de actualizar no está implementada en el backend actual.',
				)
			else:
				success, msg = self.combo_ctrl.create_combo(
					tenant_id, name, price_str, btn_color, cart_for_ctrl
				)
		except Exception as e:
			success, msg = False, str(e)
		finally:
			self.set_loading(self.btn_save_combo, False, orig_text)

		if success:
			self.show_success(msg, '¡Combo Guardado!')
			self.reset_form()
			self.load_data()
		else:
			self.show_error(msg)

	# =========================================================
	# PESTAÑA 2: BOTONES RÁPIDOS
	# =========================================================
	def _setup_tab_sueltos(self):
		outer = ctk.CTkFrame(
			self.tab_sueltos,
			fg_color=SURFACE2,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		outer.pack(fill='both', expand=True, padx=0, pady=PAD_SM)

		inner = ctk.CTkFrame(outer, fg_color='transparent')
		inner.pack(fill='both', expand=True, padx=40, pady=PAD_LG)

		ctk.CTkLabel(
			inner,
			text='Convertir Producto Normal en Botón Rápido',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
		).pack(pady=(0, PAD_SM))

		ctk.CTkLabel(
			inner,
			text='Útil para productos sin código de barras (Pan, Hielo, Bolsas)',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
		).pack(pady=(0, PAD_LG))

		make_form_label(inner, '1. SELECCIONA EL PRODUCTO')[0].pack(anchor='w')

		self.combo_sueltos = ctk.CTkComboBox(
			inner,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
		)
		self.combo_sueltos.pack(pady=(PAD_XS, PAD_MD), fill='x')
		self.combo_sueltos.bind('<KeyRelease>', lambda e: self._filter_sueltos(e))

		make_form_label(inner, '2. ELIGE EL COLOR DEL BOTÓN')[0].pack(anchor='w')

		self.combo_color_suelto = ctk.CTkComboBox(
			inner,
			values=list(self.color_map.keys()),
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
			state='readonly',
		)
		self.combo_color_suelto.pack(pady=(PAD_XS, PAD_MD), fill='x')

		self.check_touch_var = ctk.BooleanVar(value=True)
		self.check_touch = ctk.CTkCheckBox(
			inner,
			text='Mostrar en la Pantalla de Ventas (Touch)',
			variable=self.check_touch_var,
			text_color=TEXT_SECONDARY,
			font=FONT_BODY,
		)
		self.check_touch.pack(pady=(0, PAD_LG), anchor='w')

		ctk.CTkButton(
			inner,
			text='💾  ACTUALIZAR CONFIGURACIÓN (Ctrl+G)',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=50,
			font=FONT_BODY_BOLD,
			corner_radius=8,
			command=self.save_suelto,
		).pack(pady=(0, PAD_LG), fill='x')

		ctk.CTkFrame(inner, height=1, fg_color=BORDER).pack(fill='x', pady=(0, PAD_MD))

		ctk.CTkLabel(
			inner,
			text='Botones Rápidos Configurados',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(anchor='w', pady=(0, PAD_XS))

		apply_treeview_style()
		self.tree_sueltos_list = ttk.Treeview(
			inner,
			columns=('Nombre', 'Color'),
			show='headings',
			height=6,
		)
		self.tree_sueltos_list.heading('Nombre', text='Producto')
		self.tree_sueltos_list.heading('Color', text='Color')
		self.tree_sueltos_list.column('Nombre', width=280, anchor='w', stretch=True)
		self.tree_sueltos_list.column('Color', width=160, anchor='w', stretch=False)
		self.tree_sueltos_list.pack(fill='both', expand=True, pady=(0, PAD_SM))

		ctk.CTkButton(
			inner,
			text='🗑  Quitar del Panel de Acceso Rápido',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
			height=36,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self._remove_suelto,
		).pack(fill='x', pady=(0, PAD_MD))

	def _filter_sueltos(self, event):
		if event.keysym in ('Up', 'Down', 'Return', 'Tab', 'Shift_L', 'Shift_R'):
			return
		typed = self.combo_sueltos.get().lower()
		if not typed:
			self.combo_sueltos.configure(values=list(self.variant_map.keys()))
			return
		filtered = [k for k in self.variant_map.keys() if typed in k.lower()]
		self.combo_sueltos.configure(
			values=filtered if filtered else ['Sin coincidencias']
		)

	def save_suelto(self):
		desc = self.combo_sueltos.get()
		if desc not in self.variant_map:
			self.show_warning('Seleccioná un producto válido de la lista.')
			return

		variant_id = self.variant_map[desc]['variant_id']
		show_on_touch = self.check_touch_var.get()
		color_key = self.combo_color_suelto.get()
		btn_color = self.color_map.get(color_key, ACCENT_DIM)
		tenant_id = self.ctx.tenant_id

		success, msg = self.combo_ctrl.toggle_touch_status(
			tenant_id, variant_id, show_on_touch, btn_color
		)

		if success:
			self.show_success(msg, '¡Actualizado!')
			self.combo_sueltos.set('Seleccionar Producto...')
			self.load_data()
		else:
			self.show_error(msg)

	def _remove_suelto(self):
		selected = self.tree_sueltos_list.selection()
		if not selected:
			self.show_warning('Seleccioná un producto de la lista para quitarlo del panel.')
			return
		variant_id_str = selected[0]
		try:
			variant_id = int(variant_id_str)
		except ValueError:
			variant_id = variant_id_str
		variant_data = next(
			(v for v in self.db_variants if v['variant_id'] == variant_id), None
		)
		btn_color = (variant_data or {}).get('btn_color') or ''
		success, msg = self.combo_ctrl.toggle_touch_status(
			self.ctx.tenant_id, variant_id, False, btn_color
		)
		if success:
			self.show_success('Botón eliminado del panel de acceso rápido.', '¡Listo!')
			self.load_data()
		else:
			self.show_error(msg)
