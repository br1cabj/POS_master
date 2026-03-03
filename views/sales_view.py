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
		self.btn_add.pack(pady=10)

		ctk.CTkLabel(self.left_panel, text='------------------------').pack(pady=5)
		ctk.CTkLabel(
			self.left_panel,
			text='Venta Rápida (Sin Stock)',
			font=('Arial', 14, 'bold'),
			text_color='orange',
		).pack(pady=5)

		self.entry_fast_desc = ctk.CTkEntry(
			self.left_panel, placeholder_text='Descripción manual (Ej. Envío)'
		)
		self.entry_fast_desc.pack(pady=5, padx=20, fill='x')

		self.entry_fast_price = ctk.CTkEntry(
			self.left_panel, placeholder_text='Precio ($)'
		)
		self.entry_fast_price.pack(pady=5, padx=20, fill='x')

		self.entry_fast_qty = ctk.CTkEntry(self.left_panel, placeholder_text='Cantidad')
		self.entry_fast_qty.pack(pady=5, padx=20, fill='x')
		self.entry_fast_qty.insert(0, '1')

		self.btn_add_fast = ctk.CTkButton(
			self.left_panel,
			text='⚡ Agregar Venta Rápida',
			fg_color='orange',
			hover_color='#cc7000',
			command=self.add_fast_to_cart,
		)
		self.btn_add_fast.pack(pady=10)

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

	def add_fast_to_cart(self):
		self.lbl_msg.configure(text='')
		desc = self.entry_fast_desc.get().strip()
		price_str = self.entry_fast_price.get().strip()
		qty_str = self.entry_fast_qty.get().strip()

		if not desc or not price_str or not qty_str:
			self.lbl_msg.configure(text='Completa los campos de venta rápida')
			return

		try:
			price = float(price_str)
			qty = int(qty_str)
		except ValueError:
			self.lbl_msg.configure(text='Precio o cantidad inválidos')
			return

		subtotal = price * qty

		# Le ponemos un asterisco visual para saber que es una venta libre
		visual_desc = f'*(Libre)* {desc}'

		# Guardamos en el carrito con article_id = None
		self.cart.append(
			{
				'article_id': None,
				'desc': visual_desc,
				'price': price,
				'qty': qty,
				'subtotal': subtotal,
			}
		)
		self.tree.insert(
			'', 'end', values=(visual_desc, qty, f'${price:.2f}', f'${subtotal:.2f}')
		)
		self.update_total()

		# Limpiar las cajitas para la siguiente venta rápida
		self.entry_fast_desc.delete(0, 'end')
		self.entry_fast_price.delete(0, 'end')
		self.entry_fast_qty.delete(0, 'end')
		self.entry_fast_qty.insert(0, '1')

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
