import csv
from tkinter import ttk

import customtkinter as ctk

from controllers.alerts_controller import AlertsController
from core.base_view import BaseView
from core.context import AppContext
from utils.settings_manager import get_reports_path
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_TITLE,
	GREEN_TEXT,
	ORANGE_TEXT,
	PAD_LG,
	PAD_MD,
	PAD_SM,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	TEXT_MUTED,
	TEXT_SECONDARY,
)


class AlertsView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = AlertsController(ctx.db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		# ── Header ────────────────────────────────────────────────────────
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(
			row=0, column=0, pady=(PAD_LG, PAD_SM), padx=PAD_LG, sticky='ew'
		)

		ctk.CTkLabel(
			header_frame,
			text='⚠️  Productos con Stock Crítico',
			font=FONT_TITLE,
			text_color=ORANGE_TEXT,
			anchor='w',
		).pack(side='left')

		self.lbl_count = ctk.CTkLabel(
			header_frame,
			text='Buscando...',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
		)
		self.lbl_count.pack(side='right', padx=(0, PAD_MD))

		self.btn_restock = ctk.CTkButton(
			header_frame,
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
		)
		self.btn_restock.pack(side='right', padx=(0, PAD_SM))

		ctk.CTkButton(
			header_frame,
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
			font=FONT_BODY_BOLD,
			command=self.load_data,
		).pack(side='right', padx=(0, PAD_SM))

		# ── Tabla ─────────────────────────────────────────────────────────
		self.table_frame = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.table_frame.grid(
			row=1, column=0, sticky='nsew', padx=PAD_LG, pady=(0, PAD_LG)
		)

		inner = ctk.CTkFrame(self.table_frame, fg_color='transparent')
		inner.pack(fill='both', expand=True, padx=PAD_MD, pady=PAD_MD)

		self.tree_scroll = ttk.Scrollbar(inner, orient='vertical')

		columns = ('Código', 'Producto', 'Stock Actual', 'Nivel de Alerta')
		self.tree = ttk.Treeview(
			inner,
			columns=columns,
			show='headings',
			height=20,
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		# Usamos el método de la BaseView para estilos base
		self.init_treeview(self.tree)

		for col in columns:
			self.tree.heading(col, text=col)
			width = 250 if col == 'Producto' else 120
			self.tree.column(col, anchor='center', width=width)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		# Tag específico para esta vista
		self.tree.tag_configure('critical', foreground=RED_TEXT)

		# Estado vacío oculto por defecto
		self.lbl_empty_state = ctk.CTkLabel(
			inner,
			text='✅\nNo hay productos con stock crítico.\nTodo está bajo control.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			justify='center',
		)

		self.load_data()

	def export_csv(self):
		"""Exporta los productos con stock crítico directamente a la carpeta de reportes configurada."""
		rows = [self.tree.item(iid, 'values') for iid in self.tree.get_children()]
		if not rows:
			self.show_warning('No hay alertas para exportar.', 'Sin datos')
			return

		try:
			import os
			from datetime import datetime

			filepath = os.path.join(
				get_reports_path(),
				f'alertas_stock_{datetime.now().strftime("%Y%m%d_%H%M")}.csv',
			)
			with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
				w = csv.writer(f)
				w.writerow(['Código', 'Producto', 'Stock Actual', 'Nivel de Alerta'])
				w.writerows(rows)

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

	def load_data(self):
		for item in self.tree.get_children():
			self.tree.delete(item)

		tenant_id = self.ctx.tenant_id
		low_stock_items = self.controller.get_low_stock_variants(tenant_id, threshold=5)

		for row_idx, item in enumerate(low_stock_items):
			stock_actual = item.get('stock', 0)
			stock_format = (
				f'{int(stock_actual)}'
				if float(stock_actual).is_integer()
				else f'{float(stock_actual):.2f}'
			)
			alerta_nivel = item.get('threshold', 5)
			is_zero = float(stock_actual) <= 0

			tags = ('critical',) if is_zero else ()
			nivel_label = (
				f'<= {alerta_nivel}  (AGOTADO)' if is_zero else f'<= {alerta_nivel}'
			)

			self.insert_tree_row(
				tree=self.tree,
				index=row_idx,
				values=(
					item.get('barcode', 'Sin código') or 'Sin código',
					item.get('name', 'Desconocido'),
					stock_format,
					nivel_label,
				),
				tags=tags,
			)

		cantidad = len(low_stock_items)
		if cantidad == 0:
			self.lbl_count.configure(
				text='¡Todo excelente!  No hay alertas.', text_color=GREEN_TEXT
			)
			self.tree.pack_forget()
			self.tree_scroll.pack_forget()
			self.lbl_empty_state.pack(expand=True)
		else:
			self.lbl_empty_state.pack_forget()
			if not self.tree.winfo_ismapped():
				self.tree_scroll.pack(side='right', fill='y')
				self.tree.pack(side='left', fill='both', expand=True)

			self.lbl_count.configure(
				text=f'{cantidad} artículos para reponer', text_color=RED_TEXT
			)
