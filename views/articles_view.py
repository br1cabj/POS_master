from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox


class ArticlesView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		# Conectamos con el nuevo controlador
		from controllers.article_controller import ArticleController

		self.controller = ArticleController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		# === PANEL IZQUIERDO: NUEVO PRODUCTO ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.left_panel, text='📦 Nuevo Producto', font=('Arial', 18, 'bold')
		).pack(pady=20)

		self.entry_name = ctk.CTkEntry(
			self.left_panel, placeholder_text='Nombre (Ej: Coca-Cola 2L)'
		)
		self.entry_name.pack(pady=10, padx=20, fill='x')

		self.entry_barcode = ctk.CTkEntry(
			self.left_panel, placeholder_text='Código de Barras'
		)
		self.entry_barcode.pack(pady=10, padx=20, fill='x')

		self.entry_cost = ctk.CTkEntry(
			self.left_panel, placeholder_text='Precio de Costo ($)'
		)
		self.entry_cost.pack(pady=10, padx=20, fill='x')

		self.entry_price = ctk.CTkEntry(
			self.left_panel, placeholder_text='Precio de Venta ($)'
		)
		self.entry_price.pack(pady=10, padx=20, fill='x')

		# NUEVO: Campo para el stock inicial
		self.entry_stock = ctk.CTkEntry(
			self.left_panel, placeholder_text='Stock Inicial (Cantidad)'
		)
		self.entry_stock.pack(pady=10, padx=20, fill='x')

		self.btn_add = ctk.CTkButton(
			self.left_panel, text='➕ Agregar al Inventario', command=self.add_article
		)
		self.btn_add.pack(pady=20)

		# === PANEL DERECHO: CATÁLOGO ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.right_panel, text='Catálogo de Productos', font=('Arial', 18, 'bold')
		).pack(pady=10)

		# Tabla (Treeview)
		columns = ('ID Variante', 'Código', 'Nombre', 'Costo', 'Venta', 'Stock Total')
		self.tree = ttk.Treeview(
			self.right_panel, columns=columns, show='headings', height=15
		)

		for col in columns:
			self.tree.heading(col, text=col)
			# Ajustamos el ancho de las columnas
			width = 150 if col == 'Nombre' else 80
			self.tree.column(col, anchor='center', width=width)

		self.tree.pack(fill='both', expand=True, padx=20, pady=10)

		self.btn_delete = ctk.CTkButton(
			self.right_panel,
			text='🗑️ Eliminar Seleccionado',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=self.delete_article,
		)
		self.btn_delete.pack(pady=10)

		# Cargamos los datos al iniciar la pantalla
		self.load_data()

	def load_data(self):
		"""Lee las variantes de la base de datos y las dibuja en la tabla"""
		# Limpiamos la tabla primero
		for item in self.tree.get_children():
			self.tree.delete(item)

		# Traemos todas las variantes activas
		variants = self.controller.get_all_variants(self.current_user.tenant_id)

		for variant in variants:
			total_stock = sum(stock.quantity for stock in variant.stocks)

			self.tree.insert(
				'',
				'end',
				values=(
					variant.id,
					variant.barcode or 'N/A',
					variant.article.name,  # Sacamos el nombre del artículo padre
					f'${variant.cost_price:.2f}',
					f'${variant.selling_price:.2f}',
					total_stock,  # Mostramos el stock unificado
				),
			)

	def add_article(self):
		"""Toma los datos del formulario y los envía al controlador"""
		name = self.entry_name.get().strip()
		barcode = self.entry_barcode.get().strip()
		cost_str = self.entry_cost.get().strip()
		price_str = self.entry_price.get().strip()
		stock_str = self.entry_stock.get().strip()

		# Validación básica
		if not name or not cost_str or not price_str or not stock_str:
			CTkMessagebox(
				title='Faltan Datos',
				message='El nombre, costos, precio y stock son obligatorios.',
				icon='warning',
			)
			return

		try:
			cost = float(cost_str)
			price = float(price_str)
			initial_stock = float(
				stock_str
			)  # Usamos float por si venden a granel (ej: 1.5 kg)
		except ValueError:
			CTkMessagebox(
				title='Error de Formato',
				message='El costo, precio y stock deben ser números.',
				icon='cancel',
			)
			return

		# Llamamos a nuestra nueva súper función
		success, msg = self.controller.add_simple_article(
			tenant_id=self.current_user.tenant_id,
			user_id=self.current_user.id,
			name=name,
			barcode=barcode,
			cost_price=cost,
			selling_price=price,
			initial_stock=initial_stock,
		)

		if success:
			CTkMessagebox(title='¡Éxito!', message=msg, icon='check')
			# Limpiamos el formulario
			self.entry_name.delete(0, 'end')
			self.entry_barcode.delete(0, 'end')
			self.entry_cost.delete(0, 'end')
			self.entry_price.delete(0, 'end')
			self.entry_stock.delete(0, 'end')
			# Recargamos la tabla
			self.load_data()
		else:
			CTkMessagebox(title='Error al guardar', message=msg, icon='cancel')

	def delete_article(self):
		"""Elimina (borrado lógico) la variante seleccionada"""
		selected = self.tree.selection()
		if not selected:
			CTkMessagebox(
				title='Atención',
				message='Selecciona un producto de la tabla.',
				icon='info',
			)
			return

		confirm = CTkMessagebox(
			title='Confirmar',
			message='¿Seguro que deseas eliminar este producto?',
			icon='question',
			option_1='No',
			option_2='Sí',
		).get()
		if confirm == 'Sí':
			values = self.tree.item(selected[0], 'values')
			variant_id = values[0]  # El ID de la Variante está en la primera columna

			success, msg = self.controller.delete_variant(variant_id)
			if success:
				self.load_data()
				CTkMessagebox(title='Eliminado', message=msg, icon='check')
			else:
				CTkMessagebox(title='Error', message=msg, icon='cancel')
