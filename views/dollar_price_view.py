"""
views/dollar_price_view.py
==========================
Módulo de actualización de precios por tipo de cambio del dólar.
"""

import logging
import threading
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
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_HEADING,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	FONT_NAV_BOLD,
	FONT_SMALL,
	FONT_SMALL_BOLD,
	FONT_SUBHEADING,
	FONT_TITLE,
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
		self._initial_rate = float(self._cfg.get('dollar_rate', 0.0))
		self._search_timer = None
		self._trace_search = None

		self.grid_rowconfigure(0, weight=0)
		self.grid_rowconfigure(1, weight=1)
		self.grid_columnconfigure(0, weight=1)

		apply_treeview_style()
		self._build_header()
		self._build_body()

		self.after(120, self._load_data)

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

	def _build_header(self):
		hdr = ctk.CTkFrame(self, fg_color=SURFACE2, corner_radius=0, border_width=0)
		hdr.grid(row=0, column=0, sticky='ew')

		inner = ctk.CTkFrame(hdr, fg_color='transparent')
		inner.pack(fill='x', padx=20, pady=14)

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
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			anchor='w',
		)
		self.lbl_header_sub.pack(anchor='w', pady=(2, 0))

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
			font=FONT_SMALL,
			command=self._load_data,
		).pack(side='left')

	def _make_chip(self, parent, text: str, bg: str, fg: str) -> ctk.CTkLabel:
		return ctk.CTkLabel(
			parent,
			text=text,
			font=FONT_LABEL_BOLD,
			fg_color=bg,
			text_color=fg,
			corner_radius=6,
			padx=10,
			pady=4,
		)

	def _build_body(self):
		body = ctk.CTkFrame(self, fg_color='transparent')
		body.grid(row=1, column=0, sticky='nsew', padx=16, pady=12)
		body.grid_columnconfigure(0, weight=0)
		body.grid_columnconfigure(1, weight=1)
		body.grid_rowconfigure(0, weight=1)

		self._build_left_panel(body)
		self._build_right_panel(body)

	def _build_left_panel(self, parent):
		outer = ctk.CTkFrame(
			parent,
			fg_color=SURFACE2,
			corner_radius=14,
			border_width=1,
			border_color=BORDER,
		)
		outer.grid(row=0, column=0, sticky='nsew', padx=(0, 10))

		scroll = ctk.CTkScrollableFrame(
			outer, fg_color='transparent', scrollbar_button_color=SURFACE3, width=280
		)
		scroll.pack(fill='both', expand=True, padx=0, pady=0)

		# ── 1. Tipo de cotización
		self._section_label(scroll, 'TIPO DE COTIZACIÓN')
		self._type_var = ctk.StringVar(master=self, 
			value=self._cfg.get('dollar_type', 'blue').capitalize()
		)
		type_row = ctk.CTkFrame(scroll, fg_color='transparent')
		type_row.pack(fill='x', padx=16, pady=(4, 16))
		type_row.grid_columnconfigure((0, 1, 2), weight=1)

		self._type_btns: dict = {}
		for i, dtype in enumerate(_DOLLAR_TYPES):
			btn = ctk.CTkButton(
				type_row,
				text=dtype,
				font=FONT_SMALL_BOLD,
				height=34,
				corner_radius=8,
				border_width=1,
				command=lambda d=dtype: self._select_type(d),
			)
			btn.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 3, 0))
			self._type_btns[dtype] = btn

		self._select_type(self._type_var.get(), save=False)

		# ── 2. Cotización del día
		lbl_rate_frame = ctk.CTkFrame(scroll, fg_color='transparent')
		lbl_rate_frame.pack(fill='x', padx=16, pady=(14, 0))

		ctk.CTkLabel(
			lbl_rate_frame,
			text='COTIZACIÓN  (ARS por US$1)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(side='left')

		self.btn_api = ctk.CTkButton(
			lbl_rate_frame,
			text='⬇ Obtener API',
			font=('Arial', 9, 'bold'),
			fg_color=SURFACE3,
			text_color=TEXT_SECONDARY,
			height=20,
			width=90,
			command=self._fetch_api_rate,
		)
		self.btn_api.pack(side='right')

		self.rate_frame = ctk.CTkFrame(
			scroll,
			fg_color=SURFACE3,
			corner_radius=10,
			border_width=1,
			border_color=BORDER_ACTIVE,
		)
		self.rate_frame.pack(fill='x', padx=16, pady=(4, 2))

		rate_inner = ctk.CTkFrame(self.rate_frame, fg_color='transparent')
		rate_inner.pack(fill='x', padx=12, pady=10)

		ctk.CTkLabel(
			rate_inner,
			text='$',
			font=('Arial', 22, 'bold'),
			text_color=TEXT_MUTED,
			width=18,
		).pack(side='left')

		self.entry_rate = ctk.CTkEntry(
			rate_inner,
			placeholder_text='0',
			fg_color='transparent',
			border_width=0,
			text_color=TEXT_PRIMARY,
			font=('Arial', 22, 'bold'),
		)
		if self._initial_rate > 0:
			self.entry_rate.insert(0, f'{self._initial_rate:,.0f}')
		self.entry_rate.pack(side='left', fill='x', expand=True)
		self.entry_rate.bind('<KeyRelease>', self._on_value_change)

		self.lbl_rate_warning = ctk.CTkLabel(
			scroll, text='', font=FONT_SMALL, text_color=RED_TEXT, anchor='e'
		)
		self.lbl_rate_warning.pack(fill='x', padx=16)

		# ── 3. Margen de ganancia
		self._section_label(scroll, 'MARGEN DE GANANCIA GLOBAL')
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
			font=FONT_SUBHEADING,
		)
		_m = float(saved_margin)
		self.entry_margin.insert(0, str(int(_m)) if _m == int(_m) else f'{_m:.2f}')
		self.entry_margin.pack(side='left', fill='x', expand=True, padx=(0, 8))
		self.entry_margin.bind('<KeyRelease>', self._on_value_change)

		ctk.CTkLabel(
			margin_row, text='%', font=('Arial', 16, 'bold'), text_color=TEXT_MUTED
		).pack(side='left')

		# ── 4. Preview de fórmula
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
			font=FONT_NAV_BOLD,
			text_color=TEXT_PRIMARY,
			wraplength=230,
			justify='left',
		)
		self.lbl_formula.pack(padx=14, anchor='w')
		self.lbl_example = ctk.CTkLabel(
			preview,
			text='',
			font=FONT_SMALL,
			text_color=ACCENT_TEXT,
			wraplength=230,
			justify='left',
		)
		self.lbl_example.pack(padx=14, pady=(2, 12), anchor='w')

		# ── 5. Resumen / contador
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
			font=FONT_BODY_BOLD,
			text_color=TEXT_MUTED,
			wraplength=230,
			justify='center',
		)
		self.lbl_ready_main.pack(padx=14, pady=(14, 4))
		self.lbl_ready_sub = ctk.CTkLabel(
			summary,
			text='',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			wraplength=230,
			justify='center',
		)
		self.lbl_ready_sub.pack(padx=14, pady=(0, 14))

		# ── 6. Botones inferiores
		self.btn_update = ctk.CTkButton(
			scroll,
			text='✅ CONFIRMAR Y GUARDAR',
			font=FONT_NAV_BOLD,
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			height=52,
			corner_radius=10,
			command=self._confirm_and_update,
		)
		self.btn_update.pack(fill='x', padx=16, pady=(0, 4))

		self.lbl_last_update = ctk.CTkLabel(
			scroll, text='', font=FONT_SMALL, text_color=TEXT_MUTED, justify='center'
		)
		self.lbl_last_update.pack(padx=14, pady=(0, 16))

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

		toolbar = ctk.CTkFrame(panel, fg_color='transparent')
		toolbar.grid(row=0, column=0, sticky='ew', padx=14, pady=(14, 0))
		toolbar.grid_columnconfigure(0, weight=1)

		self._search_var = ctk.StringVar(master=self, )
		self._trace_search = self._search_var.trace_add('write', self._on_filter_change)
		ctk.CTkEntry(
			toolbar,
			textvariable=self._search_var,
			placeholder_text='🔍  Buscar por nombre o código...',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		).grid(row=0, column=0, sticky='ew', padx=(0, 8))

		self._filter_var = ctk.StringVar(master=self, value='Todos')
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

		legend = ctk.CTkFrame(panel, fg_color='transparent')
		legend.grid(row=1, column=0, sticky='ew', padx=16, pady=(8, 4))

		for dot_color, text in [
			(GREEN_TEXT, '● vinculado al dólar'),
			(TEXT_MUTED, '● sin precio USD'),
		]:
			ctk.CTkLabel(legend, text=text, font=FONT_LABEL, text_color=dot_color).pack(
				side='left', padx=(0, 16)
			)

		self.lbl_count = ctk.CTkLabel(
			legend, text='', font=FONT_LABEL, text_color=TEXT_MUTED
		)
		self.lbl_count.pack(side='right')

		tree_wrap = ctk.CTkFrame(panel, fg_color='transparent')
		tree_wrap.grid(row=2, column=0, sticky='nsew', padx=14, pady=(0, 8))
		tree_wrap.grid_rowconfigure(0, weight=1)
		tree_wrap.grid_columnconfigure(0, weight=1)

		cols = (
			'Nombre',
			'Código',
			'Margen %',
			'Costo USD',
			'ARS Actual',
			'ARS Nuevo',
			'Var %',
		)
		vsb = ttk.Scrollbar(tree_wrap, orient='vertical')
		self.tree = ttk.Treeview(
			tree_wrap,
			columns=cols,
			show='headings',
			yscrollcommand=vsb.set,
			selectmode='extended',
		)
		vsb.configure(command=self.tree.yview)

		_widths = {
			'Nombre': 200,
			'Código': 90,
			'Margen %': 70,
			'Costo USD': 85,
			'ARS Actual': 95,
			'ARS Nuevo': 95,
			'Var %': 72,
		}
		for col in cols:
			self.tree.heading(
				col, text=col, command=lambda c=col: self._sort_treeview(c, False)
			)
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

		btns = ctk.CTkFrame(panel, fg_color='transparent')
		btns.grid(row=3, column=0, sticky='ew', padx=14, pady=(4, 14))

		ctk.CTkButton(
			btns,
			text='💲  Asignar precio USD/Margen',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=38,
			corner_radius=8,
			font=FONT_BODY,
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

	def _section_label(self, parent, text: str):
		ctk.CTkLabel(
			parent,
			text=text,
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=16, pady=(14, 0), anchor='w')

	def _sort_treeview(self, col: str, reverse: bool):
		rows = [(self.tree.set(k, col), k) for k in self.tree.get_children('')]

		def sort_key(tup):
			val = tup[0]
			if val in ('—', ''):
				return -999999 if reverse else 999999
			if val.startswith('$') or val.startswith('US$'):
				try:
					return float(
						val.replace('US$', '').replace('$', '').replace(',', '')
					)
				except ValueError:
					return 0.0
			if val.endswith('%'):
				try:
					return float(val.replace('+', '').replace('%', ''))
				except ValueError:
					return 0.0
			return val.lower()

		rows.sort(key=sort_key, reverse=reverse)
		for index, (_, k) in enumerate(rows):
			self.tree.move(k, '', index)
		self.tree.heading(col, command=lambda: self._sort_treeview(col, not reverse))

	def _select_type(self, dtype: str, save: bool = True):
		self._type_var.set(dtype)
		for name, btn in self._type_btns.items():
			s = _TYPE_STYLE[name]
			if name == dtype:
				btn.configure(
					fg_color=s['dim'], text_color=s['text'], border_color=s['border']
				)
			else:
				btn.configure(
					fg_color=SURFACE3, text_color=TEXT_MUTED, border_color=BORDER
				)
		if save:
			s = cfg.load()
			s['dollar_type'] = dtype.lower()
			cfg.save(s)
		self._refresh_preview()

	def _fetch_api_rate(self):
		self.btn_api.configure(state='disabled', text='⏳ Consultando...')

		def worker():
			rate = self.controller.fetch_current_dollar_rate(self._current_type())
			self.after(0, lambda: self._on_api_rate_fetched(rate))

		threading.Thread(target=worker, daemon=True).start()

	def _on_api_rate_fetched(self, rate: float):
		if not self.winfo_exists():
			return
		dtype = self._current_type()
		self.btn_api.configure(state='normal', text='⬇ Obtener API')
		if rate > 0:
			self.entry_rate.delete(0, 'end')
			self.entry_rate.insert(0, f'{rate:.0f}')
			self._on_value_change()
			self.show_toast(
				f'Dólar {dtype}: ${rate:.0f} actualizado desde API', 'success'
			)
		else:
			self.show_toast(
				f'No se pudo obtener el Dólar {dtype}. Ingresá el valor manualmente.',
				'error',
			)

	def _load_data(self):
		self._all_variants = self.controller.get_variants(self.ctx.tenant_id)

		info = self.controller.get_last_update_info(self.ctx.tenant_id)
		if info:
			d_str = info['date'].strftime('%d/%m/%Y %H:%M')
			self.lbl_last_update.configure(text=f'Última actualización: {d_str}')

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
		return sorted(
			result,
			key=lambda x: (
				0 if (x.get('cost_price_usd') or 0) > 0 else 1,
				(x.get('name') or '').lower(),
			),
		)

	def _refresh_tree(self):
		if not hasattr(self, 'tree') or not hasattr(self, 'lbl_count'):
			return
		for item in self.tree.get_children():
			self.tree.delete(item)

		rate = self._current_rate()
		global_margin = self._current_margin()
		visible = self._visible_variants()

		for v in visible:
			usd = v.get('cost_price_usd')
			current_sell = v.get('selling_price', 0.0)
			has_usd = usd is not None and usd > 0

			v_margin = v.get('margin_pct')
			effective_margin = v_margin if v_margin is not None else global_margin
			margin_str = f'{effective_margin:.1f}%' if has_usd else '—'

			if has_usd:
				usd_str = f'US${usd:.2f}'
				if rate > 0:
					factor = 1 + effective_margin / 100
					new_price = usd * rate * factor
					diff_pct = (
						((new_price - current_sell) / current_sell * 100)
						if current_sell
						else 0
					)
					new_str, diff_str = f'${new_price:,.0f}', f'{diff_pct:+.1f}%'
					tag = 'up' if diff_pct >= 0 else 'down'
				else:
					new_str, diff_str, tag = '—', '—', 'linked'
			else:
				usd_str, new_str, diff_str, tag = '—', '—', '—', 'unlinked'

			self.tree.insert(
				'',
				'end',
				iid=str(v['variant_id']),
				values=(
					v.get('name', ''),
					v.get('barcode', '') or '—',
					margin_str,
					usd_str,
					f'${current_sell:,.0f}',
					new_str,
					diff_str,
				),
				tags=(tag,),
			)

		total, shown = len(self._all_variants), len(visible)
		self.lbl_count.configure(
			text=f'  ·  {shown} de {total}'
			if shown != total
			else f'  ·  {total} productos'
		)

	def _refresh_preview(self):
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
				text='Ingresá la cotización del dólar', text_color=TEXT_MUTED
			)
			self.lbl_example.configure(text='')

	def _refresh_counter(self):
		if not hasattr(self, 'chip_linked') or not hasattr(self, 'lbl_ready_main'):
			return
		with_usd, total = self._with_usd_count(), len(self._all_variants)
		without = total - with_usd

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

		if with_usd == 0:
			self.lbl_ready_main.configure(
				text='Ningún producto vinculado', text_color=ORANGE_TEXT
			)
			self.lbl_ready_sub.configure(
				text='Seleccioná productos en la tabla\npara asignarles precio USD.',
				text_color=TEXT_MUTED,
			)
		else:
			self.lbl_ready_main.configure(
				text=f'{with_usd} producto(s) listo(s)', text_color=GREEN_TEXT
			)
			extra = f'  +  {without} sin USD' if without else ''
			self.lbl_ready_sub.configure(
				text=f'Se actualizarán al presionar el botón.{extra}',
				text_color=TEXT_MUTED,
			)

	def _on_value_change(self, *_):
		current_rate = self._current_rate()
		if self._initial_rate > 0 and current_rate > 0:
			diff = abs(current_rate - self._initial_rate) / self._initial_rate
			if diff > 0.30:
				self.rate_frame.configure(border_color=RED_DIM)
				pct_diff = diff * 100
				self.lbl_rate_warning.configure(
					text=f'⚠️ Difiere {pct_diff:.0f}% del último guardado (${self._initial_rate:.0f}). Verificá antes de confirmar.'
				)
			else:
				self.rate_frame.configure(border_color=BORDER_ACTIVE)
				self.lbl_rate_warning.configure(text='')

		self._refresh_preview()
		if self._all_variants:
			self._refresh_tree()
		self.debounce(500, self._save_settings, key='save_settings')

	def _on_filter_change(self, *_):
		if self._search_timer:
			self.after_cancel(self._search_timer)
		self._search_timer = self.after(300, self._refresh_tree)

	def destroy_custom(self):
		if self._search_timer:
			try:
				self.after_cancel(self._search_timer)
			except Exception:
				pass
		if self._trace_search:
			try:
				self._search_var.trace_remove('write', self._trace_search)
			except Exception:
				pass

	def _save_settings(self):
		s = cfg.load()
		s['dollar_rate'] = self._current_rate()
		s['dollar_margin_pct'] = self._current_margin()
		s['dollar_type'] = self._current_type().lower()
		cfg.save(s)

	def _assign_usd_dialog(self):
		selected = self.tree.selection()
		if not selected:
			CTkMessagebox(
				title='Selección vacía',
				message='Seleccioná uno o más productos.',
				icon='info',
			)
			return

		variant_ids = list(selected)

		existing_usd, existing_margin = '', ''
		title_text = 'Asignar precio masivo'
		if len(selected) == 1:
			variant = next(
				(
					v
					for v in self._all_variants
					if str(v['variant_id']) == str(variant_ids[0])
				),
				None,
			)
			if variant:
				title_text = variant.get('name', '')
				existing_usd = (
					f'{float(variant.get("cost_price_usd")):.2f}'
					if variant.get('cost_price_usd')
					else ''
				)
				existing_margin = (
					f'{float(variant.get("margin_pct")):.1f}'
					if variant.get('margin_pct') is not None
					else ''
				)
		else:
			title_text = f'{len(selected)} productos seleccionados'

		dialog = ctk.CTkToplevel(self)
		dialog.title('Asignar precio en dólares')
		dialog.geometry('420x420')
		dialog.configure(fg_color=SURFACE1)
		dialog.attributes('-topmost', True)
		dialog.resizable(False, False)
		dialog.grab_set()

		hdr = ctk.CTkFrame(dialog, fg_color=SURFACE2, corner_radius=0)
		hdr.pack(fill='x')
		ctk.CTkLabel(
			hdr,
			text='💲  Asignar Valores USD',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
		).pack(padx=20, pady=14, anchor='w')

		body = ctk.CTkFrame(dialog, fg_color='transparent')
		body.pack(fill='both', expand=True, padx=24, pady=12)

		ctk.CTkLabel(
			body,
			text=title_text,
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
			wraplength=350,
		).pack(anchor='w', pady=(0, 16))

		ctk.CTkLabel(
			body,
			text='COSTO EN DÓLARES (US$)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
		).pack(anchor='w')
		usd_row = ctk.CTkFrame(
			body,
			fg_color=SURFACE3,
			corner_radius=8,
			border_width=1,
			border_color=BORDER_ACTIVE,
		)
		usd_row.pack(fill='x', pady=(4, 12))
		ctk.CTkLabel(
			usd_row,
			text='US$',
			font=('Arial', 16, 'bold'),
			text_color=TEXT_MUTED,
			width=44,
		).pack(side='left', padx=(8, 0))
		entry_usd = ctk.CTkEntry(
			usd_row,
			placeholder_text='0.00',
			fg_color='transparent',
			border_width=0,
			text_color=TEXT_PRIMARY,
			font=FONT_TITLE,
		)
		if existing_usd:
			entry_usd.insert(0, existing_usd)
		entry_usd.pack(side='left', fill='x', expand=True, padx=(4, 12), pady=8)

		ctk.CTkLabel(
			body,
			text='MARGEN INDIVIDUAL (%) [Opcional]',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
		).pack(anchor='w')
		margin_row = ctk.CTkFrame(
			body,
			fg_color=SURFACE3,
			corner_radius=8,
			border_width=1,
			border_color=BORDER_ACTIVE,
		)
		margin_row.pack(fill='x', pady=(4, 16))
		ctk.CTkLabel(
			margin_row,
			text='%',
			font=('Arial', 16, 'bold'),
			text_color=TEXT_MUTED,
			width=44,
		).pack(side='left', padx=(8, 0))
		entry_margin = ctk.CTkEntry(
			margin_row,
			placeholder_text=str(self._current_margin()),
			fg_color='transparent',
			border_width=0,
			text_color=TEXT_PRIMARY,
			font=FONT_TITLE,
		)
		if existing_margin:
			entry_margin.insert(0, existing_margin)
		entry_margin.pack(side='left', fill='x', expand=True, padx=(4, 12), pady=8)

		lbl_live_preview = ctk.CTkLabel(
			body, text='', font=FONT_BODY_BOLD, text_color=ACCENT_TEXT
		)
		lbl_live_preview.pack(pady=(0, 16))

		def update_live_preview(*_):
			try:
				u_val = float(entry_usd.get().replace(',', '.') or 0)
				m_str = entry_margin.get().replace(',', '.')
				m_val = float(m_str) if m_str else self._current_margin()
				rate = self._current_rate()

				if u_val > 0 and rate > 0:
					ars_res = u_val * rate * (1 + m_val / 100)
					lbl_live_preview.configure(
						text=f'Precio ARS proyectado: ${ars_res:,.2f}'
					)
				else:
					lbl_live_preview.configure(text='')
			except ValueError:
				lbl_live_preview.configure(text='')

		entry_usd.bind('<KeyRelease>', update_live_preview)
		entry_margin.bind('<KeyRelease>', update_live_preview)
		entry_usd.bind('<Return>', lambda e: entry_margin.focus())
		entry_margin.bind('<Return>', lambda e: _save())
		dialog.bind('<Return>', lambda e: _save())
		update_live_preview()
		entry_usd.focus()

		def _save():
			val_usd = entry_usd.get().strip()
			val_margin = entry_margin.get().strip()
			success, msg = self.controller.save_usd_prices_bulk(
				self.ctx.tenant_id, variant_ids, val_usd, val_margin
			)
			if success:
				dialog.destroy()
				self._load_data()
			else:
				self.show_toast(msg, 'error')

		btn_row = ctk.CTkFrame(body, fg_color='transparent')
		btn_row.pack(fill='x')
		ctk.CTkButton(
			btn_row,
			text='Guardar',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_color=ACCENT,
			border_width=1,
			height=40,
			font=FONT_NAV_BOLD,
			command=_save,
		).pack(side='left', expand=True, fill='x', padx=(0, 8))
		ctk.CTkButton(
			btn_row,
			text='Cancelar',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_color=BORDER,
			border_width=1,
			height=40,
			command=dialog.destroy,
		).pack(side='left', expand=True, fill='x')

	def _remove_usd_price(self):
		selected = self.tree.selection()
		if not selected:
			CTkMessagebox(
				title='Selección vacía',
				message='Seleccioná productos de la lista.',
				icon='info',
			)
			return

		variant_ids = list(selected)
		confirm = CTkMessagebox(
			title='Quitar precio USD',
			message=f'Se quitará el precio en dólares a {len(variant_ids)} producto(s).\n\n¿Confirmás?',
			icon='warning',
			option_1='Cancelar',
			option_2='Sí, quitar',
		)
		if confirm.get() == 'Sí, quitar':
			success, msg = self.controller.save_usd_prices_bulk(
				self.ctx.tenant_id, variant_ids, ''
			)
			if success:
				self._load_data()
			else:
				self.show_toast(msg, 'error')

	def _confirm_and_update(self):
		rate = self._current_rate()
		margin = self._current_margin()
		dtype = self._current_type()
		with_usd = self._with_usd_count()

		if rate <= 0:
			CTkMessagebox(
				title='Falta la cotización',
				message='Ingresá el valor del dólar hoy.',
				icon='warning',
			)
			return
		if with_usd == 0:
			CTkMessagebox(
				title='Sin productos',
				message='Ningún producto tiene precio en dólares asignado.',
				icon='info',
			)
			return

		preview_stats = self.controller.preview_recalculate_prices(
			self.ctx.tenant_id, rate, margin
		)
		stats_text = ''
		if 'error' not in preview_stats:
			stats_text = (
				f'Variación promedio: {preview_stats["avg_increase_pct"]:+.2f}%\n'
				f'Rango resultante: de ${preview_stats["min_ars"]:,.0f} a ${preview_stats["max_ars"]:,.0f} ARS\n\n'
			)

		confirm = CTkMessagebox(
			title='Confirmar actualización de precios',
			message=(
				f'Tipo de cambio:   Dólar {dtype} a ${rate:,.0f}\n'
				f'Productos:        {with_usd}\n\n'
				f'{stats_text}'
				'⚠ Esta acción es irreversible desde la aplicación.\n'
				'¿Confirmás guardar los precios mostrados?'
			),
			icon='warning',
			option_1='Cancelar',
			option_2='Sí, actualizar',
		)

		if confirm.get() != 'Sí, actualizar':
			return

		self.btn_update.configure(state='disabled', text='⏳ Guardando...')
		self.update_idletasks()
		self._save_settings()

		def worker():
			try:
				success, msg = self.controller.recalculate_prices(
					self.ctx.tenant_id, self.ctx.user_id, rate, margin
				)
			except Exception as e:
				success, msg = False, f'Error del sistema: {str(e)}'
			self.after(0, lambda: self._on_update_done(success, msg))

		threading.Thread(target=worker, daemon=True).start()

	def _on_update_done(self, success: bool, msg: str):
		if not self.winfo_exists():
			return
		self.btn_update.configure(state='normal', text='✅ CONFIRMAR Y GUARDAR')

		if success:
			self.show_toast(msg, 'success')
			self._initial_rate = self._current_rate()
			self._on_value_change()
			self._load_data()
		else:
			self.show_toast(msg, 'error')
