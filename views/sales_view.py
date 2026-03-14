from decimal import Decimal, InvalidOperation
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

		self.grid_columnconfigure(0, weight=1)  # Lector y Manual
		self.grid_columnconfigure(1, weight=2)  # Carrito y Total
		self.grid_columnconfigure(2, weight=1)  # Botonera Touch
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

		# ==========================================
		# PANEL IZQUIERDO: LECTOR Y BÚSQUEDA MANUAL
		# ==========================================
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

		# ==========================================
		# PANEL CENTRAL: CARRITO DE COMPRAS
		# ==========================================
		self.center_panel = ctk.CTkFrame(self)
		self.center_panel.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

		client_frame = ctk.CTkFrame(self.center_panel, fg_color='transparent')
		client_frame.pack(pady=5, fill='x', padx=10)
		ctk.CTkLabel(client_frame, text='Cliente:', font=('Arial', 14, 'bold')).pack(
			side='left', padx=5
		)

		self.customers_combo = ctk.CTkComboBox(client_frame, width=250)
		self.customers_combo.set('Cargando...')
		self.customers_combo.pack(side='left', padx=5)

		self.table_container = ctk.CTkFrame(self.center_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=10, pady=5)

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		self.tree = ttk.Treeview(
			self.table_container,
			columns=('Artículo', 'Cant', 'Precio', 'Subtotal'),
			show='headings',
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		self.tree.heading('Artículo', text='Artículo')
		self.tree.heading('Cant', text='Cant')
		self.tree.heading('Precio', text='Precio')
		self.tree.heading('Subtotal', text='Subtotal')

		self.tree.column('Artículo', width=200)
		self.tree.column('Cant', width=60, anchor='center')
		self.tree.column('Precio', width=100, anchor='e')
		self.tree.column('Subtotal', width=100, anchor='e')

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.btn_remove = ctk.CTkButton(
			self.center_panel,
			text='🗑️ Quitar Artículo Seleccionado',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=self.remove_from_cart,
		)
		self.btn_remove.pack(pady=5)

		self.lbl_total = ctk.CTkLabel(
			self.center_panel,
			text='TOTAL: $0.00',
			font=('Arial', 30, 'bold'),
			text_color='#00cc66',
		)
		self.lbl_total.pack(pady=10)

		self.btn_pay = ctk.CTkButton(
			self.center_panel,
			text='💰 COBRAR VENTA',
			fg_color='#5cb85c',
			hover_color='#4cae4c',
			height=60,
			font=('Arial', 20, 'bold'),
			command=self.process_sale,
		)
		self.btn_pay.pack(pady=10, fill='x', padx=20)

		# ==========================================
		# PANEL DERECHO: BOTONERA TOUCH
		# ==========================================
		self.right_panel = ctk.CTkFrame(self, fg_color='#1a1a1a')
		self.right_panel.grid(row=0, column=2, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.right_panel, text='👆 Accesos Rápidos', font=('Arial', 16, 'bold')
		).pack(pady=10)

		self.touch_scroll = ctk.CTkScrollableFrame(
			self.right_panel, fg_color='transparent'
		)
		self.touch_scroll.pack(fill='both', expand=True, padx=5, pady=5)

		# Mapas de memoria
		self.variant_map = {}
		self.customer_map = {}
		self.db_variants = []
		self.touch_buttons = []

		# Carga fluida de datos
		self.after(50, self.load_data)
		self.setup_shortcuts()

	# --- Funciones Auxiliares DRY ---
	def _get_tenant_id(self):
		return (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

	def _get_user_id(self):
		return (
			self.current_user.get('id')
			if isinstance(self.current_user, dict)
			else self.current_user.id
		)

	def load_data(self):
		tenant_id = self._get_tenant_id()
		self.db_variants = self.sales_ctrl.get_articles_for_sale(tenant_id)

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

		for widget in self.touch_scroll.winfo_children():
			widget.destroy()
		self.touch_buttons.clear()

		row, col = 0, 0
		for v in self.db_variants:
			# Mostramos el botón si es combo o si está marcado para mostrarse
			if v.get('is_combo') or v.get('show_on_touch'):
				stock = Decimal(str(v.get('total_stock', 0)))
				price = Decimal(str(v.get('selling_price', 0)))
				name = v.get('name', 'Promo')
				btn_color = v.get('btn_color', '#1f538d')
				is_disabled = stock <= 0

				btn_text = f'{name}\n${price:.2f}\n(Stock: {stock})'

				btn = ctk.CTkButton(
					self.touch_scroll,
					text=btn_text,
					fg_color='gray' if is_disabled else btn_color,
					state='disabled' if is_disabled else 'normal',
					width=120,
					height=80,
					font=('Arial', 12, 'bold'),
					command=lambda var_id=v.get('variant_id'): self.add_from_touch(
						var_id
					),
				)
				btn.grid(row=row, column=col, padx=5, pady=5)
				self.touch_buttons.append(
					{'variant_id': v.get('variant_id'), 'button': btn}
				)

				col += 1
				if col > 1:  # 2 columnas para la botonera
					col = 0
					row += 1

		self.entry_barcode.focus()

	def _get_qty_in_cart(self, variant_id):
		return sum(
			item.get('qty', 0)
			for item in self.cart
			if item.get('variant_id') == variant_id
		)

	def add_by_barcode(self, event=None):
		self.lbl_msg.configure(text='')

		raw_code = self.entry_barcode.get().strip()
		if not raw_code:
			return

		is_scale_barcode = False
		scale_price = Decimal('0.0')
		search_code = raw_code.lstrip('0') or '0'

		if len(raw_code) == 13 and raw_code.startswith('20'):
			plu_code = str(int(raw_code[2:7]))
			price_str = raw_code[7:12]
			scale_price = Decimal(price_str)
			search_code = plu_code
			is_scale_barcode = True

		found_variant = next(
			(v for v in self.db_variants if str(v.get('barcode')) == search_code), None
		)

		if not found_variant:
			CTkMessagebox(
				title='Error',
				message=f'Código no encontrado:\n{search_code}',
				icon='cancel',
			)
			self.entry_barcode.delete(0, 'end')
			return

		variant_id = found_variant.get('variant_id')
		name = found_variant.get('name', 'Desconocido')
		unit_price = Decimal(str(found_variant.get('selling_price', 0.0)))
		total_stock = Decimal(str(found_variant.get('total_stock', 0)))

		if is_scale_barcode:
			if unit_price == 0:
				CTkMessagebox(
					title='Error',
					message='El producto de balanza tiene precio $0 en la base.',
					icon='cancel',
				)
				return
			qty_to_add = scale_price / unit_price
			subtotal = scale_price
		else:
			qty_to_add = Decimal('1')
			subtotal = unit_price * qty_to_add

		current_cart_qty = Decimal(str(self._get_qty_in_cart(variant_id)))
		if (current_cart_qty + qty_to_add) > total_stock:
			CTkMessagebox(
				title='Stock Insuficiente',
				message=f'Llevas {current_cart_qty:.3f} en el carrito y solo hay {total_stock:.3f} disponibles.',
				icon='warning',
			)
			self.entry_barcode.delete(0, 'end')
			return

		qty_visual = (
			f'{int(qty_to_add)}' if qty_to_add % 1 == 0 else f'{qty_to_add:.3f}'
		)

		item_id = self.tree.insert(
			'',
			'end',
			values=(name, qty_visual, f'${unit_price:.2f}', f'${subtotal:.2f}'),
		)

		self.cart.append(
			{
				'tree_id': item_id,
				'variant_id': variant_id,
				'desc': name,
				'price': float(unit_price),
				'qty': float(qty_to_add),
				'subtotal': float(subtotal),
			}
		)

		self.update_total()
		self.entry_barcode.delete(0, 'end')
		self.lbl_msg.configure(text=f'Agregado: {name}', text_color='#00cc66')

	# 🛡️ NUEVO: Función para agregar desde la botonera
	def add_from_touch(self, variant_id):
		found = next(
			(v for v in self.db_variants if v['variant_id'] == variant_id), None
		)
		if not found:
			return

		qty_to_add = Decimal('1')
		total_stock = Decimal(str(found.get('total_stock', 0)))
		current_cart_qty = Decimal(str(self._get_qty_in_cart(variant_id)))

		if (current_cart_qty + qty_to_add) > total_stock:
			CTkMessagebox(
				title='Sin Stock',
				message='No hay ingredientes/stock suficiente para otra promo.',
				icon='warning',
			)
			return

		price = Decimal(str(found.get('selling_price', 0.0)))
		name = found.get('name')

		item_id = self.tree.insert(
			'', 'end', values=(name, '1', f'${price:.2f}', f'${price:.2f}')
		)

		self.cart.append(
			{
				'tree_id': item_id,
				'variant_id': variant_id,
				'desc': name,
				'price': float(price),
				'qty': 1.0,
				'subtotal': float(price),
			}
		)

		self.update_total()

		# Saltamos al cobro automáticamente para ahorrar clics
		self.process_sale()

	def add_to_cart(self):
		self.lbl_msg.configure(text='')
		desc = self.products_combo.get()
		qty_str = self.qty_entry.get().replace(',', '.')

		try:
			qty_to_add = Decimal(qty_str)
			if qty_to_add <= Decimal('0.0'):
				raise ValueError
		except (ValueError, InvalidOperation):
			CTkMessagebox(title='Error', message='Cantidad inválida.', icon='cancel')
			return

		if desc in self.variant_map:
			variant = self.variant_map[desc]
			variant_id = variant.get('variant_id')
			total_stock = Decimal(str(variant.get('total_stock', 0)))
			price = Decimal(str(variant.get('selling_price', 0.0)))

			current_cart_qty = Decimal(str(self._get_qty_in_cart(variant_id)))
			if (current_cart_qty + qty_to_add) > total_stock:
				CTkMessagebox(
					title='Stock Insuficiente',
					message=f'Llevas {current_cart_qty} en el carrito y solo quedan {total_stock} disponibles.',
					icon='warning',
				)
				return

			subtotal = price * qty_to_add
			qty_visual = (
				f'{int(qty_to_add)}' if qty_to_add % 1 == 0 else f'{qty_to_add:.2f}'
			)

			item_id = self.tree.insert(
				'',
				'end',
				values=(desc, qty_visual, f'${price:.2f}', f'${subtotal:.2f}'),
			)

			self.cart.append(
				{
					'tree_id': item_id,
					'variant_id': variant_id,
					'desc': desc,
					'price': float(price),
					'qty': float(qty_to_add),
					'subtotal': float(subtotal),
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
			price = Decimal(price_str)
			qty = Decimal(qty_str)
			if price < Decimal('0.0') or qty <= Decimal('0.0'):
				raise ValueError
		except (ValueError, InvalidOperation):
			CTkMessagebox(
				title='Datos Inválidos',
				message='Asegúrate de ingresar números válidos.',
				icon='cancel',
			)
			return

		subtotal = price * qty
		visual_desc = f'*(Libre)* {desc}'
		qty_visual = f'{int(qty)}' if qty % 1 == 0 else f'{qty:.2f}'

		item_id = self.tree.insert(
			'',
			'end',
			values=(visual_desc, qty_visual, f'${price:.2f}', f'${subtotal:.2f}'),
		)

		self.cart.append(
			{
				'tree_id': item_id,
				'variant_id': None,
				'desc': visual_desc,
				'price': float(price),
				'qty': float(qty),
				'subtotal': float(subtotal),
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

		if (
			CTkMessagebox(
				title='Confirmar',
				message='¿Estás seguro de quitar este artículo del carrito?',
				icon='question',
				option_1='No',
				option_2='Sí',
			).get()
			== 'Sí'
		):
			for item_id in selected_item:
				for i, item in enumerate(self.cart):
					if item.get('tree_id') == item_id:
						self.cart.pop(i)
						break
				self.tree.delete(item_id)
			self.update_total()

	def update_total(self):
		total = sum(
			(Decimal(str(item.get('subtotal', 0))) for item in self.cart),
			Decimal('0.0'),
		)
		self.lbl_total.configure(text=f'TOTAL: ${total:.2f}')

	# ==========================================
	# LÓGICA DEL POP-UP DE COBRO Y VUELTO
	# ==========================================
	def process_sale(self):
		if not self.cart:
			CTkMessagebox(
				title='Carrito Vacío',
				message='Debes agregar productos antes de cobrar.',
				icon='warning',
			)
			return

		self.current_total = sum(
			(Decimal(str(item.get('subtotal', 0))) for item in self.cart),
			Decimal('0.0'),
		)
		self.customer_name = self.customers_combo.get()

		self.popup = ctk.CTkToplevel(self)
		self.popup.title('Cobrar Venta')
		self.popup.geometry('400x550')  # Hacemos la ventana un poco más alta
		self.popup.attributes('-topmost', True)
		self.popup.grab_set()

		ctk.CTkLabel(self.popup, text='Total a Pagar:', font=('Arial', 18)).pack(
			pady=(20, 5)
		)
		ctk.CTkLabel(
			self.popup,
			text=f'${self.current_total:.2f}',
			font=('Arial', 35, 'bold'),
			text_color='#00cc66',
		).pack(pady=5)

		ctk.CTkLabel(
			self.popup, text='Método de Pago:', font=('Arial', 14, 'bold')
		).pack(pady=(15, 5))
		self.combo_payment = ctk.CTkComboBox(
			self.popup,
			values=['Efectivo', 'Tarjeta', 'Transferencia', 'QR Billetera'],
			font=('Arial', 14),
			width=200,
			command=self._calculate_change,
		)
		self.combo_payment.pack(pady=5)

		ctk.CTkLabel(
			self.popup, text='El cliente abona con (Solo Efectivo):', font=('Arial', 12)
		).pack(pady=(15, 5))
		self.entry_paid = ctk.CTkEntry(
			self.popup, font=('Arial', 20), justify='center', width=200
		)
		self.entry_paid.pack(pady=5)
		self.entry_paid.focus()

		self.lbl_change = ctk.CTkLabel(
			self.popup,
			text='Vuelto: $0.00',
			font=('Arial', 24, 'bold'),
			text_color='#00aaff',
		)
		self.lbl_change.pack(pady=15)
		self.lbl_error_popup = ctk.CTkLabel(self.popup, text='', text_color='#ff3333')
		self.lbl_error_popup.pack()

		self.entry_paid.bind('<KeyRelease>', self._calculate_change)

		# Botones de Cobro
		ctk.CTkButton(
			self.popup,
			text='✅ CONFIRMAR COBRO',
			fg_color='#5cb85c',
			hover_color='#4cae4c',
			height=45,
			font=('Arial', 14, 'bold'),
			command=lambda: self._confirm_and_save(False),
		).pack(pady=(10, 5))

		if self.customer_name != 'Consumidor Final':
			ctk.CTkButton(
				self.popup,
				text='📝 Anotar como Fiado',
				fg_color='#e68a00',
				hover_color='#cc7a00',
				height=40,
				font=('Arial', 14, 'bold'),
				command=lambda: self._confirm_and_save(True),
			).pack(pady=5)

		# 🛡️ NUEVO: Botón de Volver por si toca el botón Touch por error o quiere agregar más
		ctk.CTkButton(
			self.popup,
			text='⬅️ Volver / Agregar más cosas',
			fg_color='#555555',
			hover_color='#333333',
			height=40,
			font=('Arial', 12),
			command=self.popup.destroy,
		).pack(pady=10)

	def _calculate_change(self, event=None):
		if self.combo_payment.get() != 'Efectivo':
			self.lbl_change.configure(text='No aplica vuelto', text_color='gray')
			return

		paid_str = self.entry_paid.get().strip().replace(',', '.')
		if not paid_str:
			self.lbl_change.configure(text='Vuelto: $0.00', text_color='#00aaff')
			return

		try:
			paid = Decimal(paid_str)
			change = paid - self.current_total
			if change < Decimal('0.0'):
				self.lbl_change.configure(text='Falta dinero', text_color='#ff3333')
			else:
				self.lbl_change.configure(
					text=f'Vuelto: ${change:.2f}', text_color='#00aaff'
				)
		except (ValueError, InvalidOperation):
			self.lbl_change.configure(text='Monto inválido', text_color='#ff3333')

	def _confirm_and_save(self, is_fiado=False):
		payment_method = self.combo_payment.get()

		if not is_fiado and payment_method == 'Efectivo':
			try:
				paid_str = self.entry_paid.get().strip().replace(',', '.')
				paid = Decimal(paid_str) if paid_str else self.current_total

				if paid < self.current_total:
					self.lbl_error_popup.configure(text='El pago es menor al total')
					return
			except (ValueError, InvalidOperation):
				self.lbl_error_popup.configure(text='Monto inválido')
				return

		if hasattr(self, 'popup') and self.popup:
			self.popup.destroy()

		customer_id = None
		if self.customer_name in self.customer_map:
			customer_id = self.customer_map[self.customer_name].get('id')

		self.finalize_sale(customer_id, is_fiado, payment_method)

	def finalize_sale(self, customer_id, is_fiado, payment_method):
		tenant_id = self._get_tenant_id()
		user_id = self._get_user_id()

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
			self.load_data()
			self.entry_barcode.focus()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')

	# ==========================================
	# ATAJOS DE TECLADO
	# ==========================================
	def setup_shortcuts(self):
		top = self.winfo_toplevel()
		top.bind('<F5>', lambda e: self.process_sale())
		top.bind('<F6>', lambda e: self.entry_barcode.focus())
		top.bind('<F7>', lambda e: self.entry_fast_desc.focus())
		top.bind('<Delete>', lambda e: self.remove_from_cart())
		top.bind('<Control-Delete>', lambda e: self.clear_entire_cart())

		help_text = '⌨️ Atajos: [F5] Cobrar | [F6] Escanear | [F7] Venta Libre | [Supr] Quitar Item | [Ctrl+Supr] Vaciar Todo'
		ctk.CTkLabel(
			self.left_panel,
			text=help_text,
			text_color='gray',
			font=('Arial', 11, 'italic'),
		).pack(side='bottom', pady=5)

	def clear_entire_cart(self):
		if not self.cart:
			return
		response = CTkMessagebox(
			title='Anular Venta',
			message='¿Estás seguro de vaciar todo el carrito?',
			icon='warning',
			option_1='No',
			option_2='Sí',
		).get()
		if response == 'Sí':
			self.cart.clear()
			for item in self.tree.get_children():
				self.tree.delete(item)
			self.update_total()
			self.lbl_msg.configure(text='Venta anulada.', text_color='#ff3333')
			self.entry_barcode.focus()

	def destroy_custom(self):
		top = self.winfo_toplevel()
		top.unbind('<F5>')
		top.unbind('<F6>')
		top.unbind('<F7>')
		top.unbind('<Delete>')
		top.unbind('<Control-Delete>')
