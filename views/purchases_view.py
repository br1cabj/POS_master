from tkinter import ttk

import customtkinter as ctk


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

		# Selector de Artículo
		ctk.CTkLabel(self.left_panel, text='Artículo a reabastecer:').pack(pady=5)
		self.articles_combo = ctk.CTkComboBox(self.left_panel, width=200)
		self.articles_combo.pack(pady=5)

		self.cost_entry = ctk.CTkEntry(
			self.left_panel, placeholder_text='Costo Unitario ($)', width=150
		)
		self.cost_entry.pack(pady=5)

		self.qty_entry = ctk.CTkEntry(
			self.left_panel, placeholder_text='Cantidad Recibida', width=150
		)
		self.qty_entry.pack(pady=5)

		self.btn_add = ctk.CTkButton(
			self.left_panel, text='Agregar a la Factura ->', command=self.add_to_cart
		)
		self.btn_add.pack(pady=20)

		self.lbl_msg = ctk.CTkLabel(self.left_panel, text='', text_color='red')
		self.lbl_msg.pack(pady=5)

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
		"""Carga los proveedores y artículos en las listas desplegables"""
		# Proveedores
		suppliers = self.controller.get_suppliers(self.current_user.tenant_id)
		self.supplier_map = {s.name: s for s in suppliers}
		if self.supplier_map:
			self.supplier_combo.configure(values=list(self.supplier_map.keys()))
			self.supplier_combo.set(list(self.supplier_map.keys())[0])

		# Artículos
		articles = self.controller.get_articles(self.current_user.tenant_id)
		self.article_map = {a.description: a for a in articles}
		if self.article_map:
			self.articles_combo.configure(values=list(self.article_map.keys()))
			self.articles_combo.set('Seleccionar...')

	def add_to_cart(self):
		self.lbl_msg.configure(text='')
		desc = self.articles_combo.get()
		cost_str = self.cost_entry.get()
		qty_str = self.qty_entry.get()

		if desc in self.article_map and cost_str and qty_str.isdigit():
			try:
				qty = int(qty_str)
				cost = float(cost_str)
			except ValueError:
				self.lbl_msg.configure(text='Costo o cantidad inválidos')
				return

			article = self.article_map[desc]
			subtotal = cost * qty

			self.cart.append(
				{
					'article_id': article.id,
					'desc': article.description,
					'cost': cost,
					'qty': qty,
					'subtotal': subtotal,
				}
			)

			self.tree.insert(
				'', 'end', values=(desc, qty, f'${cost:.2f}', f'${subtotal:.2f}')
			)
			self.update_total()

			# Limpiar campos
			self.cost_entry.delete(0, 'end')
			self.qty_entry.delete(0, 'end')

	def update_total(self):
		total = sum(item['subtotal'] for item in self.cart)
		self.lbl_total.configure(text=f'TOTAL A PAGAR: ${total:.2f}')

	def process_purchase(self):
		if not self.cart:
			return

		supplier_name = self.supplier_combo.get()
		if supplier_name not in self.supplier_map:
			self.lbl_msg.configure(text='Selecciona un proveedor válido.')
			return

		supplier_id = self.supplier_map[supplier_name].id

		success, msg = self.controller.process_purchase(
			self.current_user.tenant_id, self.current_user.id, supplier_id, self.cart
		)

		if success:
			self.lbl_msg.configure(text=msg, text_color='green')
			self.cart = []
			for item in self.tree.get_children():
				self.tree.delete(item)
			self.update_total()
			self.load_combos()
		else:
			self.lbl_msg.configure(text=msg, text_color='red')
