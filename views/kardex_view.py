from tkinter import ttk

import customtkinter as ctk


class KardexView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		# Conectamos con el nuevo controlador
		from controllers.inventory_controller import InventoryController

		self.controller = InventoryController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		# --- ENCABEZADO ---
		lbl_title = ctk.CTkLabel(
			self, text='📊 Kardex: Auditoría de Inventario', font=('Arial', 24, 'bold')
		)
		lbl_title.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='w')

		# --- CONTENEDOR DE LA TABLA ---
		self.table_frame = ctk.CTkFrame(self)
		self.table_frame.grid(row=1, column=0, sticky='nsew', padx=20, pady=(0, 20))

		# Configuramos las columnas
		columns = ('Fecha', 'Tipo', 'Producto', 'Cantidad', 'Referencia', 'Usuario')
		self.tree = ttk.Treeview(
			self.table_frame, columns=columns, show='headings', height=20
		)

		for col in columns:
			self.tree.heading(col, text=col)
			# Damos más espacio a la columna del producto y referencia
			if col in ['Producto', 'Referencia']:
				self.tree.column(col, anchor='center', width=200)
			else:
				self.tree.column(col, anchor='center', width=100)

		self.tree.pack(fill='both', expand=True, padx=10, pady=10)

		# Cargamos los datos
		self.load_data()

	def load_data(self):
		"""Busca los movimientos y los inserta en la tabla"""
		# Limpiamos la tabla
		for item in self.tree.get_children():
			self.tree.delete(item)

		# Obtenemos los movimientos desde el controlador
		movements = self.controller.get_kardex(self.current_user.tenant_id)

		for mov in movements:
			# 1. Formateamos la fecha a algo legible
			date_str = mov.date.strftime('%d/%m/%Y %H:%M')

			# 2. Traducimos el tipo de movimiento con colores/emojis
			tipo = '🟢 ENTRADA' if mov.movement_type == 'in' else '🔴 SALIDA'
			if mov.movement_type == 'adjustment':
				tipo = '🟡 AJUSTE'

			# 3. Obtenemos el nombre del producto de forma segura
			producto = (
				mov.variant.article.name
				if (mov.variant and mov.variant.article)
				else 'Desconocido'
			)

			# 4. Obtenemos el usuario
			usuario = mov.user.username.capitalize() if mov.user else 'Sistema'

			# Insertamos la fila en la tabla
			self.tree.insert(
				'',
				'end',
				values=(
					date_str,
					tipo,
					producto,
					mov.quantity,
					mov.reference or '-',
					usuario,
				),
			)
