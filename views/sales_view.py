from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.sales_controller import SalesController


class SalesView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.sales_ctrl = SalesController(db_engine)
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
		self.products_combo.set('Cargando...')
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
			text_color='#ffaa00',
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
			fg_color='#e68a00',
			hover_color='#cc7a00',
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
		self.customers_combo.set('Cargando...')
		self.customers_combo.pack(side='left', padx=5)

		self.tree = ttk.Treeview(
			self.right_panel,
			columns=('Artículo', 'Cant', 'Precio', 'Subtotal'),
			show='headings',
		)
		self.tree.heading('Artículo', text='Artículo')
		self.tree.heading('Cant', text='Cant')
		self.tree.heading('Precio', text='Precio')
		self.tree.heading('Subtotal', text='Subtotal')

		self.tree.column('Artículo', width=200)
		self.tree.column('Cant', width=60, anchor='center')
		self.tree.column('Precio', width=100, anchor='e')
		self.tree.column('Subtotal', width=100, anchor='e')

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
			self.right_panel,
			text='TOTAL: $0.00',
			font=('Arial', 30, 'bold'),
			text_color='#00cc66',
		)
		self.lbl_total.pack(pady=10)

		self.btn_pay = ctk.CTkButton(
			self.right_panel,
			text='💰 COBRAR VENTA',
			fg_color='#5cb85c',
			hover_color='#4cae4c',
			height=60,
			font=('Arial', 20, 'bold'),
			command=self.process_sale,
		)
		self.btn_pay.pack(pady=10, fill='x', padx=20)

		# Mapas de memoria
		self.variant_map = {}
		self.customer_map = {}
		self.db_variants = []

		# Carga fluida de datos
		self.after(50, self.load_data)

	def load_data(self):
		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

		# 1. Traemos diccionarios desde el backend
		self.db_variants = self.sales_ctrl.get_articles_for_sale(tenant_id)

		# Mapeamos por nombre para el combo
		self.variant_map = {v.get('name'): v for v in self.db_variants if v.get('name')}
		if self.variant_map:
			self.products_combo.configure(values=list(self.variant_map.keys()))
			self.products_combo.set('Seleccionar...')
		else:
			self.products_combo.configure(values=['Sin productos'])
			self.products_combo.set('Sin productos')

		customers = self.sales_ctrl.get_customers(tenant_id)
		self.customer_map = {c.get('name'): c for c in customers}
		if self.customer_map:
			self.customers_combo.configure(values=list(self.customer_map.keys()))
			self.customers_combo.set('Consumidor Final')
		else:
			self.customers_combo.configure(values=['Consumidor Final'])
			self.customers_combo.set('Consumidor Final')

		# Ponemos el foco en el lector de códigos por defecto
		self.entry_barcode.focus()

	def add_by_barcode(self, event=None):
		self.lbl_msg.configure(text='')
		code = self.entry_barcode.get().strip()
		if not code:
			return

		# Buscamos en la lista de diccionarios
		found_variant = next(
			(v for v in self.db_variants if str(v.get('barcode')) == code), None
		)

		if not found_variant:
			CTkMessagebox(
				title='Error', message=f'Código no encontrado:\n{code}', icon='cancel'
			)
			self.entry_barcode.delete(0, 'end')
			return

		qty = 1
		total_stock = found_variant.get('total_stock', 0)
		name = found_variant.get('name', 'Desconocido')
		price = float(found_variant.get('selling_price', 0.0))

		if qty > total_stock:
			CTkMessagebox(
				title='Stock Insuficiente',
				message=f'No puedes agregar {name}.\nSolo quedan {total_stock} disponibles.',
				icon='warning',
			)
			self.entry_barcode.delete(0, 'end')
			return

		subtotal = price * qty

		# Insertamos y guardamos el ID visual (tree_id)
		item_id = self.tree.insert(
			'', 'end', values=(name, qty, f'${price:.2f}', f'${subtotal:.2f}')
		)

		self.cart.append(
			{
				'tree_id': item_id,
				'variant_id': found_variant.get('variant_id'),
				'desc': name,
				'price': price,
				'qty': qty,
				'subtotal': subtotal,
			}
		)

		self.update_total()
		self.entry_barcode.delete(0, 'end')
		self.lbl_msg.configure(text=f'Agregado: {name}', text_color='#00cc66')

	def add_to_cart(self):
		self.lbl_msg.configure(text='')
		desc = self.products_combo.get()
		qty_str = self.qty_entry.get().replace(',', '.')

		try:
			qty = float(qty_str)  # Permitimos float por si es a granel
			if qty <= 0:
				raise ValueError
		except ValueError:
			CTkMessagebox(title='Error', message='Cantidad inválida.', icon='cancel')
			return

		if desc in self.variant_map:
			variant = self.variant_map[desc]
			total_stock = variant.get('total_stock', 0)
			price = float(variant.get('selling_price', 0.0))

			if qty > total_stock:
				CTkMessagebox(
					title='Stock Insuficiente',
					message=f'Solo quedan {total_stock} unidades de {desc}.',
					icon='warning',
				)
				return

			subtotal = price * qty
			item_id = self.tree.insert(
				'', 'end', values=(desc, qty, f'${price:.2f}', f'${subtotal:.2f}')
			)

			self.cart.append(
				{
					'tree_id': item_id,
					'variant_id': variant.get('variant_id'),
					'desc': desc,
					'price': price,
					'qty': qty,
					'subtotal': subtotal,
				}
			)
			self.update_total()
			self.qty_entry.delete(0, 'end')
			self.qty_entry.insert(0, '1')

	def add_fast_to_cart(self):
		self.lbl_msg.configure(text='')
		desc = self.entry_fast_desc.get().strip()
		price_str = self.entry_fast_price.get().strip().replace(',', '.')
		qty_str = self.entry_fast_qty.get().strip().replace(',', '.')

		if not desc or not price_str or not qty_str:
			return

		try:
			price = float(price_str)
			qty = float(qty_str)
		except ValueError:
			CTkMessagebox(
				title='Datos Inválidos',
				message='Asegúrate de ingresar números válidos en Precio y Cantidad.',
				icon='cancel',
			)
			return

		subtotal = price * qty
		visual_desc = f'*(Libre)* {desc}'

		item_id = self.tree.insert(
			'', 'end', values=(visual_desc, qty, f'${price:.2f}', f'${subtotal:.2f}')
		)

		self.cart.append(
			{
				'tree_id': item_id,
				'variant_id': None,
				'desc': visual_desc,
				'price': price,
				'qty': qty,
				'subtotal': subtotal,
			}
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
				message='Primero selecciona un artículo para quitarlo.',
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
				# Borrar usando el tree_id
				for i, item in enumerate(self.cart):
					if item.get('tree_id') == item_id:
						self.cart.pop(i)
						break

				self.tree.delete(item_id)
			self.update_total()

	def update_total(self):
		total = sum(item.get('subtotal', 0) for item in self.cart)
		self.lbl_total.configure(text=f'TOTAL: ${total:.2f}')

	def process_sale(self):
		if not self.cart:
			CTkMessagebox(
				title='Carrito Vacío',
				message='Debes agregar productos antes de cobrar.',
				icon='warning',
			)
			return

		total = sum(item.get('subtotal', 0) for item in self.cart)
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
			text_color='#00cc66',
		).pack(pady=5)

		ctk.CTkLabel(popup, text='Método de Pago:', font=('Arial', 14, 'bold')).pack(
			pady=(15, 5)
		)
		self.combo_payment = ctk.CTkComboBox(
			popup,
			values=['Efectivo', 'Tarjeta', 'Transferencia', 'QR Billetera'],
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
			popup,
			text='Vuelto: $0.00',
			font=('Arial', 24, 'bold'),
			text_color='#00aaff',
		)
		lbl_change.pack(pady=15)
		lbl_error = ctk.CTkLabel(popup, text='', text_color='#ff3333')
		lbl_error.pack()

		def calculate_change(event):
			if self.combo_payment.get() != 'Efectivo':
				lbl_change.configure(text='No aplica vuelto', text_color='gray')
				return

			paid_str = entry_paid.get().strip().replace(',', '.')
			if not paid_str:
				lbl_change.configure(text='Vuelto: $0.00', text_color='#00aaff')
				return
			try:
				change = float(paid_str) - total
				lbl_change.configure(
					text='Falta dinero' if change < 0 else f'Vuelto: ${change:.2f}',
					text_color='#ff3333' if change < 0 else '#00aaff',
				)
			except ValueError:
				lbl_change.configure(text='Monto inválido', text_color='#ff3333')

		entry_paid.bind('<KeyRelease>', calculate_change)
		# Cambio mágico de tipo de pago
		self.combo_payment.configure(command=calculate_change)

		def confirm_and_save(is_fiado=False):
			payment_method = self.combo_payment.get()

			if not is_fiado and payment_method == 'Efectivo':
				try:
					paid_str = entry_paid.get().strip().replace(',', '.')
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
				customer_id = self.customer_map[customer_name].get('id')

			self.finalize_sale(customer_id, is_fiado, payment_method)

		ctk.CTkButton(
			popup,
			text='✅ CONFIRMAR COBRO',
			fg_color='#5cb85c',
			hover_color='#4cae4c',
			height=45,
			font=('Arial', 14, 'bold'),
			command=lambda: confirm_and_save(False),
		).pack(pady=10)

		if customer_name != 'Consumidor Final':
			ctk.CTkLabel(popup, text='--- O ---').pack()
			ctk.CTkButton(
				popup,
				text='📝 Anotar como Fiado',
				fg_color='#e68a00',
				hover_color='#cc7a00',
				height=40,
				font=('Arial', 14, 'bold'),
				command=lambda: confirm_and_save(True),
			).pack(pady=5)

	def finalize_sale(self, customer_id, is_fiado, payment_method):
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

		success, msg = self.sales_ctrl.process_sale(
			tenant_id,
			user_id,
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
			self.load_data()  # Recarga el stock interno
			self.entry_barcode.focus()  # Deja el lector listo para la próxima venta
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')
