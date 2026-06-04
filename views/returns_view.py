import logging
import threading
from pathlib import Path
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

		self._search_var = ctk.StringVar(master=self, )
		self._search_var.trace_add(
			'write', lambda *args: self.debounce(300, self._filter_tree, 'search_sales')
		)

		_search_row = ctk.CTkFrame(self.left, fg_color='transparent')
		_search_row.grid(row=1, column=0, sticky='ew', padx=14, pady=(4, 4))
		_search_row.grid_columnconfigure(0, weight=1)

		self._entry_search = ctk.CTkEntry(
			_search_row,
			textvariable=self._search_var,
			placeholder_text='🔍 Buscar por ID, cliente o fecha...',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
		)
		self._entry_search.grid(row=0, column=0, sticky='ew', padx=(0, 4))

		ctk.CTkButton(
			_search_row,
			text='✕',
			width=30,
			height=34,
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			command=lambda: self._search_var.set(''),
		).grid(row=0, column=1)

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

		for iid in list(self.tree.get_children()):
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
					f'${sale["total_amount"]:.2f}',
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

		item_data = self.tree.item(sel[0])
		sale_id = str(item_data['values'][0])

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
		operable = status in ('completada', 'pendiente', 'parcial')

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

		for iid in list(self.items_tree.get_children()):
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

		_tenant = self.ctx.tenant_id
		_sale_id = sale['id']
		_user = self.ctx.user_id

		def _run():
			try:
				ok, msg = self.controller.cancel_sale(_tenant, _sale_id, _user)
			except Exception as exc:
				ok, msg = False, str(exc)
			if self.winfo_exists():
				self.after(0, lambda: _done(ok, msg))

		def _done(ok, msg):
			self._set_processing_state(False, self.btn_cancel_sale, original_text)
			if ok:
				self.show_success(msg)
				self._reset_detail_panel()
				self.load_sales()
			else:
				self.show_error(msg)

		threading.Thread(target=_run, daemon=True).start()

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

		total_amount = float(sale.get('total_amount', 0))
		discount_amount = float(sale.get('discount_amount', 0))
		subtotal_orig = total_amount + discount_amount
		discount_factor = total_amount / subtotal_orig if subtotal_orig > 0 else 1.0

		popup = ctk.CTkToplevel(self)
		popup.title(f'Devolución Parcial — Ticket #{sale["id"]}')
		popup.configure(fg_color=SURFACE1)
		popup.resizable(False, True)
		popup.attributes('-topmost', True)
		popup.grab_set()

		# ── Dimensiones y posición centrada en pantalla ──
		popup.update_idletasks()
		pw = 640
		sh = popup.winfo_screenheight()
		max_popup_height = min(600, int(sh * 0.80))
		ph = min(len(items) * 68 + 150, max_popup_height)
		ph = max(ph, 480)
		sx = popup.winfo_screenwidth()
		rx = max(0, (sx - pw) // 2)
		ry = max(0, (sh - ph) // 2)
		popup.geometry(f'{pw}x{ph}+{rx}+{ry}')

		# ── HEADER ──────────────────────────────────────────────────
		header = ctk.CTkFrame(popup, fg_color=SURFACE2, corner_radius=0, border_width=0)
		header.pack(fill='x')
		header.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			header,
			text=f'↩  Devolución Parcial  —  Ticket #{sale["id"]}',
			font=FONT_HEADING,
			text_color=ORANGE_TEXT,
			anchor='w',
		).grid(row=0, column=0, sticky='w', padx=20, pady=(16, 2))

		info_parts = []
		client = sale.get('customer_name') or 'Consumidor Final'
		info_parts.append(f'Cliente: {client}')
		info_parts.append(f'Total cobrado: ${total_amount:.2f}')
		if discount_amount > 0:
			info_parts.append(f'Descuento aplicado: ${discount_amount:.2f}')

		ctk.CTkLabel(
			header,
			text='  ·  '.join(info_parts),
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=1, column=0, sticky='w', padx=20, pady=(0, 10))

		# ── BARRA DE ACCIONES RÁPIDAS ────────────────────────────────
		action_bar = ctk.CTkFrame(popup, fg_color=SURFACE3, corner_radius=0)
		action_bar.pack(fill='x')

		ctk.CTkLabel(
			action_bar,
			text='ÍTEMS A DEVOLVER',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
		).pack(side='left', padx=(20, 0), pady=8)

		def _select_all():
			for cv, ent, it in row_data:
				max_q = float(it['quantity'])
				ent.delete(0, 'end')
				ent.insert(
					0, f'{int(max_q)}' if float(max_q).is_integer() else f'{max_q:.3f}'
				)
				cv.set(True)
			_update_refund_and_btn()

		def _clear_all():
			for cv, ent, _ in row_data:
				ent.delete(0, 'end')
				ent.insert(0, '0')
				cv.set(False)
			_update_refund_and_btn()

		ctk.CTkButton(
			action_bar,
			text='Seleccionar Todo',
			height=26,
			width=130,
			font=FONT_LABEL_BOLD,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			corner_radius=6,
			command=_select_all,
		).pack(side='right', padx=(4, 20), pady=6)

		ctk.CTkButton(
			action_bar,
			text='Limpiar',
			height=26,
			width=70,
			font=FONT_LABEL,
			fg_color='transparent',
			hover_color=SURFACE4,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			corner_radius=6,
			command=_clear_all,
		).pack(side='right', padx=(0, 4), pady=6)

		# ── FOOTER FIJO (se pack-ea ANTES del scroll para garantizar visibilidad) ──
		footer = ctk.CTkFrame(popup, fg_color=SURFACE2, corner_radius=0, border_width=0)
		footer.pack(side='bottom', fill='x')
		footer.grid_columnconfigure(0, weight=1)

		# Separador
		ctk.CTkFrame(footer, height=1, fg_color=BORDER_ACTIVE, corner_radius=0).grid(
			row=0, column=0, sticky='ew'
		)

		# Resumen del reembolso
		summary_row = ctk.CTkFrame(footer, fg_color='transparent')
		summary_row.grid(row=1, column=0, sticky='ew', padx=20, pady=(12, 8))
		summary_row.grid_columnconfigure(0, weight=1)

		lbl_selection_hint = ctk.CTkLabel(
			summary_row,
			text='Seleccioná al menos un ítem para continuar',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		)
		lbl_selection_hint.grid(row=0, column=0, sticky='w')

		lbl_refund = ctk.CTkLabel(
			summary_row,
			text='$0.00',
			font=('Arial', 26, 'bold'),
			text_color=ORANGE_TEXT,
			anchor='e',
		)
		lbl_refund.grid(row=0, column=1, sticky='e')

		ctk.CTkLabel(
			summary_row,
			text='Reembolso estimado',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='e',
		).grid(row=1, column=1, sticky='e')

		# Botones
		btn_row = ctk.CTkFrame(footer, fg_color='transparent')
		btn_row.grid(row=2, column=0, sticky='ew', padx=20, pady=(0, 16))
		btn_row.grid_columnconfigure(0, weight=1)

		btn_confirm = ctk.CTkButton(
			btn_row,
			text='Seleccioná ítems para continuar',
			fg_color=SURFACE3,
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			height=46,
			font=FONT_BODY_BOLD,
			corner_radius=8,
			state='disabled',
		)
		btn_confirm.grid(row=0, column=0, sticky='ew', pady=(0, 6))

		ctk.CTkButton(
			btn_row,
			text='Cancelar',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=34,
			corner_radius=8,
			font=FONT_LABEL_BOLD,
			command=popup.destroy,
		).grid(row=1, column=0, sticky='ew')

		# ── ÁREA SCROLLABLE DE ÍTEMS ─────────────────────────────────
		scroll_frame = ctk.CTkScrollableFrame(
			popup,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		scroll_frame.pack(fill='both', expand=True, padx=16, pady=(8, 0))

		row_data = []

		_updating_refund = False

		def _update_refund_and_btn(*_args):
			nonlocal _updating_refund
			if _updating_refund:
				return
			_updating_refund = True
			try:
				_do_update_refund()
			finally:
				_updating_refund = False

		def _do_update_refund():
			total = 0.0
			selected_count = 0
			for cv, ent, it in row_data:
				if cv.get():
					try:
						q = float(ent.get().strip().replace(',', '.') or '0')
						q = min(max(q, 0), float(it['quantity']))
						if q > 0:
							total += float(it['unit_price']) * q * discount_factor
							selected_count += 1
						else:
							cv.set(False)
					except (ValueError, TypeError):
						pass

			lbl_refund.configure(text=f'${total:.2f}')

			if selected_count > 0:
				lbl_selection_hint.configure(
					text=f'{selected_count} ítem{"s" if selected_count > 1 else ""} seleccionado{"s" if selected_count > 1 else ""}',
					text_color=ORANGE_TEXT,
				)
				btn_confirm.configure(
					text=f'✓  Confirmar Devolución  —  ${total:.2f}',
					fg_color=GREEN_DIM,
					hover_color=GREEN,
					text_color=GREEN_TEXT,
					border_color=GREEN,
					state='normal',
					command=_confirm_return,
				)
			else:
				lbl_selection_hint.configure(
					text='Seleccioná al menos un ítem para continuar',
					text_color=TEXT_MUTED,
				)
				btn_confirm.configure(
					text='Seleccioná ítems para continuar',
					fg_color=SURFACE3,
					hover_color=SURFACE3,
					text_color=TEXT_MUTED,
					border_color=BORDER,
					state='disabled',
				)

		for item in items:
			qty_orig_float = float(item['quantity'])
			qty_str = (
				f'{int(qty_orig_float)}'
				if float(qty_orig_float).is_integer()
				else f'{qty_orig_float:.3f}'
			)

			row = ctk.CTkFrame(
				scroll_frame,
				fg_color=SURFACE2,
				corner_radius=10,
				border_width=1,
				border_color=BORDER,
			)
			row.pack(fill='x', pady=(0, 6))
			row.grid_columnconfigure(1, weight=1)

			check_var = ctk.BooleanVar(master=self, value=False)

			def _on_checkbox(cv=check_var, ent_ref=None, max_q=qty_orig_float):
				if cv.get() and ent_ref is not None:
					current_val = ent_ref.get().strip().replace(',', '.')
					try:
						if float(current_val) == 0:
							ent_ref.delete(0, 'end')
							ent_ref.insert(
								0,
								f'{int(max_q)}'
								if float(max_q).is_integer()
								else f'{max_q:.3f}',
							)
					except (ValueError, TypeError):
						pass
				_update_refund_and_btn()

			cb = ctk.CTkCheckBox(
				row,
				text='',
				variable=check_var,
				width=30,
				fg_color=ORANGE_DIM,
				hover_color=ORANGE,
				checkmark_color=ORANGE_TEXT,
				border_color=BORDER_ACTIVE,
			)
			cb.grid(row=0, column=0, padx=(12, 6), pady=14, rowspan=2)

			ctk.CTkLabel(
				row,
				text=item['description'][:34],
				font=FONT_BODY_BOLD,
				text_color=TEXT_PRIMARY,
				anchor='w',
			).grid(row=0, column=1, sticky='w', padx=(0, 8), pady=(10, 0))

			ctk.CTkLabel(
				row,
				text=f'Precio: ${item["unit_price"]:.2f}  ·  Cantidad original: {qty_str}  ·  Subtotal: ${item["subtotal"]:.2f}',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
				anchor='w',
			).grid(row=1, column=1, sticky='w', padx=(0, 8), pady=(0, 10))

			ctrl_frame = ctk.CTkFrame(row, fg_color='transparent')
			ctrl_frame.grid(row=0, column=2, rowspan=2, padx=(0, 12), pady=8)

			entry = ctk.CTkEntry(
				ctrl_frame,
				width=52,
				justify='center',
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				text_color=TEXT_PRIMARY,
				font=FONT_BODY_BOLD,
				height=36,
				corner_radius=6,
			)
			entry.insert(0, '0')
			entry.bind('<FocusIn>', lambda e, ent=entry: ent.select_range(0, 'end'))

			cb.configure(
				command=lambda cv=check_var, e=entry, m=qty_orig_float: _on_checkbox(
					cv, e, m
				)
			)

			def adjust_qty(delta, ent=entry, max_q=qty_orig_float, cv=check_var):
				try:
					current = float(ent.get().strip().replace(',', '.'))
				except Exception:
					current = 0.0
				new_val = round(max(0.0, min(current + delta, max_q)), 3)
				ent.delete(0, 'end')
				ent.insert(
					0,
					f'{int(new_val)}'
					if float(new_val).is_integer()
					else f'{new_val:.3f}',
				)
				cv.set(new_val > 0)
				_update_refund_and_btn()

			ctk.CTkButton(
				ctrl_frame,
				text='−',
				width=36,
				height=36,
				font=('Arial', 16, 'bold'),
				fg_color=SURFACE3,
				hover_color=RED_DIM,
				text_color=TEXT_SECONDARY,
				corner_radius=8,
				border_width=1,
				border_color=BORDER,
				command=lambda e=entry, m=qty_orig_float, c=check_var: adjust_qty(
					-1.0, e, m, c
				),
			).pack(side='left', padx=(0, 4))

			entry.pack(side='left')

			ctk.CTkButton(
				ctrl_frame,
				text='+',
				width=36,
				height=36,
				font=('Arial', 16, 'bold'),
				fg_color=SURFACE3,
				hover_color=ACCENT_DIM,
				text_color=ACCENT_TEXT,
				corner_radius=8,
				border_width=1,
				border_color=BORDER,
				command=lambda e=entry, m=qty_orig_float, c=check_var: adjust_qty(
					1.0, e, m, c
				),
			).pack(side='left', padx=(4, 0))

			entry.bind('<KeyRelease>', _update_refund_and_btn)
			row_data.append((check_var, entry, item))

		def _confirm_return():
			items_to_return = []
			for cv, ent, it in row_data:
				if not cv.get():
					continue
				try:
					qty = float(ent.get().strip().replace(',', '.') or '0')
				except (ValueError, TypeError):
					self.show_error(f'Cantidad inválida para "{it["description"]}".')
					return

				orig_qty = float(it['quantity'])
				if qty <= 0 or qty > orig_qty:
					self.show_error(
						f'"{it["description"]}": cantidad debe ser entre 0.001 y {orig_qty}.',
						'Cantidad inválida',
					)
					return

				items_to_return.append(
					{'detail_id': it['detail_id'], 'qty_to_return': qty}
				)

			if not items_to_return:
				self.show_warning(
					'Seleccioná al menos un ítem para devolver.', 'Sin selección'
				)
				return

			btn_confirm.configure(text='⏳  Procesando...', state='disabled')
			popup.update()

			success, msg = self.controller.return_items(
				self.ctx.tenant_id, sale['id'], self.ctx.user_id, items_to_return
			)

			if success:
				popup.destroy()
				self.show_success(msg)
				self._reset_detail_panel()
				self.load_sales()
			else:
				btn_confirm.configure(text='✓  Confirmar Devolución', state='normal')
				self.show_error(msg)

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
		if not self.navigate:
			self.show_error(
				'No se puede navegar a Ventas desde esta pantalla.\nOperación cancelada para evitar anular el ticket sin poder rehacerlo.',
				'Acción no disponible',
			)
			return

		if not self.confirm(msg, 'Modificar Ticket'):
			return

		original_text = self.btn_modify.cget('text')
		self._set_processing_state(True, self.btn_modify)

		_tenant = self.ctx.tenant_id
		_sale_id = sale['id']
		_user = self.ctx.user_id

		def _run():
			try:
				ok, msg = self.controller.cancel_sale(_tenant, _sale_id, _user)
			except Exception as exc:
				ok, msg = False, str(exc)
			if self.winfo_exists():
				self.after(0, lambda: _done(ok, msg))

		def _done(ok, msg):
			self._set_processing_state(False, self.btn_modify, original_text)
			if not ok:
				self.show_error(msg)
				return
			from views.sales_view import SalesView

			self.navigate(SalesView, context_data={'restore_sale': sale})

		threading.Thread(target=_run, daemon=True).start()

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

		try:
			rc = ReceiptController()
			base_dir = Path(rc.receipts_dir)
			matches = list(
				base_dir.glob(f'tenant_{self.ctx.tenant_id}_NC_{sale["id"]}_*.pdf')
			)

			if matches:
				rc.print_receipt(str(matches[0]))
			else:
				self.show_warning(
					f'No se encontró la nota de crédito del Ticket #{sale["id"]}.',
					'Archivo no encontrado',
				)
		except Exception as e:
			self.show_error(f'Error al intentar abrir la nota de crédito: {str(e)}')
