from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.article_controller import ArticleController
from controllers.combo_controller import ComboController


class ComboMakerView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.combo_ctrl = ComboController(db_engine)
		self.article_ctrl = ArticleController(db_engine)

		self.db_variants = []
		self.variant_map = {}
		self.ingredients_cart = []  # Aquí guardamos la receta temporal

		self.pack(fill='both', expand=True, padx=10, pady=10)

		# Paleta de colores para los botones táctiles
		self.color_map = {
			'🔵 Azul Marino': '#1f538d',
			'🟢 Verde Éxito': '#5cb85c',
			'🔴 Rojo Alerta': '#d9534f',
			'🟠 Naranja Promo': '#e68a00',
			'🟣 Púrpura Premium': '#6f42c1',
			'⚫ Gris Neutro': '#444444',
		}

		# === TABS (PESTAÑAS) ===
		self.tabs = ctk.CTkTabview(self)
		self.tabs.pack(fill='both', expand=True)

		self.tab_combos = self.tabs.add('🍔 Crear Combos y Promos')
		self.tab_sueltos = self.tabs.add('👆 Botones Rápidos (Sueltos)')

		self._setup_tab_combos()
		self._setup_tab_sueltos()

		self.after(100, self.load_data)

	def _get_tenant_id(self):
		return (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

	def load_data(self):
		"""Carga los productos para usarlos como ingredientes o botones"""
		tenant_id = self._get_tenant_id()
		self.db_variants = self.article_ctrl.get_all_variants(tenant_id)

		# Filtramos para no meter un combo dentro de otro combo (Inception 🤯)
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

	# ==========================================
	# PESTAÑA 1: CREADOR DE COMBOS
	# ==========================================
	def _setup_tab_combos(self):
		self.tab_combos.grid_columnconfigure(0, weight=1)
		self.tab_combos.grid_columnconfigure(1, weight=1)

		# -- Panel Izquierdo: Formulario del Combo --
		left = ctk.CTkFrame(self.tab_combos)
		left.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			left, text='1. Datos de la Promo', font=('Arial', 16, 'bold')
		).pack(pady=10)

		self.entry_combo_name = ctk.CTkEntry(
			left, placeholder_text='Nombre (Ej: Promo Panchos)', width=250
		)
		self.entry_combo_name.pack(pady=10)

		self.entry_combo_price = ctk.CTkEntry(
			left, placeholder_text='Precio Total de Venta ($)', width=250
		)
		self.entry_combo_price.pack(pady=10)

		ctk.CTkLabel(left, text='Color del Botón Táctil:').pack(pady=(10, 0))
		self.combo_color = ctk.CTkComboBox(
			left, values=list(self.color_map.keys()), width=250
		)
		self.combo_color.pack(pady=5)

		ctk.CTkLabel(left, text='------------------------').pack(pady=10)
		ctk.CTkLabel(
			left, text='2. Agregar Ingredientes (Receta)', font=('Arial', 16, 'bold')
		).pack(pady=10)

		self.combo_ingredient = ctk.CTkComboBox(left, width=250)
		self.combo_ingredient.pack(pady=5)

		self.entry_ingredient_qty = ctk.CTkEntry(
			left, placeholder_text='Cant. que descuenta (Ej: 2)', width=250
		)
		self.entry_ingredient_qty.pack(pady=10)

		ctk.CTkButton(
			left,
			text='👇 Añadir Ingrediente a la Receta',
			fg_color='#e68a00',
			hover_color='#cc7a00',
			command=self.add_ingredient,
		).pack(pady=10)

		# -- Panel Derecho: La Receta (Ingredientes) --
		right = ctk.CTkFrame(self.tab_combos)
		right.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			right, text='Ingredientes de esta Promo', font=('Arial', 16, 'bold')
		).pack(pady=10)

		# Usamos Treeview básico para la lista de ingredientes
		style = ttk.Style()
		style.theme_use('default')
		style.configure(
			'Treeview',
			background='#2b2b2b',
			foreground='white',
			rowheight=30,
			fieldbackground='#2b2b2b',
			borderwidth=0,
		)

		self.tree_recipe = ttk.Treeview(
			right, columns=('Producto', 'Cantidad'), show='headings', height=10
		)
		self.tree_recipe.heading('Producto', text='Producto')
		self.tree_recipe.heading('Cantidad', text='Cant. a descontar')
		self.tree_recipe.column('Producto', width=200)
		self.tree_recipe.column('Cantidad', width=120, anchor='center')
		self.tree_recipe.pack(fill='both', expand=True, padx=10, pady=5)

		ctk.CTkButton(
			right,
			text='🗑️ Quitar Ingrediente',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=self.remove_ingredient,
		).pack(pady=5)

		ctk.CTkButton(
			right,
			text='💾 GUARDAR COMBO Y CREAR BOTÓN',
			fg_color='#5cb85c',
			hover_color='#4cae4c',
			height=50,
			font=('Arial', 14, 'bold'),
			command=self.save_combo,
		).pack(pady=20, fill='x', padx=20)

	def add_ingredient(self):
		desc = self.combo_ingredient.get()
		qty_str = self.entry_ingredient_qty.get().replace(',', '.')

		if desc not in self.variant_map:
			return

		try:
			qty = float(qty_str)
			if qty <= 0:
				raise ValueError
		except ValueError:
			CTkMessagebox(title='Error', message='Cantidad inválida.', icon='cancel')
			return

		variant = self.variant_map[desc]
		item_id = self.tree_recipe.insert('', 'end', values=(desc, qty))

		self.ingredients_cart.append(
			{'tree_id': item_id, 'variant_id': variant['variant_id'], 'qty': qty}
		)

		self.entry_ingredient_qty.delete(0, 'end')

	def remove_ingredient(self):
		selected = self.tree_recipe.selection()
		if not selected:
			return

		for item_id in selected:
			for i, item in enumerate(self.ingredients_cart):
				if item.get('tree_id') == item_id:
					self.ingredients_cart.pop(i)
					break
			self.tree_recipe.delete(item_id)

	def save_combo(self):
		name = self.entry_combo_name.get().strip()
		price_str = self.entry_combo_price.get().replace(',', '.')
		color_key = self.combo_color.get()
		btn_color = self.color_map.get(color_key, '#1f538d')

		if not name or not price_str or not self.ingredients_cart:
			CTkMessagebox(
				title='Faltan Datos',
				message='Debes poner nombre, precio y al menos 1 ingrediente.',
				icon='warning',
			)
			return

		tenant_id = self._get_tenant_id()
		success, msg = self.combo_ctrl.create_combo(
			tenant_id, name, price_str, btn_color, self.ingredients_cart
		)

		if success:
			CTkMessagebox(title='¡Éxito!', message=msg, icon='check')
			self.entry_combo_name.delete(0, 'end')
			self.entry_combo_price.delete(0, 'end')
			for item in self.tree_recipe.get_children():
				self.tree_recipe.delete(item)
			self.ingredients_cart.clear()
			self.load_data()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')

	# ==========================================
	# PESTAÑA 2: BOTONES DE PRODUCTOS SUELTOS
	# ==========================================
	def _setup_tab_sueltos(self):
		frame = ctk.CTkFrame(self.tab_sueltos)
		frame.pack(fill='both', expand=True, padx=40, pady=20)

		ctk.CTkLabel(
			frame,
			text='Convertir Producto Normal en Botón Rápido',
			font=('Arial', 18, 'bold'),
		).pack(pady=20)
		ctk.CTkLabel(
			frame,
			text='Útil para cosas sin código de barras (Pan, Hielo, Bolsas)',
			text_color='gray',
		).pack(pady=(0, 20))

		ctk.CTkLabel(frame, text='1. Selecciona el Producto:').pack(pady=(10, 0))
		self.combo_sueltos = ctk.CTkComboBox(frame, width=300)
		self.combo_sueltos.pack(pady=5)

		ctk.CTkLabel(frame, text='2. Elige el color del Botón:').pack(pady=(15, 0))
		self.combo_color_suelto = ctk.CTkComboBox(
			frame, values=list(self.color_map.keys()), width=300
		)
		self.combo_color_suelto.pack(pady=5)

		self.check_touch_var = ctk.BooleanVar(value=True)
		self.check_touch = ctk.CTkCheckBox(
			frame,
			text='Mostrar en la Pantalla de Ventas (Touch)',
			variable=self.check_touch_var,
		)
		self.check_touch.pack(pady=20)

		ctk.CTkButton(
			frame,
			text='💾 ACTUALIZAR CONFIGURACIÓN',
			fg_color='#1f538d',
			height=50,
			font=('Arial', 14, 'bold'),
			command=self.save_suelto,
		).pack(pady=20)

	def save_suelto(self):
		desc = self.combo_sueltos.get()
		if desc not in self.variant_map:
			CTkMessagebox(
				title='Atención', message='Selecciona un producto válido.', icon='info'
			)
			return

		variant_id = self.variant_map[desc]['variant_id']
		show_on_touch = self.check_touch_var.get()

		color_key = self.combo_color_suelto.get()
		btn_color = self.color_map.get(color_key, '#1f538d')

		tenant_id = self._get_tenant_id()
		success, msg = self.combo_ctrl.toggle_touch_status(
			tenant_id, variant_id, show_on_touch, btn_color
		)

		if success:
			CTkMessagebox(title='¡Actualizado!', message=msg, icon='check')
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')
