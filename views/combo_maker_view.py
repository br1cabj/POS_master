"""
views/combo_maker_view.py
=========================
Vista para la creación de combos (productos compuestos) y botones rápidos (touch).
Implementa cálculo de costos en tiempo real y filtrado dinámico de ingredientes.
"""

from decimal import Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

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
	GREEN,
	GREEN_DIM,
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


class ComboMakerView(BaseView):
	"""
	Gestiona la interfaz para ensamblar recetas (combos) y configurar atajos de venta.
	Garantiza la integridad referencial de los ingredientes y proyecta costos de producción.
	"""

	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.combo_ctrl = ComboController(ctx.db_engine)
		self.article_ctrl = ArticleController(ctx.db_engine)

		self.db_variants = []
		self.variant_map = {}
		self.ingredients_cart = []

		self.pack(fill='both', expand=True, padx=12, pady=12)

		self.color_map = {
			'🔵 Azul Marino': ACCENT_DIM,
			'🟢 Verde Éxito': GREEN_DIM,
			'🔴 Rojo Alerta': RED_DIM,
			'🟠 Naranja Promo': ORANGE_DIM,
			'🟣 Púrpura Premium': '#2d1a4a',
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

		# Atajos de teclado globales
		self.bind(
			'<Control-g>',
			lambda e: (
				self.save_combo()
				if self.tabs.get() == '🍔  Crear Combos y Promos'
				else self.save_suelto()
			),
		)

		self.after(100, self.load_data)

	def load_data(self):
		"""Obtiene el catálogo de productos base y actualiza los mapas de referencia en memoria."""
		tenant_id = self.ctx.tenant_id
		self.db_variants = self.article_ctrl.get_all_variants(tenant_id)

		# Filtramos para no meter un combo adentro de otro combo
		normal_items = [v for v in self.db_variants if not v.get('is_combo')]
		self.variant_map = {v.get('name'): v for v in normal_items if v.get('name')}

		if self.variant_map:
			vals = list(self.variant_map.keys())
			self.combo_ingredient.configure(values=vals)
			self.combo_sueltos.configure(values=vals)
			self.combo_ingredient.set('Seleccionar Ingrediente...')
			self.combo_sueltos.set('Seleccionar Producto...')
		else:
			self.combo_ingredient.configure(values=['Sin productos'])
			self.combo_sueltos.configure(values=['Sin productos'])

	# =========================================================
	# PESTAÑA 1: CREADOR DE COMBOS
	# =========================================================
	def _setup_tab_combos(self):
		"""Construye los paneles de formulación de la receta y asignación de precios."""
		self.tab_combos.grid_columnconfigure(0, weight=1)
		self.tab_combos.grid_columnconfigure(1, weight=1)

		# ── PANEL IZQUIERDO: FORMULARIO ──
		left = ctk.CTkFrame(
			self.tab_combos,
			fg_color=SURFACE2,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		left.grid(row=0, column=0, sticky='nsew', padx=(0, 8), pady=8)

		ctk.CTkLabel(
			left,
			text='1.  Datos de la Promo',
			font=('Arial', 15, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(18, 12))

		self.entry_combo_name = ctk.CTkEntry(
			left,
			placeholder_text='Nombre  (Ej: Promo Panchos)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
			font=('Arial', 13),
		)
		self.entry_combo_name.pack(pady=(0, 8), padx=20, fill='x')

		self.entry_combo_price = ctk.CTkEntry(
			left,
			placeholder_text='Precio Total de Venta ($)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=GREEN_TEXT,
			height=40,
			font=('Arial', 14, 'bold'),
		)
		self.entry_combo_price.pack(pady=(0, 12), padx=20, fill='x')

		ctk.CTkLabel(
			left,
			text='COLOR DEL BOTÓN TÁCTIL',
			font=('Arial', 10, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w')

		self.combo_color = ctk.CTkComboBox(
			left,
			values=list(self.color_map.keys()),
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
			state='readonly',
		)
		self.combo_color.pack(pady=(2, 14), padx=20, fill='x')

		ctk.CTkFrame(left, height=1, fg_color=BORDER).pack(
			fill='x', padx=14, pady=(0, 12)
		)

		ctk.CTkLabel(
			left,
			text='2.  Agregar Ingredientes (Receta)',
			font=('Arial', 15, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(0, 10))

		# ComboBox con buscador integrado vía evento de teclado
		self.combo_ingredient = ctk.CTkComboBox(
			left,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
		)
		self.combo_ingredient.pack(pady=(0, 8), padx=20, fill='x')
		self.combo_ingredient.bind('<KeyRelease>', self._filter_ingredients)

		self.entry_ingredient_qty = ctk.CTkEntry(
			left,
			placeholder_text='Cantidad que descuenta  (Ej: 2)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
			font=('Arial', 13),
		)
		self.entry_ingredient_qty.pack(pady=(0, 10), padx=20, fill='x')
		# Atajo clave para carga rápida
		self.entry_ingredient_qty.bind('<Return>', lambda e: self.add_ingredient())

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
			font=('Arial', 12, 'bold'),
		).pack(pady=(0, 18), padx=20, fill='x')

		# ── PANEL DERECHO: LA RECETA ──
		right = ctk.CTkFrame(
			self.tab_combos,
			fg_color=SURFACE2,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		right.grid(row=0, column=1, sticky='nsew', padx=(8, 0), pady=8)

		ctk.CTkLabel(
			right,
			text='Ingredientes de esta Promo',
			font=('Arial', 15, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(18, 10))

		apply_treeview_style()
		self.tree_recipe = ttk.Treeview(
			right,
			columns=('Producto', 'Cantidad', 'Costo Parcial'),
			show='headings',
			height=10,
		)
		self.tree_recipe.heading('Producto', text='Producto')
		self.tree_recipe.heading('Cantidad', text='Cant.')
		self.tree_recipe.heading('Costo Parcial', text='Costo')

		self.tree_recipe.column('Producto', width=200, anchor='w')
		self.tree_recipe.column('Cantidad', width=60, anchor='center')
		self.tree_recipe.column('Costo Parcial', width=80, anchor='center')
		self.tree_recipe.pack(fill='both', expand=True, padx=12, pady=5)

		# Panel de totalizador de costo de producción
		self.lbl_recipe_cost = ctk.CTkLabel(
			right,
			text='Costo de Producción: $0.00',
			font=('Arial', 14, 'bold'),
			text_color=ORANGE_TEXT,
		)
		self.lbl_recipe_cost.pack(pady=(4, 8), padx=14, anchor='e')

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
		).pack(pady=(4, 8), padx=14, fill='x')

		ctk.CTkButton(
			right,
			text='💾  GUARDAR COMBO Y CREAR BOTÓN (Ctrl+G)',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			height=50,
			font=('Arial', 14, 'bold'),
			corner_radius=8,
			command=self.save_combo,
		).pack(pady=(0, 16), padx=14, fill='x')

	def _filter_ingredients(self, event):
		"""Filtra dinámicamente el ComboBox de ingredientes según la entrada del usuario."""
		# Evitar disparar con teclas de control
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
		"""Calcula y proyecta el costo interno del combo basado en la suma de sus componentes."""
		total_cost = Decimal('0')
		for item in self.ingredients_cart:
			cost_unitario = item.get('cost_price', Decimal('0'))
			total_cost += cost_unitario * item['qty']

		self.lbl_recipe_cost.configure(text=f'Costo de Producción: ${total_cost:,.2f}')

	def add_ingredient(self):
		"""Evalúa y transfiere un producto base al contenedor de la receta."""
		desc = self.combo_ingredient.get()
		qty_str = self.entry_ingredient_qty.get().replace(',', '.')

		if desc not in self.variant_map:
			CTkMessagebox(
				title='Atención',
				message='Seleccioná un producto de la lista válida.',
				icon='info',
			)
			return

		try:
			qty = Decimal(qty_str)
			if qty <= 0:
				raise ValueError
		except (ValueError, InvalidOperation):
			CTkMessagebox(
				title='Error',
				message='La cantidad debe ser un número mayor a cero.',
				icon='cancel',
			)
			return

		variant = self.variant_map[desc]
		cost_unitario = Decimal(str(variant.get('cost_price', 0)))
		costo_parcial = cost_unitario * qty

		item_id = self.tree_recipe.insert(
			'', 'end', values=(desc, f'{qty:g}', f'${costo_parcial:,.2f}')
		)

		self.ingredients_cart.append(
			{
				'tree_id': item_id,
				'variant_id': variant['variant_id'],
				'qty': qty,
				'cost_price': cost_unitario,  # Guardamos el costo para el totalizador
			}
		)

		self.entry_ingredient_qty.delete(0, 'end')
		self.combo_ingredient.set('Seleccionar Ingrediente...')
		self.combo_ingredient.focus()
		self._update_recipe_cost()

	def remove_ingredient(self):
		"""Aplica la remoción segura (bulk) de ingredientes de la receta."""
		selected = self.tree_recipe.selection()
		if not selected:
			CTkMessagebox(
				title='Aviso',
				message='Seleccioná un ingrediente de la tabla para quitarlo.',
				icon='info',
			)
			return

		# Reconstrucción de la lista para evitar errores de mutación durante iteración
		self.ingredients_cart = [
			item for item in self.ingredients_cart if item['tree_id'] not in selected
		]

		for item_id in selected:
			self.tree_recipe.delete(item_id)

		self._update_recipe_cost()

	def save_combo(self):
		"""Valida y emite la orden de persistencia para el combo compuesto."""
		name = self.entry_combo_name.get().strip()
		price_str = self.entry_combo_price.get().replace(',', '.')
		color_key = self.combo_color.get()
		btn_color = self.color_map.get(color_key, ACCENT_DIM)

		if not name or not price_str or not self.ingredients_cart:
			CTkMessagebox(
				title='Faltan Datos',
				message='Debés ingresar un nombre, precio de venta y al menos 1 ingrediente.',
				icon='warning',
			)
			return

		tenant_id = self.ctx.tenant_id
		# El controlador espera una estructura específica, convertimos los Decimal a float/int si es necesario
		cart_for_ctrl = [
			{'variant_id': i['variant_id'], 'qty': float(i['qty'])}
			for i in self.ingredients_cart
		]

		success, msg = self.combo_ctrl.create_combo(
			tenant_id, name, price_str, btn_color, cart_for_ctrl
		)

		if success:
			CTkMessagebox(title='¡Combo Guardado!', message=msg, icon='check')
			self.entry_combo_name.delete(0, 'end')
			self.entry_combo_price.delete(0, 'end')
			for item in self.tree_recipe.get_children():
				self.tree_recipe.delete(item)
			self.ingredients_cart.clear()
			self._update_recipe_cost()
			self.load_data()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')

	# =========================================================
	# PESTAÑA 2: BOTONES RÁPIDOS
	# =========================================================
	def _setup_tab_sueltos(self):
		"""Construye el panel de configuración de atajos directos para el POS."""
		outer = ctk.CTkFrame(
			self.tab_sueltos,
			fg_color=SURFACE2,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		outer.pack(fill='both', expand=True, padx=0, pady=8)

		inner = ctk.CTkFrame(outer, fg_color='transparent')
		inner.pack(fill='both', expand=True, padx=40, pady=20)

		ctk.CTkLabel(
			inner,
			text='Convertir Producto Normal en Botón Rápido',
			font=('Arial', 18, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(0, 6))

		ctk.CTkLabel(
			inner,
			text='Útil para productos sin código de barras (Pan, Hielo, Bolsas)',
			font=('Arial', 12),
			text_color=TEXT_MUTED,
		).pack(pady=(0, 20))

		ctk.CTkLabel(
			inner,
			text='1. SELECCIONA EL PRODUCTO',
			font=('Arial', 10, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w')

		self.combo_sueltos = ctk.CTkComboBox(
			inner,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
		)
		self.combo_sueltos.pack(pady=(2, 14), fill='x')
		self.combo_sueltos.bind('<KeyRelease>', lambda e: self._filter_sueltos(e))

		ctk.CTkLabel(
			inner,
			text='2. ELIGE EL COLOR DEL BOTÓN',
			font=('Arial', 10, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w')

		self.combo_color_suelto = ctk.CTkComboBox(
			inner,
			values=list(self.color_map.keys()),
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=40,
			state='readonly',
		)
		self.combo_color_suelto.pack(pady=(2, 16), fill='x')

		self.check_touch_var = ctk.BooleanVar(value=True)
		self.check_touch = ctk.CTkCheckBox(
			inner,
			text='Mostrar en la Pantalla de Ventas (Touch)',
			variable=self.check_touch_var,
			text_color=TEXT_SECONDARY,
			font=('Arial', 13),
		)
		self.check_touch.pack(pady=(0, 20), anchor='w')

		ctk.CTkButton(
			inner,
			text='💾  ACTUALIZAR CONFIGURACIÓN (Ctrl+G)',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=50,
			font=('Arial', 14, 'bold'),
			corner_radius=8,
			command=self.save_suelto,
		).pack(pady=(0, 20), fill='x')

	def _filter_sueltos(self, event):
		"""Filtra dinámicamente el ComboBox de productos sueltos."""
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
		"""Procesa y guarda la configuración de visibilidad táctil del producto seleccionado."""
		desc = self.combo_sueltos.get()
		if desc not in self.variant_map:
			CTkMessagebox(
				title='Atención',
				message='Seleccioná un producto válido de la lista.',
				icon='info',
			)
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
			CTkMessagebox(title='¡Actualizado!', message=msg, icon='check')
			self.combo_sueltos.set('Seleccionar Producto...')
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')
