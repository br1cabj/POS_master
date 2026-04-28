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
	TEXT_PRIMARY,
	apply_treeview_style,
)


class ArticleHistoryView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = ArticleController(ctx.db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		apply_treeview_style()

		# ── Header ────────────────────────────────────────────────────────
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='ew')

		ctk.CTkLabel(
			header_frame,
			text='🕵  Auditoría: Historial de Precios',
			font=('Arial', 22, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

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
		self.btn_refresh.pack(side='right')

		# ── Tabla ─────────────────────────────────────────────────────────
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
			width = 180 if col == 'Producto' else 120
			self.tree.column(col, anchor='center', width=width)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.tree.tag_configure('masivo', foreground=ORANGE_TEXT)
		self.tree.tag_configure('manual', foreground=ACCENT_TEXT)

		self.after(100, self.load_data)

	def load_data(self):
		for item in self.tree.get_children():
			self.tree.delete(item)

		tenant_id = self.ctx.tenant_id
		history = self.controller.get_price_history(tenant_id)

		for h in history:
			raw_date = h.get('date')
			date_str = (
				raw_date.strftime('%d/%m/%Y %H:%M')
				if hasattr(raw_date, 'strftime')
				else str(raw_date)
			)

			old_c, new_c = h.get('old_cost'), h.get('new_cost')
			old_p, new_p = h.get('old_price'), h.get('new_price')

			cost_str = (
				f'${float(old_c):.2f} → ${float(new_c):.2f}'
				if old_c is not None
				else '-'
			)
			price_str = (
				f'${float(old_p):.2f} → ${float(new_p):.2f}'
				if old_p is not None
				else '-'
			)

			action = h.get('action', '')
			tag = (
				'masivo'
				if action in ('AUMENTO MASIVO', 'REDUCCIÓN MASIVA')
				else 'manual'
			)

			self.tree.insert(
				'',
				'end',
				values=(
					date_str,
					h.get('user_name').capitalize(),
					h.get('action'),
					h.get('article_name'),
					cost_str,
					price_str,
				),
				tags=(tag,),
			)
