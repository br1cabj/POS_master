import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk

from controllers.article_controller import ArticleController
from controllers.combo_controller import ComboController
from controllers.promo_controller import PromoController
from core.base_view import BaseView
from utils.date_picker import CTkDatePicker
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
		self.promo_ctrl = PromoController(ctx.db_engine)

		self.db_variants = []
		self.variant_map = {}
		self.ingredients_cart = []
		self.editing_combo_id = None

		# Estado para el tab de Promociones
		self.editing_promo_id = None
		self._all_promos = []
		self._promo_filter_mode = 'activas'

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
		self.tab_promos = self.tabs.add('🎯  Promociones con Vigencia')

		self._setup_tab_combos()
		self._setup_tab_sueltos()
		self._setup_tab_promos()

		self.winfo_toplevel().bind(
			'<Control-g>',
			lambda e: (
				(
					self.save_combo()
					if self.tabs.get() == '🍔  Crear Combos y Promos'
					else (
						self.save_promo()
						if self.tabs.get() == '🎯  Promociones con Vigencia'
						else self.save_suelto()
					)
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

		# Actualizar combobox de productos del tab Promos
		if hasattr(self, 'combo_promo_product'):
			vals = list(self.variant_map.keys())
			self.combo_promo_product.configure(
				values=vals if vals else ['Sin productos']
			)
			self.combo_promo_product.set('Seleccionar Producto...')

		# Recargar lista de promos
		self._all_promos = self.promo_ctrl.get_all_promos(self.ctx.tenant_id)
		self._refresh_promo_list()

		# Cargar Directorio de Botones Rápidos (tab 2)
		if hasattr(self, 'tree_sueltos_list'):
			for item in self.tree_sueltos_list.get_children():
				self.tree_sueltos_list.delete(item)
			sueltos = [
				v
				for v in self.db_variants
				if v.get('show_on_touch') and not v.get('is_combo')
			]
			for s in sueltos:
				color_key = next(
					(
						k
						for k, val in self.color_map.items()
						if val == s.get('btn_color')
					),
					'—',
				)
				self.tree_sueltos_list.insert(
					'',
					'end',
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
			self.show_warning(
				'Seleccioná un producto de la lista para quitarlo del panel.'
			)
			return
		variant_id_str = selected[0]
		variant_id = variant_id_str  # variant IDs are UUIDs (strings)
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

	# =========================================================
	# PESTAÑA 3: PROMOCIONES CON VIGENCIA
	# =========================================================
	def _setup_tab_promos(self):
		self.tab_promos.grid_columnconfigure(0, weight=1)
		self.tab_promos.grid_columnconfigure(1, weight=2)
		self.tab_promos.grid_rowconfigure(0, weight=1)

		# ── PANEL IZQUIERDO (formulario) ──
		left = ctk.CTkScrollableFrame(
			self.tab_promos,
			fg_color=SURFACE2,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		left.grid(row=0, column=0, sticky='nsew', padx=(0, PAD_SM), pady=PAD_SM)

		self.lbl_promo_form_title = ctk.CTkLabel(
			left,
			text='✦  Nueva Promoción',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
		)
		self.lbl_promo_form_title.pack(pady=(PAD_LG, PAD_SM))

		# Nombre
		make_form_label(left, 'NOMBRE DE LA PROMOCIÓN')[0].pack(padx=PAD_LG, anchor='w')
		self.entry_promo_name = ctk.CTkEntry(
			left,
			placeholder_text='Ej: 2x1 Alfajores, 20% Bebidas Frías...',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
			font=FONT_BODY,
		)
		self.entry_promo_name.pack(pady=(PAD_XS, PAD_MD), padx=PAD_LG, fill='x')

		# Tipo
		make_form_label(left, 'TIPO DE PROMOCIÓN')[0].pack(padx=PAD_LG, anchor='w')
		self.seg_promo_type = ctk.CTkSegmentedButton(
			left,
			values=['% Descuento', 'N×M', 'Precio Fijo'],
			command=self._on_promo_type_change,
			fg_color=SURFACE3,
			selected_color=ACCENT_DIM,
			selected_hover_color=ACCENT,
			unselected_color=SURFACE3,
			unselected_hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			font=FONT_BODY,
		)
		self.seg_promo_type.set('% Descuento')
		self.seg_promo_type.pack(pady=(PAD_XS, PAD_SM), padx=PAD_LG, fill='x')

		# Área dinámica según tipo
		self.promo_value_frame = ctk.CTkFrame(left, fg_color='transparent')
		self.promo_value_frame.pack(fill='x', padx=PAD_LG, pady=(0, PAD_SM))
		self._build_promo_value_widgets('% Descuento')

		# Producto
		make_form_label(left, 'APLICA AL PRODUCTO')[0].pack(padx=PAD_LG, anchor='w')
		self.combo_promo_product = ctk.CTkComboBox(
			left,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
		)
		self.combo_promo_product.pack(pady=(PAD_XS, PAD_MD), padx=PAD_LG, fill='x')
		self.combo_promo_product.bind('<KeyRelease>', self._filter_promo_products)
		self.combo_promo_product.set('Seleccionar Producto...')

		# ── SECCIÓN VIGENCIA ──
		ctk.CTkFrame(left, height=1, fg_color=BORDER).pack(
			fill='x', padx=PAD_MD, pady=(0, PAD_SM)
		)
		ctk.CTkLabel(
			left,
			text='⏰  Vigencia',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
		).pack(pady=(0, PAD_SM))

		# Fechas
		dates_frame = ctk.CTkFrame(left, fg_color='transparent')
		dates_frame.pack(fill='x', padx=PAD_LG, pady=(0, PAD_SM))
		dates_frame.grid_columnconfigure(0, weight=1)
		dates_frame.grid_columnconfigure(1, weight=1)

		make_form_label(dates_frame, 'DESDE')[0].grid(
			row=0, column=0, sticky='w', pady=(0, PAD_XS)
		)
		self.entry_promo_date_from = CTkDatePicker(
			dates_frame,
			width=160,
			height=36,
		)
		self.entry_promo_date_from.grid(row=1, column=0, sticky='ew', padx=(0, PAD_XS))

		make_form_label(dates_frame, 'HASTA')[0].grid(
			row=0, column=1, sticky='w', pady=(0, PAD_XS)
		)
		self.entry_promo_date_to = CTkDatePicker(
			dates_frame,
			width=160,
			height=36,
		)
		self.entry_promo_date_to.grid(row=1, column=1, sticky='ew', padx=(PAD_XS, 0))

		# Días de la semana
		make_form_label(left, 'DÍAS HABILITADOS')[0].pack(
			padx=PAD_LG, anchor='w', pady=(PAD_SM, PAD_XS)
		)
		days_frame = ctk.CTkFrame(left, fg_color=SURFACE3, corner_radius=8)
		days_frame.pack(fill='x', padx=PAD_LG, pady=(0, PAD_SM))

		self.day_vars = []
		day_names = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
		for i, name in enumerate(day_names):
			var = ctk.BooleanVar(value=True)
			self.day_vars.append(var)
			ctk.CTkCheckBox(
				days_frame,
				text=name,
				variable=var,
				text_color=TEXT_SECONDARY,
				font=FONT_BODY,
				checkbox_width=18,
				checkbox_height=18,
			).grid(row=0, column=i, padx=6, pady=PAD_SM)

		# Horario (opcional)
		self.check_horario_var = ctk.BooleanVar(value=False)
		ctk.CTkCheckBox(
			left,
			text='Restringir por horario  (opcional)',
			variable=self.check_horario_var,
			command=self._toggle_promo_horario,
			text_color=TEXT_SECONDARY,
			font=FONT_BODY,
		).pack(padx=PAD_LG, anchor='w', pady=(PAD_XS, PAD_XS))

		self.horario_frame = ctk.CTkFrame(left, fg_color='transparent')
		times_inner = ctk.CTkFrame(self.horario_frame, fg_color='transparent')
		times_inner.pack(fill='x')
		times_inner.grid_columnconfigure(0, weight=1)
		times_inner.grid_columnconfigure(1, weight=1)

		make_form_label(times_inner, 'DESDE')[0].grid(
			row=0, column=0, sticky='w', pady=(0, PAD_XS)
		)
		self.entry_time_from = ctk.CTkEntry(
			times_inner,
			placeholder_text='09:00',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_time_from.grid(row=1, column=0, sticky='ew', padx=(0, PAD_XS))

		make_form_label(times_inner, 'HASTA')[0].grid(
			row=0, column=1, sticky='w', pady=(0, PAD_XS)
		)
		self.entry_time_to = ctk.CTkEntry(
			times_inner,
			placeholder_text='20:00',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_time_to.grid(row=1, column=1, sticky='ew', padx=(PAD_XS, 0))

		# Botones Guardar / Cancelar
		ctk.CTkFrame(left, height=1, fg_color=BORDER).pack(
			fill='x', padx=PAD_MD, pady=(PAD_MD, PAD_SM)
		)
		btn_row = ctk.CTkFrame(left, fg_color='transparent')
		btn_row.pack(fill='x', padx=PAD_LG, pady=(0, PAD_LG))

		self.btn_save_promo = ctk.CTkButton(
			btn_row,
			text='💾  GUARDAR PROMOCIÓN  (Ctrl+G)',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=46,
			font=FONT_BODY_BOLD,
			corner_radius=8,
			command=self.save_promo,
		)
		self.btn_save_promo.pack(side='left', expand=True, fill='x', padx=(0, PAD_SM))

		ctk.CTkButton(
			btn_row,
			text='✕ Cancelar',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=46,
			corner_radius=8,
			command=self.reset_promo_form,
		).pack(side='left', fill='x')

		# ── PANEL DERECHO (lista) ──
		right = ctk.CTkFrame(
			self.tab_promos,
			fg_color=SURFACE2,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		right.grid(row=0, column=1, sticky='nsew', padx=(PAD_SM, 0), pady=PAD_SM)
		right.grid_rowconfigure(2, weight=1)
		right.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			right,
			text='Promociones Configuradas',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
		).grid(row=0, column=0, pady=(PAD_LG, PAD_XS))

		# Filtro
		filter_frame = ctk.CTkFrame(right, fg_color='transparent')
		filter_frame.grid(
			row=1, column=0, sticky='ew', padx=PAD_MD, pady=(0, PAD_SM)
		)

		self.seg_promo_filter = ctk.CTkSegmentedButton(
			filter_frame,
			values=['Activas ahora', 'Todas'],
			command=self._on_promo_filter_change,
			fg_color=SURFACE3,
			selected_color=ACCENT_DIM,
			selected_hover_color=ACCENT,
			unselected_color=SURFACE3,
			unselected_hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			font=FONT_BODY,
		)
		self.seg_promo_filter.set('Activas ahora')
		self.seg_promo_filter.pack(fill='x')

		# Treeview
		tree_frame = ctk.CTkFrame(right, fg_color='transparent')
		tree_frame.grid(row=2, column=0, sticky='nsew', padx=PAD_MD, pady=(0, PAD_XS))
		tree_frame.grid_rowconfigure(0, weight=1)
		tree_frame.grid_columnconfigure(0, weight=1)

		apply_treeview_style()
		cols = ('Nombre', 'Tipo', 'Producto', 'Vigencia', 'Estado')
		self.tree_promos = ttk.Treeview(
			tree_frame, columns=cols, show='headings', height=12
		)
		for col in cols:
			self.tree_promos.heading(col, text=col)
		self.tree_promos.column('Nombre', width=140, anchor='w', stretch=True)
		self.tree_promos.column('Tipo', width=90, anchor='center', stretch=False)
		self.tree_promos.column('Producto', width=130, anchor='w', stretch=True)
		self.tree_promos.column('Vigencia', width=160, anchor='center', stretch=False)
		self.tree_promos.column('Estado', width=80, anchor='center', stretch=False)
		self.tree_promos.grid(row=0, column=0, sticky='nsew')
		self.tree_promos.bind('<Double-1>', self.edit_promo)
		self.tree_promos.bind('<<TreeviewSelect>>', self._on_promo_selected)

		self.tree_promos.tag_configure('activa', foreground=GREEN_TEXT)
		self.tree_promos.tag_configure('vencida', foreground=TEXT_MUTED)
		self.tree_promos.tag_configure('pausada', foreground=ORANGE_TEXT)
		self.tree_promos.tag_configure('programada', foreground=ACCENT_TEXT)
		self.tree_promos.tag_configure('fuera-horario', foreground=TEXT_SECONDARY)

		# Botones de acción
		action_row = ctk.CTkFrame(right, fg_color='transparent')
		action_row.grid(
			row=3, column=0, sticky='ew', padx=PAD_MD, pady=(PAD_XS, PAD_MD)
		)

		ctk.CTkButton(
			action_row,
			text='✏️  Editar',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=32,
			command=self.edit_promo,
		).pack(side='left', expand=True, fill='x', padx=(0, PAD_XS))

		self.btn_toggle_promo = ctk.CTkButton(
			action_row,
			text='⏸  Pausar',
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			height=32,
			command=self.toggle_promo_active,
		)
		self.btn_toggle_promo.pack(side='left', expand=True, fill='x', padx=(0, PAD_XS))

		ctk.CTkButton(
			action_row,
			text='🗑  Eliminar',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
			height=32,
			command=self.delete_promo_item,
		).pack(side='left', expand=True, fill='x')

	def _build_promo_value_widgets(self, promo_type: str = '% Descuento'):
		# Clear stale widget refs before destroying — prevents TclError when
		# save_promo calls .get() on a widget destroyed by the type switch.
		self.entry_promo_pct = None
		self.entry_promo_buy = None
		self.entry_promo_pay = None
		self.entry_promo_fixed = None
		for w in self.promo_value_frame.winfo_children():
			w.destroy()

		if promo_type == '% Descuento':
			make_form_label(self.promo_value_frame, 'PORCENTAJE DE DESCUENTO')[0].pack(
				anchor='w'
			)
			row = ctk.CTkFrame(self.promo_value_frame, fg_color='transparent')
			row.pack(fill='x', pady=(PAD_XS, 0))
			self.entry_promo_pct = ctk.CTkEntry(
				row,
				placeholder_text='Ej: 20',
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				text_color=GREEN_TEXT,
				height=40,
				font=FONT_BODY_BOLD,
				width=120,
			)
			self.entry_promo_pct.pack(side='left')
			ctk.CTkLabel(
				row,
				text=' %',
				font=FONT_HEADING,
				text_color=GREEN_TEXT,
			).pack(side='left', padx=(PAD_XS, 0))

		elif promo_type == 'N×M':
			make_form_label(self.promo_value_frame, 'LLEVA  /  PAGA')[0].pack(
				anchor='w'
			)
			row = ctk.CTkFrame(self.promo_value_frame, fg_color='transparent')
			row.pack(fill='x', pady=(PAD_XS, 0))
			ctk.CTkLabel(
				row,
				text='Lleva',
				font=FONT_BODY,
				text_color=TEXT_SECONDARY,
			).pack(side='left', padx=(0, PAD_XS))
			self.entry_promo_buy = ctk.CTkEntry(
				row,
				placeholder_text='3',
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				text_color=ORANGE_TEXT,
				height=40,
				font=FONT_BODY_BOLD,
				width=70,
			)
			self.entry_promo_buy.pack(side='left', padx=(0, PAD_MD))
			ctk.CTkLabel(
				row,
				text='Paga',
				font=FONT_BODY,
				text_color=TEXT_SECONDARY,
			).pack(side='left', padx=(0, PAD_XS))
			self.entry_promo_pay = ctk.CTkEntry(
				row,
				placeholder_text='2',
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				text_color=ORANGE_TEXT,
				height=40,
				font=FONT_BODY_BOLD,
				width=70,
			)
			self.entry_promo_pay.pack(side='left')

		elif promo_type == 'Precio Fijo':
			make_form_label(self.promo_value_frame, 'PRECIO ESPECIAL DE VENTA')[0].pack(
				anchor='w'
			)
			row = ctk.CTkFrame(self.promo_value_frame, fg_color='transparent')
			row.pack(fill='x', pady=(PAD_XS, 0))
			ctk.CTkLabel(
				row,
				text='$ ',
				font=FONT_HEADING,
				text_color=GREEN_TEXT,
			).pack(side='left')
			self.entry_promo_fixed = ctk.CTkEntry(
				row,
				placeholder_text='999.99',
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				text_color=GREEN_TEXT,
				height=40,
				font=FONT_BODY_BOLD,
				width=160,
			)
			self.entry_promo_fixed.pack(side='left', padx=(PAD_XS, 0))

	def _on_promo_type_change(self, value):
		self._build_promo_value_widgets(value)

	def _toggle_promo_horario(self):
		if self.check_horario_var.get():
			self.horario_frame.pack(fill='x', padx=PAD_LG, pady=(PAD_XS, PAD_SM))
		else:
			self.horario_frame.pack_forget()

	def _filter_promo_products(self, event):
		if event.keysym in ('Up', 'Down', 'Return', 'Tab', 'Shift_L', 'Shift_R'):
			return
		typed = self.combo_promo_product.get().lower()
		if not typed:
			self.combo_promo_product.configure(values=list(self.variant_map.keys()))
			return
		filtered = [k for k in self.variant_map.keys() if typed in k.lower()]
		self.combo_promo_product.configure(
			values=filtered if filtered else ['Sin coincidencias']
		)

	def _on_promo_filter_change(self, value):
		self._promo_filter_mode = 'activas' if value == 'Activas ahora' else 'todas'
		self._refresh_promo_list()

	def _refresh_promo_list(self):
		if not hasattr(self, 'tree_promos'):
			return
		for item in self.tree_promos.get_children():
			self.tree_promos.delete(item)

		for p in self._all_promos:
			status = p.get('status', 'vencida')

			if self._promo_filter_mode == 'activas' and status != 'activa':
				continue

			# Tipo legible
			ptype = p.get('promo_type', '')
			if ptype == 'pct':
				tipo_str = f'-{p.get("discount_value", 0):.4g}%'
			elif ptype == 'nxm':
				tipo_str = f'{p.get("buy_qty")}x{p.get("pay_qty")}'
			else:
				tipo_str = f'${p.get("discount_value", 0):.2f}'

			# Producto
			prod = p.get('variant_name') or '—'
			if len(prod) > 18:
				prod = prod[:16] + '…'

			# Período
			d_from = p.get('date_from')
			d_to = p.get('date_to')
			try:
				df = (
					d_from.strftime('%d/%m')
					if isinstance(d_from, datetime)
					else d_from[:5]
				)
				dt = (
					d_to.strftime('%d/%m/%y')
					if isinstance(d_to, datetime)
					else d_to[:8]
				)
				vigencia = f'{df} → {dt}'
			except Exception:
				vigencia = '—'

			if p.get('time_from') and p.get('time_to'):
				vigencia += f'  {p["time_from"]}-{p["time_to"]}'

			# Usamos el ID de la promo como iid para recuperarla sin ambigüedad por nombre
			status_label = {
				'activa': 'ACTIVA',
				'pausada': 'PAUSADA',
				'vencida': 'VENCIDA',
				'programada': 'PROGRAMADA',
				'fuera-horario': 'FUERA DE HORA',
			}.get(status, status.upper())

			self.tree_promos.insert(
				'',
				'end',
				iid=p['id'],
				values=(p['name'], tipo_str, prod, vigencia, status_label),
				tags=(status,),
			)

	def _on_promo_selected(self, event=None):
		promo = self._get_selected_promo()
		if promo and hasattr(self, 'btn_toggle_promo'):
			if promo.get('status') == 'pausada':
				self.btn_toggle_promo.configure(text='▶  Activar')
			else:
				self.btn_toggle_promo.configure(text='⏸  Pausar')

	def _get_selected_promo(self):
		selected = self.tree_promos.selection()
		if not selected:
			return None
		promo_id = selected[0]  # iid == promo ID (tkinter returns it as str)
		return next((p for p in self._all_promos if str(p['id']) == promo_id), None)

	def reset_promo_form(self):
		self.editing_promo_id = None
		self.lbl_promo_form_title.configure(text='✦  Nueva Promoción')
		self.btn_save_promo.configure(text='💾  GUARDAR PROMOCIÓN  (Ctrl+G)')
		self.entry_promo_name.delete(0, 'end')
		self.seg_promo_type.set('% Descuento')
		self._build_promo_value_widgets('% Descuento')
		self.combo_promo_product.set('Seleccionar Producto...')
		self.entry_promo_date_from.clear()
		self.entry_promo_date_to.clear()
		for var in self.day_vars:
			var.set(True)
		self.check_horario_var.set(False)
		self.entry_time_from.delete(0, 'end')
		self.entry_time_to.delete(0, 'end')
		self.horario_frame.pack_forget()

	def edit_promo(self, event=None):
		promo = self._get_selected_promo()
		if not promo:
			self.show_warning('Seleccioná una promoción de la lista para editar.')
			return

		self.reset_promo_form()
		self.editing_promo_id = promo['id']
		self.lbl_promo_form_title.configure(text='✏️  Editando Promoción')
		self.btn_save_promo.configure(text='💾  ACTUALIZAR PROMOCIÓN  (Ctrl+G)')

		self.entry_promo_name.insert(0, promo['name'])

		ptype = promo['promo_type']
		type_label = {'pct': '% Descuento', 'nxm': 'N×M', 'fixed': 'Precio Fijo'}.get(
			ptype, '% Descuento'
		)
		self.seg_promo_type.set(type_label)
		self._build_promo_value_widgets(type_label)

		if ptype == 'pct' and hasattr(self, 'entry_promo_pct'):
			self.entry_promo_pct.insert(0, f'{promo.get("discount_value", "")}')
		elif ptype == 'nxm' and hasattr(self, 'entry_promo_buy'):
			self.entry_promo_buy.insert(0, str(promo.get('buy_qty', '')))
			self.entry_promo_pay.insert(0, str(promo.get('pay_qty', '')))
		elif ptype == 'fixed' and hasattr(self, 'entry_promo_fixed'):
			self.entry_promo_fixed.insert(0, f'{promo.get("discount_value", "")}')

		# Buscar el producto en el mapa
		vid = promo.get('variant_id')
		if vid:
			match = next(
				(k for k, v in self.variant_map.items() if v.get('variant_id') == vid),
				None,
			)
			if match:
				self.combo_promo_product.set(match)

		# Fechas
		d_from = promo.get('date_from')
		d_to = promo.get('date_to')
		if isinstance(d_from, datetime):
			self.entry_promo_date_from.set_date(d_from.date())
		if isinstance(d_to, datetime):
			self.entry_promo_date_to.set_date(d_to.date())

		# Días
		days_str = promo.get('days_of_week') or '0,1,2,3,4,5,6'
		try:
			active_days = {int(d) for d in days_str.split(',') if d.strip()}
		except ValueError:
			active_days = set(range(7))
		for i, var in enumerate(self.day_vars):
			var.set(i in active_days)

		# Horario
		if promo.get('time_from') and promo.get('time_to'):
			self.check_horario_var.set(True)
			self.horario_frame.pack(fill='x', padx=PAD_LG, pady=(PAD_XS, PAD_SM))
			self.entry_time_from.insert(0, promo['time_from'])
			self.entry_time_to.insert(0, promo['time_to'])

	def save_promo(self):
		promo_type_label = self.seg_promo_type.get()
		ptype_map = {'% Descuento': 'pct', 'N×M': 'nxm', 'Precio Fijo': 'fixed'}
		ptype = ptype_map.get(promo_type_label, 'pct')

		# Recolectar valor según tipo
		discount_value = None
		buy_qty = None
		pay_qty = None

		if ptype == 'pct':
			discount_value = getattr(self, 'entry_promo_pct', None)
			discount_value = discount_value.get().strip() if discount_value else ''
		elif ptype == 'nxm':
			buy_qty = getattr(self, 'entry_promo_buy', None)
			buy_qty = buy_qty.get().strip() if buy_qty else ''
			pay_qty = getattr(self, 'entry_promo_pay', None)
			pay_qty = pay_qty.get().strip() if pay_qty else ''
		elif ptype == 'fixed':
			discount_value = getattr(self, 'entry_promo_fixed', None)
			discount_value = discount_value.get().strip() if discount_value else ''

		# Producto
		prod_desc = self.combo_promo_product.get()
		variant = self.variant_map.get(prod_desc)
		variant_id = variant['variant_id'] if variant else None

		# Días activos
		active_days = [str(i) for i, var in enumerate(self.day_vars) if var.get()]
		if not active_days:
			self.show_warning('Debés habilitar al menos un día de la semana.')
			return
		days_str = ','.join(active_days)

		# Horario
		time_from = None
		time_to = None
		if self.check_horario_var.get():
			time_from = self.entry_time_from.get().strip() or None
			time_to = self.entry_time_to.get().strip() or None

		data = {
			'name': self.entry_promo_name.get().strip(),
			'promo_type': ptype,
			'discount_value': discount_value,
			'buy_qty': buy_qty,
			'pay_qty': pay_qty,
			'variant_id': variant_id,
			'date_from': self.entry_promo_date_from.get().strip(),
			'date_to': self.entry_promo_date_to.get().strip(),
			'days_of_week': days_str,
			'time_from': time_from,
			'time_to': time_to,
		}

		orig_text = self.btn_save_promo.cget('text')
		self.set_loading(self.btn_save_promo, True)
		self.update_idletasks()

		try:
			if self.editing_promo_id:
				success, msg = self.promo_ctrl.update_promo(
					self.ctx.tenant_id, self.editing_promo_id, data
				)
			else:
				success, msg = self.promo_ctrl.create_promo(self.ctx.tenant_id, data)
		except Exception as e:
			success, msg = False, str(e)
		finally:
			self.set_loading(self.btn_save_promo, False, orig_text)

		if success:
			self.show_success(msg, '¡Promoción Guardada!')
			self.reset_promo_form()
			self._all_promos = self.promo_ctrl.get_all_promos(self.ctx.tenant_id)
			self._refresh_promo_list()
		else:
			self.show_error(msg)

	def toggle_promo_active(self):
		promo = self._get_selected_promo()
		if not promo:
			self.show_warning('Seleccioná una promoción de la lista.')
			return
		success, msg = self.promo_ctrl.toggle_active(self.ctx.tenant_id, promo['id'])
		if success:
			self.show_success(msg)
			self._all_promos = self.promo_ctrl.get_all_promos(self.ctx.tenant_id)
			self._refresh_promo_list()
		else:
			self.show_error(msg)

	def delete_promo_item(self):
		promo = self._get_selected_promo()
		if not promo:
			self.show_warning('Seleccioná una promoción de la lista.')
			return
		if not self.confirm(f'¿Eliminar la promoción "{promo["name"]}"?'):
			return
		success, msg = self.promo_ctrl.delete_promo(self.ctx.tenant_id, promo['id'])
		if success:
			self.show_success(msg)
			if self.editing_promo_id == promo['id']:
				self.reset_promo_form()
			self._all_promos = self.promo_ctrl.get_all_promos(self.ctx.tenant_id)
			self._refresh_promo_list()
		else:
			self.show_error(msg)
