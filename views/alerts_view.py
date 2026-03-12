from tkinter import ttk

import customtkinter as ctk


class AlertsView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		# Conectamos con el controlador de alertas
		from controllers.alerts_controller import AlertsController

		self.controller = AlertsController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		# --- ENCABEZADO ---
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='ew')

		ctk.CTkLabel(
			header_frame,
			text='⚠️ Productos con Stock Crítico',
			font=('Arial', 24, 'bold'),
			text_color='#ff8800',  # Naranja para indicar alerta
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

		# Llamamos al controlador (usamos 5 como cantidad mínima por defecto)
		low_stock_items = self.controller.get_low_stock_variants(
			self.current_user.tenant_id, threshold=5
		)

		for item in low_stock_items:
			# Insertamos la fila
			self.tree.insert(
				'',
				'end',
				values=(
					item['barcode'] or 'Sin código',
					item['name'],
					item['stock'],
					f'Menor o igual a {item["threshold"]}',
				),
			)

		# Actualizamos el contador visual
		cantidad = len(low_stock_items)
		if cantidad == 0:
			self.lbl_count.configure(
				text='¡Todo excelente! No hay alertas.', text_color='green'
			)
		else:
			self.lbl_count.configure(
				text=f'Se encontraron {cantidad} artículos para reponer.',
				text_color='red',
			)
