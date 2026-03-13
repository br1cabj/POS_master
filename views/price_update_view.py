import math
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.article_controller import ArticleController


class PriceUpdateView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = ArticleController(db_engine)

		self.catalog = []  # Catálogo original
		self.simulation_results = []  # Lo que enviaremos a la BD

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=3)
		self.grid_rowconfigure(0, weight=1)

		# --- ESTILO DE TABLA ---
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

		# === PANEL IZQUIERDO: CONTROLES DE INFLACIÓN ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.left_panel, text='📈 Ajuste de Precios', font=('Arial', 18, 'bold')
		).pack(pady=20)

		ctk.CTkLabel(self.left_panel, text='1. Filtrar por Proveedor:').pack(
			pady=(10, 0)
		)
		self.combo_supplier = ctk.CTkComboBox(
			self.left_panel, values=['Todos los proveedores']
		)
		self.combo_supplier.pack(pady=5, padx=20, fill='x')

		ctk.CTkLabel(self.left_panel, text='2. ¿Qué deseas modificar?').pack(
			pady=(15, 0)
		)
		self.combo_target = ctk.CTkComboBox(
			self.left_panel,
			values=['Costo y Venta', 'Solo Precio de Venta', 'Solo Costo'],
		)
		self.combo_target.pack(pady=5, padx=20, fill='x')

		ctk.CTkLabel(self.left_panel, text='3. Porcentaje de Aumento (%):').pack(
			pady=(15, 0)
		)
		self.entry_percent = ctk.CTkEntry(
			self.left_panel, placeholder_text='Ej: 15 (para 15%)'
		)
		self.entry_percent.pack(pady=5, padx=20, fill='x')

		# 🛡️ Función vital para el comercio: Redondeo
		self.check_round_var = ctk.BooleanVar(value=True)
		self.check_round = ctk.CTkCheckBox(
			self.left_panel,
			text='Redondear a números enteros',
			variable=self.check_round_var,
		)
		self.check_round.pack(pady=15, padx=20, anchor='w')

		self.btn_simulate = ctk.CTkButton(
			self.left_panel,
			text='🧮 SIMULAR AUMENTO',
			fg_color='#e68a00',
			hover_color='#cc7a00',
			command=self.simulate_prices,
		)
		self.btn_simulate.pack(pady=20, fill='x', padx=20)

		# === PANEL DERECHO: VISTA PREVIA ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.right_panel,
			text='Vista Previa de los Nuevos Precios',
			font=('Arial', 18, 'bold'),
		).pack(pady=10)
		ctk.CTkLabel(
			self.right_panel,
			text='* Revisa la tabla antes de guardar. Nada se cambiará hasta confirmar.',
			text_color='gray',
			font=('Arial', 12, 'italic'),
		).pack(pady=(0, 10))

		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=20, pady=10)

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		columns = (
			'Producto',
			'Proveedor',
			'Costo Ant.',
			'Costo NUEVO',
			'Venta Ant.',
			'Venta NUEVA',
		)
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
			width = 180 if col == 'Producto' else 90
			self.tree.column(
				col,
				anchor='center' if 'Costo' in col or 'Venta' in col else 'w',
				width=width,
			)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		# 🟢 Pintamos las columnas nuevas para que resalten
		self.tree.tag_configure(
			'simulated', background='#1a331a'
		)  # Un verde oscuro para modo oscuro

		self.btn_save = ctk.CTkButton(
			self.right_panel,
			text='💾 CONFIRMAR Y APLICAR A LA BASE DE DATOS',
			fg_color='#5cb85c',
			hover_color='#4cae4c',
			height=50,
			font=('Arial', 14, 'bold'),
			state='disabled',
			command=self.apply_changes,
		)
		self.btn_save.pack(pady=10, fill='x', padx=40)

		self.suppliers_map = {}
		self.after(100, self.load_data)

	def _get_tenant_id(self):
		return (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

	def load_data(self):
		"""Descarga el catálogo para hacer las matemáticas en la memoria RAM"""
		tenant_id = self._get_tenant_id()
		self.catalog = self.controller.get_all_variants(tenant_id)

		# Llenar Combo de Proveedores
		suppliers = self.controller.get_suppliers_for_combo(tenant_id)
		self.suppliers_map = {s['name']: s['id'] for s in suppliers}

		combo_vals = ['Todos los proveedores'] + list(self.suppliers_map.keys())
		self.combo_supplier.configure(values=combo_vals)

	def simulate_prices(self):
		"""Calcula el aumento y lo dibuja en la tabla sin tocar la BD"""
		percent_str = self.entry_percent.get().strip().replace(',', '.')

		try:
			percent = float(percent_str)
			if percent == 0:
				raise ValueError
		except ValueError:
			CTkMessagebox(
				title='Error',
				message='Ingresa un porcentaje válido (Ej: 15).',
				icon='cancel',
			)
			return

		supplier_filter = self.combo_supplier.get()
		target = self.combo_target.get()
		should_round = self.check_round_var.get()
		multiplier = 1 + (percent / 100)

		# Limpiamos la tabla
		for item in self.tree.get_children():
			self.tree.delete(item)

		self.simulation_results = []

		for item in self.catalog:
			# Filtro por proveedor
			if (
				supplier_filter != 'Todos los proveedores'
				and item.get('supplier_name') != supplier_filter
			):
				continue

			old_cost = float(item.get('cost_price', 0))
			old_selling = float(item.get('selling_price', 0))

			new_cost = old_cost
			new_selling = old_selling

			# Aplicar matemáticas
			if target in ['Costo y Venta', 'Solo Costo']:
				new_cost = old_cost * multiplier
				if should_round:
					new_cost = math.ceil(new_cost)

			if target in ['Costo y Venta', 'Solo Precio de Venta']:
				new_selling = old_selling * multiplier
				if should_round:
					new_selling = math.ceil(new_selling)

			# Guardamos para la BD
			self.simulation_results.append(
				{
					'variant_id': item['variant_id'],
					'new_cost': new_cost,
					'new_selling': new_selling,
				}
			)

			# Dibujamos en la UI
			row_id = self.tree.insert(
				'',
				'end',
				values=(
					item.get('name'),
					item.get('supplier_name', '-'),
					f'${old_cost:.2f}',
					f'${new_cost:.2f}',
					f'${old_selling:.2f}',
					f'${new_selling:.2f}',
				),
			)
			self.tree.item(row_id, tags=('simulated',))

		if self.simulation_results:
			self.btn_save.configure(state='normal')
		else:
			CTkMessagebox(
				title='Sin resultados',
				message='No se encontraron productos para ese proveedor.',
				icon='info',
			)

	def apply_changes(self):
		"""Envía la lista final al controlador para guardar"""
		if not self.simulation_results:
			return

		msg = CTkMessagebox(
			title='¡ATENCIÓN!',
			message=f'Estás a punto de modificar {len(self.simulation_results)} productos de forma permanente.\n¿Deseas continuar?',
			icon='warning',
			option_1='Cancelar',
			option_2='Sí, Guardar Cambios',
		)

		if msg.get() == 'Sí, Guardar Cambios':
			tenant_id = self._get_tenant_id()
			user_id = (
				self.current_user.get('id')
				if isinstance(self.current_user, dict)
				else self.current_user.id
			)
			success, message = self.controller.apply_bulk_price_changes(
				tenant_id, user_id, self.simulation_results
			)

			if success:
				CTkMessagebox(title='Completado', message=message, icon='check')
				self.btn_save.configure(state='disabled')
				for item in self.tree.get_children():
					self.tree.delete(item)
				self.simulation_results = []
				self.entry_percent.delete(0, 'end')
				self.load_data()  # Recargamos el catálogo interno
			else:
				CTkMessagebox(title='Error', message=message, icon='cancel')
