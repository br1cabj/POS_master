"""
views/article_history_view.py
==============================
Vista de auditoría de historial de precios.
Permite visualizar y filtrar los cambios de costo y precio de los artículos.
"""

from decimal import Decimal, InvalidOperation
from tkinter import ttk

import customtkinter as ctk

from controllers.article_controller import ArticleController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	ORANGE_TEXT,
	SURFACE2,
	SURFACE3,
	TEXT_PRIMARY,
	apply_treeview_style,
)


class ArticleHistoryView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = ArticleController(ctx.db_engine)

		self._full_history = []
		self._search_timer = None

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		apply_treeview_style()

		self._build_header()
		self._build_table()

		self.after(100, self.load_data)

	def _build_header(self):
		"""Construye el encabezado con el título, buscador y botón de actualización."""
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='ew')
		header_frame.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(
			header_frame,
			text='🕵  Auditoría: Historial de Precios',
			font=('Arial', 22, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).grid(row=0, column=0, sticky='w')

		self.entry_search = ctk.CTkEntry(
			header_frame,
			placeholder_text='🔍 Buscar producto, usuario o acción...',
			fg_color=SURFACE2,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			height=34,
			width=300,
		)
		self.entry_search.grid(row=0, column=1, padx=20, sticky='e')
		self.entry_search.bind('<KeyRelease>', self._debounced_search)

		self.btn_refresh = ctk.CTkButton(
			header_frame,
			text='↻  Actualizar',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			width=120,
			height=34,
			corner_radius=8,
			command=self.load_data,
		)
		self.btn_refresh.grid(row=0, column=2, sticky='e')

	def _build_table(self):
		"""Construye y configura el contenedor del Treeview y sus columnas."""
		self.table_container = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.table_container.grid(row=1, column=0, sticky='nsew', padx=20, pady=(0, 20))

		inner = ctk.CTkFrame(self.table_container, fg_color='transparent')
		inner.pack(fill='both', expand=True, padx=12, pady=12)

		self.tree_scroll = ttk.Scrollbar(inner, orient='vertical')

		columns = (
			'Fecha',
			'Usuario',
			'Acción',
			'Producto',
			'Costo (Ant → Nuevo)',
			'Venta (Ant → Nuevo)',
		)
		self.tree = ttk.Treeview(
			inner,
			columns=columns,
			show='headings',
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		for col in columns:
			self.tree.heading(col, text=col)
			width = 220 if col == 'Producto' else 140
			anchor = 'w' if col == 'Producto' else 'center'
			self.tree.column(col, anchor=anchor, width=width)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.tree.tag_configure('odd', background=SURFACE2)
		self.tree.tag_configure('even', background=SURFACE3)
		self.tree.tag_configure('masivo', foreground=ORANGE_TEXT)
		self.tree.tag_configure('manual', foreground=ACCENT_TEXT)

	def load_data(self):
		"""Obtiene el historial completo desde la base de datos y refresca la vista."""
		if not self.winfo_exists():
			return

		tenant_id = self.ctx.tenant_id
		self._full_history = self.controller.get_price_history(tenant_id)

		self.entry_search.delete(0, 'end')
		self._render_table(self._full_history)

	def _debounced_search(self, event=None):
		"""Retrasa la ejecución del filtro para optimizar el rendimiento al escribir."""
		if self._search_timer:
			self.after_cancel(self._search_timer)
		self._search_timer = self.after(300, self._filter_data)

	def _filter_data(self):
		"""Filtra los registros en memoria según el texto de búsqueda."""
		if not self.winfo_exists():
			return

		q = self.entry_search.get().lower().strip()
		if not q:
			self._render_table(self._full_history)
			return

		filtered = [
			h
			for h in self._full_history
			if q in (h.get('article_name') or '').lower()
			or q in (h.get('user_name') or '').lower()
			or q in (h.get('action') or '').lower()
		]
		self._render_table(filtered)

	def _format_money(self, value) -> str:
		"""Formatea de manera segura un valor numérico a moneda utilizando Decimal."""
		if value is None:
			return '-'
		try:
			dec_val = Decimal(str(value))
			return f'${dec_val:,.2f}'
		except (ValueError, InvalidOperation):
			return '-'

	def _render_table(self, data: list):
		"""Dibuja los registros filtrados en el Treeview con formato cebra y tags de colores."""
		for item in self.tree.get_children():
			self.tree.delete(item)

		for idx, h in enumerate(data):
			raw_date = h.get('date')
			date_str = (
				raw_date.strftime('%d/%m/%Y %H:%M')
				if hasattr(raw_date, 'strftime')
				else str(raw_date)
			)

			cost_str = f'{self._format_money(h.get("old_cost"))} → {self._format_money(h.get("new_cost"))}'
			price_str = f'{self._format_money(h.get("old_price"))} → {self._format_money(h.get("new_price"))}'

			action = h.get('action', '')

			# Combinar el tag de cebra con el tag de color semántico
			bg_tag = 'odd' if idx % 2 == 0 else 'even'
			color_tag = (
				'masivo'
				if action in ('AUMENTO MASIVO', 'REDUCCIÓN MASIVA')
				else 'manual'
			)

			self.tree.insert(
				'',
				'end',
				values=(
					date_str,
					h.get('user_name', '').capitalize(),
					action,
					h.get('article_name', ''),
					cost_str,
					price_str,
				),
				tags=(bg_tag, color_tag),
			)
