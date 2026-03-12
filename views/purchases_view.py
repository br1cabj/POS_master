from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox  # NUEVO: Para mensajes profesionales


class PurchasesView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.purchases_controller import PurchasesController

		self.controller = PurchasesController(db_engine)
		self.cart = []

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

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

		self.load_combos()

		# === PANEL DERECHO: DETALLE DE LA COMPRA ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.right_panel,
			text='Detalle de Factura / Remito',
			font=('Arial', 18, 'bold'),
		).pack(pady=10)

		style = ttk.Style()
		style.configure('Treeview', font=('Arial', 12), rowheight=25)

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

		# Botón para quitar items de la compra si me equivoco
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
			text_color='red',
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

	def load_combos(self):
		"""Carga los proveedores y artículos (variantes) en las listas desplegables"""
		# Proveedores
		suppliers = self.controller.get_suppliers(self.current_user.tenant_id)
		self.supplier_map = {s.name: s for s in suppliers}
		if self.supplier_map:
			self.supplier_combo.configure(values=list(self.supplier_map.keys()))
			self.supplier_combo.set(list(self.supplier_map.keys())[0])
		else:
			self.supplier_combo.set('No hay proveedores activos')

		# Artículos (Ahora usamos get_variants y mapeamos por el nombre del artículo padre)
		variants = self.controller.get_variants(self.current_user.tenant_id)
		self.variant_map = {v.article.name: v for v in variants if v.article}
		if self.variant_map:
			self.articles_combo.configure(values=list(self.variant_map.keys()))
			self.articles_combo.set('Seleccionar...')

	def on_article_select(self, selected_name):
		"""Autocompleta el costo cuando el usuario selecciona un producto"""
		if selected_name in self.variant_map:
			variant = self.variant_map[selected_name]
			self.cost_entry.delete(0, 'end')
			self.cost_entry.insert(
				0, str(variant.cost_price)
			)  # Sugiere el último costo conocido
			self.qty_entry.focus()  # Mueve el cursor a cantidad para mayor agilidad

	def add_to_cart(self):
		desc = self.articles_combo.get()
		cost_str = self.cost_entry.get().strip()
		qty_str = self.qty_entry.get().strip()

		if desc not in self.variant_map or not cost_str or not qty_str:
			CTkMessagebox(
				title='Faltan datos',
				message='Selecciona un producto, costo y cantidad.',
				icon='warning',
			)
			return

		try:
			qty = int(qty_str)
			cost = float(cost_str)
		except ValueError:
			CTkMessagebox(
				title='Error de formato',
				message='Costo o cantidad inválidos. Usa números.',
				icon='cancel',
			)
			return

		variant = self.variant_map[desc]
		subtotal = cost * qty

		# NUEVO: Usamos variant_id
		self.cart.append(
			{
				'variant_id': variant.id,
				'desc': variant.article.name,
				'cost': cost,
				'qty': qty,
				'subtotal': subtotal,
			}
		)

		self.tree.insert(
			'',
			'end',
			values=(variant.article.name, qty, f'${cost:.2f}', f'${subtotal:.2f}'),
		)
		self.update_total()

		# Limpiar campos y volver al selector inicial
		self.cost_entry.delete(0, 'end')
		self.qty_entry.delete(0, 'end')
		self.articles_combo.set('Seleccionar...')

	def remove_from_cart(self):
		"""Permite borrar un item si el usuario se equivocó"""
		selected_item = self.tree.selection()
		if not selected_item:
			CTkMessagebox(
				title='Atención',
				message='Selecciona un artículo de la tabla para quitarlo.',
				icon='info',
			)
			return

		for item_id in selected_item:
			values = self.tree.item(item_id, 'values')
			desc_to_remove = values[0]

			for i, item in enumerate(self.cart):
				if item['desc'] == desc_to_remove:
					self.cart.pop(i)
					break

			self.tree.delete(item_id)
		self.update_total()

	def update_total(self):
		total = sum(item['subtotal'] for item in self.cart)
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

		supplier_id = self.supplier_map[supplier_name].id

		# Pedimos confirmación antes de guardar
		confirm = CTkMessagebox(
			title='Confirmar',
			message='¿Deseas confirmar este ingreso de mercadería?',
			icon='question',
			option_1='No',
			option_2='Sí',
		).get()
		if confirm != 'Sí':
			return

		success, msg = self.controller.process_purchase(
			self.current_user.tenant_id, self.current_user.id, supplier_id, self.cart
		)

		if success:
			CTkMessagebox(title='¡Éxito!', message=msg, icon='check')
			self.cart = []
			for item in self.tree.get_children():
				self.tree.delete(item)
			self.update_total()
			self.load_combos()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')
