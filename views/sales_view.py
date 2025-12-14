from tkinter import ttk

import customtkinter as ctk


class SalesView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		# Controladores
		from controllers.product_controller import ProductController
		from controllers.sales_controller import SalesController

		self.product_ctrl = ProductController(db_engine)
		self.sales_ctrl = SalesController(db_engine)

		self.cart = []

		# --- LAYOUT ---
		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		# === PANEL IZQUIERDO: SELECCIÓN DE PRODUCTOS ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.left_panel, text='Agregar Producto', font=('Arial', 18, 'bold')
		).pack(pady=10)

		# ComboBox para seleccionar productos (Simple para empezar)
		self.products_combo = ctk.CTkComboBox(self.left_panel, width=200)
		self.products_combo.set('Seleccionar...')
		self.products_combo.pack(pady=10)

		# Cantidad
		self.qty_entry = ctk.CTkEntry(self.left_panel, placeholder_text='Cantidad')
		self.qty_entry.pack(pady=10)
		self.qty_entry.insert(0, '1')

		# Botón Agregar
		self.btn_add = ctk.CTkButton(
			self.left_panel, text='Agregar al Carrito ->', command=self.add_to_cart
		)
		self.btn_add.pack(pady=20)

		# Cargar productos disponibles en el Combo
		self.load_products_combo()

		# === PANEL DERECHO: CARRITO ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.right_panel, text='Ticket de Venta', font=('Arial', 18, 'bold')
		).pack(pady=10)

		# Tabla
		style = ttk.Style()
		style.configure('Treeview', font=('Arial', 12), rowheight=25)

		self.tree = ttk.Treeview(
			self.right_panel,
			columns=('Producto', 'Cant', 'Precio', 'Subtotal'),
			show='headings',
		)
		self.tree.heading('Producto', text='Producto')
		self.tree.heading('Cant', text='Cant')
		self.tree.heading('Precio', text='Precio')
		self.tree.heading('Subtotal', text='Subtotal')
		self.tree.pack(fill='both', expand=True, padx=10)

		self.lbl_total = ctk.CTkLabel(
			self.right_panel, text='TOTAL: $0.00', font=('Arial', 24, 'bold')
		)
		self.lbl_total.pack(pady=10)

		self.btn_pay = ctk.CTkButton(
			self.right_panel,
			text='CONFIRMAR VENTA',
			fg_color='green',
			height=50,
			command=self.process_sale,
		)
		self.btn_pay.pack(pady=10, fill='x', padx=20)

	def load_products_combo(self):
		# Buscamos productos de la DB
		self.db_products = self.product_ctrl.get_products(self.current_user.tenant_id)
		self.product_map = {p.name: p for p in self.db_products}
		self.products_combo.configure(values=list(self.product_map.keys()))

	def add_to_cart(self):
		name = self.products_combo.get()
		qty_str = self.qty_entry.get()

		if name in self.product_map and qty_str.isdigit():
			qty = int(qty_str)
			product = self.product_map[name]

			# Verificar si hay stock (simple check visual)
			if qty > product.stock:
				print('No hay suficiente stock')
				return

			subtotal = product.price * qty

			# Agregar a lista interna
			self.cart.append(
				{
					'product_id': product.id,
					'name': product.name,
					'price': product.price,
					'qty': qty,
					'subtotal': subtotal,
				}
			)

			# Agregar a la tabla visual
			self.tree.insert(
				'', 'end', values=(name, qty, f'${product.price}', f'${subtotal}')
			)
			self.update_total()

	def update_total(self):
		total = sum(item['subtotal'] for item in self.cart)
		self.lbl_total.configure(text=f'TOTAL: ${total:.2f}')

	def process_sale(self):
		if not self.cart:
			return

		success, msg = self.sales_ctrl.process_sale(
			self.current_user.tenant_id, self.current_user.id, self.cart
		)

		if success:
			print(msg)
			self.cart = []
			for item in self.tree.get_children():
				self.tree.delete(item)
			self.update_total()
			self.load_products_combo()
		else:
			print(f'Error: {msg}')
