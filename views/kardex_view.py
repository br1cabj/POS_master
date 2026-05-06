from datetime import datetime
from tkinter import ttk

import customtkinter as ctk

from controllers.inventory_controller import InventoryController
from utils.date_picker import CTkDatePicker
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
	FONT_LABEL_BOLD,
	FONT_NAV_BOLD,
	GREEN_TEXT,
	ORANGE_TEXT,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	apply_treeview_style,
)


class KardexView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = InventoryController(ctx.db_engine)

		self.current_page = 1
		self.limit_per_page = 100

		# Filtros activos
		self.current_search = ''
		self.current_type = None
		self.current_date_from = None
		self.current_date_to = None

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(2, weight=1)  # El Treeview tomará el espacio

		apply_treeview_style()

		self._build_header()
		self._build_filters_and_summary()
		self._build_table()
		self._build_footer()

		self.after(100, self.load_data)

	# =========================================================
	# UI: ENCABEZADO
	# =========================================================
	def _build_header(self):
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='ew')

		ctk.CTkLabel(
			header_frame,
			text='📊  Kardex: Auditoría de Inventario',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

	# =========================================================
	# UI: FILTROS Y RESUMEN
	# =========================================================
	def _build_filters_and_summary(self):
		panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		panel.grid(row=1, column=0, sticky='ew', padx=20, pady=(0, 10))

		# ── Fila de Filtros ──
		f_row = ctk.CTkFrame(panel, fg_color='transparent')
		f_row.pack(fill='x', padx=16, pady=(16, 8))

		self.entry_search = ctk.CTkEntry(
			f_row,
			placeholder_text='🔍 Buscar producto...',
			width=220,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
		)
		self.entry_search.pack(side='left', padx=(0, 10))
		self.entry_search.bind('<Return>', lambda e: self.apply_filters())

		self.combo_type = ctk.CTkComboBox(
			f_row,
			values=['Todos', 'Entradas', 'Salidas', 'Ajustes'],
			width=130,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
		)
		self.combo_type.pack(side='left', padx=(0, 10))

		self.entry_from = CTkDatePicker(f_row, width=175, height=32)
		self.entry_from.pack(side='left', padx=(0, 10))
		self.entry_from.bind('<Return>', lambda e: self.apply_filters())

		self.entry_to = CTkDatePicker(f_row, width=175, height=32)
		self.entry_to.pack(side='left', padx=(0, 10))
		self.entry_to.bind('<Return>', lambda e: self.apply_filters())

		ctk.CTkButton(
			f_row,
			text='🔍 Filtrar',
			width=90,
			fg_color=ACCENT_DIM,
			text_color=ACCENT_TEXT,
			hover_color=ACCENT,
			border_width=1,
			border_color=ACCENT,
			command=self.apply_filters,
		).pack(side='left')

		ctk.CTkButton(
			f_row,
			text='↺ Limpiar',
			width=90,
			fg_color='transparent',
			text_color=TEXT_SECONDARY,
			hover_color=SURFACE3,
			command=self.clear_filters,
		).pack(side='left', padx=(5, 0))

		# ── Fila de Resumen (Totales) ──
		s_row = ctk.CTkFrame(panel, fg_color='transparent')
		s_row.pack(fill='x', padx=16, pady=(0, 16))

		self.lbl_tot_in = self._make_summary_card(s_row, 'Entradas (+)', GREEN_TEXT)
		self.lbl_tot_out = self._make_summary_card(s_row, 'Salidas (-)', RED_TEXT)
		self.lbl_tot_net = self._make_summary_card(
			s_row, 'Balance Neto (Vista)', TEXT_PRIMARY
		)

	def _make_summary_card(self, parent, title, color):
		card = ctk.CTkFrame(
			parent,
			fg_color=SURFACE3,
			corner_radius=8,
			border_width=1,
			border_color=BORDER,
		)
		card.pack(side='left', expand=True, fill='x', padx=5)

		ctk.CTkLabel(
			card, text=title, font=FONT_LABEL_BOLD, text_color=TEXT_MUTED
		).pack(pady=(8, 0))

		lbl_val = ctk.CTkLabel(card, text='0', font=FONT_BODY_BOLD, text_color=color)
		lbl_val.pack(pady=(0, 8))
		return lbl_val

	# =========================================================
	# UI: TABLA DE DATOS
	# =========================================================
	def _build_table(self):
		self.table_frame = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.table_frame.grid(row=2, column=0, sticky='nsew', padx=20, pady=(0, 10))

		inner = ctk.CTkFrame(self.table_frame, fg_color='transparent')
		inner.pack(fill='both', expand=True, padx=12, pady=12)

		self.tree_scroll = ttk.Scrollbar(inner, orient='vertical')

		self.columns = {
			'Fecha': {'width': 120, 'anchor': 'center'},
			'Tipo': {'width': 100, 'anchor': 'center'},
			'Producto': {'width': 280, 'anchor': 'w'},
			'Cantidad': {'width': 90, 'anchor': 'center'},
			'Referencia': {'width': 200, 'anchor': 'w'},
			'Usuario': {'width': 120, 'anchor': 'center'},
		}

		self.tree = ttk.Treeview(
			inner,
			columns=list(self.columns.keys()),
			show='headings',
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		for col, config in self.columns.items():
			self.tree.heading(col, text=col)
			self.tree.column(col, anchor=config['anchor'], width=config['width'])

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.tree.tag_configure('entrada', foreground=GREEN_TEXT)
		self.tree.tag_configure('salida', foreground=RED_TEXT)
		self.tree.tag_configure('ajuste', foreground=ORANGE_TEXT)

	# =========================================================
	# UI: PIE DE PÁGINA (PAGINACIÓN)
	# =========================================================
	def _build_footer(self):
		footer_frame = ctk.CTkFrame(self, fg_color='transparent')
		footer_frame.grid(row=3, column=0, pady=(0, 20), padx=20, sticky='ew')

		controls = ctk.CTkFrame(footer_frame, fg_color='transparent')
		controls.pack(anchor='center')

		self.btn_prev = ctk.CTkButton(
			controls,
			text='◀  Anterior',
			width=90,
			fg_color=SURFACE2,
			hover_color=SURFACE3,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=34,
			corner_radius=8,
			command=self.prev_page,
		)
		self.btn_prev.pack(side='left', padx=4)

		self.lbl_page = ctk.CTkLabel(
			controls,
			text=f'Página {self.current_page}',
			font=FONT_NAV_BOLD,
			text_color=TEXT_PRIMARY,
			width=80,
			anchor='center',
		)
		self.lbl_page.pack(side='left', padx=6)

		self.btn_next = ctk.CTkButton(
			controls,
			text='Siguiente  ▶',
			width=90,
			fg_color=SURFACE2,
			hover_color=SURFACE3,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=34,
			corner_radius=8,
			command=self.next_page,
		)
		self.btn_next.pack(side='left', padx=4)

	# =========================================================
	# LÓGICA Y DATOS
	# =========================================================
	def apply_filters(self):
		d_from = self.entry_from.get().strip()
		d_to = self.entry_to.get().strip()

		self.current_date_from = None
		self.current_date_to = None

		try:
			if d_from:
				self.current_date_from = datetime.strptime(d_from, '%d/%m/%Y').date()
			if d_to:
				self.current_date_to = datetime.strptime(d_to, '%d/%m/%Y').date()
		except ValueError:
			self.show_error(
				'Formato de fecha inválido. Usá DD/MM/AAAA.', 'Error de filtro'
			)
			return

		if (
			self.current_date_from
			and self.current_date_to
			and self.current_date_from > self.current_date_to
		):
			self.show_error(
				"La fecha 'Desde' no puede ser mayor a 'Hasta'.", 'Error de filtro'
			)
			return

		t_val = self.combo_type.get()
		if t_val == 'Entradas':
			self.current_type = 'in'
		elif t_val == 'Salidas':
			self.current_type = 'out'
		elif t_val == 'Ajustes':
			self.current_type = 'adj'
		else:
			self.current_type = None

		self.current_search = self.entry_search.get().strip()

		self.current_page = 1
		self.load_data()

	def clear_filters(self):
		self.entry_search.delete(0, 'end')
		self.entry_from.clear()
		self.entry_to.clear()
		self.combo_type.set('Todos')
		self.apply_filters()

	def prev_page(self):
		if self.current_page > 1:
			self.current_page -= 1
			self.load_data()

	def next_page(self):
		self.current_page += 1
		self.load_data()

	def load_data(self):
		for item in list(self.tree.get_children()):
			self.tree.delete(item)

		self.lbl_page.configure(text=f'Página {self.current_page}')
		self.btn_next.configure(state='disabled')
		self.btn_prev.configure(state='disabled')
		self.update_idletasks()

		# Solicitamos limit + 1 para saber si hay una página siguiente
		try:
			movements = self.controller.get_kardex(
				self.ctx.tenant_id,
				page=self.current_page,
				limit=self.limit_per_page + 1,
				search=self.current_search,
				mov_type=self.current_type,
				date_from=self.current_date_from,
				date_to=self.current_date_to,
			)
		except TypeError:
			# Fallback por si el controlador aún no soporta los nuevos parámetros de filtro
			movements = self.controller.get_kardex(
				self.ctx.tenant_id,
				page=self.current_page,
				limit=self.limit_per_page + 1,
			)

		# ── Lógica Look-Ahead ("Paginación fantasma") ──
		if len(movements) > self.limit_per_page:
			has_next = True
			movements_to_show = movements[: self.limit_per_page]
		else:
			has_next = False
			movements_to_show = movements

		self.btn_next.configure(state='normal' if has_next else 'disabled')
		self.btn_prev.configure(
			state='disabled' if self.current_page == 1 else 'normal'
		)

		tot_in = 0.0
		tot_out = 0.0

		for mov in movements_to_show:
			raw_date = mov.get('date')
			date_str = (
				raw_date.strftime('%d/%m/%Y %H:%M')
				if hasattr(raw_date, 'strftime')
				else str(raw_date)[:16]
			)

			mov_type = mov.get('movement_type')
			raw_qty = float(mov.get('quantity', 0))
			abs_qty = abs(raw_qty)

			sign_prefix = ''
			if mov_type == 'in':
				tipo, tag = '🟢 ENTRADA', 'entrada'
				sign_prefix = '+'
				tot_in += abs_qty
			elif mov_type == 'out':
				tipo, tag = '🔴 SALIDA', 'salida'
				sign_prefix = '-'
				tot_out += abs_qty
			else:
				tipo, tag = '🟡 AJUSTE', 'ajuste'
				sign_prefix = '+' if raw_qty > 0 else ''
				if raw_qty > 0:
					tot_in += abs_qty
				else:
					tot_out += abs_qty

			qty_formatted = f'{abs_qty:.3f}'.rstrip('0').rstrip('.')
			cantidad_final = f'{sign_prefix}{qty_formatted}'

			item_id = self.tree.insert(
				'',
				'end',
				values=(
					date_str,
					tipo,
					mov.get('article_name', 'Desconocido'),
					cantidad_final,
					mov.get('reference') or '-',
					mov.get('user_name', 'Sistema').capitalize(),
				),
			)
			self.tree.item(item_id, tags=(tag,))

		# Actualizar Tarjetas de Resumen
		net = tot_in - tot_out
		self.lbl_tot_in.configure(text=f'+{tot_in:g}')
		self.lbl_tot_out.configure(text=f'-{tot_out:g}')
		self.lbl_tot_net.configure(text=f'{net:+g}')
