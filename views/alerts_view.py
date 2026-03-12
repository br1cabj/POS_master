from tkinter import ttk

import customtkinter as ctk

from controllers.alerts_controller import AlertsController


class AlertsView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		# Conectamos con el controlador de alertas
		self.controller = AlertsController(db_engine)

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
		header_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='ew')

		ctk.CTkLabel(
			header_frame,
			text='⚠️ Productos con Stock Crítico',
			font=('Arial', 24, 'bold'),
			text_color='#ff8800',
		).pack(side='left')

		self.lbl_count = ctk.CTkLabel(
			header_frame, text='Buscando...', font=('Arial', 14, 'italic')
		)
		self.lbl_count.pack(side='right', padx=10)

		# --- CONTENEDOR DE LA TABLA ---
		self.table_frame = ctk.CTkFrame(self)
		self.table_frame.grid(row=1, column=0, sticky='nsew', padx=20, pady=(0, 20))

		columns = ('Código', 'Producto', 'Stock Actual', 'Nivel de Alerta')
		self.tree = ttk.Treeview(
			self.table_frame, columns=columns, show='headings', height=20
		)

		for col in columns:
			self.tree.heading(col, text=col)
			width = 250 if col == 'Producto' else 120
			self.tree.column(col, anchor='center', width=width)

		self.tree.pack(fill='both', expand=True, padx=10, pady=10)

		# Cargamos los datos al iniciar la pantalla
		self.load_data()

	def load_data(self):
		"""Busca los productos críticos y los muestra en la tabla"""
		# Limpiamos la tabla
		for item in self.tree.get_children():
			self.tree.delete(item)

		# 2. Manejo seguro del usuario
		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

		low_stock_items = self.controller.get_low_stock_variants(tenant_id, threshold=5)

		for item in low_stock_items:
			self.tree.insert(
				'',
				'end',
				values=(
					item.get('barcode', 'Sin código')
					or 'Sin código',  # Manejo seguro de nulos
					item.get('name', 'Desconocido'),
					item.get('stock', 0),
					f'Menor o igual a {item.get("threshold", 5)}',
				),
			)

		# Actualizamos el contador visual
		cantidad = len(low_stock_items)
		if cantidad == 0:
			self.lbl_count.configure(
				text='¡Todo excelente! No hay alertas.',
				text_color='#00cc66',
			)
		else:
			self.lbl_count.configure(
				text=f'Se encontraron {cantidad} artículos para reponer.',
				text_color='#ff3333',  # Rojo más brillante
			)
