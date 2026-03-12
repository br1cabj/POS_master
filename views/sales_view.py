from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox


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

		# === PANEL IZQUIERDO ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.left_panel, text='Punto de Venta', font=('Arial', 18, 'bold')
		).pack(pady=10)

		ctk.CTkLabel(
			self.left_panel,
			text='Lector de Código de Barras:',
			font=('Arial', 12, 'bold'),
			text_color='#00aaff',
		).pack(pady=(10, 0))
		self.entry_barcode = ctk.CTkEntry(
			self.left_panel, placeholder_text='Escanea o escribe + Enter', width=200
		)
		self.entry_barcode.pack(pady=5)
		self.entry_barcode.bind('<Return>', self.add_by_barcode)

		ctk.CTkLabel(self.left_panel, text='--- O búsqueda manual ---').pack(
			pady=(10, 5)
		)

		self.products_combo = ctk.CTkComboBox(self.left_panel, width=200)
		self.products_combo.set('Seleccionar...')
		self.products_combo.pack(pady=5)

		self.qty_entry = ctk.CTkEntry(
			self.left_panel, placeholder_text='Cantidad', width=100
		)
		self.qty_entry.pack(pady=5)
		self.qty_entry.insert(0, '1')

		self.btn_add = ctk.CTkButton(
			self.left_panel, text='Agregar del Catálogo', command=self.add_to_cart
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
			self.left_panel, placeholder_text='Descripción manual'
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

		self.lbl_msg = ctk.CTkLabel(self.left_panel, text='')
		self.lbl_msg.pack(pady=5)

		# === PANEL DERECHO ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

		client_frame = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		client_frame.pack(pady=5, fill='x', padx=10)
		ctk.CTkLabel(client_frame, text='Cliente:', font=('Arial', 14, 'bold')).pack(
			side='left', padx=5
		)

		self.customers_combo = ctk.CTkComboBox(client_frame, width=250)
		self.customers_combo.pack(side='left', padx=5)

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
		self.tree.pack(fill='both', expand=True, padx=10, pady=5)

		self.btn_remove = ctk.CTkButton(
			self.right_panel,
			text='🗑️ Quitar Artículo Seleccionado',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=self.remove_from_cart,
		)
		self.btn_remove.pack(pady=5)

		self.lbl_total = ctk.CTkLabel(
			self.right_panel, text='TOTAL: $0.00', font=('Arial', 24, 'bold')
		)
		self.lbl_total.pack(pady=10)

		self.btn_pay = ctk.CTkButton(
			self.right_panel,
			text='💰 COBRAR VENTA',
			fg_color='green',
			height=50,
			command=self.process_sale,
		)
		self.btn_pay.pack(pady=10, fill='x', padx=20)

		self.load_data()

	def load_data(self):
		self.db_articles = self.sales_ctrl.get_articles_for_sale(
			self.current_user.tenant_id
		)
		self.article_map = {a.description: a for a in self.db_articles}
		if self.article_map:
			self.products_combo.configure(values=list(self.article_map.keys()))

		customers = self.sales_ctrl.get_customers(self.current_user.tenant_id)
		self.customer_map = {c.name: c for c in customers}
		if self.customer_map:
			self.customers_combo.configure(values=list(self.customer_map.keys()))
			self.customers_combo.set('Consumidor Final')

	def add_by_barcode(self, event=None):
		self.lbl_msg.configure(text='')
		code = self.entry_barcode.get().strip()
		if not code:
			return

		found_article = next((a for a in self.db_articles if a.barcode == code), None)

		if not found_article:
			CTkMessagebox(
				title='Error de Búsqueda',
				message=f'No se encontró ningún artículo con el código:\n{code}',
				icon='cancel',
			)
			self.entry_barcode.delete(0, 'end')
			return

		qty = 1
		if qty > found_article.stock:
			CTkMessagebox(
				title='Stock Insuficiente',
				message=f'No puedes agregar {found_article.description}.\nSolo quedan {found_article.stock} disponibles.',
				icon='warning',
			)
			self.entry_barcode.delete(0, 'end')
			return

		subtotal = found_article.price_1 * qty
		self.cart.append(
			{
				'article_id': found_article.id,
				'desc': found_article.description,
				'price': found_article.price_1,
				'qty': qty,
				'subtotal': subtotal,
			}
		)
		self.tree.insert(
			'',
			'end',
			values=(
				found_article.description,
				qty,
				f'${found_article.price_1:.2f}',
				f'${subtotal:.2f}',
			),
		)

		self.update_total()
		self.entry_barcode.delete(0, 'end')
		self.lbl_msg.configure(
			text=f'Agregado: {found_article.description}', text_color='green'
		)

	def add_to_cart(self):
		self.lbl_msg.configure(text='')
		desc = self.products_combo.get()
		qty_str = self.qty_entry.get()

		if desc in self.article_map and qty_str.isdigit():
			qty = int(qty_str)
			article = self.article_map[desc]
			if qty > article.stock:
				CTkMessagebox(
					title='Stock Insuficiente',
					message=f'Solo quedan {article.stock} unidades de {article.description}.',
					icon='warning',
				)
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
			return
		try:
			price = float(price_str)
			qty = int(qty_str)
		except ValueError:
			CTkMessagebox(
				title='Datos Inválidos',
				message='Asegúrate de ingresar números válidos en Precio y Cantidad.',
				icon='cancel',
			)
			return

		subtotal = price * qty
		visual_desc = f'*(Libre)* {desc}'
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

		self.entry_fast_desc.delete(0, 'end')
		self.entry_fast_price.delete(0, 'end')
		self.entry_fast_qty.delete(0, 'end')
		self.entry_fast_qty.insert(0, '1')

	def remove_from_cart(self):
		self.lbl_msg.configure(text='')
		selected_item = self.tree.selection()

		if not selected_item:
			CTkMessagebox(
				title='Atención',
				message='Primero selecciona un artículo de la tabla para quitarlo.',
				icon='info',
			)
			return

		response = CTkMessagebox(
			title='Confirmar',
			message='¿Estás seguro de quitar este artículo del carrito?',
			icon='question',
			option_1='No',
			option_2='Sí',
		).get()
		if response == 'Sí':
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
		self.lbl_total.configure(text=f'TOTAL: ${total:.2f}')

	# --- POP-UP OPTIMIZADO CON MÉTODOS DE PAGO ---
	def process_sale(self):
		if not self.cart:
			CTkMessagebox(
				title='Carrito Vacío',
				message='Debes agregar productos antes de cobrar.',
				icon='warning',
			)
			return

		total = sum(item['subtotal'] for item in self.cart)
		customer_name = self.customers_combo.get()

		popup = ctk.CTkToplevel(self)
		popup.title('Cobrar Venta')
		popup.geometry('380x500')
		popup.attributes('-topmost', True)
		popup.grab_set()

		ctk.CTkLabel(popup, text='Total a Pagar:', font=('Arial', 18)).pack(
			pady=(20, 5)
		)
		ctk.CTkLabel(
			popup,
			text=f'${total:.2f}',
			font=('Arial', 35, 'bold'),
			text_color='#2A8C55',
		).pack(pady=5)

		# Selector de Método de Pago
		ctk.CTkLabel(popup, text='Método de Pago:', font=('Arial', 14, 'bold')).pack(
			pady=(15, 5)
		)
		self.combo_payment = ctk.CTkComboBox(
			popup,
			values=['Efectivo', 'Tarjeta', 'Transferencia'],
			font=('Arial', 14),
			width=200,
		)
		self.combo_payment.pack(pady=5)

		ctk.CTkLabel(
			popup, text='El cliente abona con (Solo Efectivo):', font=('Arial', 12)
		).pack(pady=(15, 5))
		entry_paid = ctk.CTkEntry(
			popup, font=('Arial', 20), justify='center', width=200
		)
		entry_paid.pack(pady=5)
		entry_paid.focus()

		lbl_change = ctk.CTkLabel(
			popup, text='Vuelto: $0.00', font=('Arial', 24, 'bold'), text_color='blue'
		)
		lbl_change.pack(pady=15)
		lbl_error = ctk.CTkLabel(popup, text='', text_color='red')
		lbl_error.pack()

		def calculate_change(event):
			if self.combo_payment.get() != 'Efectivo':
				lbl_change.configure(text='No aplica vuelto', text_color='gray')
				return

			paid_str = entry_paid.get().strip()
			if not paid_str:
				lbl_change.configure(text='Vuelto: $0.00', text_color='blue')
				return
			try:
				change = float(paid_str) - total
				lbl_change.configure(
					text='Falta dinero' if change < 0 else f'Vuelto: ${change:.2f}',
					text_color='red' if change < 0 else 'blue',
				)
			except ValueError:
				lbl_change.configure(text='Monto inválido', text_color='red')

		entry_paid.bind('<KeyRelease>', calculate_change)

		def confirm_and_save(is_fiado=False):
			payment_method = self.combo_payment.get()

			if not is_fiado and payment_method == 'Efectivo':
				try:
					paid_str = entry_paid.get().strip()
					paid = float(paid_str) if paid_str else total
					if paid < total:
						lbl_error.configure(text='El pago es menor al total')
						return
				except ValueError:
					lbl_error.configure(text='Monto inválido')
					return

			popup.destroy()

			customer_id = None
			if customer_name in self.customer_map:
				customer_id = self.customer_map[customer_name].id

			self.finalize_sale(customer_id, is_fiado, payment_method)

		ctk.CTkButton(
			popup,
			text='✅ CONFIRMAR COBRO',
			fg_color='green',
			hover_color='#216e41',
			height=45,
			font=('Arial', 14, 'bold'),
			command=lambda: confirm_and_save(False),
		).pack(pady=10)

		if customer_name != 'Consumidor Final':
			ctk.CTkLabel(popup, text='--- O ---').pack()
			ctk.CTkButton(
				popup,
				text='📝 Anotar como Fiado',
				fg_color='orange',
				hover_color='#cc7000',
				height=40,
				font=('Arial', 14, 'bold'),
				command=lambda: confirm_and_save(True),
			).pack(pady=5)

	def finalize_sale(self, customer_id, is_fiado, payment_method):
		success, msg = self.sales_ctrl.process_sale(
			self.current_user.tenant_id,
			self.current_user.id,
			self.cart,
			customer_id,
			is_fiado,
			payment_method,
		)

		if success:
			CTkMessagebox(title='¡Éxito!', message=msg, icon='check')
			self.cart.clear()
			for item in self.tree.get_children():
				self.tree.delete(item)
			self.update_total()
			self.load_data()
		else:
			CTkMessagebox(title='Error al guardar', message=msg, icon='cancel')
