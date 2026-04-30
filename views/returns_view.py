"""
views/returns_view.py
=====================
Módulo de Devoluciones y Anulaciones de Tickets.

Layout: dos paneles
  - Izquierdo: lista de tickets con búsqueda y filtros rápidos
  - Derecho:  detalle del ticket seleccionado + botones de acción
"""

import logging
import os
from tkinter import ttk

import customtkinter as ctk

from controllers.receipt_controller import ReceiptController
from controllers.returns_controller import ReturnsController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_HEADING,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	FONT_NAV_BOLD,
	FONT_SMALL,
	FONT_TITLE,
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
	# ¡Mira qué limpio queda el init ahora! No hace falta interceptar nada.
	def __init__(self, master, ctx: AppContext, **kwargs):
		super().__init__(master, ctx, **kwargs)
		self.controller = ReturnsController(ctx.db_engine)

		self._all_sales = []
		self._active_filter = 'all'
		self._selected_sale = None

		self.grid_columnconfigure(0, weight=2)
		self.grid_columnconfigure(1, weight=3)
		self.grid_rowconfigure(0, weight=1)

		apply_treeview_style()

		self._build_left_panel()
		self._build_right_panel()

		self.schedule(100, self.load_sales)

	def set_initial_focus(self):
		if hasattr(self, '_entry_search') and self._entry_search.winfo_exists():
			self._entry_search.focus_set()

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
			font=FONT_HEADING,
			command=self.load_sales,
		).pack(side='right')

		self._search_var = ctk.StringVar()
		self._search_var.trace_add(
			'write', lambda *args: self.debounce(300, self._filter_tree, 'search_sales')
		)

		self._entry_search = ctk.CTkEntry(
			self.left,
			textvariable=self._search_var,
			placeholder_text='🔍 Buscar por ID, cliente o fecha...',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
		)
		self._entry_search.grid(row=1, column=0, sticky='ew', padx=14, pady=(4, 4))

		filter_frame = ctk.CTkFrame(self.left, fg_color='transparent')
		filter_frame.grid(row=2, column=0, sticky='ew', padx=14, pady=(0, 6))

		self._filter_btns = {}
		_filters = [
			('all', 'Todos'),
			('today', 'Hoy'),
			('fiado', 'Fiados'),
			('anuladas', 'Anuladas'),
			('cotizacion', '📋 Cotización'),
		]
		for fkey, flabel in _filters:
			is_active = fkey == 'all'
			btn = ctk.CTkButton(
				filter_frame,
				text=flabel,
				height=26,
				corner_radius=5,
				font=FONT_LABEL_BOLD if is_active else FONT_LABEL,
				fg_color=ACCENT_DIM if is_active else SURFACE3,
				hover_color=ACCENT if is_active else SURFACE4,
				text_color=ACCENT_TEXT if is_active else TEXT_SECONDARY,
				border_width=1,
				border_color=ACCENT if is_active else BORDER,
				command=lambda k=fkey: self._apply_filter(k),
			)
			btn.pack(side='left', padx=(0, 4))
			self._filter_btns[fkey] = btn

		tree_frame = ctk.CTkFrame(self.left, fg_color='transparent')
		tree_frame.grid(row=3, column=0, sticky='nsew', padx=14, pady=(0, 14))

		scroll = ttk.Scrollbar(tree_frame, orient='vertical')
		cols = ('ID', 'Fecha', 'Cliente', 'Total', 'Origen', 'Estado')
		self.tree = ttk.Treeview(
			tree_frame,
			columns=cols,
			show='headings',
			yscrollcommand=scroll.set,
		)
		scroll.configure(command=self.tree.yview)

		_widths = {
			'ID': 45,
			'Fecha': 108,
			'Cliente': 100,
			'Total': 68,
			'Origen': 100,
			'Estado': 85,
		}
		for col in cols:
			self.tree.heading(col, text=col)
			self.tree.column(col, width=_widths[col], anchor='center')

		self.init_treeview(self.tree)

		self.tree.tag_configure('completada', foreground=GREEN_TEXT)
		self.tree.tag_configure('pendiente', foreground=ORANGE_TEXT)
		self.tree.tag_configure('parcial', foreground=ORANGE_TEXT)
		self.tree.tag_configure('devuelta', foreground=TEXT_MUTED)
		self.tree.tag_configure('anulada', foreground=RED_TEXT)
		self.tree.tag_configure('fiado', foreground=ORANGE_TEXT)
		self.tree.tag_configure('cotizacion', foreground=ACCENT_TEXT)

		scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)
		self.tree.bind('<<TreeviewSelect>>', self._on_sale_selected)

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
		self.right.grid_rowconfigure(0, weight=1)
		self.right.grid_columnconfigure(0, weight=1)

		self.right_content = ctk.CTkFrame(self.right, fg_color='transparent')
		self.right_content.grid(row=0, column=0, sticky='nsew')

		self._reset_detail_panel()

	def _reset_detail_panel(self):
		self._selected_sale = None
		for w in list(self.right_content.winfo_children()):
			w.destroy()

		self.show_empty_state(
			self.right_content,
			message='Seleccioná un ticket de la lista para ver su\ndetalle o procesar devoluciones.',
			icon='🧾',
		)

	def _build_detail_ui(self):
		for w in list(self.right_content.winfo_children()):
			w.destroy()

		self.right_content.grid_rowconfigure(3, weight=1)
		self.right_content.grid_columnconfigure(0, weight=1)

		self.lbl_ticket_title = ctk.CTkLabel(
			self.right_content,
			text='',
			font=('Arial', 17, 'bold'),
		)
		self.lbl_ticket_title.grid(row=0, column=0, sticky='w', padx=20, pady=(18, 0))

		self.lbl_quotation_origin = ctk.CTkLabel(
			self.right_content,
			text='',
			font=FONT_LABEL,
			text_color=ACCENT_TEXT,
			anchor='w',
		)
		self.lbl_quotation_origin.grid(
			row=1, column=0, sticky='w', padx=22, pady=(2, 6)
		)

		info_frame = ctk.CTkFrame(
			self.right_content, fg_color=SURFACE3, corner_radius=8
		)
		info_frame.grid(row=2, column=0, sticky='ew', padx=16, pady=(0, 10))
		info_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

		self.lbl_date = self._info_cell(info_frame, '—', 'Fecha', 0)
		self.lbl_client = self._info_cell(info_frame, '—', 'Cliente', 1)
		self.lbl_method = self._info_cell(info_frame, '—', 'Pago', 2)
		self.lbl_status = self._info_cell(info_frame, '—', 'Estado', 3)

		items_container = ctk.CTkFrame(self.right_content, fg_color='transparent')
		items_container.grid(row=3, column=0, sticky='nsew', padx=16, pady=(0, 8))

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

		self.init_treeview(self.items_tree)

		items_scroll.pack(side='right', fill='y')
		self.items_tree.pack(side='left', fill='both', expand=True)

		bottom = ctk.CTkFrame(self.right_content, fg_color='transparent')
		bottom.grid(row=4, column=0, sticky='ew', padx=16, pady=(0, 16))
		bottom.grid_columnconfigure(0, weight=1)

		self.lbl_discount_info = ctk.CTkLabel(
			bottom,
			text='',
			font=FONT_SMALL,
			text_color=ORANGE_TEXT,
			anchor='e',
		)
		self.lbl_discount_info.grid(
			row=0, column=0, columnspan=3, sticky='e', pady=(0, 2)
		)

		self.lbl_total = ctk.CTkLabel(
			bottom,
			text='Total: —',
			font=FONT_TITLE,
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
			font=FONT_BODY_BOLD,
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
			font=FONT_BODY_BOLD,
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
			font=FONT_BODY_BOLD,
			command=self._confirm_modify,
		)
		self.btn_modify.grid(row=4, column=0, sticky='ew', pady=(0, 10))

		ctk.CTkFrame(bottom, fg_color=BORDER, height=1).grid(
			row=5, column=0, sticky='ew', pady=(0, 8)
		)

		print_row = ctk.CTkFrame(bottom, fg_color='transparent')
		print_row.grid(row=6, column=0, sticky='ew')
		print_row.grid_columnconfigure((0, 1), weight=1)

		self.btn_reprint = ctk.CTkButton(
			print_row,
			text='🖨️  Reimprimir Ticket',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=34,
			corner_radius=8,
			font=FONT_LABEL_BOLD,
			command=self._reprint_ticket,
		)
		self.btn_reprint.grid(row=0, column=0, sticky='ew', padx=(0, 4))

		self.btn_credit_note = ctk.CTkButton(
			print_row,
			text='📄  Nota de Crédito',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			height=34,
			corner_radius=8,
			font=FONT_LABEL_BOLD,
			command=self._open_credit_note,
		)
		self.btn_credit_note.grid(row=0, column=1, sticky='ew', padx=(4, 0))

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
			font=FONT_NAV_BOLD,
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
				font=FONT_LABEL_BOLD if active else FONT_LABEL,
			)
		self.load_sales()

	def _filter_tree(self):
		if not self.winfo_exists():
			return

		q = self._search_var.get().lower().strip()

		def _matches_search(s):
			if not q:
				return True
			return (
				q in str(s.get('id', '')).lower()
				or q in (s.get('customer_name') or '').lower()
				or q in str(s.get('date') or '').lower()
				or q in (s.get('quotation_number') or '').lower()
			)

		def _matches_filter(s):
			if self._active_filter == 'cotizacion':
				return bool(s.get('quotation_number'))
			return True

		matches = [
			s for s in self._all_sales if _matches_search(s) and _matches_filter(s)
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
			quotation_number = sale.get('quotation_number') or ''
			origen_label = (
				f'📋 {quotation_number}' if quotation_number else '🛒 Directa'
			)

			if pm == 'fiado':
				tag = 'fiado'
			elif quotation_number:
				tag = 'cotizacion'
			else:
				tag = status

			self.insert_tree_row(
				self.tree,
				i,
				values=(
					sale['id'],
					date_str,
					(sale.get('customer_name') or 'S/N')[:14],
					f'${sale["total_amount"]:.0f}',
					origen_label,
					_STATUS_LABELS.get(status, status),
				),
				tags=(tag,),
			)

	# =========================================================
	# SELECCIÓN DE TICKET
	# =========================================================
	def _on_sale_selected(self, event=None):
		sel = self.tree.selection()
		if not sel:
			return
		sale_id = str(sel[0])
		sale = self.controller.get_sale_with_details(self.ctx.tenant_id, sale_id)
		if not sale:
			return
		self._selected_sale = sale
		self._refresh_detail_panel(sale)

	def _refresh_detail_panel(self, sale):
		if (
			not hasattr(self, 'lbl_ticket_title')
			or not self.lbl_ticket_title.winfo_exists()
		):
			self._build_detail_ui()

		status = sale.get('status', 'completada')
		pm = sale.get('payment_method', '')
		operable = status in ('completada', 'pendiente')

		self.lbl_ticket_title.configure(
			text=f'Ticket  #{sale["id"]}',
			text_color=_STATUS_COLORS.get(status, TEXT_PRIMARY),
		)

		quotation_number = sale.get('quotation_number') or ''
		if quotation_number:
			self.lbl_quotation_origin.configure(
				text=f'📋 Originado desde cotización  {quotation_number}'
			)
		else:
			self.lbl_quotation_origin.configure(text='')

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

		for iid in self.items_tree.get_children():
			self.items_tree.delete(iid)

		for i, item in enumerate(sale.get('items', [])):
			qty = float(item['quantity'])
			qty_str = f'{int(qty)}' if qty.is_integer() else f'{qty:.3f}'

			self.insert_tree_row(
				self.items_tree,
				i,
				values=(
					item['description'][:30],
					qty_str,
					f'${item["unit_price"]:.2f}',
					f'${item["subtotal"]:.2f}',
				),
			)

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

		state = 'normal' if operable else 'disabled'
		self.btn_cancel_sale.configure(state=state)
		self.btn_return_items.configure(state=state)
		self.btn_modify.configure(state=state)

		if not operable:
			self.btn_cancel_sale.configure(text=f'🚫  Ticket ya {status.upper()}')
		else:
			self.btn_cancel_sale.configure(text='🚫  Anular Ticket Completo')

		self.btn_reprint.configure(state='normal')

		nc_available = status in ('anulada', 'devuelta', 'parcial')
		self.btn_credit_note.configure(
			state='normal' if nc_available else 'disabled',
			text_color=TEXT_SECONDARY if nc_available else TEXT_MUTED,
		)

	# =========================================================
	# ESTADO DE PROCESAMIENTO
	# =========================================================
	def _set_processing_state(
		self, processing: bool, button: ctk.CTkButton = None, original_text: str = ''
	):
		state = 'disabled' if processing else 'normal'
		self.btn_cancel_sale.configure(state=state)
		self.btn_return_items.configure(state=state)
		self.btn_modify.configure(state=state)

		if button:
			self.set_loading(button, processing, original_text)

	# =========================================================
	# ACCIÓN: ANULAR TICKET COMPLETO
	# =========================================================
	def _confirm_cancel(self):
		if not self._selected_sale:
			return
		sale = self._selected_sale

		msg = (
			f'¿Anulás el Ticket #{sale["id"]}?\n\n'
			f'Cliente: {sale.get("customer_name", "—")}\n'
			f'Total: ${sale["total_amount"]:.2f}\n\n'
			f'El stock se restaurará y el monto se\n'
			f'descontará de la caja activa.'
		)
		if not self.confirm(msg, 'Confirmar Anulación'):
			return

		original_text = self.btn_cancel_sale.cget('text')
		self._set_processing_state(True, self.btn_cancel_sale)

		success, result_msg = self.controller.cancel_sale(
			self.ctx.tenant_id, sale['id'], self.ctx.user_id
		)

		self._set_processing_state(False, self.btn_cancel_sale, original_text)

		if success:
			self.show_success(result_msg)
			self._reset_detail_panel()
			self.load_sales()
		else:
			self.show_error(result_msg)

	# =========================================================
	# ACCIÓN: DEVOLUCIÓN PARCIAL — POPUP TOUCH-FRIENDLY
	# =========================================================
	def _open_return_popup(self):
		if not self._selected_sale:
			return
		sale = self._selected_sale
		items = sale.get('items', [])

		if not items:
			self.show_warning('Este ticket no tiene ítems.')
			return

		popup = ctk.CTkToplevel(self)
		popup.title(f'Devolución Parcial — Ticket #{sale["id"]}')
		popup.configure(fg_color=SURFACE1)
		popup.attributes('-topmost', True)
		popup.grab_set()

		popup.update_idletasks()
		pw, ph = 600, 100 + len(items) * 60 + 150
		ph = min(ph, 700)
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
			text='Ajustá la cantidad a devolver usando los botones + y -',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(pady=(0, 12))

		scroll_frame = ctk.CTkScrollableFrame(popup, fg_color='transparent')
		scroll_frame.pack(fill='both', expand=True, padx=20)

		row_data = []

		def _update_refund(*args):
			total = 0.0
			for cv, ent, it in row_data:
				if cv.get():
					try:
						raw_val = ent.get().replace(',', '.')
						if not raw_val:
							continue
						q = float(raw_val)
						q = min(max(q, 0), float(it['quantity']))
						if q > 0:
							total += float(it['unit_price']) * q
						else:
							cv.set(False)
					except (ValueError, TypeError):
						pass
			lbl_refund.configure(text=f'Reembolso estimado: ${total:.2f}')

		for item in items:
			qty_orig_float = float(item['quantity'])
			qty_str = (
				f'{int(qty_orig_float)}'
				if qty_orig_float.is_integer()
				else f'{qty_orig_float:.3f}'
			)

			row = ctk.CTkFrame(scroll_frame, fg_color=SURFACE2, corner_radius=8)
			row.pack(fill='x', pady=(0, 6))
			row.grid_columnconfigure(1, weight=1)

			check_var = ctk.BooleanVar(value=False)
			cb = ctk.CTkCheckBox(
				row,
				text='',
				variable=check_var,
				width=30,
				fg_color=ACCENT_DIM,
				hover_color=ACCENT,
				checkmark_color=ACCENT_TEXT,
				command=_update_refund,
			)
			cb.grid(row=0, column=0, padx=(10, 4), pady=12)

			ctk.CTkLabel(
				row,
				text=f'{item["description"][:28]}',
				font=FONT_BODY,
				text_color=TEXT_PRIMARY,
				anchor='w',
			).grid(row=0, column=1, sticky='w', padx=4)

			ctk.CTkLabel(
				row,
				text=f'x{qty_str}  ·  ${item["unit_price"]:.2f}',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
				anchor='e',
			).grid(row=0, column=2, padx=10)

			ctrl_frame = ctk.CTkFrame(row, fg_color='transparent')
			ctrl_frame.grid(row=0, column=3, padx=(0, 10))

			entry = ctk.CTkEntry(
				ctrl_frame,
				width=50,
				justify='center',
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				text_color=TEXT_PRIMARY,
				height=32,
			)
			entry.insert(0, '0')
			entry.bind('<FocusIn>', lambda e, ent=entry: ent.select_range(0, 'end'))

			def adjust_qty(delta, ent=entry, max_q=qty_orig_float, cv=check_var):
				try:
					current = float(ent.get().replace(',', '.'))
				except Exception:
					current = 0.0

				new_val = current + delta
				new_val = max(0.0, min(new_val, max_q))

				ent.delete(0, 'end')
				ent.insert(
					0, f'{int(new_val)}' if new_val.is_integer() else f'{new_val:.3f}'
				)

				if new_val > 0 and not cv.get():
					cv.set(True)
				elif new_val == 0 and cv.get():
					cv.set(False)
				_update_refund()

			ctk.CTkButton(
				ctrl_frame,
				text='-',
				width=32,
				height=32,
				font=FONT_BODY_BOLD,
				fg_color=SURFACE4,
				text_color=TEXT_PRIMARY,
				command=lambda e=entry, m=qty_orig_float, c=check_var: adjust_qty(
					-1.0, e, m, c
				),
			).pack(side='left', padx=2)

			entry.pack(side='left', padx=2)

			ctk.CTkButton(
				ctrl_frame,
				text='+',
				width=32,
				height=32,
				font=FONT_BODY_BOLD,
				fg_color=SURFACE4,
				text_color=TEXT_PRIMARY,
				command=lambda e=entry, m=qty_orig_float, c=check_var: adjust_qty(
					1.0, e, m, c
				),
			).pack(side='left', padx=2)

			entry.bind('<KeyRelease>', _update_refund)
			row_data.append((check_var, entry, item))

		lbl_refund = ctk.CTkLabel(
			popup,
			text='Reembolso estimado: $0.00',
			font=('Arial', 16, 'bold'),
			text_color=ORANGE_TEXT,
		)
		lbl_refund.pack(pady=(10, 0))

		def _confirm_return():
			items_to_return = []
			for cv, ent, it in row_data:
				if not cv.get():
					continue
				try:
					raw_val = ent.get().replace(',', '.')
					if not raw_val:
						continue
					qty = float(raw_val)
				except (ValueError, TypeError):
					self.show_error(f'Cantidad inválida para "{it["description"]}".')
					return

				orig_qty = float(it['quantity'])
				if qty <= 0 or qty > orig_qty:
					self.show_error(
						f'"{it["description"]}": ingresá entre 0.001 y {orig_qty}.',
						'Cantidad inválida',
					)
					return

				items_to_return.append(
					{'detail_id': it['detail_id'], 'qty_to_return': qty}
				)

			if not items_to_return:
				self.show_warning(
					'Aumentá la cantidad de al menos un ítem para devolver.',
					'Sin selección',
				)
				return

			btn_confirm.configure(text='⏳ Procesando...', state='disabled')
			popup.update()

			success, msg = self.controller.return_items(
				self.ctx.tenant_id, sale['id'], self.ctx.user_id, items_to_return
			)
			popup.destroy()

			if success:
				self.show_success(msg)
				self._reset_detail_panel()
				self.load_sales()
			else:
				self.show_error(msg)

		btn_confirm = ctk.CTkButton(
			popup,
			text='✓  Confirmar Devolución',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			height=42,
			font=FONT_NAV_BOLD,
			corner_radius=8,
			command=_confirm_return,
		)
		btn_confirm.pack(pady=(12, 6), padx=24, fill='x')

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

		msg = (
			f'Esto va a ANULAR el Ticket #{sale["id"]} y te va a llevar\n'
			f'a la pantalla de Ventas para que lo rehagas con los cambios.\n\n'
			f'Total original: ${sale["total_amount"]:.2f}\n'
			f'¿Continuás?'
		)
		if not self.confirm(msg, 'Modificar Ticket'):
			return

		original_text = self.btn_modify.cget('text')
		self._set_processing_state(True, self.btn_modify)

		success, result_msg = self.controller.cancel_sale(
			self.ctx.tenant_id, sale['id'], self.ctx.user_id
		)

		self._set_processing_state(False, self.btn_modify, original_text)

		if not success:
			self.show_error(result_msg)
			return

		if self.navigate:
			from views.sales_view import SalesView

			self.navigate(SalesView, context_data={'restore_sale': sale})
		else:
			self.show_toast(
				f'{result_msg} — Andá a Ventas para rehacerlo.', 'info', 5000
			)
			self._reset_detail_panel()
			self.load_sales()

	# =========================================================
	# ACCIÓN: REIMPRIMIR TICKET
	# =========================================================
	def _reprint_ticket(self):
		if not self._selected_sale:
			return
		ok, result = ReceiptController().reprint_receipt(
			self.ctx.tenant_id, self._selected_sale['id']
		)
		if not ok:
			self.show_toast(result, 'info')

	# =========================================================
	# ACCIÓN: VER NOTA DE CRÉDITO
	# =========================================================
	def _open_credit_note(self):
		if not self._selected_sale:
			return
		sale = self._selected_sale
		status = sale.get('status', '')
		note_type = 'Anulación' if status == 'anulada' else 'Devolución'

		rc = ReceiptController()
		filepath = os.path.join(
			rc.receipts_dir,
			f'tenant_{self.ctx.tenant_id}_NC_{sale["id"]}_{note_type[:3].lower()}.pdf',
		)
		if os.path.exists(filepath):
			rc.print_receipt(filepath)
		else:
			self.show_warning(
				f'No se encontró la nota de crédito del Ticket #{sale["id"]}.',
				'Archivo no encontrado',
			)
