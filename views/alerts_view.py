import csv
from tkinter import ttk

import customtkinter as ctk

from controllers.alerts_controller import AlertsController
from core.base_view import BaseView
from core.context import AppContext
from utils.settings_manager import get_reports_path
from utils.csv_utils import safe_spreadsheet_text
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_LABEL,
	FONT_TITLE,
	ORANGE_DIM,
	ORANGE_TEXT,
	PAD_LG,
	PAD_MD,
	PAD_SM,
	RED_DIM,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	apply_treeview_style,
)


class AlertsView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = AlertsController(ctx.db_engine)

		self._all_items: list = []
		self._active_filter = 'all'
		self._sort_col: str | None = None
		self._sort_asc = True
		self._filter_buttons: dict = {}
		self._card_labels: dict = {}

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(2, weight=1)

		apply_treeview_style()

		self._build_header()
		self._build_summary_and_filters()
		self._build_table()

		self.after(50, self.load_data)

	# =========================================================
	# CONSTRUCCIÓN DE LA UI
	# =========================================================
	def _build_header(self):
		header = ctk.CTkFrame(self, fg_color='transparent')
		header.grid(row=0, column=0, pady=(PAD_LG, PAD_SM), padx=PAD_LG, sticky='ew')

		ctk.CTkLabel(
			header,
			text='⚠️  Alertas de Stock',
			font=FONT_TITLE,
			text_color=ORANGE_TEXT,
			anchor='w',
		).pack(side='left')

		ctk.CTkButton(
			header,
			text='📥  Ir a Compras',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			width=140,
			height=34,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self._go_to_purchases,
		).pack(side='right', padx=(0, PAD_SM))

		ctk.CTkButton(
			header,
			text='📄  Exportar CSV',
			fg_color=SURFACE2,
			hover_color=SURFACE3,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			width=130,
			height=34,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self.export_csv,
		).pack(side='right', padx=(0, PAD_SM))

		ctk.CTkButton(
			header,
			text='↻  Actualizar',
			fg_color=SURFACE2,
			hover_color=SURFACE3,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			width=110,
			height=34,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self.load_data,
		).pack(side='right', padx=(0, PAD_SM))

		# ── Campo de umbral configurable ──
		threshold_frame = ctk.CTkFrame(
			header,
			fg_color=SURFACE2,
			corner_radius=8,
			border_width=1,
			border_color=BORDER,
		)
		threshold_frame.pack(side='right', padx=(0, PAD_MD))

		ctk.CTkLabel(
			threshold_frame,
			text='Alertar con menos de',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(side='left', padx=(12, 4), pady=7)

		self._threshold_var = ctk.StringVar(master=self, value='5')
		self._last_threshold = '5'
		entry = ctk.CTkEntry(
			threshold_frame,
			textvariable=self._threshold_var,
			width=46,
			height=28,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			justify='center',
		)
		entry.pack(side='left', pady=7)
		self._threshold_entry = entry
		entry.bind('<Return>', lambda e: self.load_data())
		entry.bind('<FocusOut>', lambda e: self._load_if_changed())

		ctk.CTkLabel(
			threshold_frame,
			text='unidades',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(side='left', padx=(4, 12), pady=7)

	def _build_summary_and_filters(self):
		row_frame = ctk.CTkFrame(self, fg_color='transparent')
		row_frame.grid(row=1, column=0, padx=PAD_LG, pady=(0, PAD_SM), sticky='ew')
		row_frame.grid_columnconfigure(3, weight=1)

		# ── Tarjetas de resumen ──
		cards = [
			('agotado', '🔴 Agotados', RED_DIM, RED_TEXT),
			('critico', '🟠 Críticos', ORANGE_DIM, ORANGE_TEXT),
			('alerta', '🟡 En alerta', SURFACE2, TEXT_SECONDARY),
		]
		for col, (key, label, bg, fg) in enumerate(cards):
			card = ctk.CTkFrame(
				row_frame,
				fg_color=bg,
				corner_radius=10,
				border_width=1,
				border_color=BORDER,
				cursor='hand2',
			)
			card.grid(row=0, column=col, padx=(0, PAD_SM), sticky='nsew')
			card.bind('<Button-1>', lambda e, k=key: self._set_filter(k))

			lbl_n = ctk.CTkLabel(
				card,
				text='0',
				font=('Arial', 26, 'bold'),
				text_color=fg,
				cursor='hand2',
			)
			lbl_n.pack(pady=(12, 2))
			lbl_n.bind('<Button-1>', lambda e, k=key: self._set_filter(k))
			lbl_cat = ctk.CTkLabel(
				card, text=label, font=FONT_LABEL, text_color=fg, cursor='hand2'
			)
			lbl_cat.pack(pady=(0, 12))
			lbl_cat.bind('<Button-1>', lambda e, k=key: self._set_filter(k))
			self._card_labels[key] = lbl_n

		# ── Botones de filtro ──
		filter_frame = ctk.CTkFrame(row_frame, fg_color='transparent')
		filter_frame.grid(row=0, column=3, sticky='e')

		ctk.CTkLabel(
			filter_frame, text='Filtrar:', font=FONT_LABEL, text_color=TEXT_MUTED
		).pack(side='left', padx=(0, PAD_SM))

		for key, label in (
			('all', 'Todos'),
			('agotado', 'Agotados'),
			('critico', 'Críticos'),
			('alerta', 'En alerta'),
		):
			btn = ctk.CTkButton(
				filter_frame,
				text=label,
				fg_color=SURFACE2,
				hover_color=SURFACE3,
				text_color=TEXT_SECONDARY,
				border_width=1,
				border_color=BORDER,
				width=90,
				height=30,
				corner_radius=6,
				font=FONT_BODY,
				command=lambda k=key: self._set_filter(k),
			)
			btn.pack(side='left', padx=(0, 4))
			self._filter_buttons[key] = btn

		self._highlight_filter('all')

	def _build_table(self):
		table_frame = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		table_frame.grid(row=2, column=0, sticky='nsew', padx=PAD_LG, pady=(0, PAD_LG))

		inner = ctk.CTkFrame(table_frame, fg_color='transparent')
		inner.pack(fill='both', expand=True, padx=PAD_MD, pady=PAD_MD)

		self.tree_scroll = ttk.Scrollbar(inner, orient='vertical')

		columns = ('Código', 'Producto', 'Stock', 'Urgencia')
		self.tree = ttk.Treeview(
			inner,
			columns=columns,
			show='headings',
			height=20,
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)
		self.init_treeview(self.tree)

		col_widths = {'Código': 110, 'Producto': 340, 'Stock': 90, 'Urgencia': 110}
		col_anchors = {
			'Código': 'center',
			'Producto': 'w',
			'Stock': 'center',
			'Urgencia': 'center',
		}
		for col in columns:
			self.tree.column(col, anchor=col_anchors[col], width=col_widths[col])
			self.tree.heading(col, text=col, command=lambda c=col: self._sort_by(c))

		self.tree.tag_configure('agotado', foreground=RED_TEXT)
		self.tree.tag_configure('critico', foreground=ORANGE_TEXT)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.lbl_empty_state = ctk.CTkLabel(
			inner,
			text='✅\nNo hay productos con stock crítico.\nTodo está bajo control.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			justify='center',
		)

	# =========================================================
	# LÓGICA
	# =========================================================
	def _get_threshold(self) -> int:
		try:
			raw = int(self._threshold_var.get())
			val = max(1, raw)
			if (
				hasattr(self, '_threshold_entry')
				and self._threshold_entry.winfo_exists()
			):
				if raw < 1:
					self._threshold_entry.configure(border_color='#f97316')
				else:
					self._threshold_entry.configure(border_color=BORDER_ACTIVE)
			return val
		except ValueError:
			if (
				hasattr(self, '_threshold_entry')
				and self._threshold_entry.winfo_exists()
			):
				self._threshold_entry.configure(border_color='#ef4444')
			return 5

	def _severity(self, stock: float, threshold: int = 5) -> tuple[str, str]:
		if stock <= 0:
			return 'agotado', 'AGOTADO'
		critical_limit = max(1, round(threshold * 0.3))
		if stock <= critical_limit:
			return 'critico', 'CRÍTICO'
		return 'alerta', 'ALERTA'

	def _set_filter(self, key: str):
		self._active_filter = key
		self._highlight_filter(key)
		self._apply_display()

	def _highlight_filter(self, active: str):
		for key, btn in self._filter_buttons.items():
			if key == active:
				btn.configure(
					fg_color=ACCENT_DIM, border_color=ACCENT, text_color=ACCENT_TEXT
				)
			else:
				btn.configure(
					fg_color=SURFACE2, border_color=BORDER, text_color=TEXT_SECONDARY
				)

	def _sort_by(self, col: str):
		if self._sort_col == col:
			self._sort_asc = not self._sort_asc
		else:
			self._sort_col = col
			self._sort_asc = True
		self._refresh_headings()
		self._apply_display()

	def _refresh_headings(self):
		arrow_map = {True: '▲', False: '▼'}
		for col in ('Código', 'Producto', 'Stock', 'Urgencia'):
			arrow = f'  {arrow_map[self._sort_asc]}' if col == self._sort_col else ''
			self.tree.heading(
				col, text=f'{col}{arrow}', command=lambda c=col: self._sort_by(c)
			)

	def _apply_display(self):
		# Filtrar
		if self._active_filter == 'agotado':
			items = [i for i in self._all_items if float(i['stock']) <= 0]
		elif self._active_filter == 'critico':
			items = [i for i in self._all_items if i['_sev_key'] == 'critico']
		elif self._active_filter == 'alerta':
			items = [i for i in self._all_items if i['_sev_key'] == 'alerta']
		else:
			items = list(self._all_items)

		# Ordenar
		if self._sort_col:
			reverse = not self._sort_asc
			sev_order = {'agotado': 0, 'critico': 1, 'alerta': 2}
			key_fns = {
				'Stock': lambda x: float(x['stock']),
				'Producto': lambda x: x['_label'].lower(),
				'Código': lambda x: (x.get('barcode') or '').lower(),
				'Urgencia': lambda x: sev_order.get(x['_sev_key'], 3),
			}
			if self._sort_col in key_fns:
				items.sort(key=key_fns[self._sort_col], reverse=reverse)

		# Renderizar
		for row in self.tree.get_children():
			self.tree.delete(row)

		for idx, item in enumerate(items):
			stock = float(item['stock'])
			stock_str = f'{int(stock)}' if stock == int(stock) else f'{stock:.2f}'
			sev_key = item['_sev_key']
			tags = (sev_key,) if sev_key in ('agotado', 'critico') else ()
			self.insert_tree_row(
				tree=self.tree,
				index=idx,
				values=(
					item.get('barcode') or 'Sin código',
					item['_label'],
					stock_str,
					item['_sev_label'],
				),
				tags=tags,
			)

		# Empty state
		if not items:
			self.tree.pack_forget()
			self.tree_scroll.pack_forget()
			if self._active_filter != 'all':
				self.lbl_empty_state.configure(
					text='🔍\nNingún artículo coincide con el filtro aplicado.'
				)
			else:
				self.lbl_empty_state.configure(
					text='✅\nNo hay productos con stock crítico.\nTodo está bajo control.'
				)
			self.lbl_empty_state.pack(expand=True)
		else:
			self.lbl_empty_state.pack_forget()
			if not self.tree.winfo_ismapped():
				self.tree_scroll.pack(side='right', fill='y')
				self.tree.pack(side='left', fill='both', expand=True)

	def _update_cards(self):
		agotados = sum(1 for i in self._all_items if i['_sev_key'] == 'agotado')
		criticos = sum(1 for i in self._all_items if i['_sev_key'] == 'critico')
		alertas = sum(1 for i in self._all_items if i['_sev_key'] == 'alerta')
		self._card_labels['agotado'].configure(text=str(agotados))
		self._card_labels['critico'].configure(text=str(criticos))
		self._card_labels['alerta'].configure(text=str(alertas))

	def _load_if_changed(self):
		current = self._threshold_var.get()
		if current != self._last_threshold:
			self._last_threshold = current
			self.load_data()

	def load_data(self):
		threshold = self._get_threshold()
		raw = self.controller.get_low_stock_variants(
			self.ctx.tenant_id, threshold=threshold
		)

		self._all_items = []
		for item in raw:
			parts = [item['name']]
			if item.get('attribute_1'):
				parts.append(item['attribute_1'])
			if item.get('attribute_2'):
				parts.append(item['attribute_2'])
			label = ' — '.join(parts)
			sev_key, sev_label = self._severity(float(item['stock']), threshold)
			self._all_items.append(
				{
					**item,
					'_label': label,
					'_sev_key': sev_key,
					'_sev_label': sev_label,
				}
			)

		self._update_cards()
		self._apply_display()

	def export_csv(self):
		rows = [self.tree.item(iid, 'values') for iid in self.tree.get_children()]
		if not rows:
			self.show_warning('No hay alertas para exportar.', 'Sin datos')
			return
		try:
			import os
			from datetime import datetime

			filepath = os.path.join(
				get_reports_path(),
				f'alertas_stock_{datetime.now().strftime("%Y%m%d_%H%M%S_%f")}.csv',
			)
			with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
				w = csv.writer(f, delimiter=';')
				w.writerow(['Código', 'Producto', 'Stock', 'Urgencia'])
				w.writerows(
					[
						safe_spreadsheet_text(row[0]),
						safe_spreadsheet_text(row[1]),
						row[2],
						safe_spreadsheet_text(row[3]),
					]
					for row in rows
				)
			self.show_success(f'Guardado en:\n{filepath}', 'Exportado')
		except Exception as e:
			self.show_error(f'No se pudo exportar: {e}')

	def _go_to_purchases(self):
		navigate = getattr(self.ctx, 'navigate', None)
		if navigate:
			from views.purchases_view import PurchasesView

			navigate(PurchasesView, requires_admin=True)
		else:
			self.show_warning(
				'Ve a la sección Compras para reponer el producto seleccionado.',
				'Reponer Stock',
			)
