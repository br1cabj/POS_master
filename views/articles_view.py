from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.article_controller import ArticleController


class ArticlesView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		self.controller = ArticleController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		# --- ESTILO PARA EL TREEVIEW ---
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

		# Cargamos los datos con un ligero retraso para que la UI se dibuje rápido
		self.after(100, self.load_data)

	def load_data(self):
		"""Lee las variantes de la base de datos y las dibuja en la tabla"""
		for item in self.tree.get_children():
			self.tree.delete(item)

		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

		# Traemos los diccionarios limpios desde el controlador
		variants = self.controller.get_all_variants(tenant_id)

		for variant in variants:
			# Ahora accedemos a los datos como diccionarios, no como objetos SQL
			self.tree.insert(
				'',
				'end',
				values=(
					variant.get('variant_id'),
					variant.get('barcode') or 'N/A',
					variant.get('name'),
					f'${variant.get("cost_price", 0):.2f}',
					f'${variant.get("selling_price", 0):.2f}',
					variant.get('total_stock', 0),
				),
			)

	def add_article(self):
		"""Toma los datos del formulario y los envía al controlador"""
		name = self.entry_name.get().strip()
		barcode = self.entry_barcode.get().strip()
		cost_str = (
			self.entry_cost.get().strip().replace(',', '.')
		)  # <-- Truco antimolestias
		price_str = self.entry_price.get().strip().replace(',', '.')
		stock_str = self.entry_stock.get().strip().replace(',', '.')

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
			initial_stock = float(stock_str)
		except ValueError:
			CTkMessagebox(
				title='Error de Formato',
				message='El costo, precio y stock deben ser números válidos.',
				icon='cancel',
			)
			return

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

		success, msg = self.controller.add_simple_article(
			tenant_id=tenant_id,
			user_id=user_id,
			name=name,
			barcode=barcode,
			cost_price=cost,
			selling_price=price,
			initial_stock=initial_stock,
		)

		if success:
			CTkMessagebox(title='¡Éxito!', message=msg, icon='check')
			self.entry_name.delete(0, 'end')
			self.entry_barcode.delete(0, 'end')
			self.entry_cost.delete(0, 'end')
			self.entry_price.delete(0, 'end')
			self.entry_stock.delete(0, 'end')
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

		# CTkMessagebox devuelve un objeto, obtenemos el texto de la respuesta con get()
		msg = CTkMessagebox(
			title='Confirmar',
			message='¿Seguro que deseas eliminar este producto?',
			icon='question',
			option_1='No',
			option_2='Sí',
		)

		if msg.get() == 'Sí':
			values = self.tree.item(selected[0], 'values')
			variant_id = values[0]

			success, msg_response = self.controller.delete_variant(variant_id)
			if success:
				self.load_data()
				CTkMessagebox(title='Eliminado', message=msg_response, icon='check')
			else:
				CTkMessagebox(title='Error', message=msg_response, icon='cancel')
