from tkinter import ttk

import customtkinter as ctk


class SalesView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.sales_controller import SalesController

		self.sales_ctrl = SalesController(db_engine)

		self.cart = []

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		# === PANEL IZQUIERDO: BUSCADOR ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.left_panel, text='Punto de Venta', font=('Arial', 18, 'bold')
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

		self.lbl_msg = ctk.CTkLabel(self.left_panel, text='', text_color='red')
		self.lbl_msg.pack(pady=5)

		self.load_articles_combo()

		# === PANEL DERECHO: CARRITO ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.right_panel, text='Ticket Actual', font=('Arial', 18, 'bold')
		).pack(pady=10)

		style = ttk.Style()
		style.configure('Treeview', font=('Arial', 12), rowheight=25)

		self.tree = ttk.Treeview(
			self.right_panel,
			columns=('Artículo', 'Cant', 'Precio', 'Subtotal'),
			show='headings',
		)
		self.tree.heading('Artículo', text='Artículo')
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
			text='💰 CONFIRMAR VENTA',
			fg_color='green',
			height=50,
			command=self.process_sale,
		)
		self.btn_pay.pack(pady=10, fill='x', padx=20)

	def load_articles_combo(self):
		self.db_articles = self.sales_ctrl.get_articles_for_sale(
			self.current_user.tenant_id
		)
		self.article_map = {a.description: a for a in self.db_articles}
		if self.article_map:
			self.products_combo.configure(values=list(self.article_map.keys()))

	def add_to_cart(self):
		self.lbl_msg.configure(text='')  # Limpiar errores
		desc = self.products_combo.get()
		qty_str = self.qty_entry.get()

		if desc in self.article_map and qty_str.isdigit():
			qty = int(qty_str)
			article = self.article_map[desc]

			if qty > article.stock:
				self.lbl_msg.configure(text=f'Solo quedan {article.stock} en stock')
				return

			subtotal = article.price_1 * qty

			self.cart.append(
				{
					'article_id': article.id,
					'desc': article.description,
					'price': article.price_1,
					'qty': qty,
					'subtotal': subtotal,
				}
			)

			self.tree.insert(
				'',
				'end',
				values=(desc, qty, f'${article.price_1:.2f}', f'${subtotal:.2f}'),
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
			self.lbl_msg.configure(text=msg, text_color='green')
			self.cart = []
			for item in self.tree.get_children():
				self.tree.delete(item)
			self.update_total()
			self.load_articles_combo()
		else:
			self.lbl_msg.configure(text=msg, text_color='red')
