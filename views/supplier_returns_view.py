from decimal import Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.supplier_returns_controller import REASONS, SupplierReturnsController
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
	TEXT_SECONDARY,
	apply_treeview_style,
)


class SupplierReturnsView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = SupplierReturnsController(ctx.db_engine)
		self._purchases = []
		self._selected_purchase = None
		self._return_cart = []  # [{'detail_id', 'description', 'qty', 'unit_cost', 'subtotal', 'variant_id', 'available'}]

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		apply_treeview_style()
		self._build_left_panel()
		self._build_right_panel()
		self.after(100, self._load_purchases)

	# ── Panel izquierdo: listado de compras ─────────────────────────────────

	def _build_left_panel(self):
		self.left = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.left.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)
		self.left.grid_rowconfigure(2, weight=1)
		self.left.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			self.left,
			text='Compras a Proveedores',
			font=('Arial', 15, 'bold'),
			text_color=TEXT_PRIMARY,
		).grid(row=0, column=0, pady=(18, 6), padx=16, sticky='w')

		self.search_entry = ctk.CTkEntry(
			self.left,
			placeholder_text='Buscar proveedor...',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
		)
		self.search_entry.grid(row=1, column=0, padx=14, pady=(0, 8), sticky='ew')
		self.search_entry.bind('<KeyRelease>', self._on_search)

		tree_frame = ctk.CTkFrame(self.left, fg_color='transparent')
		tree_frame.grid(row=2, column=0, sticky='nsew', padx=8, pady=(0, 8))
		tree_frame.grid_rowconfigure(0, weight=1)
		tree_frame.grid_columnconfigure(0, weight=1)

		scroll_y = ttk.Scrollbar(tree_frame, orient='vertical')
		self.purchases_tree = ttk.Treeview(
			tree_frame,
			columns=('Proveedor', 'Fecha', 'Total', 'Estado'),
			show='headings',
			yscrollcommand=scroll_y.set,
		)
		scroll_y.configure(command=self.purchases_tree.yview)
		scroll_y.pack(side='right', fill='y')
		self.purchases_tree.pack(side='left', fill='both', expand=True)

		self.purchases_tree.heading('Proveedor', text='Proveedor')
		self.purchases_tree.heading('Fecha', text='Fecha')
		self.purchases_tree.heading('Total', text='Total')
		self.purchases_tree.heading('Estado', text='Estado')

		self.purchases_tree.column('Proveedor', width=120, minwidth=90)
		self.purchases_tree.column('Fecha', width=90, minwidth=70)
		self.purchases_tree.column('Total', width=70, minwidth=60)
		self.purchases_tree.column('Estado', width=90, minwidth=70)

		self.purchases_tree.bind('<<TreeviewSelect>>', self._on_purchase_select)

		self.lbl_empty_purchases = ctk.CTkLabel(
			tree_frame,
			text='Sin compras que coincidan con la búsqueda.',
			font=('Arial', 11),
			text_color=TEXT_MUTED,
		)

	def _load_purchases(self):
		self._purchases = self.controller.get_purchases(self.ctx.tenant_id)
		self._populate_purchases_tree(self._purchases)

	def _populate_purchases_tree(self, purchases):
		self.purchases_tree.delete(*self.purchases_tree.get_children())
		for p in purchases:
			date_str = (
				p['date'].strftime('%d/%m/%Y')
				if hasattr(p['date'], 'strftime')
				else str(p['date'])[:10]
			)
			estado = p['status'].replace('_', ' ').capitalize()
			tag = 'devuelta' if 'devuelta' in p['status'] else 'normal'
			self.purchases_tree.insert(
				'',
				'end',
				iid=p['id'],
				values=(
					p['supplier_name'],
					date_str,
					f'${p["total_amount"]:.2f}',
					estado,
				),
				tags=(tag,),
			)
		self.purchases_tree.tag_configure('devuelta', foreground='#f87171')
		self.purchases_tree.tag_configure('normal', foreground=TEXT_PRIMARY)

	def _on_search(self, event=None):
		q = self.search_entry.get().lower().strip()
		if not q:
			self._populate_purchases_tree(self._purchases)
			return
		filtered = [
			p for p in self._purchases
			if q in p['supplier_name'].lower()
			or q in (p.get('invoice_number') or '').lower()
		]
		self._populate_purchases_tree(filtered)
		if not filtered and hasattr(self, 'lbl_empty_purchases'):
			self.lbl_empty_purchases.place(relx=0.5, rely=0.5, anchor='center')
		elif hasattr(self, 'lbl_empty_purchases'):
			self.lbl_empty_purchases.place_forget()

	def _on_purchase_select(self, event=None):
		sel = self.purchases_tree.selection()
		if not sel:
			return
		purchase_id = sel[0]
		purchase = self.controller.get_purchase_with_details(
			self.ctx.tenant_id, purchase_id
		)
		if not purchase:
			return
		self._selected_purchase = purchase
		self._return_cart.clear()
		self._refresh_items_tree()
		self._refresh_cart_tree()
		self._update_purchase_info_label()

	# ── Panel derecho ────────────────────────────────────────────────────────

	def _build_right_panel(self):
		self.right = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.right.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=16)
		self.right.grid_rowconfigure(2, weight=1)
		self.right.grid_rowconfigure(5, weight=1)
		self.right.grid_columnconfigure(0, weight=1)

		# Info de la compra seleccionada
		self.lbl_purchase_info = ctk.CTkLabel(
			self.right,
			text='Seleccioná una compra de la lista',
			font=('Arial', 13, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		)
		self.lbl_purchase_info.grid(row=0, column=0, padx=16, pady=(16, 4), sticky='w')

		ctk.CTkLabel(
			self.right,
			text='ÍTEMS DE LA COMPRA  (seleccioná un ítem para agregar a la devolución)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=1, column=0, padx=16, sticky='w')

		# Tabla de ítems de la compra
		items_frame = ctk.CTkFrame(self.right, fg_color='transparent')
		items_frame.grid(row=2, column=0, sticky='nsew', padx=10, pady=(2, 0))
		items_frame.grid_rowconfigure(0, weight=1)
		items_frame.grid_columnconfigure(0, weight=1)

		scroll_items = ttk.Scrollbar(items_frame, orient='vertical')
		self.items_tree = ttk.Treeview(
			items_frame,
			columns=('Artículo', 'Comprado', 'Ya Dev.', 'Disponible', 'Costo Unit.'),
			show='headings',
			yscrollcommand=scroll_items.set,
			height=6,
		)
		scroll_items.configure(command=self.items_tree.yview)
		scroll_items.pack(side='right', fill='y')
		self.items_tree.pack(side='left', fill='both', expand=True)

		self.items_tree.heading('Artículo', text='Artículo')
		self.items_tree.heading('Comprado', text='Comprado')
		self.items_tree.heading('Ya Dev.', text='Ya Dev.')
		self.items_tree.heading('Disponible', text='Disponible')
		self.items_tree.heading('Costo Unit.', text='Costo Unit.')
		self.items_tree.column('Artículo', width=160, minwidth=100)
		self.items_tree.column('Comprado', width=70, minwidth=50, anchor='center')
		self.items_tree.column('Ya Dev.', width=70, minwidth=50, anchor='center')
		self.items_tree.column('Disponible', width=80, minwidth=50, anchor='center')
		self.items_tree.column('Costo Unit.', width=80, minwidth=60, anchor='e')
		self.items_tree.bind('<<TreeviewSelect>>', self._on_item_select)

		# Fila de cantidad + botón agregar
		add_row = ctk.CTkFrame(self.right, fg_color='transparent')
		add_row.grid(row=3, column=0, padx=10, pady=(4, 2), sticky='ew')
		add_row.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(
			add_row,
			text='Cant. a devolver:',
			font=('Arial', 10),
			text_color=TEXT_SECONDARY,
		).grid(row=0, column=0, padx=(4, 6))
		self.qty_entry = ctk.CTkEntry(
			add_row,
			placeholder_text='0',
			width=80,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=32,
		)
		self.qty_entry.grid(row=0, column=1, sticky='w', padx=(0, 10))
		self.qty_entry.bind('<Return>', lambda e: self._add_item_to_cart())

		ctk.CTkButton(
			add_row,
			text='➕ Agregar a Devolución',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=32,
			corner_radius=8,
			command=self._add_item_to_cart,
		).grid(row=0, column=2, padx=(0, 4))

		# Carrito de devolución
		ctk.CTkLabel(
			self.right,
			text='ÍTEMS A DEVOLVER',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=4, column=0, padx=16, pady=(10, 0), sticky='w')

		cart_frame = ctk.CTkFrame(self.right, fg_color='transparent')
		cart_frame.grid(row=5, column=0, sticky='nsew', padx=10, pady=(2, 0))
		cart_frame.grid_rowconfigure(0, weight=1)
		cart_frame.grid_columnconfigure(0, weight=1)

		scroll_cart = ttk.Scrollbar(cart_frame, orient='vertical')
		self.cart_tree = ttk.Treeview(
			cart_frame,
			columns=('Artículo', 'Cant.', 'Costo Unit.', 'Subtotal'),
			show='headings',
			yscrollcommand=scroll_cart.set,
			height=5,
		)
		scroll_cart.configure(command=self.cart_tree.yview)
		scroll_cart.pack(side='right', fill='y')
		self.cart_tree.pack(side='left', fill='both', expand=True)

		self.lbl_cart_empty = ctk.CTkLabel(
			cart_frame,
			text='Seleccioná ítems de la compra\ny agregalos al carrito.',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
			justify='center',
		)
		self.lbl_cart_empty.place(relx=0.5, rely=0.5, anchor='center')

		self.cart_tree.heading('Artículo', text='Artículo')
		self.cart_tree.heading('Cant.', text='Cant.')
		self.cart_tree.heading('Costo Unit.', text='Costo Unit.')
		self.cart_tree.heading('Subtotal', text='Subtotal')
		self.cart_tree.column('Artículo', width=160, minwidth=100)
		self.cart_tree.column('Cant.', width=60, minwidth=40, anchor='center')
		self.cart_tree.column('Costo Unit.', width=80, minwidth=60, anchor='e')
		self.cart_tree.column('Subtotal', width=80, minwidth=60, anchor='e')

		ctk.CTkButton(
			self.right,
			text='🗑  Quitar ítem',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
			height=30,
			corner_radius=8,
			command=self._remove_from_cart,
		).grid(row=6, column=0, padx=10, pady=(2, 0), sticky='ew')

		# Formulario inferior
		form_frame = ctk.CTkFrame(self.right, fg_color=SURFACE3, corner_radius=8)
		form_frame.grid(row=7, column=0, padx=10, pady=(8, 4), sticky='ew')
		form_frame.grid_columnconfigure(1, weight=1)
		form_frame.grid_columnconfigure(3, weight=1)

		ctk.CTkLabel(
			form_frame,
			text='Motivo:',
			font=('Arial', 10, 'bold'),
			text_color=TEXT_SECONDARY,
		).grid(row=0, column=0, padx=(12, 6), pady=8)
		self.reason_combo = ctk.CTkComboBox(
			form_frame,
			values=REASONS,
			fg_color=SURFACE2,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=32,
			button_color=SURFACE2,
			button_hover_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			dropdown_text_color=TEXT_PRIMARY,
		)
		self.reason_combo.set(REASONS[0])
		self.reason_combo.grid(row=0, column=1, padx=(0, 12), pady=8, sticky='ew')

		ctk.CTkLabel(
			form_frame,
			text='Reembolso:',
			font=('Arial', 10, 'bold'),
			text_color=TEXT_SECONDARY,
		).grid(row=0, column=2, padx=(12, 6))
		self.refund_var = ctk.StringVar(value='efectivo')
		refund_frame = ctk.CTkFrame(form_frame, fg_color='transparent')
		refund_frame.grid(row=0, column=3, padx=(0, 12), sticky='w')
		ctk.CTkRadioButton(
			refund_frame,
			text='Efectivo',
			variable=self.refund_var,
			value='efectivo',
			text_color=TEXT_PRIMARY,
			font=('Arial', 10),
		).pack(side='left', padx=(0, 10))
		ctk.CTkRadioButton(
			refund_frame,
			text='Crédito proveedor',
			variable=self.refund_var,
			value='credito',
			text_color=TEXT_PRIMARY,
			font=('Arial', 10),
		).pack(side='left')

		ctk.CTkLabel(
			form_frame,
			text='Notas:',
			font=('Arial', 10, 'bold'),
			text_color=TEXT_SECONDARY,
		).grid(row=1, column=0, padx=(12, 6), pady=(0, 8))
		self.notes_entry = ctk.CTkEntry(
			form_frame,
			placeholder_text='Opcional...',
			fg_color=SURFACE2,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=30,
		)
		self.notes_entry.grid(
			row=1, column=1, columnspan=3, padx=(0, 12), pady=(0, 8), sticky='ew'
		)

		# Total y botón confirmar
		bottom = ctk.CTkFrame(self.right, fg_color='transparent')
		bottom.grid(row=8, column=0, padx=10, pady=(0, 14), sticky='ew')
		bottom.grid_columnconfigure(0, weight=1)

		self.lbl_total = ctk.CTkLabel(
			bottom,
			text='TOTAL A RECUPERAR: $0.00',
			font=('Arial', 18, 'bold'),
			text_color=ACCENT_TEXT,
		)
		self.lbl_total.grid(row=0, column=0, pady=(4, 6), sticky='e', padx=10)

		self.btn_confirm = ctk.CTkButton(
			bottom,
			text='↩  CONFIRMAR DEVOLUCIÓN A PROVEEDOR',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=48,
			font=('Arial', 13, 'bold'),
			corner_radius=8,
			command=self._confirm_return,
		)
		self.btn_confirm.grid(row=1, column=0, sticky='ew')

	# ── Lógica de la vista ───────────────────────────────────────────────────

	def _update_purchase_info_label(self):
		if not self._selected_purchase:
			self.lbl_purchase_info.configure(
				text='Seleccioná una compra de la lista', text_color=TEXT_MUTED
			)
			return
		p = self._selected_purchase
		date_str = (
			p['date'].strftime('%d/%m/%Y')
			if hasattr(p['date'], 'strftime')
			else str(p['date'])[:10]
		)
		self.lbl_purchase_info.configure(
			text=f'{p["supplier_name"]}  ·  {date_str}  ·  ${p["total_amount"]:.2f}  ·  {p["status"].replace("_", " ").upper()}',
			text_color=TEXT_PRIMARY,
		)

	def _refresh_items_tree(self):
		self.items_tree.delete(*self.items_tree.get_children())
		if not self._selected_purchase:
			return
		for item in self._selected_purchase['items']:
			qty = item['quantity']
			returned = item['already_returned']
			available = item['available']
			qty_str = f'{int(qty)}' if qty % 1 == 0 else f'{qty:.2f}'
			ret_str = f'{int(returned)}' if returned % 1 == 0 else f'{returned:.2f}'
			avail_str = (
				f'{int(available)}' if available % 1 == 0 else f'{available:.2f}'
			)
			tag = 'done' if available <= 0 else 'normal'
			self.items_tree.insert(
				'',
				'end',
				iid=item['detail_id'],
				values=(
					item['description'],
					qty_str,
					ret_str,
					avail_str,
					f'${item["unit_cost"]:.2f}',
				),
				tags=(tag,),
			)
		self.items_tree.tag_configure('done', foreground='#6b7280')
		self.items_tree.tag_configure('normal', foreground=TEXT_PRIMARY)

	def destroy_custom(self):
		self._purchases = []
		self._return_cart = []
		self._selected_purchase = None

	def _refresh_cart_tree(self):
		self.cart_tree.delete(*self.cart_tree.get_children())
		if hasattr(self, 'lbl_cart_empty'):
			if self._return_cart:
				self.lbl_cart_empty.place_forget()
			else:
				self.lbl_cart_empty.place(relx=0.5, rely=0.5, anchor='center')
		total = Decimal('0')
		for i, item in enumerate(self._return_cart):
			qty = item['qty']
			qty_str = f'{int(qty)}' if qty % 1 == 0 else f'{qty:.2f}'
			sub = item['subtotal']
			total += Decimal(str(sub))
			self.cart_tree.insert(
				'',
				'end',
				iid=str(i),
				values=(
					item['description'],
					qty_str,
					f'${item["unit_cost"]:.2f}',
					f'${sub:.2f}',
				),
			)
		self.lbl_total.configure(text=f'TOTAL A RECUPERAR: ${total:.2f}')

	def _on_item_select(self, event=None):
		sel = self.items_tree.selection()
		if not sel:
			return
		detail_id = sel[0]
		if not self._selected_purchase:
			return
		item = next(
			(
				i
				for i in self._selected_purchase['items']
				if i['detail_id'] == detail_id
			),
			None,
		)
		if not item or item['available'] <= 0:
			return
		available = item['available']
		max_str = f'{int(available)}' if available % 1 == 0 else f'{available:.2f}'
		self.qty_entry.delete(0, 'end')
		self.qty_entry.insert(0, '1')
		self.qty_entry.configure(placeholder_text=f'Máx: {max_str}')
		self.qty_entry.focus()

	def _add_item_to_cart(self):
		sel = self.items_tree.selection()
		if not sel:
			CTkMessagebox(
				title='Atención',
				message='Seleccioná un ítem de la compra.',
				icon='info',
			)
			return

		detail_id = sel[0]
		if not self._selected_purchase:
			return

		item = next(
			(
				i
				for i in self._selected_purchase['items']
				if i['detail_id'] == detail_id
			),
			None,
		)
		if not item:
			return
		if item['available'] <= 0:
			CTkMessagebox(
				title='Sin disponible',
				message='Este ítem ya fue devuelto completamente.',
				icon='warning',
			)
			return

		qty_str = self.qty_entry.get().strip().replace(',', '.')
		try:
			qty = Decimal(qty_str)
			if qty <= 0:
				raise ValueError
		except (ValueError, InvalidOperation):
			CTkMessagebox(
				title='Cantidad inválida',
				message='Ingresá una cantidad mayor a cero.',
				icon='cancel',
			)
			return

		# Calcular disponible restando lo ya en el carrito
		in_cart = sum(
			Decimal(str(c['qty']))
			for c in self._return_cart
			if c['detail_id'] == detail_id
		)
		available_now = Decimal(str(item['available'])) - in_cart
		if qty > available_now:
			CTkMessagebox(
				title='Cantidad excesiva',
				message=f'Máximo disponible para devolver: {available_now:.2f}.',
				icon='warning',
			)
			return

		cost = Decimal(str(item['unit_cost']))
		existing = next((c for c in self._return_cart if c['detail_id'] == detail_id), None)
		if existing:
			new_qty = Decimal(str(existing['qty'])) + qty
			existing['qty'] = float(new_qty)
			existing['subtotal'] = float(new_qty * cost)
			self._refresh_cart_tree()
			return
		self._return_cart.append(
			{
				'detail_id': detail_id,
				'description': item['description'],
				'qty': float(qty),
				'unit_cost': float(cost),
				'subtotal': float(qty * cost),
				'variant_id': item['variant_id'],
				'available': item['available'],
			}
		)
		self._refresh_cart_tree()
		self.qty_entry.delete(0, 'end')

	def _remove_from_cart(self):
		sel = self.cart_tree.selection()
		if not sel:
			CTkMessagebox(
				title='Atención', message='Seleccioná un ítem para quitar.', icon='info'
			)
			return
		# Procesar en orden descendente para que los pops no desplacen índices pendientes
		for idx in sorted((int(iid) for iid in sel), reverse=True):
			if 0 <= idx < len(self._return_cart):
				self._return_cart.pop(idx)
		self._refresh_cart_tree()

	def _confirm_return(self):
		if self.btn_confirm.cget('state') == 'disabled':
			return
		if not self._selected_purchase:
			CTkMessagebox(
				title='Sin compra',
				message='Seleccioná una compra primero.',
				icon='warning',
			)
			return
		if not self._return_cart:
			CTkMessagebox(
				title='Sin ítems',
				message='Agregá al menos un ítem a la devolución.',
				icon='warning',
			)
			return

		reason = self.reason_combo.get()
		refund_type = self.refund_var.get()
		notes = self.notes_entry.get().strip()

		total = sum(Decimal(str(i['subtotal'])) for i in self._return_cart)
		refund_label = (
			'efectivo en caja' if refund_type == 'efectivo' else 'crédito al proveedor'
		)

		msg = CTkMessagebox(
			title='Confirmar Devolución',
			message=(
				f'¿Confirmar devolución de {len(self._return_cart)} ítem(s) '
				f'por ${total:.2f} ({refund_label})?\n\nMotivo: {reason}'
			),
			icon='question',
			option_1='No',
			option_2='Sí',
		)
		if msg.get() != 'Sí':
			return

		orig_text = self.btn_confirm.cget('text')
		self.btn_confirm.configure(state='disabled', text='⏳ Procesando...')
		self.update_idletasks()

		items_payload = [
			{
				'detail_id': i['detail_id'],
				'qty_to_return': i['qty'],
				'unit_cost': i['unit_cost'],
				'description': i['description'],
				'variant_id': i['variant_id'],
			}
			for i in self._return_cart
		]

		try:
			success, message = self.controller.process_return(
				tenant_id=self.ctx.tenant_id,
				user_id=self.ctx.user_id,
				purchase_id=self._selected_purchase['id'],
				items_to_return=items_payload,
				reason=reason,
				refund_type=refund_type,
				notes=notes,
			)
			if success:
				self.show_toast(message, 'success', duration=5000)
				self._return_cart.clear()
				self._refresh_cart_tree()
				# Recargar los datos de la compra para reflejar lo ya devuelto
				self._load_purchases()
				updated = self.controller.get_purchase_with_details(
					self.ctx.tenant_id, self._selected_purchase['id']
				)
				if updated:
					self._selected_purchase = updated
				self._refresh_items_tree()
				self._update_purchase_info_label()
				self.notes_entry.delete(0, 'end')
			else:
				self.show_toast(message, 'error', duration=6000)
		finally:
			self.btn_confirm.configure(state='normal', text=orig_text)
