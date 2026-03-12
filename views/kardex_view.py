from tkinter import ttk

import customtkinter as ctk

from controllers.inventory_controller import InventoryController


class KardexView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = InventoryController(db_engine)

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

		# Carga diferida para que la UI se dibuje instantáneamente
		self.after(100, self.load_data)

	def load_data(self):
		"""Busca los movimientos y los inserta en la tabla"""
		# Limpiamos la tabla
		for item in self.tree.get_children():
			self.tree.delete(item)

		# Manejo seguro del usuario
		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

		# Obtenemos los movimientos desde el controlador (ahora es una lista de diccionarios)
		movements = self.controller.get_kardex(tenant_id)

		for mov in movements:
			# 1. Formateamos la fecha de forma segura
			raw_date = mov.get('date')
			date_str = (
				raw_date.strftime('%d/%m/%Y %H:%M')
				if hasattr(raw_date, 'strftime')
				else str(raw_date)
			)

			# 2. Traducimos el tipo de movimiento usando la clave del diccionario
			mov_type = mov.get('movement_type')
			tipo = '🟢 ENTRADA' if mov_type == 'in' else '🔴 SALIDA'
			if mov_type == 'adjustment':
				tipo = '🟡 AJUSTE'

			# 3. La vista queda súper limpia porque el controlador ya hizo el trabajo sucio
			producto = mov.get('article_name', 'Desconocido')
			usuario = mov.get('user_name', 'Sistema').capitalize()
			cantidad = mov.get('quantity', 0)
			referencia = mov.get('reference') or '-'

			# Insertamos la fila en la tabla
			self.tree.insert(
				'',
				'end',
				values=(
					date_str,
					tipo,
					producto,
					cantidad,
					referencia,
					usuario,
				),
			)
