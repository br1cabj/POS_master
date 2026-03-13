from decimal import Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.purchases_controller import PurchasesController


class PurchasesView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = PurchasesController(db_engine)
		self.cart = []

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		# === ESTILO MODERNO PARA LA TABLA ===
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

		# === PANEL IZQUIERDO: FORMULARIO DE INGRESO ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.left_panel, text='Ingreso de Mercadería', font=('Arial', 18, 'bold')
		).pack(pady=10)

		ctk.CTkLabel(self.left_panel, text='Proveedor:').pack(pady=5)
		self.supplier_combo = ctk.CTkComboBox(self.left_panel, width=200)
		self.supplier_combo.pack(pady=5)

		ctk.CTkLabel(self.left_panel, text='Artículo a reabastecer:').pack(pady=5)
		self.articles_combo = ctk.CTkComboBox(
			self.left_panel, width=200, command=self.on_article_select
		)
		self.articles_combo.pack(pady=5)

		self.cost_entry = ctk.CTkEntry(
			self.left_panel, placeholder_text='Costo Unitario ($)', width=150
		)
		self.cost_entry.pack(pady=5)

		self.qty_entry = ctk.CTkEntry(
			self.left_panel, placeholder_text='Cantidad Recibida', width=150
		)
		self.qty_entry.pack(pady=5)

		self.btn_add = ctk.CTkButton(
			self.left_panel, text='Agregar a la Factura ->', command=self.add_to_cart
		)
		self.btn_add.pack(pady=20)

		# === PANEL DERECHO: DETALLE DE LA COMPRA ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

		ctk.CTkLabel(
			self.right_panel,
			text='Detalle de Factura / Remito',
			font=('Arial', 18, 'bold'),
		).pack(pady=10)

		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=10)

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		self.tree = ttk.Treeview(
			self.table_container,
			columns=('Artículo', 'Cant', 'Costo', 'Subtotal'),
			show='headings',
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		self.tree.heading('Artículo', text='Artículo')
		self.tree.heading('Cant', text='Cant')
		self.tree.heading('Costo', text='Costo Unitario')
		self.tree.heading('Subtotal', text='Subtotal')

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.btn_remove = ctk.CTkButton(
			self.right_panel,
			text='🗑️ Quitar Artículo',
			fg_color='#d9534f',
			hover_color='#c9302c',
			command=self.remove_from_cart,
		)
		self.btn_remove.pack(pady=5)

		self.lbl_total = ctk.CTkLabel(
			self.right_panel,
			text='TOTAL A PAGAR: $0.00',
			font=('Arial', 24, 'bold'),
			text_color='#ff3333',
		)
		self.lbl_total.pack(pady=10)

		self.btn_pay = ctk.CTkButton(
			self.right_panel,
			text='📦 CONFIRMAR INGRESO Y PAGAR',
			fg_color='#0055ff',
			height=50,
			command=self.process_purchase,
		)
		self.btn_pay.pack(pady=10, fill='x', padx=20)

		# Diccionarios internos
		self.supplier_map = {}
		self.variant_map = {}

		self.after(100, self.load_combos)

	def _get_tenant_id(self):
		return (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

	def load_combos(self):
		"""Carga los proveedores y artículos (variantes) desde el controlador"""
		tenant_id = self._get_tenant_id()

		suppliers = self.controller.get_suppliers(tenant_id)
		self.supplier_map = {s['name']: s for s in suppliers}

		if self.supplier_map:
			self.supplier_combo.configure(values=list(self.supplier_map.keys()))
			self.supplier_combo.set('Seleccionar Proveedor...')
		else:
			self.supplier_combo.configure(values=['Sin Proveedores'])
			self.supplier_combo.set('No hay proveedores activos')

		variants = self.controller.get_variants(tenant_id)
		self.variant_map = {v['name']: v for v in variants if v.get('name')}

		if self.variant_map:
			self.articles_combo.configure(values=list(self.variant_map.keys()))
			self.articles_combo.set('Seleccionar Artículo...')
		else:
			self.articles_combo.configure(values=['Sin Artículos'])
			self.articles_combo.set('No hay artículos activos')

	def on_article_select(self, selected_name):
		"""Autocompleta el costo cuando el usuario selecciona un producto"""

		if selected_name in self.variant_map:
			variant_dict = self.variant_map[selected_name]

			self.cost_entry.delete(0, 'end')
			cost = float(variant_dict.get('cost_price', 0.0))
			self.cost_entry.insert(0, f'{cost:.2f}')

			self.qty_entry.focus()

	def add_to_cart(self):
		desc = self.articles_combo.get()
		cost_str = self.cost_entry.get().strip().replace(',', '.')
		qty_str = self.qty_entry.get().strip().replace(',', '.')

		if desc not in self.variant_map or not cost_str or not qty_str:
			CTkMessagebox(
				title='Faltan datos',
				message='Selecciona un producto, costo y cantidad.',
				icon='warning',
			)
			return

		# 🐛 SOLUCIÓN BUG 3: Cálculos de UI usando Decimal para no perder centavos
		try:
			qty = Decimal(qty_str)
			cost = Decimal(cost_str)
			if qty <= Decimal('0.0') or cost < Decimal('0.0'):
				raise ValueError
		except (ValueError, InvalidOperation):
			CTkMessagebox(
				title='Error de formato',
				message='Costo o cantidad inválidos. Usa números positivos.',
				icon='cancel',
			)
			return

		variant = self.variant_map[desc]
		subtotal = cost * qty

		# Formateo visual
		qty_visual = f'{int(qty)}' if qty % 1 == 0 else f'{qty:.2f}'

		item_id = self.tree.insert(
			'',
			'end',
			values=(variant['name'], qty_visual, f'${cost:.2f}', f'${subtotal:.2f}'),
		)

		self.cart.append(
			{
				'tree_id': item_id,
				'variant_id': variant['variant_id'],
				'desc': variant['name'],
				# El controlador igual los leerá como strings/floats y los parseará,
				# pero los mandamos como float para compatibilidad con tu parseador actual.
				'cost': float(cost),
				'qty': float(qty),
				'subtotal': float(subtotal),
			}
		)

		self.update_total()

		self.cost_entry.delete(0, 'end')
		self.qty_entry.delete(0, 'end')
		self.articles_combo.set('Seleccionar Artículo...')

	def remove_from_cart(self):
		"""Borra un item seleccionando su ID único de fila en Tkinter"""
		selected_item = self.tree.selection()
		if not selected_item:
			CTkMessagebox(
				title='Atención',
				message='Selecciona un artículo para quitarlo.',
				icon='info',
			)
			return

		for item_id in selected_item:
			for i, item in enumerate(self.cart):
				if item.get('tree_id') == item_id:
					self.cart.pop(i)
					break
			self.tree.delete(item_id)

		self.update_total()

	def update_total(self):
		# 🛡️ Usamos Decimal para la suma visual y que coincida con la DB
		total = sum(
			(Decimal(str(item.get('subtotal', 0))) for item in self.cart),
			Decimal('0.0'),
		)
		self.lbl_total.configure(text=f'TOTAL A PAGAR: ${total:.2f}')

	def process_purchase(self):
		if not self.cart:
			CTkMessagebox(
				title='Carrito vacío', message='Agrega productos.', icon='warning'
			)
			return

		supplier_name = self.supplier_combo.get()
		if supplier_name not in self.supplier_map:
			CTkMessagebox(
				title='Proveedor inválido',
				message='Selecciona un proveedor válido.',
				icon='cancel',
			)
			return

		supplier_id = self.supplier_map[supplier_name]['id']

		msg_box = CTkMessagebox(
			title='Confirmar',
			message='¿Deseas confirmar este ingreso de mercadería?',
			icon='question',
			option_1='No',
			option_2='Sí',
		)

		if msg_box.get() != 'Sí':
			return

		tenant_id = self._get_tenant_id()
		user_id = (
			self.current_user.get('id')
			if isinstance(self.current_user, dict)
			else self.current_user.id
		)

		success, msg = self.controller.process_purchase(
			tenant_id, user_id, supplier_id, self.cart
		)

		if success:
			CTkMessagebox(title='¡Éxito!', message=msg, icon='check')
			self.cart = []
			for item in self.tree.get_children():
				self.tree.delete(item)
			self.update_total()
			self.load_combos()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')
