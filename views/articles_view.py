from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.article_controller import ArticleController


class ArticlesView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = ArticleController(db_engine)

		self.editing_variant_id = None
		self.current_variants = []
		self.suppliers_map = {}

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

		# === PANEL IZQUIERDO: FORMULARIO ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

		self.lbl_form_title = ctk.CTkLabel(
			self.left_panel, text='📦 Carga de Producto', font=('Arial', 18, 'bold')
		)
		self.lbl_form_title.pack(pady=(20, 10))

		ctk.CTkLabel(
			self.left_panel,
			text='[Lector de Códigos Aquí]',
			text_color='gray',
			font=('Arial', 10, 'italic'),
		).pack()

		# 1. CÓDIGO PRIMERO (Flujo Pistola)
		self.entry_barcode = ctk.CTkEntry(
			self.left_panel, placeholder_text='Código de Barras (Enter)'
		)
		self.entry_barcode.pack(pady=5, padx=20, fill='x')
		self.entry_barcode.bind('<Return>', self.on_barcode_scanned)

		self.entry_name = ctk.CTkEntry(
			self.left_panel, placeholder_text='Nombre (Ej: Coca-Cola 2L)'
		)
		self.entry_name.pack(pady=5, padx=20, fill='x')

		# 2. PROVEEDOR
		ctk.CTkLabel(self.left_panel, text='Proveedor Asociado:').pack(pady=(10, 0))
		self.combo_supplier = ctk.CTkComboBox(self.left_panel, values=['Cargando...'])
		self.combo_supplier.pack(pady=5, padx=20, fill='x')

		# 3. PRECIOS Y STOCK
		self.entry_cost = ctk.CTkEntry(
			self.left_panel, placeholder_text='Precio de Costo ($)'
		)
		self.entry_cost.pack(pady=10, padx=20, fill='x')

		self.entry_price = ctk.CTkEntry(
			self.left_panel, placeholder_text='Precio de Venta ($)'
		)
		self.entry_price.pack(pady=10, padx=20, fill='x')

		# 🛡️ El stock solo se puede poner al crearlo. Si se edita, se deshabilita por seguridad contable.
		self.entry_stock = ctk.CTkEntry(
			self.left_panel, placeholder_text='Stock Inicial (Cantidad)'
		)
		self.entry_stock.pack(pady=10, padx=20, fill='x')

		# 4. BOTONES
		self.btn_add = ctk.CTkButton(
			self.left_panel, text='➕ Agregar al Inventario', command=self.save_article
		)
		self.btn_add.pack(pady=15)

		self.btn_cancel = ctk.CTkButton(
			self.left_panel,
			text='🔄 Limpiar Formulario',
			fg_color='#555555',
			command=self.reset_form,
		)
		self.btn_cancel.pack(pady=5)

		# === PANEL DERECHO: CATÁLOGO ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.right_panel, text='Catálogo de Productos', font=('Arial', 18, 'bold')
		).pack(pady=10)
		ctk.CTkLabel(
			self.right_panel,
			text='* Haz doble clic en un producto para editarlo',
			text_color='gray',
			font=('Arial', 12, 'italic'),
		).pack(pady=(0, 10))

		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=20, pady=10)

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		columns = ('ID', 'Código', 'Nombre', 'Proveedor', 'Costo', 'Venta', 'Stock')
		self.tree = ttk.Treeview(
			self.table_container,
			columns=columns,
			show='headings',
			height=15,
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		for col in columns:
			self.tree.heading(col, text=col)
			width = 150 if col == 'Nombre' else 80
			self.tree.column(col, anchor='center', width=width)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.tree.bind('<Double-1>', self.on_tree_double_click)

		self.btn_delete = ctk.CTkButton(
			self.right_panel,
			text='🗑️ Eliminar Seleccionado',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=self.delete_article,
		)
		self.btn_delete.pack(pady=10)

		self.after(100, self.load_data)

		# Foco inicial en la pistola de barras
		self.entry_barcode.focus()

	def _get_tenant_id(self):
		return (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

	def load_data(self):
		tenant_id = self._get_tenant_id()

		# 1. Cargar Proveedores
		suppliers = self.controller.get_suppliers_for_combo(tenant_id)
		self.suppliers_map = {s['name']: s['id'] for s in suppliers}

		if self.suppliers_map:
			combo_vals = ['Sin Proveedor'] + list(self.suppliers_map.keys())
			self.combo_supplier.configure(values=combo_vals)
		else:
			self.combo_supplier.configure(values=['Sin Proveedor'])
		self.combo_supplier.set('Sin Proveedor')

		# 2. Cargar Artículos
		for item in self.tree.get_children():
			self.tree.delete(item)

		self.current_variants = self.controller.get_all_variants(tenant_id)

		for variant in self.current_variants:
			stock_actual = variant.get('total_stock', 0)
			stock_format = (
				f'{int(stock_actual)}'
				if float(stock_actual).is_integer()
				else f'{float(stock_actual):.2f}'
			)

			self.tree.insert(
				'',
				'end',
				values=(
					variant.get('variant_id'),
					variant.get('barcode') or 'N/A',
					variant.get('name'),
					variant.get('supplier_name'),
					f'${variant.get("cost_price", 0):.2f}',
					f'${variant.get("selling_price", 0):.2f}',
					stock_format,
				),
			)

	# --- 🪄 FLUJO Pistola de Barras ---
	def on_barcode_scanned(self, event):
		"""Se activa al escanear un código. Si existe, lo edita. Si no, prepara para crear."""
		barcode = self.entry_barcode.get().strip().lstrip('0') or '0'
		if not barcode:
			return

		found = next(
			(v for v in self.current_variants if str(v.get('barcode')) == barcode), None
		)

		if found:
			self.load_variant_into_form(found)
			self.entry_price.focus()
		else:
			self.reset_form(keep_barcode=True)
			self.entry_name.focus()

	def on_tree_double_click(self, event):
		"""Permite editar al hacer doble clic en la tabla"""
		selected = self.tree.selection()
		if not selected:
			return

		variant_id = self.tree.item(selected[0], 'values')[0]
		found = next(
			(
				v
				for v in self.current_variants
				if str(v.get('variant_id')) == str(variant_id)
			),
			None,
		)
		if found:
			self.load_variant_into_form(found)

	def load_variant_into_form(self, variant):
		"""Prepara el formulario en MODO EDICIÓN"""
		self.reset_form()
		self.editing_variant_id = variant['variant_id']

		self.entry_barcode.insert(0, variant.get('barcode', ''))
		self.entry_name.insert(0, variant.get('name', ''))
		self.entry_cost.insert(0, f'{variant.get("cost_price", 0):.2f}')
		self.entry_price.insert(0, f'{variant.get("selling_price", 0):.2f}')

		supplier_name = variant.get('supplier_name', 'Sin Proveedor')
		self.combo_supplier.set(
			supplier_name if supplier_name in self.suppliers_map else 'Sin Proveedor'
		)

		# Bloqueamos el stock. Regla contable: El stock existente solo se modifica por ventas, compras o Kardex.
		self.entry_stock.insert(0, 'Bloqueado en Edición')
		self.entry_stock.configure(state='disabled')

		# Cambiamos la UI
		self.lbl_form_title.configure(text='✏️ Editando Producto', text_color='#00aaff')
		self.btn_add.configure(text='💾 Actualizar Precios/Datos', fg_color='#0055ff')

	def reset_form(self, keep_barcode=False):
		"""Devuelve el formulario al MODO CREACIÓN"""
		self.editing_variant_id = None

		barcode_temp = self.entry_barcode.get() if keep_barcode else ''
		self.entry_barcode.delete(0, 'end')
		if keep_barcode:
			self.entry_barcode.insert(0, barcode_temp)

		self.entry_name.delete(0, 'end')
		self.entry_cost.delete(0, 'end')
		self.entry_price.delete(0, 'end')

		self.entry_stock.configure(state='normal')
		self.entry_stock.delete(0, 'end')
		self.combo_supplier.set('Sin Proveedor')

		self.lbl_form_title.configure(text='📦 Nuevo Producto', text_color='white')
		self.btn_add.configure(
			text='➕ Agregar al Inventario', fg_color=['#3a7ebf', '#1f538d']
		)
		if not keep_barcode:
			self.entry_barcode.focus()

	# --- GUARDAR / ACTUALIZAR ---
	def save_article(self):
		name = self.entry_name.get().strip()
		barcode = self.entry_barcode.get().strip().lstrip('0') or '0'
		cost_str = self.entry_cost.get().strip().replace(',', '.')
		price_str = self.entry_price.get().strip().replace(',', '.')

		supplier_name = self.combo_supplier.get()
		supplier_id = self.suppliers_map.get(
			supplier_name
		)  # Será None si dice 'Sin Proveedor'

		if not name or not cost_str or not price_str:
			CTkMessagebox(
				title='Faltan Datos',
				message='Nombre, costo y precio son obligatorios.',
				icon='warning',
			)
			return

		try:
			cost = float(cost_str)
			price = float(price_str)

			# Si estamos editando, el stock no importa porque el backend no lo tocará
			initial_stock = 0.0
			if not self.editing_variant_id:
				stock_str = self.entry_stock.get().strip().replace(',', '.')
				initial_stock = float(stock_str) if stock_str else 0.0

		except ValueError:
			CTkMessagebox(
				title='Error',
				message='Precios o stock deben ser números.',
				icon='cancel',
			)
			return

		tenant_id = self._get_tenant_id()

		if self.editing_variant_id:
			success, msg = self.controller.update_article(
				tenant_id,
				self.editing_variant_id,
				name,
				barcode,
				cost,
				price,
				supplier_id,
			)
		else:
			user_id = (
				self.current_user.get('id')
				if isinstance(self.current_user, dict)
				else self.current_user.id
			)
			success, msg = self.controller.add_simple_article(
				tenant_id,
				user_id,
				name,
				barcode,
				cost,
				price,
				initial_stock,
				supplier_id,
			)

		if success:
			CTkMessagebox(title='¡Éxito!', message=msg, icon='check')
			self.reset_form()
			self.load_data()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')

	def delete_article(self):
		selected = self.tree.selection()
		if not selected:
			return

		msg = CTkMessagebox(
			title='Confirmar',
			message='¿Seguro que deseas eliminar este producto?',
			icon='question',
			option_1='No',
			option_2='Sí',
		)
		if msg.get() == 'Sí':
			variant_id = self.tree.item(selected[0], 'values')[0]
			tenant_id = self._get_tenant_id()

			success, msg_response = self.controller.delete_variant(
				tenant_id, variant_id
			)
			if success:
				self.load_data()
				self.reset_form()
				CTkMessagebox(title='Eliminado', message=msg_response, icon='check')
			else:
				CTkMessagebox(title='Error', message=msg_response, icon='cancel')
