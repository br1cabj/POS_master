from tkinter import messagebox, ttk  # <--- IMPORTANTE: Importar messagebox

import customtkinter as ctk


class SalesView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.product_controller import ProductController
		from controllers.sales_controller import SalesController

		self.product_ctrl = ProductController(db_engine)
		self.sales_ctrl = SalesController(db_engine)

		self.cart = []

		# --- LAYOUT ---
		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		# === PANEL IZQUIERDO ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.left_panel, text='Agregar Producto', font=('Arial', 18, 'bold')
		).pack(pady=10)

		self.products_combo = ctk.CTkComboBox(self.left_panel, width=200)
		self.products_combo.set('Seleccionar...')
		self.products_combo.pack(pady=10)

		self.qty_entry = ctk.CTkEntry(self.left_panel, placeholder_text='Cantidad')
		self.qty_entry.pack(pady=10)
		self.qty_entry.insert(0, '1')

		self.btn_add = ctk.CTkButton(
			self.left_panel, text='Agregar al Carrito ->', command=self.add_to_cart
		)
		self.btn_add.pack(pady=20)

		self.load_products_combo()

		# === PANEL DERECHO ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.right_panel, text='Ticket de Venta', font=('Arial', 18, 'bold')
		).pack(pady=10)

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
		try:
			self.db_products = self.product_ctrl.get_products(
				self.current_user.tenant_id
			)
			self.product_map = {p.name: p for p in self.db_products}

			if not self.product_map:
				self.products_combo.set('Sin productos disponibles')
				self.products_combo.configure(state='disabled')
			else:
				self.products_combo.configure(values=list(self.product_map.keys()))
		except Exception as e:
			messagebox.showerror('Error DB', f'No se pudieron cargar productos: {e}')
			self.product_map = {}

	def add_to_cart(self):
		name = self.products_combo.get()
		qty_str = self.qty_entry.get()

		if name == 'Seleccionar...' or name == 'Sin productos disponibles':
			messagebox.showwarning(
				'Atención', 'Por favor selecciona un producto válido.'
			)
			return

		if name not in self.product_map:
			messagebox.showerror(
				'Error',
				'El producto seleccionado no parece existir en la base de datos cargada.',
			)
			return

		if not qty_str.isdigit():
			messagebox.showwarning('Atención', 'La cantidad debe ser un número entero.')
			return

		qty = int(qty_str)
		if qty <= 0:
			messagebox.showwarning('Atención', 'La cantidad debe ser mayor a 0.')
			return

		product = self.product_map[name]

		if qty > product.stock:
			messagebox.showwarning(
				'Stock Insuficiente', f'Solo quedan {product.stock} unidades.'
			)
			return

		subtotal = product.price * qty

		self.cart.append(
			{
				'product_id': product.id,
				'name': product.name,
				'price': product.price,
				'qty': qty,
				'subtotal': subtotal,
			}
		)

		self.tree.insert(
			'', 'end', values=(name, qty, f'${product.price}', f'${subtotal}')
		)
		self.update_total()

	def update_total(self):
		total = sum(item['subtotal'] for item in self.cart)
		self.lbl_total.configure(text=f'TOTAL: ${total:.2f}')

	def process_sale(self):
		if not self.cart:
			messagebox.showinfo('Carrito Vacío', 'No hay productos para vender.')
			return

		try:
			success, msg = self.sales_ctrl.process_sale(
				self.current_user.tenant_id, self.current_user.id, self.cart
			)

			if success:
				messagebox.showinfo('Éxito', f'Venta realizada: {msg}')
				self.cart = []
				for item in self.tree.get_children():
					self.tree.delete(item)
				self.update_total()
				self.load_products_combo()
			else:
				messagebox.showerror('Error en Venta', f'No se pudo procesar: {msg}')

		except Exception as e:
			print(f'Error crítico al procesar venta: {e}')
			messagebox.showerror(
				'Error Crítico', 'Ocurrió un error al intentar guardar la venta.'
			)
