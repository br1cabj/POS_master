"""
views/dollar_price_view.py
==========================
Módulo de actualización de precios por tipo de cambio del dólar.

Flujo de usuario:
  1. Elegir tipo de cotización (Blue / Oficial / MEP).
  2. Ingresar la cotización del día.
  3. Ajustar el margen de ganancia si hace falta.
  4. Ver el preview en vivo en la tabla derecha.
  5. Presionar "ACTUALIZAR PRECIOS" — listo.

Para que un producto aparezca en el recálculo, primero debe tener asignado
su precio en dólares (doble clic o botón "Asignar US$").
"""

import logging
from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.dollar_price_controller import DollarPriceController
from core.base_view import BaseView
from core.context import AppContext
from utils import settings_manager as cfg
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
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

_DOLLAR_TYPES = ['Blue', 'Oficial', 'MEP']
_TYPE_STYLE = {
	'Blue': {'dim': ACCENT_DIM, 'text': ACCENT_TEXT, 'border': ACCENT},
	'Oficial': {'dim': GREEN_DIM, 'text': GREEN_TEXT, 'border': GREEN},
	'MEP': {'dim': ORANGE_DIM, 'text': ORANGE_TEXT, 'border': ORANGE},
}
_FILTER_OPTIONS = ['Todos', 'Con precio USD', 'Sin precio USD']


class DollarPriceView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = DollarPriceController(ctx.db_engine)
		self._all_variants: list = []
		self._cfg = cfg.load()

		# Filas: 0 = header, 1 = contenido principal
		self.grid_rowconfigure(0, weight=0)
		self.grid_rowconfigure(1, weight=1)
		self.grid_columnconfigure(0, weight=1)

		apply_treeview_style()
		self._build_header()
		self._build_body()

		self.after(120, self._load_data)

	# ═══════════════════════════════════════════════════════
	# HELPERS
	# ═══════════════════════════════════════════════════════

	def _current_rate(self) -> float:
		try:
			return max(
				0.0,
				float(self.entry_rate.get().replace(',', '.').replace(' ', '') or '0'),
			)
		except ValueError:
			return 0.0

	def _current_margin(self) -> float:
		try:
			return max(
				0.0,
				float(
					self.entry_margin.get().replace(',', '.').replace(' ', '') or '0'
				),
			)
		except ValueError:
			return 0.0

	def _current_type(self) -> str:
		return self._type_var.get()

	def _with_usd_count(self) -> int:
		return sum(
			1
			for v in self._all_variants
			if v.get('cost_price_usd') is not None and v['cost_price_usd'] > 0
		)

	# ═══════════════════════════════════════════════════════
	# HEADER
	# ═══════════════════════════════════════════════════════
	def _build_header(self):
		hdr = ctk.CTkFrame(self, fg_color=SURFACE2, corner_radius=0, border_width=0)
		hdr.grid(row=0, column=0, sticky='ew')

		inner = ctk.CTkFrame(hdr, fg_color='transparent')
		inner.pack(fill='x', padx=20, pady=14)

		# Título + descripción
		left = ctk.CTkFrame(inner, fg_color='transparent')
		left.pack(side='left', fill='y')

		ctk.CTkLabel(
			left,
			text='💵  Precios al Dólar',
			font=('Arial', 20, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(anchor='w')

		self.lbl_header_sub = ctk.CTkLabel(
			left,
			text='Actualizá todos tus precios con un solo clic cuando sube el dólar.',
			font=('Arial', 11),
			text_color=TEXT_MUTED,
			anchor='w',
		)
		self.lbl_header_sub.pack(anchor='w', pady=(2, 0))

		# Chips de estado (derecha)
		right = ctk.CTkFrame(inner, fg_color='transparent')
		right.pack(side='right', fill='y')

		self.chip_linked = self._make_chip(right, '0 vinculados', GREEN_DIM, GREEN_TEXT)
		self.chip_linked.pack(side='left', padx=(0, 8))

		self.chip_unlinked = self._make_chip(
			right, '0 sin asignar', SURFACE3, TEXT_SECONDARY
		)
		self.chip_unlinked.pack(side='left', padx=(0, 16))

		ctk.CTkButton(
			right,
			text='↻  Recargar',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=32,
			width=100,
			corner_radius=8,
			font=('Arial', 11),
			command=self._load_data,
		).pack(side='left')

	def _make_chip(self, parent, text: str, bg: str, fg: str) -> ctk.CTkLabel:
		return ctk.CTkLabel(
			parent,
			text=text,
			font=('Arial', 10, 'bold'),
			fg_color=bg,
			text_color=fg,
			corner_radius=6,
			padx=10,
			pady=4,
		)

	# ═══════════════════════════════════════════════════════
	# BODY  (panel izq. + panel der.)
	# ═══════════════════════════════════════════════════════
	def _build_body(self):
		body = ctk.CTkFrame(self, fg_color='transparent')
		body.grid(row=1, column=0, sticky='nsew', padx=16, pady=12)
		body.grid_columnconfigure(0, weight=0)
		body.grid_columnconfigure(1, weight=1)
		body.grid_rowconfigure(0, weight=1)

		self._build_left_panel(body)
		self._build_right_panel(body)

	# ───────────────────────────────────────────────────────
	# PANEL IZQUIERDO — configuración y acción
	# ───────────────────────────────────────────────────────
	def _build_left_panel(self, parent):
		outer = ctk.CTkFrame(
			parent,
			fg_color=SURFACE2,
			corner_radius=14,
			border_width=1,
			border_color=BORDER,
		)
		outer.grid(row=0, column=0, sticky='nsew', padx=(0, 10))

		# Scroll interno (por si la ventana es muy pequeña)
		scroll = ctk.CTkScrollableFrame(
			outer,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
			width=268,
		)
		scroll.pack(fill='both', expand=True, padx=0, pady=0)

		# ── 1. Tipo de cotización ────────────────────────
		self._section_label(scroll, 'TIPO DE COTIZACIÓN')

		self._type_var = ctk.StringVar(
			value=self._cfg.get('dollar_type', 'blue').capitalize()
		)
		type_row = ctk.CTkFrame(scroll, fg_color='transparent')
		type_row.pack(fill='x', padx=16, pady=(4, 16))
		type_row.grid_columnconfigure((0, 1, 2), weight=1)

		self._type_btns: dict = {}
		for i, dtype in enumerate(_DOLLAR_TYPES):
			s = _TYPE_STYLE[dtype]
			btn = ctk.CTkButton(
				type_row,
				text=dtype,
				font=('Arial', 11, 'bold'),
				height=34,
				corner_radius=8,
				border_width=1,
				command=lambda d=dtype: self._select_type(d),
			)
			btn.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 3, 0))
			self._type_btns[dtype] = btn

		self._select_type(self._type_var.get(), save=False)

		# ── 2. Cotización del día ────────────────────────
		self._section_label(scroll, 'COTIZACIÓN  (ARS por US$1)')

		rate_frame = ctk.CTkFrame(
			scroll,
			fg_color=SURFACE3,
			corner_radius=10,
			border_width=1,
			border_color=BORDER_ACTIVE,
		)
		rate_frame.pack(fill='x', padx=16, pady=(4, 16))

		rate_inner = ctk.CTkFrame(rate_frame, fg_color='transparent')
		rate_inner.pack(fill='x', padx=12, pady=10)

		ctk.CTkLabel(
			rate_inner,
			text='$',
			font=('Arial', 22, 'bold'),
			text_color=TEXT_MUTED,
			width=18,
		).pack(side='left')

		saved_rate = self._cfg.get('dollar_rate', 0.0)
		self.entry_rate = ctk.CTkEntry(
			rate_inner,
			placeholder_text='0',
			fg_color='transparent',
			border_width=0,
			text_color=TEXT_PRIMARY,
			font=('Arial', 22, 'bold'),
		)
		if saved_rate and float(saved_rate) > 0:
			self.entry_rate.insert(0, f'{float(saved_rate):,.0f}')
		self.entry_rate.pack(side='left', fill='x', expand=True)
		self.entry_rate.bind('<KeyRelease>', self._on_value_change)

		# ── 3. Margen de ganancia ────────────────────────
		self._section_label(scroll, 'MARGEN DE GANANCIA')

		margin_row = ctk.CTkFrame(scroll, fg_color='transparent')
		margin_row.pack(fill='x', padx=16, pady=(4, 18))

		saved_margin = self._cfg.get('dollar_margin_pct', 30.0)
		self.entry_margin = ctk.CTkEntry(
			margin_row,
			placeholder_text='30',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=38,
			font=('Arial', 14),
		)
		self.entry_margin.insert(0, str(int(float(saved_margin))))
		self.entry_margin.pack(side='left', fill='x', expand=True, padx=(0, 8))
		self.entry_margin.bind('<KeyRelease>', self._on_value_change)

		ctk.CTkLabel(
			margin_row,
			text='%',
			font=('Arial', 16, 'bold'),
			text_color=TEXT_MUTED,
		).pack(side='left')

		# ── 4. Preview de fórmula ────────────────────────
		preview = ctk.CTkFrame(
			scroll,
			fg_color=ACCENT_DIM,
			corner_radius=10,
			border_width=1,
			border_color=ACCENT,
		)
		preview.pack(fill='x', padx=16, pady=(0, 16))

		ctk.CTkLabel(
			preview,
			text='PRECIO RESULTANTE',
			font=('Arial', 8, 'bold'),
			text_color=ACCENT_TEXT,
		).pack(padx=14, pady=(12, 4), anchor='w')

		self.lbl_formula = ctk.CTkLabel(
			preview,
			text='Ingresá la cotización',
			font=('Arial', 13, 'bold'),
			text_color=TEXT_PRIMARY,
			wraplength=230,
			justify='left',
		)
		self.lbl_formula.pack(padx=14, anchor='w')

		self.lbl_example = ctk.CTkLabel(
			preview,
			text='',
			font=('Arial', 11),
			text_color=ACCENT_TEXT,
			wraplength=230,
			justify='left',
		)
		self.lbl_example.pack(padx=14, pady=(2, 12), anchor='w')

		# ── 5. Resumen / contador ────────────────────────
		summary = ctk.CTkFrame(
			scroll,
			fg_color=SURFACE3,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		summary.pack(fill='x', padx=16, pady=(0, 20))

		self.lbl_ready_main = ctk.CTkLabel(
			summary,
			text='Cargando productos...',
			font=('Arial', 12, 'bold'),
			text_color=TEXT_MUTED,
			wraplength=230,
			justify='center',
		)
		self.lbl_ready_main.pack(padx=14, pady=(14, 4))

		self.lbl_ready_sub = ctk.CTkLabel(
			summary,
			text='',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
			wraplength=230,
			justify='center',
		)
		self.lbl_ready_sub.pack(padx=14, pady=(0, 14))

		# ── 6. Botón principal ───────────────────────────
		self.btn_update = ctk.CTkButton(
			scroll,
			text='ACTUALIZAR PRECIOS',
			font=('Arial', 13, 'bold'),
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			height=52,
			corner_radius=10,
			command=self._confirm_and_update,
		)
		self.btn_update.pack(fill='x', padx=16, pady=(0, 20))

	# ───────────────────────────────────────────────────────
	# PANEL DERECHO — tabla de productos
	# ───────────────────────────────────────────────────────
	def _build_right_panel(self, parent):
		panel = ctk.CTkFrame(
			parent,
			fg_color=SURFACE2,
			corner_radius=14,
			border_width=1,
			border_color=BORDER,
		)
		panel.grid(row=0, column=1, sticky='nsew')
		panel.grid_rowconfigure(2, weight=1)
		panel.grid_columnconfigure(0, weight=1)

		# ── Barra de búsqueda + filtro ───────────────────
		toolbar = ctk.CTkFrame(panel, fg_color='transparent')
		toolbar.grid(row=0, column=0, sticky='ew', padx=14, pady=(14, 0))
		toolbar.grid_columnconfigure(0, weight=1)

		self._search_var = ctk.StringVar()
		self._search_var.trace_add('write', self._on_filter_change)
		ctk.CTkEntry(
			toolbar,
			textvariable=self._search_var,
			placeholder_text='🔍  Buscar por nombre o código...',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		).grid(row=0, column=0, sticky='ew', padx=(0, 8))

		self._filter_var = ctk.StringVar(value='Todos')
		ctk.CTkComboBox(
			toolbar,
			variable=self._filter_var,
			values=_FILTER_OPTIONS,
			command=lambda _: self._on_filter_change(),
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			width=150,
			button_color=SURFACE3,
			button_hover_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			dropdown_text_color=TEXT_PRIMARY,
		).grid(row=0, column=1)

		# ── Leyenda de colores ───────────────────────────
		legend = ctk.CTkFrame(panel, fg_color='transparent')
		legend.grid(row=1, column=0, sticky='ew', padx=16, pady=(8, 4))

		for dot_color, text in [
			(GREEN_TEXT, '● vinculado al dólar'),
			(TEXT_MUTED, '● sin precio USD'),
		]:
			ctk.CTkLabel(
				legend,
				text=text,
				font=('Arial', 10),
				text_color=dot_color,
			).pack(side='left', padx=(0, 16))

		self.lbl_count = ctk.CTkLabel(
			legend,
			text='',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
		)
		self.lbl_count.pack(side='right')

		# ── Treeview ─────────────────────────────────────
		tree_wrap = ctk.CTkFrame(panel, fg_color='transparent')
		tree_wrap.grid(row=2, column=0, sticky='nsew', padx=14, pady=(0, 8))
		tree_wrap.grid_rowconfigure(0, weight=1)
		tree_wrap.grid_columnconfigure(0, weight=1)

		cols = ('Nombre', 'Código', 'Costo USD', 'ARS Actual', 'ARS Nuevo', 'Var %')
		vsb = ttk.Scrollbar(tree_wrap, orient='vertical')
		self.tree = ttk.Treeview(
			tree_wrap,
			columns=cols,
			show='headings',
			yscrollcommand=vsb.set,
		)
		vsb.configure(command=self.tree.yview)

		_widths = {
			'Nombre': 200,
			'Código': 100,
			'Costo USD': 95,
			'ARS Actual': 105,
			'ARS Nuevo': 105,
			'Var %': 72,
		}
		for col in cols:
			self.tree.heading(col, text=col)
			self.tree.column(
				col,
				width=_widths[col],
				anchor='w' if col == 'Nombre' else 'center',
				minwidth=60,
			)

		self.tree.tag_configure('linked', foreground=GREEN_TEXT)
		self.tree.tag_configure('unlinked', foreground=TEXT_MUTED)
		self.tree.tag_configure('up', foreground=GREEN_TEXT)
		self.tree.tag_configure('down', foreground=RED_TEXT)

		vsb.grid(row=0, column=1, sticky='ns')
		self.tree.grid(row=0, column=0, sticky='nsew')
		self.tree.bind('<Double-1>', lambda e: self._assign_usd_dialog())

		# ── Botones inferiores ───────────────────────────
		btns = ctk.CTkFrame(panel, fg_color='transparent')
		btns.grid(row=3, column=0, sticky='ew', padx=14, pady=(4, 14))

		ctk.CTkButton(
			btns,
			text='💲  Asignar precio USD al seleccionado',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=38,
			corner_radius=8,
			font=('Arial', 12),
			command=self._assign_usd_dialog,
		).pack(side='left', expand=True, fill='x', padx=(0, 6))

		ctk.CTkButton(
			btns,
			text='✕  Quitar USD',
			fg_color=SURFACE3,
			hover_color=RED_DIM,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=38,
			corner_radius=8,
			width=110,
			command=self._remove_usd_price,
		).pack(side='left')

	# ═══════════════════════════════════════════════════════
	# HELPERS DE UI
	# ═══════════════════════════════════════════════════════
	def _section_label(self, parent, text: str):
		ctk.CTkLabel(
			parent,
			text=text,
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=16, pady=(14, 0), anchor='w')

	# ═══════════════════════════════════════════════════════
	# TIPO DE DÓLAR
	# ═══════════════════════════════════════════════════════
	def _select_type(self, dtype: str, save: bool = True):
		self._type_var.set(dtype)
		for name, btn in self._type_btns.items():
			s = _TYPE_STYLE[name]
			if name == dtype:
				btn.configure(
					fg_color=s['dim'],
					text_color=s['text'],
					border_color=s['border'],
				)
			else:
				btn.configure(
					fg_color=SURFACE3,
					text_color=TEXT_MUTED,
					border_color=BORDER,
				)
		if save:
			s = cfg.load()
			s['dollar_type'] = dtype.lower()
			cfg.save(s)
		self._refresh_preview()

	# ═══════════════════════════════════════════════════════
	# DATOS
	# ═══════════════════════════════════════════════════════
	def _load_data(self):
		self._all_variants = self.controller.get_variants(self.ctx.tenant_id)
		self._refresh_all()

	def _refresh_all(self):
		self._refresh_tree()
		self._refresh_preview()
		self._refresh_counter()

	def _visible_variants(self) -> list:
		q = self._search_var.get().lower()
		filt = self._filter_var.get()
		result = []
		for v in self._all_variants:
			has_usd = v.get('cost_price_usd') is not None and v['cost_price_usd'] > 0
			if filt == 'Con precio USD' and not has_usd:
				continue
			if filt == 'Sin precio USD' and has_usd:
				continue
			if (
				q
				and q not in (v.get('name') or '').lower()
				and q not in str(v.get('barcode') or '').lower()
			):
				continue
			result.append(v)
		# Ordenar: primero los que tienen USD
		return sorted(
			result,
			key=lambda x: (
				0 if (x.get('cost_price_usd') or 0) > 0 else 1,
				(x.get('name') or '').lower(),
			),
		)

	def _refresh_tree(self):
		# Puede llamarse antes de que el panel derecho esté construido
		if not hasattr(self, 'tree') or not hasattr(self, 'lbl_count'):
			return
		for item in self.tree.get_children():
			self.tree.delete(item)

		rate = self._current_rate()
		margin = self._current_margin()
		factor = 1 + margin / 100

		visible = self._visible_variants()
		for v in visible:
			usd = v.get('cost_price_usd')
			current_sell = v.get('selling_price', 0.0)
			has_usd = usd is not None and usd > 0

			if has_usd:
				usd_str = f'US${usd:.2f}'
				if rate > 0:
					new_price = usd * rate * factor
					diff_pct = (
						(new_price - current_sell) / current_sell * 100
						if current_sell
						else 0
					)
					new_str = f'${new_price:,.0f}'
					diff_str = f'{diff_pct:+.1f}%'
					tag = 'up' if diff_pct >= 0 else 'down'
				else:
					new_str = '—'
					diff_str = '—'
					tag = 'linked'
			else:
				usd_str = '—'
				new_str = '—'
				diff_str = '—'
				tag = 'unlinked'

			self.tree.insert(
				'',
				'end',
				iid=str(v['variant_id']),
				values=(
					v.get('name', ''),
					v.get('barcode', '') or '—',
					usd_str,
					f'${current_sell:,.0f}',
					new_str,
					diff_str,
				),
				tags=(tag,),
			)

		total = len(self._all_variants)
		shown = len(visible)
		q_info = (
			f'  ·  {shown} de {total}' if shown != total else f'  ·  {total} productos'
		)
		self.lbl_count.configure(text=q_info)

	def _refresh_preview(self):
		# entry_rate / lbl_formula se crean DESPUÉS de que _select_type los necesita
		if not hasattr(self, 'entry_rate') or not hasattr(self, 'lbl_formula'):
			return
		rate = self._current_rate()
		margin = self._current_margin()
		factor = 1 + margin / 100
		dtype = self._current_type()

		if rate > 0:
			self.lbl_formula.configure(
				text=f'US$1  ×  ${rate:,.0f}  ×  {factor:.2f}  =  ${rate * factor:,.0f} ARS',
				text_color=TEXT_PRIMARY,
			)
			self.lbl_example.configure(
				text=f'Ej. producto a US$5.00  →  ${5.0 * rate * factor:,.0f} ARS  [{dtype}]'
			)
		else:
			self.lbl_formula.configure(
				text='Ingresá la cotización del dólar',
				text_color=TEXT_MUTED,
			)
			self.lbl_example.configure(text='')

		if self._all_variants:
			self._refresh_tree()

	def _refresh_counter(self):
		if not hasattr(self, 'chip_linked') or not hasattr(self, 'lbl_ready_main'):
			return
		with_usd = self._with_usd_count()
		total = len(self._all_variants)
		without = total - with_usd

		# Chips del header
		self.chip_linked.configure(
			text=f'✓  {with_usd} vinculados',
			fg_color=GREEN_DIM if with_usd > 0 else SURFACE3,
			text_color=GREEN_TEXT if with_usd > 0 else TEXT_SECONDARY,
		)
		self.chip_unlinked.configure(
			text=f'{without} sin asignar',
			fg_color=ORANGE_DIM if without > 0 else SURFACE3,
			text_color=ORANGE_TEXT if without > 0 else TEXT_SECONDARY,
		)

		# Card resumen en panel izq.
		if with_usd == 0:
			self.lbl_ready_main.configure(
				text='Ningún producto vinculado',
				text_color=ORANGE_TEXT,
			)
			self.lbl_ready_sub.configure(
				text='Doble clic sobre un producto\npara asignarle su precio en USD.',
				text_color=TEXT_MUTED,
			)
		else:
			self.lbl_ready_main.configure(
				text=f'{with_usd} producto{"s" if with_usd != 1 else ""} listo{"s" if with_usd != 1 else ""}',
				text_color=GREEN_TEXT,
			)
			extra = f'  +  {without} sin USD' if without else ''
			self.lbl_ready_sub.configure(
				text=f'Se actualizarán al presionar el botón.{extra}',
				text_color=TEXT_MUTED,
			)

	# ═══════════════════════════════════════════════════════
	# EVENTOS
	# ═══════════════════════════════════════════════════════
	def _on_value_change(self, *_):
		self._refresh_preview()
		self._save_settings()

	def _on_filter_change(self, *_):
		self._refresh_tree()

	def _save_settings(self):
		s = cfg.load()
		s['dollar_rate'] = self._current_rate()
		s['dollar_margin_pct'] = self._current_margin()
		s['dollar_type'] = self._current_type().lower()
		cfg.save(s)

	# ═══════════════════════════════════════════════════════
	# DIÁLOGO — ASIGNAR PRECIO USD
	# ═══════════════════════════════════════════════════════
	def _assign_usd_dialog(self):
		selected = self.tree.selection()
		if not selected:
			CTkMessagebox(
				title='Seleccioná un producto',
				message='Hacé clic sobre un producto de la lista\ny luego presioná "Asignar precio USD".',
				icon='info',
			)
			return

		variant_id = int(selected[0])
		variant = next(
			(v for v in self._all_variants if v['variant_id'] == variant_id), None
		)
		if not variant:
			return

		existing_usd = variant.get('cost_price_usd')
		existing_str = f'{float(existing_usd):.2f}' if existing_usd else ''

		dialog = ctk.CTkToplevel(self)
		dialog.title('Asignar precio en dólares')
		dialog.geometry('400x280')
		dialog.configure(fg_color=SURFACE1)
		dialog.attributes('-topmost', True)
		dialog.resizable(False, False)
		dialog.grab_set()

		# Header del diálogo
		hdr = ctk.CTkFrame(dialog, fg_color=SURFACE2, corner_radius=0)
		hdr.pack(fill='x')
		ctk.CTkLabel(
			hdr,
			text='💲  Asignar precio en dólares',
			font=('Arial', 14, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(padx=20, pady=14, anchor='w')

		body = ctk.CTkFrame(dialog, fg_color='transparent')
		body.pack(fill='both', expand=True, padx=24, pady=16)

		ctk.CTkLabel(
			body,
			text='Producto:',
			font=('Arial', 10, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w')
		ctk.CTkLabel(
			body,
			text=variant.get('name', ''),
			font=('Arial', 14, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(anchor='w', pady=(2, 16))

		ctk.CTkLabel(
			body,
			text='PRECIO DE COSTO EN DÓLARES (US$)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w')

		usd_row = ctk.CTkFrame(
			body,
			fg_color=SURFACE3,
			corner_radius=8,
			border_width=1,
			border_color=BORDER_ACTIVE,
		)
		usd_row.pack(fill='x', pady=(4, 20))

		ctk.CTkLabel(
			usd_row,
			text='US$',
			font=('Arial', 16, 'bold'),
			text_color=TEXT_MUTED,
			width=44,
		).pack(side='left', padx=(8, 0))

		entry = ctk.CTkEntry(
			usd_row,
			placeholder_text='0.00',
			fg_color='transparent',
			border_width=0,
			text_color=TEXT_PRIMARY,
			font=('Arial', 18, 'bold'),
		)
		if existing_str:
			entry.insert(0, existing_str)
		entry.pack(side='left', fill='x', expand=True, padx=(4, 12), pady=8)
		entry.focus()

		btn_row = ctk.CTkFrame(body, fg_color='transparent')
		btn_row.pack(fill='x')

		def _save():
			val = entry.get().strip()
			success, msg = self.controller.save_usd_price(
				self.ctx.tenant_id, variant_id, val
			)
			dialog.destroy()
			if success:
				self._load_data()
			else:
				CTkMessagebox(title='Error', message=msg, icon='cancel')

		ctk.CTkButton(
			btn_row,
			text='Guardar',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=40,
			corner_radius=8,
			font=('Arial', 13, 'bold'),
			command=_save,
		).pack(side='left', expand=True, fill='x', padx=(0, 8))

		ctk.CTkButton(
			btn_row,
			text='Cancelar',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=40,
			corner_radius=8,
			command=dialog.destroy,
		).pack(side='left', expand=True, fill='x')

		entry.bind('<Return>', lambda e: _save())

	# ═══════════════════════════════════════════════════════
	# QUITAR PRECIO USD
	# ═══════════════════════════════════════════════════════
	def _remove_usd_price(self):
		selected = self.tree.selection()
		if not selected:
			CTkMessagebox(
				title='Seleccioná un producto',
				message='Seleccioná un producto de la lista para quitarle el precio USD.',
				icon='info',
			)
			return

		variant_id = int(selected[0])
		variant = next(
			(v for v in self._all_variants if v['variant_id'] == variant_id), None
		)
		if not variant or not (variant.get('cost_price_usd') or 0) > 0:
			CTkMessagebox(
				title='Sin precio USD',
				message='Este producto no tiene precio en dólares asignado.',
				icon='info',
			)
			return

		confirm = CTkMessagebox(
			title='Quitar precio USD',
			message=(
				f'"{variant["name"]}" ya no se actualizará\n'
				'automáticamente cuando cambie el dólar.\n\n¿Confirmás?'
			),
			icon='warning',
			option_1='Cancelar',
			option_2='Sí, quitar',
		)
		if confirm.get() == 'Sí, quitar':
			success, msg = self.controller.save_usd_price(
				self.ctx.tenant_id, variant_id, ''
			)
			if success:
				self._load_data()
			else:
				CTkMessagebox(title='Error', message=msg, icon='cancel')

	# ═══════════════════════════════════════════════════════
	# ACTUALIZACIÓN MASIVA
	# ═══════════════════════════════════════════════════════
	def _confirm_and_update(self):
		rate = self._current_rate()
		margin = self._current_margin()
		dtype = self._current_type()
		with_usd = self._with_usd_count()

		if rate <= 0:
			CTkMessagebox(
				title='Falta la cotización',
				message='Ingresá el valor del dólar hoy\nantes de actualizar los precios.',
				icon='warning',
			)
			return

		if with_usd == 0:
			CTkMessagebox(
				title='Sin productos vinculados',
				message=(
					'Ningún producto tiene precio en dólares asignado.\n\n'
					'Seleccioná un producto en la tabla y presioná\n'
					'"Asignar precio USD" para vincularlo.'
				),
				icon='info',
			)
			return

		factor = 1 + margin / 100
		confirm = CTkMessagebox(
			title='Confirmar actualización de precios',
			message=(
				f'Tipo de cambio usado:   Dólar {dtype}\n'
				f'Cotización:                  ${rate:,.0f} ARS\n'
				f'Margen de ganancia:     {margin:.0f}%\n'
				f'Fórmula:                       US$ × ${rate:,.0f} × {factor:.2f}\n\n'
				f'Productos a actualizar:   {with_usd}\n\n'
				'¿Aplicar los nuevos precios?'
			),
			icon='warning',
			option_1='Cancelar',
			option_2='Sí, actualizar',
		)

		if confirm.get() != 'Sí, actualizar':
			return

		self.btn_update.configure(state='disabled', text='Actualizando...')
		self.update()
		self._save_settings()

		success, msg = self.controller.recalculate_prices(
			tenant_id=self.ctx.tenant_id,
			user_id=self.ctx.user_id,
			rate=rate,
			margin_pct=margin,
		)

		self.btn_update.configure(state='normal', text='ACTUALIZAR PRECIOS')

		if success:
			CTkMessagebox(title='¡Precios actualizados!', message=msg, icon='check')
			self._load_data()
		else:
			CTkMessagebox(title='Error al actualizar', message=msg, icon='cancel')
