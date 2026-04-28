"""
views/article_history_view.py
==============================
Vista de auditoría de historial de precios.
Permite visualizar, filtrar y exportar los cambios de costo y precio de los artículos.
"""

import csv
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from tkinter import filedialog, ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.article_controller import ArticleController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	GREEN,
	GREEN_TEXT,
	ORANGE_TEXT,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	TEXT_MUTED,
	TEXT_PRIMARY,
	apply_treeview_style,
)


class ArticleHistoryView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = ArticleController(ctx.db_engine)

		self._full_history = []
		self._current_filtered_data = []
		self._search_timer = None

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		apply_treeview_style()

		self._build_header()
		self._build_table()

		self.after(100, self.load_data)

	def _build_header(self):
		"""Construye el encabezado con el título, buscador y botones de acción."""
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='ew')
		header_frame.grid_columnconfigure(1, weight=1)

		title_box = ctk.CTkFrame(header_frame, fg_color='transparent')
		title_box.grid(row=0, column=0, sticky='w')

		ctk.CTkLabel(
			title_box,
			text='🕵  Auditoría: Historial de Precios',
			font=('Arial', 22, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(anchor='w')

		self.lbl_count = ctk.CTkLabel(
			title_box,
			text='Cargando registros...',
			font=('Arial', 11),
			text_color=TEXT_MUTED,
		)
		self.lbl_count.pack(anchor='w')

		self.entry_search = ctk.CTkEntry(
			header_frame,
			placeholder_text='🔍 Buscar producto, usuario o acción...',
			fg_color=SURFACE2,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			height=36,
			width=300,
		)
		self.entry_search.grid(row=0, column=1, padx=20, sticky='e')
		self.entry_search.bind('<KeyRelease>', self._debounced_search)

		btn_box = ctk.CTkFrame(header_frame, fg_color='transparent')
		btn_box.grid(row=0, column=2, sticky='e')

		self.btn_export = ctk.CTkButton(
			btn_box,
			text='📥  Exportar CSV',
			fg_color=SURFACE3,
			hover_color=SURFACE2,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			width=120,
			height=36,
			corner_radius=8,
			command=self.export_to_csv,
		)
		self.btn_export.pack(side='left', padx=(0, 10))

		self.btn_refresh = ctk.CTkButton(
			btn_box,
			text='↻  Actualizar',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			width=120,
			height=36,
			corner_radius=8,
			command=self.load_data,
		)
		self.btn_refresh.pack(side='left')

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
			width = 240 if col == 'Producto' else 150
			anchor = 'w' if col == 'Producto' else 'center'
			self.tree.column(col, anchor=anchor, width=width)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.tree.tag_configure('aumento', foreground=ORANGE_TEXT)
		self.tree.tag_configure('baja', foreground=RED_TEXT)
		self.tree.tag_configure('neutro', foreground=TEXT_MUTED)
		self.tree.tag_configure('normal', foreground=TEXT_PRIMARY)

	def load_data(self):
		"""Obtiene el historial completo desde la base de datos y refresca la vista."""
		if not self.winfo_exists():
			return

		tenant_id = self.ctx.tenant_id
		self._full_history = self.controller.get_price_history(tenant_id)

		self.entry_search.delete(0, 'end')
		self._current_filtered_data = self._full_history
		self._render_table(self._current_filtered_data)

	def _debounced_search(self, event=None):
		if self._search_timer:
			self.after_cancel(self._search_timer)
		self._search_timer = self.after(300, self._filter_data)

	def _filter_data(self):
		if not self.winfo_exists():
			return

		q = self.entry_search.get().lower().strip()
		if not q:
			self._current_filtered_data = self._full_history
		else:
			self._current_filtered_data = [
				h
				for h in self._full_history
				if q in (h.get('article_name') or '').lower()
				or q in (h.get('user_name') or '').lower()
				or q in (h.get('action') or '').lower()
			]

		self._render_table(self._current_filtered_data)

	def _format_money(self, value) -> str:
		if value is None:
			return '-'
		try:
			dec_val = Decimal(str(value))
			return f'${dec_val:,.2f}'
		except (ValueError, InvalidOperation):
			return '-'

	def _render_table(self, data: list):
		"""Dibuja los registros filtrados en el Treeview con tags de colores semánticos."""
		for item in self.tree.get_children():
			self.tree.delete(item)

		total_mostrados = len(data)
		self.lbl_count.configure(text=f'Mostrando {total_mostrados} registros')

		for h in data:
			raw_date = h.get('date')
			date_str = (
				raw_date.strftime('%d/%m/%Y %H:%M')
				if hasattr(raw_date, 'strftime')
				else str(raw_date)
			)

			old_c, new_c = h.get('old_cost'), h.get('new_cost')
			old_p, new_p = h.get('old_price'), h.get('new_price')

			cost_str = f'{self._format_money(old_c)} → {self._format_money(new_c)}'
			price_str = f'{self._format_money(old_p)} → {self._format_money(new_p)}'

			action = h.get('action', '')

			color_tag = 'normal'
			if 'AUMENTO' in action.upper():
				color_tag = 'aumento'
			elif 'REDUCCIÓN' in action.upper() or 'BAJA' in action.upper():
				color_tag = 'baja'
			elif old_c == new_c and old_p == new_p:
				color_tag = 'neutro'

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
				tags=(color_tag,),
			)

	def export_to_csv(self):
		"""Exporta los datos actualmente visibles en la tabla a un archivo CSV para el contador."""
		if not self._current_filtered_data:
			CTkMessagebox(
				title='Aviso', message='No hay datos para exportar.', icon='info'
			)
			return

		desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
		if not os.path.exists(desktop_path):
			desktop_path = os.path.join(
				os.path.expanduser('~'), 'Escritorio'
			)  # Fallback

		default_filename = (
			f'auditoria_precios_{datetime.now().strftime("%Y%m%d_%H%M")}.csv'
		)
		filepath = filedialog.asksaveasfilename(
			initialdir=desktop_path,
			defaultextension='.csv',
			initialfile=default_filename,
			title='Guardar auditoría como...',
			filetypes=[('Archivos CSV', '*.csv'), ('Todos los archivos', '*.*')],
		)

		if not filepath:
			return

		try:
			with open(filepath, mode='w', newline='', encoding='utf-8') as file:
				writer = csv.writer(file, delimiter=';')
				# Escribir cabeceras
				writer.writerow(
					[
						'Fecha',
						'Usuario',
						'Acción',
						'Producto',
						'Costo Anterior',
						'Costo Nuevo',
						'Precio Venta Anterior',
						'Precio Venta Nuevo',
					]
				)

				# Escribir datos
				for h in self._current_filtered_data:
					raw_date = h.get('date')
					date_str = (
						raw_date.strftime('%Y-%m-%d %H:%M')
						if hasattr(raw_date, 'strftime')
						else str(raw_date)
					)
					writer.writerow(
						[
							date_str,
							h.get('user_name', '').capitalize(),
							h.get('action', ''),
							h.get('article_name', ''),
							h.get('old_cost', 0),
							h.get('new_cost', 0),
							h.get('old_price', 0),
							h.get('new_price', 0),
						]
					)

			CTkMessagebox(
				title='¡Archivo Guardado!',
				message=f'El historial de precios se exportó correctamente a:\n{filepath}',
				icon='check',
			)
		except Exception as e:
			CTkMessagebox(
				title='Error',
				message=f'No se pudo exportar el archivo:\n{e}',
				icon='cancel',
			)
