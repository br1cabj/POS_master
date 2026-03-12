from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

# Importación arriba
from controllers.purchases_controller import PurchasesController


class PurchasesView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = PurchasesController(db_engine)
		self.cart = []

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		# === ESTILO MODERNO PARA LA TABLA ===
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
		style.map('Treeview', background=[('selected', '#1f538d')])
		style.configure(
			'Treeview.Heading',
			background='#565b5e',
			foreground='white',
			relief='flat',
			font=('Arial', 10, 'bold'),
		)
		style.map('Treeview.Heading', background=[('active', '#343638')])

		# === PANEL IZQUIERDO: FORMULARIO DE INGRESO ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.left_panel, text='Ingreso de Mercadería', font=('Arial', 18, 'bold')
		).pack(pady=10)

		# Selector de Proveedor
		ctk.CTkLabel(self.left_panel, text='Proveedor:').pack(pady=5)
		self.supplier_combo = ctk.CTkComboBox(self.left_panel, width=200)
		self.supplier_combo.pack(pady=5)

		# Selector de Artículo (Variante)
		ctk.CTkLabel(self.left_panel, text='Artículo a reabastecer:').pack(pady=5)
		self.articles_combo = ctk.CTkComboBox(
			self.left_panel, width=200, command=self.on_article_select
		)
		self.articles_combo.pack(pady=5)

		# Campo de Costo
		self.cost_entry = ctk.CTkEntry(
			self.left_panel, placeholder_text='Costo Unitario ($)', width=150
		)
		self.cost_entry.pack(pady=5)

		# Campo de Cantidad
		self.qty_entry = ctk.CTkEntry(
			self.left_panel, placeholder_text='Cantidad Recibida', width=150
		)
		self.qty_entry.pack(pady=5)

		self.btn_add = ctk.CTkButton(
			self.left_panel, text='Agregar a la Factura ->', command=self.add_to_cart
		)
		self.btn_add.pack(pady=20)

		# === PANEL DERECHO: DETALLE DE LA COMPRA ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.right_panel,
			text='Detalle de Factura / Remito',
			font=('Arial', 18, 'bold'),
		).pack(pady=10)

		self.tree = ttk.Treeview(
			self.right_panel,
			columns=('Artículo', 'Cant', 'Costo', 'Subtotal'),
			show='headings',
		)
		self.tree.heading('Artículo', text='Artículo')
		self.tree.heading('Cant', text='Cant')
		self.tree.heading('Costo', text='Costo Unitario')
		self.tree.heading('Subtotal', text='Subtotal')
		self.tree.pack(fill='both', expand=True, padx=10)

		self.btn_remove = ctk.CTkButton(
			self.right_panel,
			text='🗑️ Quitar Artículo',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=self.remove_from_cart,
		)
		self.btn_remove.pack(pady=5)

		self.lbl_total = ctk.CTkLabel(
			self.right_panel,
			text='TOTAL A PAGAR: $0.00',
			font=('Arial', 24, 'bold'),
			text_color='#ff3333',
		)
		self.lbl_total.pack(pady=10)

		self.btn_pay = ctk.CTkButton(
			self.right_panel,
			text='📦 CONFIRMAR INGRESO Y PAGAR',
			fg_color='#0055ff',
			height=50,
			command=self.process_purchase,
		)
		self.btn_pay.pack(pady=10, fill='x', padx=20)

		# Diccionarios internos
		self.supplier_map = {}
		self.variant_map = {}

		# Carga asíncrona de combos
		self.after(100, self.load_combos)

	def load_combos(self):
		"""Carga los proveedores y artículos (variantes) desde el controlador"""
		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

		# Proveedores (Vienen como diccionarios)
		suppliers = self.controller.get_suppliers(tenant_id)
		self.supplier_map = {s['name']: s for s in suppliers}

		if self.supplier_map:
			self.supplier_combo.configure(values=list(self.supplier_map.keys()))
			self.supplier_combo.set('Seleccionar Proveedor')
		else:
			self.supplier_combo.configure(values=['Sin Proveedores'])
			self.supplier_combo.set('No hay proveedores activos')

		# Artículos (Vienen como diccionarios)
		variants = self.controller.get_variants(tenant_id)
		# Filtramos para asegurarnos de que tengan nombre
		self.variant_map = {v['name']: v for v in variants if v.get('name')}

		if self.variant_map:
			self.articles_combo.configure(values=list(self.variant_map.keys()))
			self.articles_combo.set('Seleccionar Artículo...')
		else:
			self.articles_combo.configure(values=['Sin Artículos'])
			self.articles_combo.set('No hay artículos activos')

	def on_article_select(self, selected_name):
		"""Autocompleta el costo cuando el usuario selecciona un producto"""
		if selected_name in self.variant_map:
			variant_dict = self.variant_map[selected_name]
			self.cost_entry.delete(0, 'end')

			# Formateamos a 2 decimales para limpieza visual
			cost_str = f'{variant_dict.get("cost_price", 0.0):.2f}'
			self.cost_entry.insert(0, cost_str)

			self.qty_entry.focus()

	def add_to_cart(self):
		desc = self.articles_combo.get()
		cost_str = self.cost_entry.get().strip().replace(',', '.')
		qty_str = self.qty_entry.get().strip().replace(',', '.')

		if desc not in self.variant_map or not cost_str or not qty_str:
			CTkMessagebox(
				title='Faltan datos',
				message='Selecciona un producto, costo y cantidad.',
				icon='warning',
			)
			return

		try:
			qty = float(qty_str)  # Cambiado a float por si compran a granel
			cost = float(cost_str)
			if qty <= 0 or cost < 0:
				raise ValueError
		except ValueError:
			CTkMessagebox(
				title='Error de formato',
				message='Costo o cantidad inválidos. Usa números positivos.',
				icon='cancel',
			)
			return

		variant = self.variant_map[desc]
		subtotal = cost * qty

		# Insertamos visualmente y obtenemos el ID de la fila en Tkinter
		# Esto es clave para poder borrarlo correctamente después
		item_id = self.tree.insert(
			'',
			'end',
			values=(variant['name'], qty, f'${cost:.2f}', f'${subtotal:.2f}'),
		)

		# Guardamos en la memoria RAM el item exacto, atado al ID de la fila
		self.cart.append(
			{
				'tree_id': item_id,  # <- MAGIA: Relacionamos UI con Memoria
				'variant_id': variant['variant_id'],
				'desc': variant['name'],
				'cost': cost,
				'qty': qty,
				'subtotal': subtotal,
			}
		)

		self.update_total()

		self.cost_entry.delete(0, 'end')
		self.qty_entry.delete(0, 'end')
		self.articles_combo.set('Seleccionar Artículo...')

	def remove_from_cart(self):
		"""Borra un item seleccionando su ID único de fila en Tkinter"""
		selected_item = self.tree.selection()
		if not selected_item:
			CTkMessagebox(
				title='Atención',
				message='Selecciona un artículo de la tabla para quitarlo.',
				icon='info',
			)
			return

		for item_id in selected_item:
			# 1. Lo borramos de la memoria (lista self.cart) buscando su tree_id
			for i, item in enumerate(self.cart):
				if item.get('tree_id') == item_id:
					self.cart.pop(i)
					break

			# 2. Lo borramos visualmente
			self.tree.delete(item_id)

		self.update_total()

	def update_total(self):
		total = sum(item.get('subtotal', 0) for item in self.cart)
		self.lbl_total.configure(text=f'TOTAL A PAGAR: ${total:.2f}')

	def process_purchase(self):
		if not self.cart:
			CTkMessagebox(
				title='Carrito vacío',
				message='Agrega productos antes de confirmar el ingreso.',
				icon='warning',
			)
			return

		supplier_name = self.supplier_combo.get()
		if supplier_name not in self.supplier_map:
			CTkMessagebox(
				title='Proveedor inválido',
				message='Selecciona un proveedor válido de la lista.',
				icon='cancel',
			)
			return

		# Obtenemos el ID del proveedor desde el diccionario
		supplier_id = self.supplier_map[supplier_name]['id']

		# CTkMessagebox asíncrono-ish
		msg_box = CTkMessagebox(
			title='Confirmar',
			message='¿Deseas confirmar este ingreso de mercadería?',
			icon='question',
			option_1='No',
			option_2='Sí',
		)

		if msg_box.get() != 'Sí':
			return

		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)
		user_id = (
			self.current_user.get('id')
			if isinstance(self.current_user, dict)
			else self.current_user.id
		)

		success, msg = self.controller.process_purchase(
			tenant_id, user_id, supplier_id, self.cart
		)

		if success:
			CTkMessagebox(title='¡Éxito!', message=msg, icon='check')
			self.cart = []
			for item in self.tree.get_children():
				self.tree.delete(item)
			self.update_total()
			self.load_combos()  # Recargamos combos por si cambiaron costos
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')
