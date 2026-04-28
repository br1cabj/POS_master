"""
views/quotation_view.py
========================
Módulo de Cotizaciones / Presupuestos.
Layout: panel izquierdo (lista + filtros) | panel derecho (formulario o detalle).
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.quotation_controller import QuotationController
from core.context import AppContext
from utils.settings_manager import fmt_price
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_HEADING,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	FONT_TITLE,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE_DIM,
	ORANGE_TEXT,
	RED,
	RED_DIM,
	RED_TEXT,
	SURFACE0,
	SURFACE1,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
)

logger = logging.getLogger(__name__)

STATUS_THEME = {
	'borrador': (SURFACE3, TEXT_SECONDARY),
	'enviada': (ACCENT_DIM, ACCENT_TEXT),
	'aceptada': (GREEN_DIM, GREEN_TEXT),
	'rechazada': (RED_DIM, RED_TEXT),
	'vencida': (ORANGE_DIM, ORANGE_TEXT),
}
STATUS_OPTIONS = ['borrador', 'enviada', 'aceptada', 'rechazada', 'vencida']


class QuotationView(ctk.CTkFrame):
	def __init__(self, master, ctx: AppContext, **kwargs):
		super().__init__(master, fg_color=SURFACE1, **kwargs)
		self.ctx = ctx
		self._ctrl = QuotationController(ctx.db_engine)
		self._all_quotes: list[dict] = []
		self._selected_id: int | None = None
		self._edit_id: int | None = None
		self._items: list[dict] = []
		self._item_widgets: list[tuple] = []
		self._entry_disc = None
		self._tot_frame = None
		self._customers: list[dict] = []

		self._build()
		self.after(100, self._load_list)

	# ─────────────────────────────────────────────────────────────────────────
	# Layout
	# ─────────────────────────────────────────────────────────────────────────

	def _build(self):
		self.grid_columnconfigure(0, weight=0)
		self.grid_columnconfigure(1, weight=1)
		self.grid_rowconfigure(0, weight=1)
		self._build_left()
		self._build_right()

	def _build_left(self):
		left = ctk.CTkFrame(self, fg_color=SURFACE0, width=300, corner_radius=0)
		left.grid(row=0, column=0, sticky='nsew')
		left.grid_propagate(False)
		left.grid_rowconfigure(2, weight=1)
		left.grid_columnconfigure(0, weight=1)

		hdr = ctk.CTkFrame(left, fg_color='transparent')
		hdr.grid(row=0, column=0, sticky='ew', padx=12, pady=(14, 6))
		hdr.grid_columnconfigure(0, weight=1)
		ctk.CTkLabel(
			hdr, text='Cotizaciones', font=FONT_HEADING, text_color=TEXT_PRIMARY
		).grid(row=0, column=0, sticky='w')
		ctk.CTkButton(
			hdr,
			text='+ Nueva',
			width=80,
			height=28,
			fg_color=ACCENT,
			hover_color='#1d4ed8',
			font=FONT_LABEL_BOLD,
			command=self._open_form_new,
		).grid(row=0, column=1, padx=(6, 0))

		flt = ctk.CTkFrame(left, fg_color='transparent')
		flt.grid(row=1, column=0, sticky='ew', padx=12, pady=(0, 6))
		flt.grid_columnconfigure(0, weight=1)
		self._entry_search = ctk.CTkEntry(
			flt,
			placeholder_text='Buscar por número, cliente...',
			height=32,
			fg_color=SURFACE2,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
		)
		self._entry_search.grid(row=0, column=0, sticky='ew', pady=(0, 5))
		self._entry_search.bind('<KeyRelease>', lambda e: self._apply_filter())

		self._filter_var = ctk.StringVar(value='todas')
		self._combo_filter = ctk.CTkOptionMenu(
			flt,
			values=['todas'] + STATUS_OPTIONS,
			variable=self._filter_var,
			fg_color=SURFACE3,
			button_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			text_color=TEXT_PRIMARY,
			font=FONT_LABEL,
			height=30,
			command=lambda _: self._apply_filter(),
		)
		self._combo_filter.grid(row=1, column=0, sticky='ew')

		self._list_frame = ctk.CTkScrollableFrame(
			left,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
		)
		self._list_frame.grid(row=2, column=0, sticky='nsew', padx=8, pady=(4, 8))
		self._list_frame.grid_columnconfigure(0, weight=1)

	def _build_right(self):
		self._right = ctk.CTkFrame(self, fg_color=SURFACE1, corner_radius=0)
		self._right.grid(row=0, column=1, sticky='nsew')
		self._right.grid_columnconfigure(0, weight=1)
		self._right.grid_rowconfigure(0, weight=1)
		self._show_empty_state()

	def _clear_right(self):
		if not self.winfo_exists():
			return
		for w in list(self._right.winfo_children()):
			try:
				w.destroy()
			except Exception:
				pass

	def _show_empty_state(self):
		self._clear_right()
		f = ctk.CTkFrame(self._right, fg_color='transparent')
		f.place(relx=0.5, rely=0.5, anchor='center')
		ctk.CTkLabel(f, text='📄', font=('Arial', 48)).pack()
		ctk.CTkLabel(
			f,
			text='Seleccioná una cotización\no creá una nueva',
			font=FONT_BODY,
			text_color=TEXT_SECONDARY,
			justify='center',
		).pack(pady=8)
		ctk.CTkButton(
			f,
			text='+ Nueva cotización',
			command=self._open_form_new,
			fg_color=ACCENT,
			hover_color='#1d4ed8',
		).pack(pady=4)

	# ─────────────────────────────────────────────────────────────────────────
	# Lista
	# ─────────────────────────────────────────────────────────────────────────

	def _load_list(self):
		if not self.winfo_exists():
			return
		self._all_quotes = self._ctrl.list_quotations(self.ctx.tenant_id)
		self._apply_filter()

	def _apply_filter(self):
		if not self.winfo_exists():
			return
		q = self._entry_search.get().lower().strip()
		status = self._filter_var.get()
		filtered = [
			row
			for row in self._all_quotes
			if (status == 'todas' or row['status'] == status)
			and (
				not q
				or q in row['number'].lower()
				or q in (row['customer_name'] or '').lower()
				or q in row['date'].lower()
			)
		]
		self._render_list(filtered)

	def _render_list(self, quotes: list[dict]):
		if not self.winfo_exists():
			return
		for w in list(self._list_frame.winfo_children()):
			try:
				w.destroy()
			except Exception:
				pass

		if not quotes:
			ctk.CTkLabel(
				self._list_frame,
				text='Sin resultados',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
			).grid(row=0, column=0, pady=20)
			return
		for i, q in enumerate(quotes):
			self._list_card(self._list_frame, q, i)

	def _list_card(self, parent, q: dict, row: int):
		is_sel = q['id'] == self._selected_id
		bg = ACCENT_DIM if is_sel else SURFACE2
		bd = ACCENT if is_sel else BORDER

		card = ctk.CTkFrame(
			parent,
			fg_color=bg,
			border_color=bd,
			border_width=1,
			corner_radius=8,
			cursor='hand2',
		)
		card.grid(row=row, column=0, sticky='ew', pady=3)
		card.grid_columnconfigure(0, weight=1)

		r1 = ctk.CTkFrame(card, fg_color='transparent')
		r1.pack(fill='x', padx=10, pady=(8, 2))

		ctk.CTkLabel(
			r1, text=q['number'], font=FONT_LABEL_BOLD, text_color=TEXT_PRIMARY
		).pack(side='left')

		s_bg, s_fg = STATUS_THEME.get(q['status'], (SURFACE3, TEXT_SECONDARY))
		badge = ctk.CTkFrame(r1, fg_color=s_bg, corner_radius=10)
		badge.pack(side='right')
		ctk.CTkLabel(
			badge, text=q['status_label'], font=('Arial', 8), text_color=s_fg
		).pack(padx=6, pady=2)

		r2 = ctk.CTkFrame(card, fg_color='transparent')
		r2.pack(fill='x', padx=10, pady=(0, 4))
		cname = q['customer_name'] or 'Consumidor Final'
		ctk.CTkLabel(r2, text=cname, font=FONT_LABEL, text_color=TEXT_SECONDARY).pack(
			side='left'
		)
		ctk.CTkLabel(
			r2, text=q['date'][:10], font=FONT_LABEL, text_color=TEXT_MUTED
		).pack(side='right')

		r3 = ctk.CTkFrame(card, fg_color='transparent')
		r3.pack(fill='x', padx=10, pady=(0, 8))
		ctk.CTkLabel(
			r3,
			text=fmt_price(q['total_amount']),
			font=FONT_BODY_BOLD,
			text_color=ACCENT_TEXT,
		).pack(side='left')

		qid = q['id']

		def _bind_all(widget, qid=qid):
			widget.bind('<Button-1>', lambda e, i=qid: self._select(i))
			for child in widget.winfo_children():
				_bind_all(child, qid)

		_bind_all(card)

	def _select(self, qid: int):
		self._selected_id = qid
		self._apply_filter()
		self._show_detail(qid)

	# ─────────────────────────────────────────────────────────────────────────
	# Detalle
	# ─────────────────────────────────────────────────────────────────────────

	def _show_detail(self, qid: int):
		data = self._ctrl.get_quotation(qid)
		if not data:
			return
		self._clear_right()

		scroll = ctk.CTkScrollableFrame(
			self._right, fg_color='transparent', scrollbar_button_color=SURFACE3
		)
		scroll.grid(row=0, column=0, sticky='nsew', padx=20, pady=16)
		scroll.grid_columnconfigure(0, weight=1)

		r = 0

		hdr = ctk.CTkFrame(scroll, fg_color=SURFACE2, corner_radius=10)
		hdr.grid(row=r, column=0, sticky='ew', pady=(0, 10))
		r += 1

		top = ctk.CTkFrame(hdr, fg_color='transparent')
		top.pack(fill='x', padx=16, pady=(14, 6))
		ctk.CTkLabel(
			top, text=data['number'], font=FONT_TITLE, text_color=TEXT_PRIMARY
		).pack(side='left')
		s_bg, s_fg = STATUS_THEME.get(data['status'], (SURFACE3, TEXT_SECONDARY))
		badge = ctk.CTkFrame(top, fg_color=s_bg, corner_radius=12)
		badge.pack(side='right')
		ctk.CTkLabel(
			badge, text=data['status_label'], font=FONT_LABEL_BOLD, text_color=s_fg
		).pack(padx=12, pady=5)

		meta = ctk.CTkFrame(hdr, fg_color='transparent')
		meta.pack(fill='x', padx=16, pady=(0, 14))
		for col, (icon, lbl, val) in enumerate(
			[
				('📅', 'Fecha', data['date']),
				('⏳', 'Válido hasta', data['valid_until'] or '—'),
				('👤', 'Cliente', data['customer_name'] or 'Consumidor Final'),
			]
		):
			f = ctk.CTkFrame(meta, fg_color='transparent')
			f.grid(row=0, column=col, padx=(0, 28), sticky='w')
			ctk.CTkLabel(
				f, text=f'{icon} {lbl}', font=FONT_LABEL, text_color=TEXT_MUTED
			).pack(anchor='w')
			ctk.CTkLabel(
				f, text=val, font=FONT_LABEL_BOLD, text_color=TEXT_PRIMARY
			).pack(anchor='w')

		acts = ctk.CTkFrame(scroll, fg_color='transparent')
		acts.grid(row=r, column=0, sticky='ew', pady=(0, 10))
		r += 1

		for col, (txt, bg, hov, cmd) in enumerate(
			[
				(
					'✏  Editar',
					SURFACE3,
					SURFACE4,
					lambda d=data: self._open_form_edit(d),
				),
				(
					'📄  PDF',
					ACCENT,
					'#1d4ed8',
					lambda i=data['id']: self._export_pdf(i),
				),
				(
					'📋  Duplicar',
					SURFACE3,
					SURFACE4,
					lambda i=data['id']: self._duplicate(i),
				),
				(
					'🛒  Convertir',
					GREEN,
					'#15803d',
					lambda i=data['id']: self._convert_to_sale(i),
				),
				('🗑  Eliminar', RED, '#b91c1c', lambda i=data['id']: self._delete(i)),
			]
		):
			ctk.CTkButton(
				acts,
				text=txt,
				command=cmd,
				height=32,
				width=108,
				fg_color=bg,
				hover_color=hov,
				font=FONT_LABEL,
			).grid(row=0, column=col, padx=(0, 6))

		st_f = ctk.CTkFrame(scroll, fg_color=SURFACE2, corner_radius=8)
		st_f.grid(row=r, column=0, sticky='ew', pady=(0, 10))
		r += 1
		ctk.CTkLabel(
			st_f, text='Estado:', font=FONT_LABEL, text_color=TEXT_SECONDARY
		).pack(side='left', padx=12, pady=8)
		for s in STATUS_OPTIONS:
			s_bg2, s_fg2 = STATUS_THEME.get(s, (SURFACE3, TEXT_SECONDARY))
			active = data['status'] == s
			ctk.CTkButton(
				st_f,
				text=QuotationController.STATUS_LABELS[s],
				width=85,
				height=26,
				fg_color=s_bg2 if active else SURFACE3,
				hover_color=s_bg2,
				text_color=s_fg2 if active else TEXT_SECONDARY,
				font=FONT_LABEL_BOLD if active else FONT_LABEL,
				border_width=2 if active else 0,
				border_color=s_fg2
				if active
				else SURFACE3,  # CORRECCIÓN 1: Evitar ValueError de transparent
				command=lambda st=s, i=data['id']: self._change_status(i, st),
			).pack(side='left', padx=3, pady=8)

		tbl = ctk.CTkFrame(scroll, fg_color=SURFACE2, corner_radius=10)
		tbl.grid(row=r, column=0, sticky='ew', pady=(0, 10))
		r += 1
		tbl.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			tbl,
			text=f'Productos / Servicios  ({len(data["items"])} ítem{"s" if len(data["items"]) != 1 else ""})',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_PRIMARY,
		).grid(row=0, column=0, sticky='w', padx=14, pady=(10, 6))

		hd = ctk.CTkFrame(tbl, fg_color=SURFACE3, corner_radius=0)
		hd.grid(row=1, column=0, sticky='ew')
		hd.grid_columnconfigure(0, weight=1)
		hd.grid_columnconfigure(1, minsize=60)
		hd.grid_columnconfigure(2, minsize=100)
		hd.grid_columnconfigure(3, minsize=100)
		for ci, (txt, anc) in enumerate(
			[('Descripción', 'w'), ('Cant.', 'e'), ('P. Unit.', 'e'), ('Subtotal', 'e')]
		):
			ctk.CTkLabel(
				hd,
				text=txt,
				font=FONT_LABEL_BOLD,
				text_color=TEXT_SECONDARY,
			).grid(row=0, column=ci, padx=12, pady=5, sticky=anc)

		for ri, it in enumerate(data['items']):
			bg_row = SURFACE2 if ri % 2 == 0 else '#232323'
			row_f = ctk.CTkFrame(tbl, fg_color=bg_row, corner_radius=0)
			row_f.grid(row=ri + 2, column=0, sticky='ew')
			row_f.grid_columnconfigure(0, weight=1)
			row_f.grid_columnconfigure(1, minsize=60)
			row_f.grid_columnconfigure(2, minsize=100)
			row_f.grid_columnconfigure(3, minsize=100)
			qty = float(it['quantity'])
			qty_str = f'{int(qty)}' if qty == int(qty) else f'{qty:.3f}'
			for ci, (txt, anc) in enumerate(
				[
					(it['description'], 'w'),
					(qty_str, 'e'),
					(fmt_price(it['unit_price']), 'e'),
					(fmt_price(it['subtotal']), 'e'),
				]
			):
				ctk.CTkLabel(
					row_f, text=txt, font=FONT_LABEL, text_color=TEXT_PRIMARY
				).grid(row=0, column=ci, padx=12, pady=6, sticky=anc)

		tot_f = ctk.CTkFrame(tbl, fg_color='transparent')
		tot_f.grid(
			row=len(data['items']) + 2, column=0, sticky='e', padx=16, pady=(8, 14)
		)

		subtotal_val = sum(it['subtotal'] for it in data['items'])
		disc = data['discount_amount']

		def _tot_row(lbl, val, bold=False, color=None):
			f = ctk.CTkFrame(tot_f, fg_color='transparent')
			f.pack(fill='x', pady=1)
			fn = FONT_BODY_BOLD if bold else FONT_LABEL
			tc = color or (TEXT_PRIMARY if bold else TEXT_SECONDARY)
			ctk.CTkLabel(
				f, text=lbl, font=fn, text_color=tc, width=120, anchor='e'
			).pack(side='left')
			ctk.CTkLabel(
				f, text=val, font=fn, text_color=tc, width=110, anchor='e'
			).pack(side='left')

		_tot_row('Subtotal:', fmt_price(subtotal_val))
		if disc > 0:
			_tot_row('Descuento:', f'-{fmt_price(disc)}', color=ORANGE_TEXT)
		_tot_row('TOTAL:', fmt_price(data['total_amount']), bold=True)

		if data['notes']:
			nf = ctk.CTkFrame(scroll, fg_color=SURFACE2, corner_radius=10)
			nf.grid(row=r, column=0, sticky='ew', pady=(0, 10))
			r += 1
			ctk.CTkLabel(
				nf,
				text='📝  Notas / Condiciones',
				font=FONT_LABEL_BOLD,
				text_color=TEXT_SECONDARY,
			).pack(anchor='w', padx=14, pady=(10, 4))
			ctk.CTkLabel(
				nf,
				text=data['notes'],
				font=FONT_LABEL,
				text_color=TEXT_PRIMARY,
				wraplength=640,
				justify='left',
			).pack(anchor='w', padx=14, pady=(0, 12))

	# ─────────────────────────────────────────────────────────────────────────
	# Formulario
	# ─────────────────────────────────────────────────────────────────────────

	def _open_form_new(self):
		self._edit_id = None
		self._items = []
		self._item_widgets = []
		self._render_form(prefill=None)

	def _open_form_edit(self, data: dict):
		self._edit_id = data['id']
		self._items = [dict(it) for it in data['items']]
		self._item_widgets = []
		self._render_form(prefill=data)

	def _render_form(self, prefill: dict | None):
		self._clear_right()
		self._entry_disc = None
		self._tot_frame = None

		scroll = ctk.CTkScrollableFrame(
			self._right, fg_color='transparent', scrollbar_button_color=SURFACE3
		)
		scroll.grid(row=0, column=0, sticky='nsew', padx=20, pady=16)
		scroll.grid_columnconfigure(0, weight=1)

		r = 0

		title_txt = 'Editar Cotización' if self._edit_id else 'Nueva Cotización'
		ctk.CTkLabel(
			scroll, text=title_txt, font=FONT_TITLE, text_color=TEXT_PRIMARY
		).grid(row=r, column=0, sticky='w', pady=(0, 12))
		r += 1

		gen = ctk.CTkFrame(scroll, fg_color=SURFACE2, corner_radius=10)
		gen.grid(row=r, column=0, sticky='ew', pady=(0, 10))
		r += 1
		gen.grid_columnconfigure((0, 1, 2), weight=1)

		ctk.CTkLabel(
			gen, text='Datos generales', font=FONT_LABEL_BOLD, text_color=TEXT_SECONDARY
		).grid(row=0, column=0, columnspan=3, sticky='w', padx=14, pady=(10, 6))

		ctk.CTkLabel(
			gen, text='Cliente (opcional)', font=FONT_LABEL, text_color=TEXT_SECONDARY
		).grid(row=1, column=0, sticky='w', padx=14)
		self._customers = self._load_customers()
		cust_names = ['Consumidor Final'] + [c['name'] for c in self._customers]
		self._combo_cust = ctk.CTkOptionMenu(
			gen,
			values=cust_names,
			fg_color=SURFACE3,
			button_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			text_color=TEXT_PRIMARY,
			font=FONT_LABEL,
			height=32,
		)
		self._combo_cust.grid(row=2, column=0, sticky='ew', padx=14, pady=(2, 10))
		if prefill and prefill.get('customer_name'):
			self._combo_cust.set(prefill['customer_name'])

		ctk.CTkLabel(
			gen, text='Días de validez', font=FONT_LABEL, text_color=TEXT_SECONDARY
		).grid(row=1, column=1, sticky='w', padx=14)
		self._entry_valid = ctk.CTkEntry(
			gen,
			height=32,
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
		)
		self._entry_valid.grid(row=2, column=1, sticky='ew', padx=14, pady=(2, 10))
		if prefill and prefill.get('valid_until_raw'):
			days_left = (prefill['valid_until_raw'] - datetime.utcnow().date()).days
			self._entry_valid.insert(0, str(max(days_left, 1)))
		else:
			self._entry_valid.insert(0, '15')

		ctk.CTkLabel(
			gen, text='Descuento ($)', font=FONT_LABEL, text_color=TEXT_SECONDARY
		).grid(row=1, column=2, sticky='w', padx=14)
		self._entry_disc = ctk.CTkEntry(
			gen,
			height=32,
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
		)
		self._entry_disc.grid(row=2, column=2, sticky='ew', padx=14, pady=(2, 10))
		disc_prefill = str(prefill['discount_amount']) if prefill else '0'
		if disc_prefill.endswith('.0'):
			disc_prefill = disc_prefill[:-2]
		self._entry_disc.insert(0, disc_prefill)
		self._entry_disc.bind('<KeyRelease>', lambda e: self._update_totals_label())

		ctk.CTkLabel(
			gen, text='Notas / Condiciones', font=FONT_LABEL, text_color=TEXT_SECONDARY
		).grid(row=3, column=0, columnspan=3, sticky='w', padx=14)
		self._entry_notes = ctk.CTkTextbox(
			gen,
			height=60,
			fg_color=SURFACE3,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
		)
		self._entry_notes.grid(
			row=4, column=0, columnspan=3, sticky='ew', padx=14, pady=(2, 12)
		)
		if prefill and prefill.get('notes'):
			self._entry_notes.insert('1.0', prefill['notes'])

		self._tot_frame = ctk.CTkFrame(scroll, fg_color=SURFACE2, corner_radius=10)
		self._tot_frame.grid(row=r, column=0, sticky='ew', pady=(0, 10))
		r += 1
		self._update_totals_label()

		items_outer = ctk.CTkFrame(scroll, fg_color=SURFACE2, corner_radius=10)
		items_outer.grid(row=r, column=0, sticky='ew', pady=(0, 10))
		r += 1
		items_outer.grid_columnconfigure(0, weight=1)

		bar = ctk.CTkFrame(items_outer, fg_color='transparent')
		bar.pack(fill='x', padx=14, pady=(10, 6))
		bar.grid_columnconfigure(0, weight=1)
		ctk.CTkLabel(
			bar,
			text='Productos / Servicios',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
		).grid(row=0, column=0, sticky='w')
		ctk.CTkButton(
			bar,
			text='+ Ítem manual',
			width=110,
			height=28,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			font=FONT_LABEL,
			command=self._add_item_row,
		).grid(row=0, column=1, padx=(4, 0))

		srch = ctk.CTkFrame(items_outer, fg_color=SURFACE3, corner_radius=8)
		srch.pack(fill='x', padx=14, pady=(0, 6))
		ctk.CTkLabel(
			srch,
			text='🔍  Buscar artículo del catálogo',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=10, pady=(6, 2))
		srch_row = ctk.CTkFrame(srch, fg_color='transparent')
		srch_row.pack(fill='x', padx=10, pady=(0, 4))
		srch_row.grid_columnconfigure(0, weight=1)
		self._entry_art_search = ctk.CTkEntry(
			srch_row,
			height=32,
			placeholder_text='Nombre o código de barras...',
			fg_color=SURFACE2,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
		)
		self._entry_art_search.grid(row=0, column=0, sticky='ew', padx=(0, 6))
		ctk.CTkButton(
			srch_row,
			text='Agregar',
			width=80,
			height=32,
			fg_color=ACCENT,
			hover_color='#1d4ed8',
			font=FONT_LABEL,
			command=self._art_pick_first,
		).grid(row=0, column=1)
		self._entry_art_search.bind('<KeyRelease>', self._on_art_search)
		self._entry_art_search.bind('<Return>', lambda e: self._art_pick_first())
		self._entry_art_search.bind('<Escape>', lambda e: self._close_art_results())

		self._art_results_frame = ctk.CTkFrame(srch, fg_color=SURFACE2, corner_radius=6)
		self._art_results_visible = False
		self._last_art_results = []

		self._items_outer_ref = items_outer
		self._items_table_frame = ctk.CTkFrame(items_outer, fg_color='transparent')
		self._items_table_frame.pack(fill='x', padx=14, pady=(4, 14))
		self._rebuild_items_table()

		footer = ctk.CTkFrame(scroll, fg_color='transparent')
		footer.grid(row=r, column=0, sticky='ew', pady=(0, 20))
		r += 1

		ctk.CTkButton(
			footer,
			text='💾  Guardar cotización',
			height=38,
			fg_color=ACCENT,
			hover_color='#1d4ed8',
			font=FONT_BODY_BOLD,
			command=self._save_form,
		).pack(side='left', padx=(0, 8))
		ctk.CTkButton(
			footer,
			text='Cancelar',
			height=38,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			font=FONT_BODY,
			command=self._cancel_form,
		).pack(side='left')

	def _load_customers(self) -> list[dict]:
		try:
			from sqlalchemy.orm import sessionmaker

			from database.models import Customer

			Session = sessionmaker(bind=self.ctx.db_engine)
			with Session() as s:
				rows = (
					s.query(Customer)
					.filter_by(tenant_id=self.ctx.tenant_id, is_active=True)
					.order_by(Customer.name)
					.all()
				)
				return [{'id': c.id, 'name': c.name} for c in rows]
		except Exception:
			return []

	# ── Búsqueda de artículos ─────────────────────────────────────────────────

	def _on_art_search(self, event=None):
		if not self.winfo_exists():
			return
		query = self._entry_art_search.get().strip()
		if not query:
			self._close_art_results()
			return
		results = self._ctrl.search_variants(self.ctx.tenant_id, query)
		self._last_art_results = results

		for w in list(self._art_results_frame.winfo_children()):
			try:
				w.destroy()
			except Exception:
				pass

		if not results:
			ctk.CTkLabel(
				self._art_results_frame,
				text=f'  Sin resultados para "{query}"',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
				anchor='w',
			).pack(fill='x', padx=8, pady=6)
		else:
			for res in results[:10]:
				f = ctk.CTkFrame(
					self._art_results_frame,
					fg_color='transparent',
					cursor='hand2',
				)
				f.pack(fill='x', padx=4, pady=1)
				lbl = ctk.CTkLabel(
					f,
					text=f'  {res["label"]}   {fmt_price(res["selling_price"])}',
					font=FONT_LABEL,
					text_color=TEXT_PRIMARY,
					anchor='w',
					cursor='hand2',
				)
				lbl.pack(fill='x', ipady=4)

				# CORRECCIÓN 3: Validar que el widget exista al dispararse los eventos del mouse
				for widget in (f, lbl):
					widget.bind('<Button-1>', lambda e, r=res: self._pick_article(r))
					widget.bind(
						'<Enter>',
						lambda e, w=f: (
							w.configure(fg_color=SURFACE3) if w.winfo_exists() else None
						),
					)
					widget.bind(
						'<Leave>',
						lambda e, w=f: (
							w.configure(fg_color='transparent')
							if w.winfo_exists()
							else None
						),
					)

		if not self._art_results_visible:
			self._art_results_frame.pack(fill='x', padx=10, pady=(0, 8))
			self._art_results_visible = True

	def _art_pick_first(self):
		if not self.winfo_exists():
			return
		query = self._entry_art_search.get().strip()
		if not query:
			return
		if not getattr(self, '_last_art_results', None):
			self._on_art_search()
		if self._last_art_results:
			self._pick_article(self._last_art_results[0])

	def _close_art_results(self):
		if self._art_results_frame.winfo_exists():
			self._art_results_frame.pack_forget()
		self._art_results_visible = False
		self._last_art_results = []

	def _pick_article(self, res: dict):
		self._sync_items_from_widgets()
		self._items.append(
			{
				'description': res['label'],
				'quantity': 1.0,
				'unit_price': res['selling_price'],
				'subtotal': res['selling_price'],
				'variant_id': res['variant_id'],
			}
		)
		self._close_art_results()
		if self._entry_art_search.winfo_exists():
			self._entry_art_search.delete(0, 'end')
		self._rebuild_items_table()

	def _add_item_row(self):
		self._sync_items_from_widgets()
		self._items.append(
			{
				'description': '',
				'quantity': 1.0,
				'unit_price': 0.0,
				'subtotal': 0.0,
				'variant_id': None,
			}
		)
		self._rebuild_items_table(focus_last=True)

	# ── Tabla de ítems del formulario ─────────────────────────────────────────

	def _rebuild_items_table(self, focus_last=False):
		if not self.winfo_exists():
			return
		for w in list(self._items_table_frame.winfo_children()):
			try:
				w.destroy()
			except Exception:
				pass

		self._item_widgets = []

		if not self._items:
			ctk.CTkLabel(
				self._items_table_frame,
				text='Sin ítems. Buscá un artículo o usá "+ Ítem manual".',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
			).pack(pady=10)
			self._update_totals_label()
			return

		hrow = ctk.CTkFrame(self._items_table_frame, fg_color=SURFACE3, corner_radius=4)
		hrow.pack(fill='x', pady=(0, 2))
		hrow.grid_columnconfigure(0, weight=1)
		for ci, (txt, w, anc) in enumerate(
			[
				('Descripción', 0, 'w'),
				('Cant.', 60, 'e'),
				('Precio unit.', 90, 'e'),
				('Subtotal', 90, 'e'),
				('', 34, 'ew'),
			]
		):
			ctk.CTkLabel(
				hrow,
				text=txt,
				font=FONT_LABEL_BOLD,
				text_color=TEXT_SECONDARY,
				width=w if w else 0,
			).grid(row=0, column=ci, padx=6, pady=4, sticky=anc if ci > 0 else 'w')
		hrow.grid_columnconfigure(0, weight=1)

		first_desc_entry = None
		for idx, it in enumerate(self._items):
			row_f = ctk.CTkFrame(self._items_table_frame, fg_color='transparent')
			row_f.pack(fill='x', pady=2)
			row_f.grid_columnconfigure(0, weight=1)

			e_desc = ctk.CTkEntry(
				row_f,
				height=28,
				fg_color=SURFACE3,
				border_color=BORDER,
				text_color=TEXT_PRIMARY,
				placeholder_text='Descripción del producto/servicio',
			)
			e_desc.grid(row=0, column=0, sticky='ew', padx=(0, 4))
			e_desc.insert(0, it.get('description', ''))
			if idx == 0 and first_desc_entry is None:
				first_desc_entry = e_desc

			e_qty = ctk.CTkEntry(
				row_f,
				width=60,
				height=28,
				fg_color=SURFACE3,
				border_color=BORDER,
				text_color=TEXT_PRIMARY,
			)
			e_qty.grid(row=0, column=1, padx=(0, 4))
			e_qty.insert(0, str(it.get('quantity', 1)))

			e_price = ctk.CTkEntry(
				row_f,
				width=90,
				height=28,
				fg_color=SURFACE3,
				border_color=BORDER,
				text_color=TEXT_PRIMARY,
			)
			e_price.grid(row=0, column=2, padx=(0, 4))
			e_price.insert(0, str(it.get('unit_price', 0)))

			lbl_sub = ctk.CTkLabel(
				row_f,
				text='$0',
				width=90,
				font=FONT_LABEL,
				text_color=ACCENT_TEXT,
				anchor='e',
			)
			lbl_sub.grid(row=0, column=3, padx=(0, 4))

			btn_del = ctk.CTkButton(
				row_f,
				text='✕',
				width=30,
				height=28,
				fg_color=RED_DIM,
				hover_color=RED,
				text_color=RED_TEXT,
				font=FONT_LABEL,
				command=lambda i=idx: self._remove_item(i),
			)
			btn_del.grid(row=0, column=4)

			# CORRECCIÓN 3: Validar que el Entry exista al momento de recalcular (al cerrar la ventana se disparan KeyRelease sueltos)
			def _upd(e=None, i=idx, eq=e_qty, ep=e_price, ls=lbl_sub, ed=e_desc):
				if not eq.winfo_exists():
					return
				self._recalc_item(i, eq, ep, ls)
				if i < len(self._items):
					self._items[i]['description'] = ed.get()

			e_qty.bind('<KeyRelease>', _upd)
			e_price.bind('<KeyRelease>', _upd)
			e_desc.bind('<KeyRelease>', _upd)
			_upd()

			self._item_widgets.append((e_desc, e_qty, e_price, lbl_sub))

		if focus_last and self._item_widgets:
			self._item_widgets[-1][0].focus_set()

		self._update_totals_label()

	def _recalc_item(self, idx, e_qty, e_price, lbl_sub):
		try:
			qty = Decimal(str(e_qty.get() or '0').replace(',', '.'))
			price = Decimal(str(e_price.get() or '0').replace(',', '.'))
			sub = (qty * price).quantize(Decimal('0.01'))
			if idx < len(self._items):
				self._items[idx]['quantity'] = float(qty)
				self._items[idx]['unit_price'] = float(price)
				self._items[idx]['subtotal'] = float(sub)
			if lbl_sub.winfo_exists():
				lbl_sub.configure(text=fmt_price(float(sub)))
		except (InvalidOperation, Exception):
			pass
		self._update_totals_label()

	def _remove_item(self, idx: int):
		self._sync_items_from_widgets()
		if 0 <= idx < len(self._items):
			self._items.pop(idx)
		self._rebuild_items_table()

	def _update_totals_label(self):
		if self._tot_frame is None or not self.winfo_exists():
			return
		for w in list(self._tot_frame.winfo_children()):
			try:
				w.destroy()
			except Exception:
				pass

		try:
			disc = (
				Decimal(str(self._entry_disc.get() or '0').replace(',', '.'))
				if self._entry_disc and self._entry_disc.winfo_exists()
				else Decimal('0')
			)
		except (InvalidOperation, Exception):
			disc = Decimal('0')

		subtotal = sum(Decimal(str(it.get('subtotal', 0))) for it in self._items)
		total = max(subtotal - disc, Decimal('0'))

		f = ctk.CTkFrame(self._tot_frame, fg_color='transparent')
		f.pack(anchor='e', padx=16, pady=8)
		if disc > 0:
			ctk.CTkLabel(
				f,
				text=f'Subtotal: {fmt_price(float(subtotal))}',
				font=FONT_LABEL,
				text_color=TEXT_SECONDARY,
			).pack(anchor='e')
			ctk.CTkLabel(
				f,
				text=f'Descuento: -{fmt_price(float(disc))}',
				font=FONT_LABEL,
				text_color=ORANGE_TEXT,
			).pack(anchor='e')
		ctk.CTkLabel(
			f,
			text=f'TOTAL: {fmt_price(float(total))}',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
		).pack(anchor='e')

	def _sync_items_from_widgets(self):
		for idx, (e_desc, e_qty, e_price, lbl_sub) in enumerate(self._item_widgets):
			if idx >= len(self._items):
				break
			try:
				if e_qty.winfo_exists():
					qty = float(str(e_qty.get() or '1').replace(',', '.'))
					price = float(str(e_price.get() or '0').replace(',', '.'))
					sub = round(qty * price, 2)
				else:
					qty, price, sub = 1.0, 0.0, 0.0
			except Exception:
				qty, price, sub = 1.0, 0.0, 0.0

			if e_desc.winfo_exists():
				self._items[idx]['description'] = e_desc.get()
			self._items[idx]['quantity'] = qty
			self._items[idx]['unit_price'] = price
			self._items[idx]['subtotal'] = sub

	# ─────────────────────────────────────────────────────────────────────────
	# Guardar
	# ─────────────────────────────────────────────────────────────────────────

	def _save_form(self):
		self._sync_items_from_widgets()

		if not self._items:
			CTkMessagebox(
				title='Falta información',
				message='Agregá al menos un ítem a la cotización.',
				icon='warning',
			)
			return
		empty_descs = [
			i + 1
			for i, it in enumerate(self._items)
			if not it.get('description', '').strip()
		]
		if empty_descs:
			CTkMessagebox(
				title='Falta información',
				message=f'El ítem {"#" + str(empty_descs[0])} no tiene descripción.',
				icon='warning',
			)
			return
		no_price = [
			i + 1
			for i, it in enumerate(self._items)
			if float(it.get('unit_price', 0)) == 0
		]
		if no_price:
			CTkMessagebox(
				title='Falta información',
				message=f'El ítem #{no_price[0]} tiene precio $0. Verificá antes de guardar.',
				icon='warning',
			)
			return

		cust_name = self._combo_cust.get()
		cust_id = next(
			(c['id'] for c in self._customers if c['name'] == cust_name), None
		)

		try:
			valid_days = int(self._entry_valid.get() or '15')
			valid_days = max(valid_days, 0)
		except Exception:
			valid_days = 15

		try:
			disc = float(str(self._entry_disc.get() or '0').replace(',', '.'))
		except Exception:
			disc = 0.0

		notes = self._entry_notes.get('1.0', 'end').strip()

		if self._edit_id:
			valid_until = (
				(datetime.utcnow() + timedelta(days=valid_days)).date()
				if valid_days > 0
				else None
			)
			ok, result = self._ctrl.update_quotation(
				quotation_id=self._edit_id,
				items=self._items,
				customer_id=cust_id,
				valid_until=valid_until,
				notes=notes,
				discount_amount=disc,
			)
		else:
			ok, result = self._ctrl.create_quotation(
				tenant_id=self.ctx.tenant_id,
				user_id=self.ctx.user_id,
				items=self._items,
				customer_id=cust_id,
				valid_days=valid_days,
				notes=notes,
				discount_amount=disc,
			)

		if ok:
			new_id = result['id']
			self._edit_id = None
			self._load_list()
			self._selected_id = new_id
			self._apply_filter()
			self._show_detail(new_id)
		else:
			CTkMessagebox(title='Error al guardar', message=str(result), icon='cancel')

	def _cancel_form(self):
		self._edit_id = None
		if self._selected_id:
			self._show_detail(self._selected_id)
		else:
			self._show_empty_state()

	# ─────────────────────────────────────────────────────────────────────────
	# Acciones
	# ─────────────────────────────────────────────────────────────────────────

	def _export_pdf(self, qid: int):
		ok, result = self._ctrl.generate_pdf(qid)
		if ok:
			CTkMessagebox(
				title='PDF generado',
				message='El PDF se abrió automáticamente.',
				icon='check',
			)
		else:
			CTkMessagebox(
				title='Error al generar PDF', message=str(result), icon='cancel'
			)

	def _duplicate(self, qid: int):
		ok, result = self._ctrl.duplicate_quotation(qid, self.ctx.user_id)
		if ok:
			self._load_list()
			self._selected_id = result['id']
			self._apply_filter()
			self._show_detail(result['id'])
			CTkMessagebox(
				title='Cotización duplicada',
				message=f'Se creó {result["number"]} como borrador.',
				icon='check',
			)
		else:
			CTkMessagebox(title='Error', message=str(result), icon='cancel')

	def _change_status(self, qid: int, new_status: str):
		ok, _ = self._ctrl.set_status(qid, new_status)
		if ok:
			self._load_list()
			self._show_detail(qid)

	def _delete(self, qid: int):
		msg = CTkMessagebox(
			title='Eliminar cotización',
			message='¿Eliminar esta cotización? Esta acción no se puede deshacer.',
			icon='warning',
			option_1='Cancelar',
			option_2='Eliminar',
		)
		if msg.get() != 'Eliminar':
			return
		ok, result = self._ctrl.delete_quotation(qid)
		if ok:
			self._selected_id = None
			self._load_list()
			self._show_empty_state()
		else:
			CTkMessagebox(title='Error', message=result, icon='cancel')

	def _convert_to_sale(self, qid: int):
		data = self._ctrl.get_quotation(qid)
		if not data:
			return
		if data['status'] == 'rechazada':
			CTkMessagebox(
				title='No permitido',
				message='No se puede convertir una cotización rechazada.',
				icon='warning',
			)
			return
		if float(data['total_amount']) <= 0:
			CTkMessagebox(
				title='Total inválido',
				message='El total de la cotización debe ser mayor a $0.',
				icon='warning',
			)
			return

		popup = ctk.CTkToplevel(self)
		popup.title('Convertir a Venta')
		popup.geometry('380x240')
		popup.resizable(False, False)
		popup.grab_set()
		popup.focus_set()

		ctk.CTkLabel(
			popup,
			text=f'Cotización {data["number"]}',
			font=FONT_BODY_BOLD,
			text_color=TEXT_PRIMARY,
		).pack(pady=(20, 4))
		ctk.CTkLabel(
			popup,
			text=fmt_price(data['total_amount']),
			font=FONT_TITLE,
			text_color=ACCENT_TEXT,
		).pack()
		ctk.CTkLabel(
			popup,
			text='Esto creará una venta real y cerrará la cotización.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(pady=(6, 0))

		ctk.CTkLabel(
			popup, text='Método de pago:', font=FONT_LABEL, text_color=TEXT_SECONDARY
		).pack(pady=(14, 2))
		pay_var = ctk.StringVar(value='efectivo')
		ctk.CTkOptionMenu(
			popup,
			values=['efectivo', 'transferencia', 'tarjeta', 'fiado'],
			variable=pay_var,
			fg_color=SURFACE3,
			button_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			text_color=TEXT_PRIMARY,
			font=FONT_LABEL,
		).pack(padx=40, fill='x')

		def _do():
			ok, result = self._ctrl.convert_to_sale(
				quotation_id=qid,
				user_id=self.ctx.user_id,
				payment_method=pay_var.get(),
			)
			popup.destroy()
			if ok:
				CTkMessagebox(
					title='Venta generada',
					message=f'Venta #{result} creada correctamente.',
					icon='check',
				)
				self._load_list()
				self._show_detail(qid)
			else:
				CTkMessagebox(title='Error', message=result, icon='cancel')

		ctk.CTkButton(
			popup,
			text='✔  Confirmar y crear venta',
			fg_color=GREEN,
			hover_color='#15803d',
			font=FONT_BODY_BOLD,
			height=36,
			command=_do,
		).pack(pady=14)
