from tkinter import ttk

import customtkinter as ctk

# Clean Code: Importaciones arriba
from controllers.sales_controller import SalesController


class HistoryView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = SalesController(db_engine)

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
		header_frame.pack(fill='x', pady=20, padx=20)

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

		# --- TABLA DE VENTAS ---
		columns = ('ID', 'Fecha', 'Cliente', 'Vendedor', 'Total', 'Ganancia')
		self.tree = ttk.Treeview(self, columns=columns, show='headings')

		for col in columns:
			self.tree.heading(col, text=col)
			width = 150 if col == 'Cliente' else 100
			self.tree.column(col, width=width, anchor='center')

		self.tree.pack(fill='both', expand=True, padx=20, pady=10)
		self.tree.bind('<Double-1>', self.open_details_popup)

		# Carga diferida para evitar congelamientos al iniciar la app
		self.after(100, self.load_history)

	def load_history(self):
		# Limpiar tabla
		for item in self.tree.get_children():
			self.tree.delete(item)

		# Manejo seguro del usuario (Diccionario u Objeto)
		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

		# Obtenemos la lista de diccionarios desde el controlador
		sales = self.controller.get_history(tenant_id)

		for sale in sales:
			# Manejo seguro de la fecha por si viene como string desde la BD
			raw_date = sale.get('date')
			date_str = (
				raw_date.strftime('%Y-%m-%d %H:%M')
				if hasattr(raw_date, 'strftime')
				else str(raw_date)
			)

			self.tree.insert(
				'',
				'end',
				values=(
					sale.get('id'),
					date_str,
					sale.get('customer_name', 'Sin Cliente'),
					sale.get('user_name', 'Desconocido'),
					f'${sale.get("total_amount", 0.0):.2f}',
					# Ojo: Asegúrate de que tu sales_controller devuelva 'profit' en el diccionario
					f'${sale.get("profit", 0.0):.2f}',
				),
			)

	def open_details_popup(self, event):
		selected_item = self.tree.selection()
		if not selected_item:
			return

		item_data = self.tree.item(selected_item)
		sale_id = item_data['values'][0]

		# Obtenemos el detalle (que ahora es una lista de diccionarios)
		details = self.controller.get_sale_details(sale_id)

		popup = ctk.CTkToplevel(self)
		popup.title(f'Detalle Venta #{sale_id}')
		popup.geometry('500x350')  # Un poco más grande para que quepa bien el texto
		popup.attributes('-topmost', True)

		ctk.CTkLabel(
			popup, text=f'Artículos de la Venta #{sale_id}', font=('Arial', 16, 'bold')
		).pack(pady=15)

		# Usamos una fuente monoespaciada (Courier) para que las columnas del ticket se alineen mejor
		textbox = ctk.CTkTextbox(popup, width=460, height=250, font=('Courier', 12))
		textbox.pack(pady=10, padx=20)

		text_content = ''
		for d in details:
			# Accedemos como diccionario
			desc = d.get('description', 'Desconocido')
			qty = d.get('quantity', 0)
			price = d.get('unit_price', 0.0)
			subtotal = d.get('subtotal', 0.0)

			# Formateamos el texto para que se vea como un mini ticket
			text_content += f'• {desc[:20]:<20} | x{qty:<4} | ${price:<7.2f} | Sub: ${subtotal:.2f}\n'

		textbox.insert('0.0', text_content)
		textbox.configure(state='disabled')  # Bloqueamos edición
