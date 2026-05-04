import csv
import tkinter.filedialog as filedialog
from datetime import date, datetime, timedelta
from tkinter import ttk

import customtkinter as ctk

from controllers.sales_controller import SalesController
from core.base_view import BaseView
from core.context import AppContext
from utils.settings_manager import get_reports_path
from utils.styles import (
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_BODY,
	FONT_LABEL,
	FONT_NAV,
	FONT_SMALL,
	FONT_SMALL_BOLD,
	GREEN_TEXT,
	ORANGE_TEXT,
	RED_TEXT,
	SURFACE1,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	make_toggle_button,
)


class HistoryView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = SalesController(ctx.db_engine)

		self._all_sales = []
		self._active_filter = 'all'

		self._custom_start = None
		self._custom_end = None

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(0, weight=0)
		self.grid_rowconfigure(1, weight=0)
		self.grid_rowconfigure(2, weight=0)
		self.grid_rowconfigure(3, weight=1)

		# ── Header ────────────────────────────────────────────────────────
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(row=0, column=0, sticky='ew', pady=(20, 6), padx=20)

		ctk.CTkLabel(
			header_frame,
			text='📊  Historial de Ventas y Ganancias',
			font=('Arial', 22, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		ctk.CTkButton(
			header_frame,
			text='↻  Actualizar',
			fg_color=SURFACE2,
			hover_color=SURFACE3,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			width=120,
			height=34,
			corner_radius=8,
			command=self.load_history,
		).pack(side='right')

		# ── Search Bar ────────────────────────────────────────────────────
		search_row = ctk.CTkFrame(self, fg_color='transparent')
		search_row.grid(row=1, column=0, sticky='ew', padx=20, pady=(0, 8))

		self._search_var = ctk.StringVar()
		self._search_var.trace_add('write', self.debounce_filter)

		ctk.CTkEntry(
			search_row,
			textvariable=self._search_var,
			placeholder_text='🔍 Buscar por cliente, vendedor o fecha...',
			fg_color=SURFACE2,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			height=34,
		).pack(side='left', fill='x', expand=True)

		self.lbl_count = ctk.CTkLabel(
			search_row,
			text='',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			width=110,
			anchor='e',
		)
		self.lbl_count.pack(side='right', padx=(8, 0))

		# ── Filters ───────────────────────────────────────────────────────
		filter_row = ctk.CTkFrame(self, fg_color='transparent')
		filter_row.grid(row=2, column=0, sticky='ew', padx=20, pady=(0, 6))

		self._filter_btns = {}
		_filters = [
			('all', 'Todos'),
			('today', 'Hoy'),
			('week', 'Esta Semana'),
			('fiado', 'Solo Fiados'),
			('anuladas', 'Anuladas / Devueltas'),
			('cotizacion', '📋 Cotizaciones'),
			('custom', 'Personalizado'),
		]

		for fkey, flabel in _filters:
			is_active = fkey == 'all'
			btn = make_toggle_button(
				filter_row,
				text=flabel,
				active=is_active,
				command=lambda k=fkey: self._apply_filter(k),
			)
			btn.pack(side='left', padx=(0, 6))
			self._filter_btns[fkey] = btn

		# ── Date Picker Personalizado (oculto por defecto) ──
		self._custom_date_frame = ctk.CTkFrame(filter_row, fg_color='transparent')
		self._entry_date_start = ctk.CTkEntry(
			self._custom_date_frame,
			width=95,
			placeholder_text='DD/MM/AAAA',
			height=28,
			font=FONT_SMALL,
		)
		self._entry_date_start.pack(side='left', padx=2)
		ctk.CTkLabel(
			self._custom_date_frame, text='-', font=FONT_SMALL, text_color=TEXT_MUTED
		).pack(side='left')
		self._entry_date_end = ctk.CTkEntry(
			self._custom_date_frame,
			width=95,
			placeholder_text='DD/MM/AAAA',
			height=28,
			font=FONT_SMALL,
		)
		self._entry_date_end.pack(side='left', padx=2)
		ctk.CTkButton(
			self._custom_date_frame,
			text='Aplicar',
			width=60,
			height=28,
			font=FONT_SMALL,
			command=self._apply_custom_dates,
		).pack(side='left', padx=(4, 0))
		self._custom_date_frame.pack_forget()

		ctk.CTkButton(
			filter_row,
			text='📄  Exportar CSV',
			height=28,
			corner_radius=6,
			font=FONT_SMALL,
			fg_color=SURFACE2,
			hover_color=SURFACE3,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			command=self.export_csv,
		).pack(side='right')

		# ── Data Table ────────────────────────────────────────────────────
		self.table_container = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.table_container.grid(row=3, column=0, sticky='nsew', padx=20, pady=(0, 4))

		inner = ctk.CTkFrame(self.table_container, fg_color='transparent')
		inner.pack(fill='both', expand=True, padx=12, pady=12)

		self.tree_scroll = ttk.Scrollbar(inner, orient='vertical')

		columns = (
			'ID',
			'Fecha',
			'Cliente',
			'Vendedor',
			'Origen',
			'Descuento',
			'Total',
			'Ganancia',
			'Estado',
		)
		self.tree = ttk.Treeview(
			inner,
			columns=columns,
			show='headings',
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		self.init_treeview(self.tree)

		_col_widths = {
			'ID': 50,
			'Fecha': 130,
			'Cliente': 150,
			'Vendedor': 100,
			'Origen': 120,
			'Descuento': 85,
			'Total': 90,
			'Ganancia': 90,
			'Estado': 100,
		}
		for col in columns:
			self.tree.heading(col, text=col)
			self.tree.column(col, width=_col_widths.get(col, 100), anchor='center')

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)
		self.tree.bind('<Double-1>', self.open_details_popup)

		self.lbl_empty_history = ctk.CTkLabel(
			inner,
			text='📋\nNo hay ventas para el período seleccionado.',
			font=FONT_NAV,
			text_color=TEXT_MUTED,
			justify='center',
		)

		self.tree.tag_configure('fiado', foreground='#fb923c')
		self.tree.tag_configure('pendiente', foreground='#facc15')
		self.tree.tag_configure('completada', foreground=GREEN_TEXT)
		self.tree.tag_configure('has_disc', foreground=ORANGE_TEXT)
		self.tree.tag_configure('cotizacion', foreground=ACCENT_TEXT)
		self.tree.tag_configure('anulada', foreground=RED_TEXT)
		self.tree.tag_configure('devuelta', foreground=ORANGE_TEXT)
		self.tree.tag_configure('parcial', foreground=ORANGE_TEXT)

		# ── Actions ───────────────────────────────────────────────────────
		btn_row = ctk.CTkFrame(self, fg_color='transparent')
		btn_row.grid(row=4, column=0, sticky='ew', padx=20, pady=(0, 14))

		ctk.CTkButton(
			btn_row,
			text='🔍  Ver Detalle de Venta Seleccionada',
			height=34,
			corner_radius=8,
			font=FONT_BODY,
			fg_color=SURFACE2,
			hover_color=SURFACE3,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			command=lambda: self.open_details_popup(None),
		).pack(side='left', padx=(0, 8))

		self.after(100, self.load_history)

	def debounce_filter(self, *args):
		self.debounce(200, self._filter_tree)

	def _apply_filter(self, key: str):
		self._active_filter = key
		for k, btn in self._filter_btns.items():
			active = k == key
			btn.configure(
				fg_color=SURFACE4 if active else SURFACE2,
				text_color=TEXT_PRIMARY if active else TEXT_SECONDARY,
				border_color=BORDER_ACTIVE if active else BORDER,
			)

		if key == 'custom':
			self._custom_date_frame.pack(side='left', padx=(10, 0))
		else:
			self._custom_date_frame.pack_forget()
			self._filter_tree()

	def _apply_custom_dates(self):
		start_str = self._entry_date_start.get().strip()
		end_str = self._entry_date_end.get().strip()
		try:
			self._custom_start = datetime.strptime(start_str, '%d/%m/%Y').date()
			self._custom_end = datetime.strptime(end_str, '%d/%m/%Y').date()
			self._filter_tree()
		except ValueError:
			self.show_error(
				'Formato de fecha inválido. Usá el formato DD/MM/AAAA', 'Error en Fecha'
			)

	def _filter_tree(self, *args):
		q = self._search_var.get().lower()
		today = date.today()
		week_start = today - timedelta(days=today.weekday())

		def _passes_quick_filter(s):
			if self._active_filter == 'all':
				return True
			raw_date = s.get('date')
			sale_date = raw_date.date() if hasattr(raw_date, 'date') else None

			if self._active_filter == 'today':
				return sale_date == today
			if self._active_filter == 'week':
				return sale_date is not None and sale_date >= week_start
			if self._active_filter == 'fiado':
				return s.get('payment_method') == 'fiado'
			if self._active_filter == 'anuladas':
				return s.get('status') in ('anulada', 'devuelta', 'parcial')
			if self._active_filter == 'cotizacion':
				return bool(s.get('quotation_number'))
			if self._active_filter == 'custom':
				if not self._custom_start or not self._custom_end:
					return True
				return (
					sale_date is not None
					and self._custom_start <= sale_date <= self._custom_end
				)
			return True

		matches = [
			s
			for s in self._all_sales
			if _passes_quick_filter(s)
			and (
				not q
				or q in (s.get('customer_name') or '').lower()
				or q in (s.get('user_name') or '').lower()
				or q in str(s.get('date') or '').lower()
				or q in (s.get('quotation_number') or '').lower()
			)
		]

		for item in self.tree.get_children():
			self.tree.delete(item)

		for row_idx, sale in enumerate(matches):
			raw_date = sale.get('date')
			date_str = (
				raw_date.strftime('%Y-%m-%d %H:%M')
				if hasattr(raw_date, 'strftime')
				else str(raw_date)
			)
			total_amount = float(sale.get('total_amount', 0.0))
			discount_amount = float(sale.get('discount_amount', 0.0))
			profit = float(sale.get('profit', 0.0))
			pm = sale.get('payment_method', '') or ''
			pm2 = sale.get('payment_method_2', '') or ''
			status = sale.get('status', '') or ''
			quotation_number = sale.get('quotation_number', '') or ''

			origen_label = (
				f'📋 {quotation_number}' if quotation_number else '🛒 Directa'
			)

			if quotation_number:
				estado_label = '📋 Cotización'
				row_color = 'cotizacion'
			elif status == 'anulada':
				estado_label, row_color = '🚫 Anulada', 'anulada'
			elif status == 'devuelta':
				estado_label, row_color = '↩ Devuelta', 'devuelta'
			elif status == 'parcial':
				estado_label, row_color = '↩ Parcial', 'parcial'
			elif pm == 'fiado':
				estado_label, row_color = '💳 Fiado', 'fiado'
			elif status == 'pendiente':
				estado_label, row_color = '⏳ Pendiente', 'pendiente'
			elif pm2:
				estado_label, row_color = '💰 Mixto', 'completada'
			else:
				estado_label, row_color = (
					('✓ Efectivo' if pm == 'efectivo' else f'✓ {pm.capitalize()}'),
					'completada',
				)

			disc_str = f'-${discount_amount:.2f}' if discount_amount > 0 else '—'
			tags = (
				('has_disc',)
				if discount_amount > 0 and row_color == 'completada'
				else (row_color,)
			)

			self.insert_tree_row(
				tree=self.tree,
				index=row_idx,
				values=(
					sale.get('id'),
					date_str,
					sale.get('customer_name', 'Sin Cliente'),
					sale.get('user_name', 'Desconocido'),
					origen_label,
					disc_str,
					f'${total_amount:.2f}',
					f'${profit:.2f}',
					estado_label,
				),
				tags=tags,
			)

		if hasattr(self, 'lbl_empty_history'):
			if not matches:
				self.tree.pack_forget()
				self.tree_scroll.pack_forget()
				self.lbl_empty_history.pack(expand=True)
			else:
				self.lbl_empty_history.pack_forget()
				if not self.tree.winfo_ismapped():
					self.tree_scroll.pack(side='right', fill='y')
					self.tree.pack(side='left', fill='both', expand=True)

		total = len(self._all_sales)
		shown = len(matches)
		if hasattr(self, 'lbl_count'):
			self.lbl_count.configure(
				text=f'{shown} de {total}' if q else f'{total} ventas'
			)

	def export_csv(self):
		rows = [self.tree.item(iid, 'values') for iid in self.tree.get_children()]
		if not rows:
			self.show_warning('No hay ventas para exportar.', 'Sin datos')
			return

		try:
			default_filename = (
				f'historial_ventas_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
			)
			filepath = filedialog.asksaveasfilename(
				initialdir=get_reports_path(),
				initialfile=default_filename,
				defaultextension='.csv',
				filetypes=[('Archivos CSV', '*.csv'), ('Todos los archivos', '*.*')],
				title='Guardar Historial de Ventas',
			)

			if not filepath:
				return

			with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
				w = csv.writer(f)
				w.writerow(
					[
						'ID',
						'Fecha',
						'Cliente',
						'Vendedor',
						'Origen',
						'Descuento',
						'Total',
						'Ganancia',
						'Estado',
					]
				)
				w.writerows(rows)

			self.show_success(f'Archivo guardado en:\n{filepath}', 'Exportado')
		except Exception as e:
			self.show_error(f'No se pudo exportar: {e}')

	def load_history(self):
		tenant_id = self.ctx.tenant_id
		self._all_sales = self.controller.get_history(tenant_id)
		self._filter_tree()

	def open_details_popup(self, event):
		selected_item = self.tree.selection()
		if not selected_item:
			self.show_warning('Seleccioná una venta de la tabla primero.', 'Selección')
			return

		item_data = self.tree.item(selected_item)
		sale_id = item_data['values'][0]
		tenant_id = self.ctx.tenant_id

		result = self.controller.get_sale_details(tenant_id, sale_id)
		details = result.get('items', []) if isinstance(result, dict) else result
		discount_amount = (
			result.get('discount_amount', 0.0) if isinstance(result, dict) else 0.0
		)
		pay_method = (
			result.get('payment_method', '') if isinstance(result, dict) else ''
		)
		pay_method_2 = (
			result.get('payment_method_2', '') if isinstance(result, dict) else ''
		)
		pay_amount_2 = (
			result.get('amount_method_2', 0.0) if isinstance(result, dict) else 0.0
		)
		sale_total = (
			result.get('total_amount', 0.0) if isinstance(result, dict) else 0.0
		)

		popup = ctk.CTkToplevel(self)
		popup.title(f'Detalle Venta #{sale_id}')

		screen_height = self.winfo_screenheight()
		req_height = 320 + len(details) * 45
		ph = min(req_height, screen_height - 100)
		popup.geometry(f'560x{ph}')

		popup.configure(fg_color=SURFACE1)
		popup.attributes('-topmost', True)

		ctk.CTkLabel(
			popup,
			text=f'Artículos de la Venta  #{sale_id}',
			font=('Arial', 16, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(18, 10))

		scroll_container = ctk.CTkScrollableFrame(
			popup,
			fg_color=SURFACE2,
			border_color=BORDER,
			border_width=1,
			corner_radius=8,
		)
		scroll_container.pack(fill='both', expand=True, padx=20, pady=(0, 20))

		header = ctk.CTkFrame(scroll_container, fg_color='transparent')
		header.pack(fill='x', padx=10, pady=(10, 5))

		ctk.CTkLabel(header, text='Descripción', font=FONT_SMALL_BOLD, anchor='w').pack(
			side='left', fill='x', expand=True
		)
		ctk.CTkLabel(header, text='Cant', font=FONT_SMALL_BOLD, width=50).pack(
			side='left'
		)
		ctk.CTkLabel(header, text='P. Unit', font=FONT_SMALL_BOLD, width=80).pack(
			side='left'
		)
		ctk.CTkLabel(header, text='Subtotal', font=FONT_SMALL_BOLD, width=80).pack(
			side='left'
		)

		subtotal_items = 0.0
		for d in details:
			desc = d.get('description', 'Desconocido')
			raw_qty = float(d.get('quantity', 0))
			qty = f'{int(raw_qty)}' if raw_qty.is_integer() else f'{raw_qty:.2f}'
			price = float(d.get('unit_price', 0.0))
			subtotal = float(d.get('subtotal', 0.0))
			subtotal_items += subtotal

			row = ctk.CTkFrame(scroll_container, fg_color='transparent')
			row.pack(fill='x', padx=10, pady=2)

			ctk.CTkLabel(
				row, text=desc, font=FONT_SMALL, text_color=TEXT_SECONDARY, anchor='w'
			).pack(side='left', fill='x', expand=True)
			ctk.CTkLabel(
				row, text=f'x{qty}', font=FONT_SMALL, text_color=TEXT_PRIMARY, width=50
			).pack(side='left')
			ctk.CTkLabel(
				row,
				text=f'${price:.2f}',
				font=FONT_SMALL,
				text_color=TEXT_PRIMARY,
				width=80,
			).pack(side='left')
			ctk.CTkLabel(
				row,
				text=f'${subtotal:.2f}',
				font=FONT_SMALL_BOLD,
				text_color=TEXT_PRIMARY,
				width=80,
			).pack(side='left')

		ctk.CTkFrame(scroll_container, height=1, fg_color=BORDER).pack(
			fill='x', padx=10, pady=10
		)

		# ── Totals & Summary ──────────────────────────────────────────────
		if discount_amount > 0:
			summary = ctk.CTkFrame(scroll_container, fg_color='transparent')
			summary.pack(fill='x', padx=10, pady=2)
			ctk.CTkLabel(
				summary,
				text='Subtotal:',
				font=FONT_SMALL,
				text_color=TEXT_SECONDARY,
				anchor='e',
			).pack(side='left', fill='x', expand=True)
			ctk.CTkLabel(
				summary,
				text=f'${subtotal_items:.2f}',
				font=FONT_SMALL,
				width=80,
				anchor='e',
			).pack(side='right')

			summary2 = ctk.CTkFrame(scroll_container, fg_color='transparent')
			summary2.pack(fill='x', padx=10, pady=2)
			ctk.CTkLabel(
				summary2,
				text='Descuento:',
				font=FONT_SMALL,
				text_color=ORANGE_TEXT,
				anchor='e',
			).pack(side='left', fill='x', expand=True)
			ctk.CTkLabel(
				summary2,
				text=f'-${discount_amount:.2f}',
				font=FONT_SMALL_BOLD,
				text_color=ORANGE_TEXT,
				width=80,
				anchor='e',
			).pack(side='right')

		total_row = ctk.CTkFrame(scroll_container, fg_color='transparent')
		total_row.pack(fill='x', padx=10, pady=(8, 4))
		ctk.CTkLabel(
			total_row,
			text='TOTAL FINAL:',
			font=('Arial', 14, 'bold'),
			text_color=ACCENT_TEXT,
			anchor='e',
		).pack(side='left', fill='x', expand=True)
		ctk.CTkLabel(
			total_row,
			text=f'${sale_total:.2f}',
			font=('Arial', 14, 'bold'),
			text_color=ACCENT_TEXT,
			width=80,
			anchor='e',
		).pack(side='right')

		pm_frame = ctk.CTkFrame(scroll_container, fg_color=SURFACE3, corner_radius=6)
		pm_frame.pack(fill='x', padx=10, pady=(10, 10))

		if pay_method_2 and pay_amount_2 > 0:
			amount_1 = sale_total - pay_amount_2
			pm_text = f'Pago Mixto: {pay_method.capitalize()} (${amount_1:.2f}) + {pay_method_2.capitalize()} (${pay_amount_2:.2f})'
		else:
			pm_text = f'Método de Pago: {pay_method.capitalize()}'

		ctk.CTkLabel(
			pm_frame, text=pm_text, font=FONT_SMALL, text_color=TEXT_PRIMARY
		).pack(pady=8, padx=10)

		btn_close = ctk.CTkButton(
			popup,
			text='Cerrar',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_PRIMARY,
			command=popup.destroy,
		)
		btn_close.pack(pady=(0, 20))
