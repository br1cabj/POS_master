from tkinter import ttk

import customtkinter as ctk

from controllers.sales_controller import SalesController


class HistoryView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = SalesController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		# --- ESTILO MODERNO PARA LA TABLA ---
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

		# --- ENCABEZADO ---
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(row=0, column=0, sticky='ew', pady=20, padx=20)

		ctk.CTkLabel(
			header_frame,
			text='📊 Historial de Ventas y Ganancias',
			font=('Arial', 24, 'bold'),
		).pack(side='left')

		ctk.CTkButton(
			header_frame,
			text='🔄 Actualizar',
			command=self.load_history,
			width=120,
			fg_color='#1f538d',
		).pack(side='right')

		# --- CONTENEDOR DE LA TABLA Y SCROLLBAR ---
		# 🛡️ MEJORA: Contenedor dedicado para la tabla
		self.table_container = ctk.CTkFrame(self, fg_color='transparent')
		self.table_container.grid(row=1, column=0, sticky='nsew', padx=20, pady=(0, 20))

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		# --- TABLA DE VENTAS ---
		columns = ('ID', 'Fecha', 'Cliente', 'Vendedor', 'Total', 'Ganancia')
		self.tree = ttk.Treeview(
			self.table_container,
			columns=columns,
			show='headings',
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		for col in columns:
			self.tree.heading(col, text=col)
			width = 150 if col == 'Cliente' else 100
			self.tree.column(col, width=width, anchor='center')

		# Empaquetamos
		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.tree.bind('<Double-1>', self.open_details_popup)

		# Carga diferida
		self.after(100, self.load_history)

	# --- Función DRY ---
	def _get_tenant_id(self):
		return (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

	def load_history(self):
		# Limpiar tabla
		for item in self.tree.get_children():
			self.tree.delete(item)

		tenant_id = self._get_tenant_id()
		sales = self.controller.get_history(tenant_id)

		for sale in sales:
			raw_date = sale.get('date')
			date_str = (
				raw_date.strftime('%Y-%m-%d %H:%M')
				if hasattr(raw_date, 'strftime')
				else str(raw_date)
			)

			# 🛡️ MEJORA: Conversión segura de Decimal a float para el formateo
			total_amount = float(sale.get('total_amount', 0.0))
			profit = float(sale.get('profit', 0.0))

			self.tree.insert(
				'',
				'end',
				values=(
					sale.get('id'),
					date_str,
					sale.get('customer_name', 'Sin Cliente'),
					sale.get('user_name', 'Desconocido'),
					f'${total_amount:.2f}',
					f'${profit:.2f}',
				),
			)

	def open_details_popup(self, event):
		selected_item = self.tree.selection()
		if not selected_item:
			return

		item_data = self.tree.item(selected_item)
		sale_id = item_data['values'][0]
		tenant_id = self._get_tenant_id()

		# 🐛 SOLUCIÓN BUG 1: Pasamos el tenant_id por seguridad
		details = self.controller.get_sale_details(tenant_id, sale_id)

		popup = ctk.CTkToplevel(self)
		popup.title(f'Detalle Venta #{sale_id}')
		popup.geometry('550x350')  # Un poco más ancho
		popup.attributes('-topmost', True)

		ctk.CTkLabel(
			popup, text=f'Artículos de la Venta #{sale_id}', font=('Arial', 16, 'bold')
		).pack(pady=15)

		# CustomTkinter Textbox ya incluye scroll interno, así que aquí estamos a salvo.
		textbox = ctk.CTkTextbox(popup, width=500, height=250, font=('Courier', 12))
		textbox.pack(pady=10, padx=20)

		text_content = ''
		for d in details:
			desc = d.get('description', 'Desconocido')

			# 🛡️ Formateo limpio de cantidades (ej. 1 en vez de 1.00)
			raw_qty = float(d.get('quantity', 0))
			qty = f'{int(raw_qty)}' if raw_qty.is_integer() else f'{raw_qty:.2f}'

			price = float(d.get('unit_price', 0.0))
			subtotal = float(d.get('subtotal', 0.0))

			# Ajustamos un poco el espaciado para que se vea perfectamente alineado
			text_content += f'• {desc[:20]:<20} | x{qty:<5} | ${price:<7.2f} | Sub: ${subtotal:.2f}\n'

		textbox.insert('0.0', text_content)
		textbox.configure(state='disabled')  # Bloqueamos edición
