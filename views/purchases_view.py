from decimal import Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.purchases_controller import PurchasesController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	RED,
	RED_DIM,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	apply_treeview_style,
)


class PurchasesView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = PurchasesController(ctx.db_engine)
		self.cart = []

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		apply_treeview_style()

		# ── Panel izquierdo: Formulario de ingreso ───────────────────────
		self.left_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)

		ctk.CTkLabel(
			self.left_panel,
			text='Ingreso de Mercadería',
			font=('Arial', 17, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(22, 16))

		ctk.CTkLabel(
			self.left_panel,
			text='PROVEEDOR',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w')
		self.supplier_combo = ctk.CTkComboBox(
			self.left_panel,
			width=200,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			button_color=SURFACE3,
			button_hover_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			dropdown_text_color=TEXT_PRIMARY,
		)
		self.supplier_combo.pack(pady=(2, 10), padx=20, fill='x')

		ctk.CTkLabel(
			self.left_panel,
			text='ARTÍCULO A REABASTECER',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w')
		self.articles_combo = ctk.CTkComboBox(
			self.left_panel,
			width=200,
			command=self.on_article_select,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			button_color=SURFACE3,
			button_hover_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			dropdown_text_color=TEXT_PRIMARY,
		)
		self.articles_combo.pack(pady=(2, 10), padx=20, fill='x')

		self.cost_entry = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Costo Unitario ($)',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.cost_entry.pack(pady=(0, 8), padx=20, fill='x')

		self.qty_entry = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Cantidad Recibida',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.qty_entry.pack(pady=(0, 16), padx=20, fill='x')

		self.btn_add = ctk.CTkButton(
			self.left_panel,
			text='➕  Agregar a la Factura',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=38,
			corner_radius=8,
			command=self.add_to_cart,
		)
		self.btn_add.pack(pady=(0, 20), padx=20, fill='x')

		# ── Panel derecho: Detalle de la compra ──────────────────────────
		self.right_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=16)

		hdr = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		hdr.pack(fill='x', padx=16, pady=(16, 4))
		ctk.CTkLabel(
			hdr,
			text='Detalle de Factura / Remito',
			font=('Arial', 15, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=14, pady=(0, 8))

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
			text='🗑  Quitar Artículo',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
			height=34,
			corner_radius=8,
			command=self.remove_from_cart,
		)
		self.btn_remove.pack(pady=(4, 0), padx=14, fill='x')

		self.lbl_total = ctk.CTkLabel(
			self.right_panel,
			text='TOTAL A PAGAR: $0.00',
			font=('Arial', 24, 'bold'),
			text_color=RED_TEXT,
		)
		self.lbl_total.pack(pady=(10, 8))

		self.btn_pay = ctk.CTkButton(
			self.right_panel,
			text='📦  CONFIRMAR INGRESO Y PAGAR',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=52,
			font=('Arial', 15, 'bold'),
			corner_radius=8,
			command=self.process_purchase,
		)
		self.btn_pay.pack(pady=(0, 16), padx=14, fill='x')

		self.supplier_map = {}
		self.variant_map = {}
		self.after(100, self.load_combos)

	def load_combos(self):
		tenant_id = self.ctx.tenant_id

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
				message='Seleccioná un producto, costo y cantidad.',
				icon='warning',
			)
			return

		try:
			qty = Decimal(qty_str)
			cost = Decimal(cost_str)
			if qty <= Decimal('0.0') or cost < Decimal('0.0'):
				raise ValueError
		except (ValueError, InvalidOperation):
			CTkMessagebox(
				title='Error de formato',
				message='Costo o cantidad inválidos. Usá números positivos.',
				icon='cancel',
			)
			return

		variant = self.variant_map[desc]
		subtotal = cost * qty
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
		selected_item = self.tree.selection()
		if not selected_item:
			CTkMessagebox(
				title='Atención',
				message='Seleccioná un artículo para quitarlo.',
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
		total = sum(
			(Decimal(str(item.get('subtotal', 0))) for item in self.cart),
			Decimal('0.0'),
		)
		self.lbl_total.configure(text=f'TOTAL A PAGAR: ${total:.2f}')

	def process_purchase(self):
		if not self.cart:
			CTkMessagebox(
				title='Carrito vacío', message='Agregá productos.', icon='warning'
			)
			return

		supplier_name = self.supplier_combo.get()
		if supplier_name not in self.supplier_map:
			CTkMessagebox(
				title='Proveedor inválido',
				message='Seleccioná un proveedor válido.',
				icon='cancel',
			)
			return

		supplier_id = self.supplier_map[supplier_name]['id']

		msg_box = CTkMessagebox(
			title='Confirmar',
			message='¿Deseás confirmar este ingreso de mercadería?',
			icon='question',
			option_1='No',
			option_2='Sí',
		)
		if msg_box.get() != 'Sí':
			return

		tenant_id = self.ctx.tenant_id
		user_id = self.ctx.user_id

		success, msg = self.controller.process_purchase(
			tenant_id, user_id, supplier_id, self.cart
		)

		if success:
			self.show_toast(msg, 'success')
			self.cart = []
			for item in self.tree.get_children():
				self.tree.delete(item)
			self.update_total()
			self.load_combos()
		else:
			self.show_toast(msg, 'error')
