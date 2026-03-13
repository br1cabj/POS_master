from tkinter import ttk

import customtkinter as ctk

from controllers.alerts_controller import AlertsController


class AlertsView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
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

		# --- ENCABEZADO Y CONTROLES ---
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='ew')

		ctk.CTkLabel(
			header_frame,
			text='⚠️ Productos con Stock Crítico',
			font=('Arial', 24, 'bold'),
			text_color='#ff8800',
		).pack(side='left')

		# 🛡️ MEJORA: Botón de actualización
		btn_refresh = ctk.CTkButton(
			header_frame, text='🔄 Actualizar', width=100, command=self.load_data
		)
		btn_refresh.pack(side='right', padx=(10, 0))

		self.lbl_count = ctk.CTkLabel(
			header_frame, text='Buscando...', font=('Arial', 14, 'italic')
		)
		self.lbl_count.pack(side='right', padx=10)

		# --- CONTENEDOR DE LA TABLA ---
		self.table_frame = ctk.CTkFrame(self)
		self.table_frame.grid(row=1, column=0, sticky='nsew', padx=20, pady=(0, 20))

		# 🛡️ ESCUDO: Agregamos el Scrollbar
		self.tree_scroll = ttk.Scrollbar(self.table_frame, orient='vertical')

		columns = ('Código', 'Producto', 'Stock Actual', 'Nivel de Alerta')
		self.tree = ttk.Treeview(
			self.table_frame,
			columns=columns,
			show='headings',
			height=20,
			yscrollcommand=self.tree_scroll.set,  # Conectamos la tabla al scroll
		)
		self.tree_scroll.configure(
			command=self.tree.yview
		)  # Conectamos el scroll a la tabla

		for col in columns:
			self.tree.heading(col, text=col)
			width = 250 if col == 'Producto' else 120
			self.tree.column(col, anchor='center', width=width)

		# Empaquetamos el scrollbar a la derecha y la tabla a la izquierda
		self.tree_scroll.pack(side='right', fill='y', pady=10)
		self.tree.pack(side='left', fill='both', expand=True, padx=(10, 0), pady=10)

		# Cargamos los datos al iniciar la pantalla
		self.load_data()

	def load_data(self):
		"""Busca los productos críticos y los muestra en la tabla"""
		# Limpiamos la tabla
		for item in self.tree.get_children():
			self.tree.delete(item)

		# Manejo seguro del usuario (Tenant ID)
		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

		low_stock_items = self.controller.get_low_stock_variants(tenant_id, threshold=5)

		for item in low_stock_items:
			stock_actual = item.get('stock', 0)
			stock_format = (
				f'{int(stock_actual)}'
				if float(stock_actual).is_integer()
				else f'{float(stock_actual):.2f}'
			)

			alerta_nivel = item.get('threshold', 5)

			self.tree.insert(
				'',
				'end',
				values=(
					item.get('barcode', 'Sin código') or 'Sin código',
					item.get('name', 'Desconocido'),
					stock_format,  # Mostramos el stock sin decimales extraños
					f'Menor o igual a {alerta_nivel}',
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
				text_color='#ff3333',
			)
