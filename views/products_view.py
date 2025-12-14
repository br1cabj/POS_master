import customtkinter as ctk


class ProductsView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		# Importamos el controlador
		from controllers.product_controller import ProductController

		self.controller = ProductController(db_engine)

		# --- ESTRUCTURA ---
		self.grid_columnconfigure(1, weight=1)
		self.grid_rowconfigure(0, weight=1)

		# 1. Panel Izquierdo
		self.left_panel = ctk.CTkFrame(self, width=250)
		self.left_panel.grid(row=0, column=0, sticky='ns', padx=10, pady=10)
		self.left_panel.grid_propagate(False)

		ctk.CTkLabel(
			self.left_panel, text='Nuevo Producto', font=('Arial', 20, 'bold')
		).pack(pady=20)

		self.entry_name = ctk.CTkEntry(
			self.left_panel, placeholder_text='Nombre del Producto'
		)
		self.entry_name.pack(pady=10, padx=10)

		self.entry_price = ctk.CTkEntry(self.left_panel, placeholder_text='Precio')
		self.entry_price.pack(pady=10, padx=10)

		self.entry_stock = ctk.CTkEntry(
			self.left_panel, placeholder_text='Stock Inicial'
		)
		self.entry_stock.pack(pady=10, padx=10)

		# Label para mensajes de estado (éxito/error)
		self.status_label = ctk.CTkLabel(self.left_panel, text='', text_color='red')
		self.status_label.pack(pady=5)

		self.btn_add = ctk.CTkButton(
			self.left_panel, text='Guardar Producto', command=self.save_product
		)
		self.btn_add.pack(pady=20, padx=10)

		# 2. Panel Derecho
		self.right_panel = ctk.CTkScrollableFrame(self, label_text='Mis Productos')
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

		self.refresh_list()

	def save_product(self):
		name = self.entry_name.get()
		price_str = self.entry_price.get()
		stock_str = self.entry_stock.get()

		if not name or not price_str or not stock_str:
			self.status_label.configure(
				text='Todos los campos son obligatorios', text_color='red'
			)
			return

		# 2. Validación de tipos numéricos
		try:
			price = float(price_str)
			stock = int(stock_str)
		except ValueError:
			self.status_label.configure(
				text='Precio o Stock inválidos', text_color='red'
			)
			return

		# 3. Llamada al controlador
		success, message = self.controller.add_product(
			name, price, stock, self.current_user.tenant_id
		)

		if success:
			self.refresh_list()
			self.entry_name.delete(0, 'end')
			self.entry_price.delete(0, 'end')
			self.entry_stock.delete(0, 'end')

			self.status_label.configure(text='Producto guardado!', text_color='green')

			self.entry_name.focus()
		else:
			self.status_label.configure(text=f'Error: {message}', text_color='red')

	def refresh_list(self):
		for widget in self.right_panel.winfo_children():
			widget.destroy()

		products = self.controller.get_products(self.current_user.tenant_id)

		for p in products:
			row_frame = ctk.CTkFrame(self.right_panel)
			row_frame.pack(fill='x', pady=5)

			info = f'{p.name} | ${p.price:.2f} | Stock: {p.stock}'

			ctk.CTkLabel(row_frame, text=info, anchor='w').pack(
				side='left', padx=10, pady=5, fill='x', expand=True
			)
