"""
views/returns_view.py
=====================
Módulo de Devoluciones y Anulaciones de Tickets.

Layout: dos paneles
  - Izquierdo: lista de tickets con búsqueda y filtros rápidos
  - Derecho:   detalle del ticket seleccionado + botones de acción

Acciones disponibles:
  🚫 Anular Ticket    → cancel_sale() — anula todo, restaura stock y caja
  ↩  Devolver Ítems   → popup parcial — elige qué ítems y cuántos devolver
  ✏️ Modificar        → anula + navega a Ventas para rehacer el ticket
"""

import logging
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.returns_controller import ReturnsController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	RED,
	RED_DIM,
	RED_TEXT,
	SURFACE1,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	apply_treeview_style,
)

logger = logging.getLogger(__name__)

# Colores de estado
_STATUS_COLORS = {
	'completada': GREEN_TEXT,
	'pendiente': ORANGE_TEXT,
	'fiado': ORANGE_TEXT,
	'parcial': ORANGE_TEXT,
	'devuelta': TEXT_MUTED,
	'anulada': RED_TEXT,
}

_STATUS_LABELS = {
	'completada': '✓ Completada',
	'pendiente': '⏳ Pendiente',
	'parcial': '↩ Parcial',
	'devuelta': '↩ Devuelta',
	'anulada': '🚫 Anulada',
}


class ReturnsView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = ReturnsController(ctx.db_engine)

		self._all_sales = []
		self._active_filter = 'all'
		self._selected_sale = None  # dict completo del ticket seleccionado

		self.grid_columnconfigure(0, weight=2)
		self.grid_columnconfigure(1, weight=3)
		self.grid_rowconfigure(0, weight=1)

		apply_treeview_style()

		self._build_left_panel()
		self._build_right_panel()

		self.after(100, self.load_sales)

	# =========================================================
	# PANEL IZQUIERDO — Lista de Tickets
	# =========================================================
	def _build_left_panel(self):
		self.left = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.left.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)
		self.left.grid_rowconfigure(3, weight=1)
		self.left.grid_columnconfigure(0, weight=1)

		# ── Header ───────────────────────────────────────────────
		hdr = ctk.CTkFrame(self.left, fg_color='transparent')
		hdr.grid(row=0, column=0, sticky='ew', padx=16, pady=(16, 4))

		ctk.CTkLabel(
			hdr,
			text='↩  Tickets Emitidos',
			font=('Arial', 16, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		ctk.CTkButton(
			hdr,
			text='↻',
			width=32,
			height=28,
			corner_radius=6,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			font=('Arial', 14, 'bold'),
			command=self.load_sales,
		).pack(side='right')

		# ── Búsqueda ─────────────────────────────────────────────
		self._search_var = ctk.StringVar()
		self._search_var.trace_add('write', self._filter_tree)
		ctk.CTkEntry(
			self.left,
			textvariable=self._search_var,
			placeholder_text='🔍 Buscar por ID, cliente o fecha...',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
		).grid(row=1, column=0, sticky='ew', padx=14, pady=(4, 4))

		# ── Filtros rápidos ───────────────────────────────────────
		filter_frame = ctk.CTkFrame(self.left, fg_color='transparent')
		filter_frame.grid(row=2, column=0, sticky='ew', padx=14, pady=(0, 6))

		self._filter_btns = {}
		_filters = [
			('all', 'Todos'),
			('today', 'Hoy'),
			('fiado', 'Fiados'),
			('anuladas', 'Anuladas'),
		]
		for fkey, flabel in _filters:
			is_active = fkey == 'all'
			btn = ctk.CTkButton(
				filter_frame,
				text=flabel,
				height=26,
				corner_radius=5,
				font=('Arial', 10, 'bold') if is_active else ('Arial', 10),
				fg_color=ACCENT_DIM if is_active else SURFACE3,
				hover_color=ACCENT if is_active else SURFACE4,
				text_color=ACCENT_TEXT if is_active else TEXT_SECONDARY,
				border_width=1,
				border_color=ACCENT if is_active else BORDER,
				command=lambda k=fkey: self._apply_filter(k),
			)
			btn.pack(side='left', padx=(0, 4))
			self._filter_btns[fkey] = btn

		# ── Tabla de tickets ──────────────────────────────────────
		tree_frame = ctk.CTkFrame(self.left, fg_color='transparent')
		tree_frame.grid(row=3, column=0, sticky='nsew', padx=14, pady=(0, 14))

		scroll = ttk.Scrollbar(tree_frame, orient='vertical')
		cols = ('ID', 'Fecha', 'Cliente', 'Total', 'Estado')
		self.tree = ttk.Treeview(
			tree_frame,
			columns=cols,
			show='headings',
			yscrollcommand=scroll.set,
		)
		scroll.configure(command=self.tree.yview)

		_widths = {'ID': 45, 'Fecha': 120, 'Cliente': 120, 'Total': 75, 'Estado': 90}
		for col in cols:
			self.tree.heading(col, text=col)
			self.tree.column(col, width=_widths[col], anchor='center')

		self.tree.tag_configure('completada', foreground=GREEN_TEXT)
		self.tree.tag_configure('pendiente', foreground=ORANGE_TEXT)
		self.tree.tag_configure('parcial', foreground=ORANGE_TEXT)
		self.tree.tag_configure('devuelta', foreground=TEXT_MUTED)
		self.tree.tag_configure('anulada', foreground=RED_TEXT)
		self.tree.tag_configure('fiado', foreground=ORANGE_TEXT)
		self.tree.tag_configure('odd', background='#161616')
		self.tree.tag_configure('even', background='#1a1a1a')

		scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)
		self.tree.bind('<<TreeviewSelect>>', self._on_sale_selected)
		self.tree.bind('<Double-1>', self._on_sale_selected)

	# =========================================================
	# PANEL DERECHO — Detalle del Ticket
	# =========================================================
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
		self.right.grid_columnconfigure(0, weight=1)

		# ── Header del detalle ─────────────────────────────────────
		self.lbl_ticket_title = ctk.CTkLabel(
			self.right,
			text='Seleccioná un ticket de la lista',
			font=('Arial', 17, 'bold'),
			text_color=TEXT_MUTED,
		)
		self.lbl_ticket_title.grid(row=0, column=0, sticky='w', padx=20, pady=(18, 4))

		# ── Info del ticket (labels) ───────────────────────────────
		info_frame = ctk.CTkFrame(self.right, fg_color=SURFACE3, corner_radius=8)
		info_frame.grid(row=1, column=0, sticky='ew', padx=16, pady=(0, 10))
		info_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

		self.lbl_date = self._info_cell(info_frame, '—', 'Fecha', 0)
		self.lbl_client = self._info_cell(info_frame, '—', 'Cliente', 1)
		self.lbl_method = self._info_cell(info_frame, '—', 'Pago', 2)
		self.lbl_status = self._info_cell(info_frame, '—', 'Estado', 3)

		# ── Tabla de ítems ─────────────────────────────────────────
		items_container = ctk.CTkFrame(self.right, fg_color='transparent')
		items_container.grid(row=2, column=0, sticky='nsew', padx=16, pady=(0, 8))

		ctk.CTkLabel(
			items_container,
			text='ÍTEMS DEL TICKET',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', pady=(0, 4))

		inner = ctk.CTkFrame(items_container, fg_color='transparent')
		inner.pack(fill='both', expand=True)

		items_scroll = ttk.Scrollbar(inner, orient='vertical')
		icols = ('Producto', 'Cantidad', 'P. Unit.', 'Subtotal')
		self.items_tree = ttk.Treeview(
			inner,
			columns=icols,
			show='headings',
			yscrollcommand=items_scroll.set,
		)
		items_scroll.configure(command=self.items_tree.yview)

		_iwidths = {'Producto': 200, 'Cantidad': 80, 'P. Unit.': 90, 'Subtotal': 90}
		for col in icols:
			self.items_tree.heading(col, text=col)
			self.items_tree.column(col, width=_iwidths[col], anchor='center')
		self.items_tree.column('Producto', anchor='w')

		self.items_tree.tag_configure('odd', background='#161616')
		self.items_tree.tag_configure('even', background='#1a1a1a')

		items_scroll.pack(side='right', fill='y')
		self.items_tree.pack(side='left', fill='both', expand=True)

		# ── Total y botones ────────────────────────────────────────
		bottom = ctk.CTkFrame(self.right, fg_color='transparent')
		bottom.grid(row=3, column=0, sticky='ew', padx=16, pady=(0, 16))
		bottom.grid_columnconfigure(0, weight=1)

		self.lbl_discount_info = ctk.CTkLabel(
			bottom,
			text='',
			font=('Arial', 11),
			text_color=ORANGE_TEXT,
			anchor='e',
		)
		self.lbl_discount_info.grid(
			row=0, column=0, columnspan=3, sticky='e', pady=(0, 2)
		)

		self.lbl_total = ctk.CTkLabel(
			bottom,
			text='Total: —',
			font=('Arial', 18, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='e',
		)
		self.lbl_total.grid(row=1, column=0, columnspan=3, sticky='e', pady=(0, 10))

		self.btn_cancel_sale = ctk.CTkButton(
			bottom,
			text='🚫  Anular Ticket Completo',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
			height=40,
			corner_radius=8,
			font=('Arial', 12, 'bold'),
			state='disabled',
			command=self._confirm_cancel,
		)
		self.btn_cancel_sale.grid(row=2, column=0, sticky='ew', pady=(0, 6))

		self.btn_return_items = ctk.CTkButton(
			bottom,
			text='↩  Devolver Ítems (Parcial)',
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			height=40,
			corner_radius=8,
			font=('Arial', 12, 'bold'),
			state='disabled',
			command=self._open_return_popup,
		)
		self.btn_return_items.grid(row=3, column=0, sticky='ew', pady=(0, 6))

		self.btn_modify = ctk.CTkButton(
			bottom,
			text='✏️  Modificar → Ir a Ventas',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=40,
			corner_radius=8,
			font=('Arial', 12, 'bold'),
			state='disabled',
			command=self._confirm_modify,
		)
		self.btn_modify.grid(row=4, column=0, sticky='ew')

	def _info_cell(self, parent, value, label, col):
		frame = ctk.CTkFrame(parent, fg_color='transparent')
		frame.grid(row=0, column=col, padx=10, pady=8, sticky='ew')
		ctk.CTkLabel(
			frame,
			text=label.upper(),
			font=('Arial', 8, 'bold'),
			text_color=TEXT_MUTED,
			anchor='center',
		).pack()
		lbl = ctk.CTkLabel(
			frame,
			text=value,
			font=('Arial', 13, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='center',
		)
		lbl.pack()
		return lbl

	# =========================================================
	# CARGA Y FILTRADO
	# =========================================================
	def load_sales(self):
		self._all_sales = self.controller.get_sales_for_returns(
			self.ctx.tenant_id, filter_key=self._active_filter
		)
		self._filter_tree()

	def _apply_filter(self, key):
		self._active_filter = key
		for k, btn in self._filter_btns.items():
			active = k == key
			btn.configure(
				fg_color=ACCENT_DIM if active else SURFACE3,
				hover_color=ACCENT if active else SURFACE4,
				text_color=ACCENT_TEXT if active else TEXT_SECONDARY,
				border_color=ACCENT if active else BORDER,
				font=('Arial', 10, 'bold') if active else ('Arial', 10),
			)
		self.load_sales()

	def _filter_tree(self, *args):
		q = self._search_var.get().lower().strip()
		matches = [
			s
			for s in self._all_sales
			if not q
			or q in str(s.get('id', '')).lower()
			or q in (s.get('customer_name') or '').lower()
			or q in str(s.get('date') or '').lower()
		]

		for iid in self.tree.get_children():
			self.tree.delete(iid)

		for i, sale in enumerate(matches):
			raw = sale.get('date')
			date_str = (
				raw.strftime('%d/%m %H:%M')
				if hasattr(raw, 'strftime')
				else str(raw)[:13]
			)
			pm = sale.get('payment_method', '')
			status = sale.get('status', 'completada')
			tag = 'fiado' if pm == 'fiado' else status
			alt = 'odd' if i % 2 == 0 else 'even'
			self.tree.insert(
				'',
				'end',
				iid=str(sale['id']),
				values=(
					sale['id'],
					date_str,
					(sale.get('customer_name') or 'S/N')[:16],
					f'${sale["total_amount"]:.0f}',
					_STATUS_LABELS.get(status, status),
				),
				tags=(tag, alt),
			)

	# =========================================================
	# SELECCIÓN DE TICKET
	# =========================================================
	def _on_sale_selected(self, event=None):
		sel = self.tree.selection()
		if not sel:
			return
		sale_id = int(sel[0])
		sale = self.controller.get_sale_with_details(self.ctx.tenant_id, sale_id)
		if not sale:
			return
		self._selected_sale = sale
		self._refresh_detail_panel(sale)

	def _refresh_detail_panel(self, sale):
		status = sale.get('status', 'completada')
		pm = sale.get('payment_method', '')
		operable = status in ('completada', 'pendiente')

		# Header
		self.lbl_ticket_title.configure(
			text=f'Ticket  #{sale["id"]}',
			text_color=_STATUS_COLORS.get(status, TEXT_PRIMARY),
		)

		# Info cells
		raw = sale.get('date')
		date_str = (
			raw.strftime('%d/%m/%Y  %H:%M') if hasattr(raw, 'strftime') else str(raw)
		)
		self.lbl_date.configure(text=date_str)
		self.lbl_client.configure(
			text=(sale.get('customer_name') or 'Consumidor Final')[:18]
		)
		self.lbl_method.configure(
			text=pm.capitalize() if pm else '—',
			text_color=ORANGE_TEXT if pm == 'fiado' else TEXT_PRIMARY,
		)
		self.lbl_status.configure(
			text=_STATUS_LABELS.get(status, status),
			text_color=_STATUS_COLORS.get(status, TEXT_PRIMARY),
		)

		# Ítems
		for iid in self.items_tree.get_children():
			self.items_tree.delete(iid)

		for i, item in enumerate(sale.get('items', [])):
			qty = item['quantity']
			qty_str = f'{int(qty)}' if float(qty).is_integer() else f'{qty:.3f}'
			alt = 'odd' if i % 2 == 0 else 'even'
			self.items_tree.insert(
				'',
				'end',
				values=(
					item['description'][:30],
					qty_str,
					f'${item["unit_price"]:.2f}',
					f'${item["subtotal"]:.2f}',
				),
				tags=(alt,),
			)

		# Total — con desglose de descuento si corresponde
		total = sale['total_amount']
		discount = sale.get('discount_amount', 0.0)
		if discount > 0:
			subtotal_orig = total + discount
			self.lbl_discount_info.configure(
				text=f'Subtotal ${subtotal_orig:.2f}  ·  Descuento -${discount:.2f}'
			)
		else:
			self.lbl_discount_info.configure(text='')
		self.lbl_total.configure(text=f'Total cobrado:  ${total:.2f}')

		# Botones
		state = 'normal' if operable else 'disabled'
		self.btn_cancel_sale.configure(state=state)
		self.btn_return_items.configure(state=state)
		self.btn_modify.configure(state=state)

		if not operable:
			self.btn_cancel_sale.configure(
				text=f'🚫  Ticket ya {status.upper()}',
			)
		else:
			self.btn_cancel_sale.configure(text='🚫  Anular Ticket Completo')

	# =========================================================
	# ACCIÓN: ANULAR TICKET COMPLETO
	# =========================================================
	def _confirm_cancel(self):
		if not self._selected_sale:
			return
		sale = self._selected_sale
		msg = CTkMessagebox(
			title='Confirmar Anulación',
			message=(
				f'¿Anulás el Ticket #{sale["id"]}?\n\n'
				f'Cliente: {sale.get("customer_name", "—")}\n'
				f'Total: ${sale["total_amount"]:.2f}\n\n'
				f'El stock se restaurará y el monto se\n'
				f'descontará de la caja activa.'
			),
			icon='warning',
			option_1='No, volver',
			option_2='Sí, Anular',
		)
		if msg.get() != 'Sí, Anular':
			return

		success, result_msg = self.controller.cancel_sale(
			self.ctx.tenant_id, sale['id'], self.ctx.user_id
		)

		if success:
			CTkMessagebox(title='Anulación Exitosa', message=result_msg, icon='check')
			self._selected_sale = None
			self.load_sales()
			self._reset_detail_panel()
		else:
			CTkMessagebox(title='Error', message=result_msg, icon='cancel')

	# =========================================================
	# ACCIÓN: DEVOLUCIÓN PARCIAL — POPUP
	# =========================================================
	def _open_return_popup(self):
		if not self._selected_sale:
			return
		sale = self._selected_sale
		items = sale.get('items', [])
		if not items:
			CTkMessagebox(
				title='Sin ítems', message='Este ticket no tiene ítems.', icon='info'
			)
			return

		popup = ctk.CTkToplevel(self)
		popup.title(f'Devolución Parcial — Ticket #{sale["id"]}')
		popup.configure(fg_color=SURFACE1)
		popup.attributes('-topmost', True)
		popup.grab_set()

		popup.update_idletasks()
		pw, ph = 520, 100 + len(items) * 52 + 140
		ph = min(ph, 680)
		rx = self.winfo_rootx() + (self.winfo_width() - pw) // 2
		ry = self.winfo_rooty() + (self.winfo_height() - ph) // 2
		popup.geometry(f'{pw}x{ph}+{rx}+{ry}')

		ctk.CTkLabel(
			popup,
			text='Seleccioná los ítems a devolver',
			font=('Arial', 16, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(18, 4))
		ctk.CTkLabel(
			popup,
			text='Marcá el ítem y escribí la cantidad a devolver (máx = cantidad original)',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
		).pack(pady=(0, 12))

		scroll_frame = ctk.CTkScrollableFrame(popup, fg_color='transparent')
		scroll_frame.pack(fill='both', expand=True, padx=20)

		row_data = []  # list of (check_var, qty_entry, item_dict)

		for item in items:
			qty_orig = item['quantity']
			qty_str = (
				f'{int(qty_orig)}'
				if float(qty_orig).is_integer()
				else f'{qty_orig:.3f}'
			)

			row = ctk.CTkFrame(scroll_frame, fg_color=SURFACE2, corner_radius=8)
			row.pack(fill='x', pady=(0, 6))
			row.grid_columnconfigure(1, weight=1)

			check_var = ctk.BooleanVar(value=False)
			ctk.CTkCheckBox(
				row,
				text='',
				variable=check_var,
				width=30,
				fg_color=ACCENT_DIM,
				hover_color=ACCENT,
				checkmark_color=ACCENT_TEXT,
			).grid(row=0, column=0, padx=(10, 4), pady=10)

			ctk.CTkLabel(
				row,
				text=f'{item["description"][:28]}',
				font=('Arial', 12),
				text_color=TEXT_PRIMARY,
				anchor='w',
			).grid(row=0, column=1, sticky='w', padx=4)

			ctk.CTkLabel(
				row,
				text=f'x{qty_str}  ·  ${item["unit_price"]:.2f}',
				font=('Arial', 10),
				text_color=TEXT_MUTED,
				anchor='e',
			).grid(row=0, column=2, padx=6)

			entry = ctk.CTkEntry(
				row,
				width=70,
				justify='center',
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				text_color=TEXT_PRIMARY,
				height=32,
				placeholder_text=qty_str,
			)
			entry.insert(0, qty_str)
			entry.grid(row=0, column=3, padx=(4, 10), pady=8)

			row_data.append((check_var, entry, item))

		# Total del reembolso (dinámico)
		lbl_refund = ctk.CTkLabel(
			popup,
			text='Reembolso estimado: $0.00',
			font=('Arial', 15, 'bold'),
			text_color=ORANGE_TEXT,
		)
		lbl_refund.pack(pady=(10, 0))

		def _update_refund(*args):
			total = 0.0
			for cv, ent, it in row_data:
				if cv.get():
					try:
						q = float(ent.get().replace(',', '.'))
						q = min(max(q, 0), it['quantity'])
						total += it['unit_price'] * q
					except (ValueError, TypeError):
						pass
			lbl_refund.configure(text=f'Reembolso estimado: ${total:.2f}')

		for cv, ent, _ in row_data:
			cv.trace_add('write', _update_refund)
			ent.bind('<KeyRelease>', _update_refund)

		def _confirm_return():
			items_to_return = []
			for cv, ent, it in row_data:
				if not cv.get():
					continue
				try:
					qty = float(ent.get().replace(',', '.'))
				except (ValueError, TypeError):
					CTkMessagebox(
						title='Error',
						message=f'Cantidad inválida para "{it["description"]}".',
						icon='cancel',
					)
					return
				if qty <= 0 or qty > it['quantity']:
					CTkMessagebox(
						title='Cantidad inválida',
						message=f'"{it["description"]}": ingresá entre 0 y {it["quantity"]}.',
						icon='cancel',
					)
					return
				items_to_return.append(
					{
						'detail_id': it['detail_id'],
						'qty_to_return': qty,
					}
				)

			if not items_to_return:
				CTkMessagebox(
					title='Sin selección',
					message='Marcá al menos un ítem para devolver.',
					icon='info',
				)
				return

			success, msg = self.controller.return_items(
				self.ctx.tenant_id, sale['id'], self.ctx.user_id, items_to_return
			)
			popup.destroy()
			if success:
				CTkMessagebox(title='Devolución Registrada', message=msg, icon='check')
				self._selected_sale = None
				self.load_sales()
				self._reset_detail_panel()
			else:
				CTkMessagebox(title='Error', message=msg, icon='cancel')

		ctk.CTkButton(
			popup,
			text='✓  Confirmar Devolución',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			height=42,
			font=('Arial', 13, 'bold'),
			corner_radius=8,
			command=_confirm_return,
		).pack(pady=(8, 6), padx=24, fill='x')

		ctk.CTkButton(
			popup,
			text='Cancelar',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=34,
			corner_radius=8,
			command=popup.destroy,
		).pack(padx=24, pady=(0, 16), fill='x')

	# =========================================================
	# ACCIÓN: MODIFICAR (Anular + ir a Ventas)
	# =========================================================
	def _confirm_modify(self):
		if not self._selected_sale:
			return
		sale = self._selected_sale
		msg = CTkMessagebox(
			title='Modificar Ticket',
			message=(
				f'Esto va a ANULAR el Ticket #{sale["id"]} y te va a llevar\n'
				f'a la pantalla de Ventas para que lo rehagas con los cambios.\n\n'
				f'Total original: ${sale["total_amount"]:.2f}\n'
				f'¿Continuás?'
			),
			icon='warning',
			option_1='No',
			option_2='Sí, Modificar',
		)
		if msg.get() != 'Sí, Modificar':
			return

		success, result_msg = self.controller.cancel_sale(
			self.ctx.tenant_id, sale['id'], self.ctx.user_id
		)

		if not success:
			CTkMessagebox(title='Error', message=result_msg, icon='cancel')
			return

		# Navegar a SalesView
		navigate = getattr(self.ctx, 'navigate', None)
		if navigate:
			from views.sales_view import SalesView

			navigate(SalesView)
		else:
			CTkMessagebox(
				title='Ticket Anulado',
				message=(
					f'{result_msg}\n\n'
					f'Andá a la sección Ventas para procesar el ticket nuevamente.'
				),
				icon='check',
			)
			self.load_sales()
			self._reset_detail_panel()

	# =========================================================
	# HELPERS
	# =========================================================
	def _reset_detail_panel(self):
		self.lbl_ticket_title.configure(
			text='Seleccioná un ticket de la lista', text_color=TEXT_MUTED
		)
		self.lbl_date.configure(text='—')
		self.lbl_client.configure(text='—')
		self.lbl_method.configure(text='—')
		self.lbl_status.configure(text='—', text_color=TEXT_PRIMARY)
		for iid in self.items_tree.get_children():
			self.items_tree.delete(iid)
		self.lbl_discount_info.configure(text='')
		self.lbl_total.configure(text='Total: —')
		for btn in (self.btn_cancel_sale, self.btn_return_items, self.btn_modify):
			btn.configure(state='disabled')
		self.btn_cancel_sale.configure(text='🚫  Anular Ticket Completo')
		self._selected_sale = None
