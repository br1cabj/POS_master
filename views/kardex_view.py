from tkinter import ttk

import customtkinter as ctk

from controllers.inventory_controller import InventoryController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	FONT_NAV_BOLD,
	GREEN_TEXT,
	ORANGE_TEXT,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
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

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		apply_treeview_style()

		self._build_header()
		self._build_table()

		self.after(100, self.load_data)

	# =========================================================
	# UI: ENCABEZADO Y CONTROLES
	# =========================================================
	def _build_header(self):
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='ew')

		ctk.CTkLabel(
			header_frame,
			text='📊  Kardex: Auditoría de Inventario',
			font=('Arial', 22, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		controls_frame = ctk.CTkFrame(header_frame, fg_color='transparent')
		controls_frame.pack(side='right')

		self.btn_prev = ctk.CTkButton(
			controls_frame,
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
			controls_frame,
			text=f'Página {self.current_page}',
			font=FONT_NAV_BOLD,
			text_color=TEXT_PRIMARY,
			width=80,  # Ancho fijo para que los botones no salten al cambiar de dígito
			anchor='center',
		)
		self.lbl_page.pack(side='left', padx=6)

		self.btn_next = ctk.CTkButton(
			controls_frame,
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

		self.btn_refresh = ctk.CTkButton(
			controls_frame,
			text='↻  Actualizar',
			width=110,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=34,
			corner_radius=8,
			command=self.refresh_data,
		)
		self.btn_refresh.pack(side='left', padx=(12, 0))

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
		self.table_frame.grid(row=1, column=0, sticky='nsew', padx=20, pady=(0, 20))

		inner = ctk.CTkFrame(self.table_frame, fg_color='transparent')
		inner.pack(fill='both', expand=True, padx=12, pady=12)

		self.tree_scroll = ttk.Scrollbar(inner, orient='vertical')

		self.columns = {
			'Fecha': {'width': 120, 'anchor': 'center'},
			'Tipo': {'width': 100, 'anchor': 'center'},
			'Producto': {'width': 280, 'anchor': 'w'},  # Texto largo -> Izquierda
			'Cantidad': {'width': 90, 'anchor': 'center'},
			'Referencia': {'width': 200, 'anchor': 'w'},  # Texto largo -> Izquierda
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
	# LÓGICA Y DATOS
	# =========================================================
	def prev_page(self):
		if self.current_page > 1:
			self.current_page -= 1
			self.load_data()

	def next_page(self):
		self.current_page += 1
		self.load_data()

	def refresh_data(self):
		self.current_page = 1
		self.load_data()

	def load_data(self):
		for item in list(self.tree.get_children()):
			self.tree.delete(item)

		self.lbl_page.configure(text=f'Página {self.current_page}')

		# Deshabilitar controles temporalmente mientras carga (feedback visual)
		self.btn_next.configure(state='disabled')
		self.btn_prev.configure(state='disabled')

		movements = self.controller.get_kardex(
			self.ctx.tenant_id, page=self.current_page, limit=self.limit_per_page
		)

		if not movements and self.current_page > 1:
			self.current_page -= 1
			self.load_data()
			return

		# Reactivar botón Anterior si no estamos en la primera página
		self.btn_prev.configure(
			state='disabled' if self.current_page == 1 else 'normal'
		)

		if len(movements) == self.limit_per_page:
			self.btn_next.configure(state='normal')
		else:
			self.btn_next.configure(state='disabled')

		for mov in movements:
			raw_date = mov.get('date')
			date_str = (
				raw_date.strftime('%d/%m/%Y %H:%M')
				if hasattr(raw_date, 'strftime')
				else str(raw_date)[:16]  # Fallback seguro
			)

			mov_type = mov.get('movement_type')
			raw_qty = float(mov.get('quantity', 0))

			sign_prefix = ''
			if mov_type == 'in':
				tipo, tag = '🟢 ENTRADA', 'entrada'
				sign_prefix = '+'
			elif mov_type == 'out':
				tipo, tag = '🔴 SALIDA', 'salida'
				sign_prefix = '-'
			else:
				tipo, tag = '🟡 AJUSTE', 'ajuste'
				# Los ajustes pueden ser positivos o negativos, usamos el número tal cual
				sign_prefix = '+' if raw_qty > 0 else ''

			qty_formatted = f'{abs(raw_qty):.3f}'.rstrip('0').rstrip('.')
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
