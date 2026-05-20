"""
views/label_view.py
===================
Vista para gestionar y previsualizar la impresión masiva de etiquetas.
"""

import logging
import threading
import tkinter as tk
from datetime import datetime

import customtkinter as ctk
from sqlalchemy.orm import sessionmaker

import utils.settings_manager as _cfg_mgr
from controllers.label_controller import TEMPLATES, LabelController
from utils.date_picker import CTkDatePicker
from core.base_view import BaseView
from core.context import AppContext
from utils.settings_manager import fmt_price
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_HOVER,
	ACCENT_TEXT,
	BORDER,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_HEADING,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	GREEN,
	GREEN_HOVER,
	ORANGE_TEXT,
	PAD_LG,
	PAD_MD,
	PAD_SM,
	PAD_XS,
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

TEMPLATE_KEYS = list(TEMPLATES.keys())


class LabelView(BaseView):
	def __init__(self, master, ctx: AppContext, **kwargs):
		super().__init__(master, ctx, **kwargs)
		self._ctrl = LabelController()
		self._variants: list[dict] = []
		self._queue: list[dict] = []
		self._selected_variants: set = set()
		self._tpl_key = 'supermercado'
		self._search_timer = None
		self._load_price_list_cfg()

		self._build()

		self.after(120, self._load_catalog)
		self.after(100, self._setup_bindings)
		self.after(150, self._refresh_price_list_bar)
		self.after(200, lambda: self._entry_search.focus())

	def _load_price_list_cfg(self):
		cfg = _cfg_mgr.load()
		self._list_a_name = cfg.get('price_list_a_name', 'Minorista')
		self._list_b_name = cfg.get('price_list_b_name', 'Mayorista')
		self._price_options: list[tuple] = [
			('retail', f'Lista A · {self._list_a_name}', 1.0),
			('price_b', f'Lista B · {self._list_b_name}', None),
		]

	def _load_wholesale_cfg(self):
		self._load_price_list_cfg()

	def _build(self):
		self.grid_columnconfigure(0, weight=2) # Catálogo
		self.grid_columnconfigure(1, weight=3) # Cola
		self.grid_columnconfigure(2, weight=2) # Preview
		self.grid_rowconfigure(0, weight=1)
		
		self._build_left()
		self._build_center()
		self._build_right()

	def _build_left(self):
		# Panel de Catálogo (Bento 1)
		left = ctk.CTkFrame(self, fg_color=SURFACE1, corner_radius=12, border_width=1, border_color=BORDER)
		left.grid(row=0, column=0, sticky='nsew', padx=(PAD_MD, PAD_SM), pady=PAD_MD)
		left.grid_rowconfigure(2, weight=1)
		left.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			left,
			text='📦  CATÁLOGO',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
		).grid(row=0, column=0, sticky='w', padx=PAD_MD, pady=(PAD_MD, PAD_XS))

		srch_f = ctk.CTkFrame(left, fg_color='transparent')
		srch_f.grid(row=1, column=0, sticky='ew', padx=PAD_MD, pady=(0, PAD_SM))
		srch_f.grid_columnconfigure(0, weight=1)

		self._entry_search = ctk.CTkEntry(
			srch_f,
			placeholder_text='Buscar artículo...',
			height=36,
			fg_color=SURFACE2,
			border_color=BORDER,
			font=FONT_BODY,
		)
		self._entry_search.grid(row=0, column=0, sticky='ew')
		self._entry_search.bind('<KeyRelease>', self._debounced_search)

		self._catalog_frame = ctk.CTkScrollableFrame(
			left,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
		)
		self._catalog_frame.grid(row=2, column=0, sticky='nsew', padx=PAD_SM, pady=(0, PAD_SM))
		self._catalog_frame.grid_columnconfigure(0, weight=1)

		action_bar = ctk.CTkFrame(left, fg_color='transparent')
		action_bar.grid(row=3, column=0, sticky='ew', padx=PAD_MD, pady=(0, PAD_MD))
		action_bar.grid_columnconfigure(0, weight=1)
		action_bar.grid_columnconfigure(1, weight=1)

		ctk.CTkButton(
			action_bar,
			text='✓  Seleccionados',
			height=32,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			font=FONT_LABEL_BOLD,
			command=self._add_selected_to_queue,
		).grid(row=0, column=0, sticky='ew', padx=(0, PAD_XS))

		ctk.CTkButton(
			action_bar,
			text='✎  Artículo manual',
			height=32,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			font=FONT_LABEL_BOLD,
			command=self._open_custom_article_dialog,
		).grid(row=0, column=1, sticky='ew', padx=(PAD_XS, 0))

	def _build_center(self):
		# Panel de Cola de Impresión (Bento 2)
		center = ctk.CTkFrame(self, fg_color=SURFACE1, corner_radius=12, border_width=1, border_color=BORDER)
		center.grid(row=0, column=1, sticky='nsew', padx=PAD_SM, pady=PAD_MD)
		center.grid_rowconfigure(3, weight=1)
		center.grid_columnconfigure(0, weight=1)

		hdr = ctk.CTkFrame(center, fg_color='transparent')
		hdr.grid(row=0, column=0, sticky='ew', padx=PAD_MD, pady=PAD_MD)
		hdr.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			hdr,
			text='📑  COLA DE IMPRESIÓN',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
		).grid(row=0, column=0, sticky='w')

		self._lbl_total = ctk.CTkLabel(
			hdr,
			text='0 etiquetas',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		)
		self._lbl_total.grid(row=0, column=1, padx=PAD_SM)

		ctk.CTkButton(
			hdr,
			text='Limpiar',
			width=70,
			height=26,
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			font=FONT_LABEL_BOLD,
			command=self._confirm_clear_queue,
		).grid(row=0, column=2)

		# Barra de Precio (Wholesale / Retail)
		self._wholesale_bar = ctk.CTkFrame(center, fg_color=SURFACE2, corner_radius=8)
		self._wholesale_bar.grid(row=1, column=0, sticky='ew', padx=PAD_MD, pady=(0, PAD_MD))

		# Selector de Plantilla rápido
		tpl_bar = ctk.CTkFrame(center, fg_color=SURFACE2, corner_radius=8)
		tpl_bar.grid(row=2, column=0, sticky='ew', padx=PAD_MD, pady=(0, PAD_MD))
		
		self._tpl_btns = {}
		for i, (key, tpl) in enumerate(TEMPLATES.items()):
			btn = ctk.CTkButton(
				tpl_bar,
				text=f"{tpl['icon']} {tpl['label']}",
				height=30,
				font=FONT_LABEL_BOLD,
				fg_color=ACCENT_DIM if key == self._tpl_key else 'transparent',
				text_color=ACCENT_TEXT if key == self._tpl_key else TEXT_SECONDARY,
				hover_color=SURFACE3,
				command=lambda k=key: self._select_template(k),
			)
			btn.pack(side='left', padx=2, pady=4, expand=True)
			self._tpl_btns[key] = btn

		self._queue_frame = ctk.CTkScrollableFrame(
			center,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
		)
		self._queue_frame.grid(row=3, column=0, sticky='nsew', padx=PAD_SM, pady=(0, PAD_SM))
		self._queue_frame.grid_columnconfigure(0, weight=1)

		# Botón de Impresión
		self._btn_print = ctk.CTkButton(
			center,
			text='🖨  GENERAR PDF (Ctrl+P)',
			height=48,
			fg_color=GREEN,
			hover_color=GREEN_HOVER,
			font=FONT_BODY_BOLD,
			command=self._print_labels,
		)
		self._btn_print.grid(row=4, column=0, sticky='ew', padx=PAD_MD, pady=PAD_MD)

	def _build_right(self):
		# Panel de Preview (Bento 3)
		right = ctk.CTkFrame(self, fg_color=SURFACE1, corner_radius=12, border_width=1, border_color=BORDER)
		right.grid(row=0, column=2, sticky='nsew', padx=(PAD_SM, PAD_MD), pady=PAD_MD)
		right.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			right,
			text='✨  LIVE PREVIEW',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=PAD_MD, pady=PAD_MD)

		# Contenedor de la etiqueta simulada
		self._preview_container = ctk.CTkFrame(right, fg_color=SURFACE2, corner_radius=12)
		self._preview_container.pack(fill='both', expand=True, padx=PAD_MD, pady=(0, PAD_MD))
		
		self._preview_label_card = ctk.CTkFrame(
			self._preview_container,
			fg_color='white',
			corner_radius=4,
			width=220,
			height=150,
		)
		self._preview_label_card.place(relx=0.5, rely=0.4, anchor='center')
		self._preview_label_card.pack_propagate(False)

		self._build_live_preview_widgets()

	def _build_live_preview_widgets(self):
		if not self.winfo_exists():
			return
		card = self._preview_label_card
		for w in list(card.winfo_children()):
			try:
				w.destroy()
			except Exception:
				pass

		# Reset widget references
		self._pw_header = None
		self._pw_brand = None
		self._pw_name = None
		self._pw_attr = None
		self._pw_price_before = None
		self._pw_price = None
		self._pw_bc_zone = None
		self._pw_footer_label = None
		self._pw_footer = None
		self._pw_body = None

		tpl_styles = {
			'supermercado': {'hdr_color': '#1e293b', 'hdr_h': 20, 'name_font': 9,  'price_font': 18, 'bc_h': 24, 'price_color': '#0f172a'},
			'producto':     {'hdr_color': '#0f172a', 'hdr_h': 22, 'name_font': 11, 'price_font': 22, 'bc_h': 28, 'price_color': '#0f172a'},
			'precio':       {'hdr_color': '#1e293b', 'hdr_h': 10, 'name_font': 8,  'price_font': 20, 'bc_h': 18, 'price_color': '#0f172a'},
			'mini':         {'hdr_color': '#f77f00', 'hdr_h': 14, 'name_font': 7,  'price_font': 14, 'bc_h': 18, 'price_color': '#f77f00'},
		}
		st = tpl_styles.get(self._tpl_key, tpl_styles['supermercado'])

		card.configure(fg_color='white', border_width=0)

		# Grid layout inside card so row weights work correctly.
		# pack(expand=True) on the body would steal ALL remaining space,
		# leaving separator / bc_zone / footer with zero height.
		card.grid_columnconfigure(0, weight=1)
		card.grid_rowconfigure(1, weight=1)   # body row expands
		card.grid_propagate(False)            # keep card at its declared 220×150

		# Row 0 — Header
		self._pw_header = ctk.CTkFrame(
			card, fg_color=st['hdr_color'], corner_radius=0, height=st['hdr_h']
		)
		self._pw_header.grid(row=0, column=0, sticky='ew')
		self._pw_header.pack_propagate(False)
		self._pw_brand = ctk.CTkLabel(
			self._pw_header, text='MI NEGOCIO',
			font=('Arial', 7, 'bold'), text_color='white', anchor='center',
		)
		self._pw_brand.pack(expand=True, fill='both', padx=4)

		# Row 1 — Body (expands)
		self._pw_body = ctk.CTkFrame(card, fg_color='white', corner_radius=0)
		self._pw_body.grid(row=1, column=0, sticky='nsew', padx=6, pady=(3, 2))

		self._pw_name = ctk.CTkLabel(
			self._pw_body, text='Nombre del Producto',
			font=('Arial', st['name_font'], 'bold'), text_color='black',
			anchor='w', wraplength=195, justify='left',
		)
		self._pw_name.pack(fill='x', anchor='w')

		self._pw_attr = ctk.CTkLabel(
			self._pw_body, text='',
			font=('Arial', 6), text_color='#64748b', anchor='w',
		)
		self._pw_attr.pack(fill='x', anchor='w')

		self._pw_price_before = ctk.CTkLabel(
			self._pw_body, text='',
			font=('Arial', 6), text_color='#94a3b8', anchor='w',
		)
		self._pw_price_before.pack(fill='x', anchor='w', pady=(2, 0))

		self._pw_price = ctk.CTkLabel(
			self._pw_body, text='$0',
			font=('Arial', st['price_font'], 'bold'),
			text_color=st['price_color'], anchor='w',
		)
		self._pw_price.pack(fill='x', anchor='w', pady=(1, 0))

		# Row 2 — Separator
		ctk.CTkFrame(card, fg_color='#e2e8f0', corner_radius=0, height=1).grid(
			row=2, column=0, sticky='ew'
		)

		# Row 3 — Barcode zone
		self._pw_bc_zone = ctk.CTkFrame(
			card, fg_color='#f1f5f9', corner_radius=0, height=st['bc_h']
		)
		self._pw_bc_zone.grid(row=3, column=0, sticky='ew')
		self._pw_bc_zone.pack_propagate(False)
		ctk.CTkFrame(
			self._pw_bc_zone, fg_color='#334155', corner_radius=0, height=st['bc_h'] - 8
		).pack(fill='x', padx=10, pady=(3, 0))

		# Row 4 — Footer
		self._pw_footer = ctk.CTkFrame(card, fg_color='#f8fafc', corner_radius=0, height=14)
		self._pw_footer.grid(row=4, column=0, sticky='ew')
		self._pw_footer.pack_propagate(False)
		self._pw_footer_label = ctk.CTkLabel(
			self._pw_footer, text='0000000000   Imp: 20/05/26',
			font=('Arial', 4), text_color='#64748b',
		)
		self._pw_footer_label.pack(expand=True)

		self._update_live_preview()

	def _update_live_preview(self):
		if not self.winfo_exists():
			return
		if not getattr(self, '_pw_name', None) or not getattr(self, '_pw_price', None):
			return
		try:
			if not self._pw_name.winfo_exists():
				return
		except Exception:
			return

		item = self._queue[0] if self._queue else {
			'name': 'Producto de Ejemplo',
			'price': 1250.0,
			'barcode': '1234567890',
			'price_mode': 'retail',
			'discount_price': None,
			'discount_until': '',
			'attribute': '',
		}

		cfg = _cfg_mgr.load()
		company = cfg.get('company_name', 'MI NEGOCIO')[:15].upper()
		is_offer = bool(item.get('discount_price'))
		price = self._get_item_display_price(item)
		disc = item.get('discount_price')
		p_final = disc if (is_offer and disc) else price
		name_txt = item.get('name', 'Producto')[:30]
		attr_txt = item.get('attribute', '')
		barcode_txt = item.get('barcode', '') or '0000000000'
		date_str = datetime.now().strftime('%d/%m/%y')

		tpl_colors = {
			'supermercado': '#1e293b',
			'producto':     '#0f172a',
			'precio':       '#1e293b',
			'mini':         '#f77f00',
		}
		hdr_normal = tpl_colors.get(self._tpl_key, '#1e293b')

		def _safe(widget_attr, **kwargs):
			w = getattr(self, widget_attr, None)
			if not w:
				return
			try:
				if w.winfo_exists():
					w.configure(**kwargs)
			except Exception:
				pass

		try:
			_safe('_pw_header', fg_color='#dc2626' if is_offer else hdr_normal)
			_safe('_pw_brand', text='* OFERTA *' if is_offer else company)
			_safe('_pw_name', text=name_txt, text_color='black')
			_safe('_pw_attr', text=attr_txt)
			_safe(
				'_pw_price_before',
				text=f'Antes: {fmt_price(price)}' if is_offer else '',
			)
			_safe(
				'_pw_price',
				text=fmt_price(p_final),
				text_color='#dc2626' if is_offer else '#0f172a',
			)
			_safe(
				'_pw_footer_label',
				text=f'{barcode_txt[:18]}   Imp: {date_str}',
			)
		except Exception as e:
			logger.debug('Preview update error: %s', e)

	def _select_template(self, key: str):
		self._tpl_key = key
		for k, btn in self._tpl_btns.items():
			active = k == key
			btn.configure(
				fg_color=ACCENT_DIM if active else 'transparent',
				text_color=ACCENT_TEXT if active else TEXT_SECONDARY
			)
		self._build_live_preview_widgets()

	def _refresh_price_list_bar(self):
		if not self.winfo_exists():
			return
		self._load_price_list_cfg()

		bar = self._wholesale_bar
		for w in bar.winfo_children():
			try:
				w.destroy()
			except Exception:
				pass

		inner = ctk.CTkFrame(bar, fg_color='transparent')
		inner.pack(fill='x', padx=PAD_MD, pady=PAD_SM)
		inner.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			inner,
			text='💰  Precio en etiquetas',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
		).grid(row=0, column=0, sticky='w', pady=(0, PAD_XS))

		btn_row = ctk.CTkFrame(inner, fg_color='transparent')
		btn_row.grid(row=1, column=0, sticky='ew')

		self._mode_btns: dict[str, ctk.CTkButton] = {}
		for col, (key, label, _factor) in enumerate(self._price_options):
			btn = ctk.CTkButton(
				btn_row,
				text=label,
				height=28,
				font=FONT_LABEL_BOLD,
				fg_color=ACCENT if key == 'retail' else SURFACE3,
				hover_color=ACCENT_HOVER if key == 'retail' else SURFACE4,
				text_color=TEXT_PRIMARY,
				border_width=1,
				border_color=ACCENT if key == 'retail' else BORDER,
				corner_radius=6,
				command=lambda k=key: self._set_global_price_mode(k),
			)
			btn.pack(side='left', padx=(0, PAD_XS))
			self._mode_btns[key] = btn

		self._current_price_mode = 'retail'

	def _set_global_price_mode(self, mode_key: str):
		self._current_price_mode = mode_key

		for k, btn in self._mode_btns.items():
			if not btn.winfo_exists():
				continue
			active = k == mode_key
			btn.configure(
				fg_color=ACCENT if active else SURFACE3,
				hover_color=ACCENT_HOVER if active else SURFACE4,
				border_color=ACCENT if active else BORDER,
			)

		for item in self._queue:
			item['price_mode'] = mode_key

		self._render_queue()

	def _debounced_search(self, event=None):
		if self._search_timer:
			self.after_cancel(self._search_timer)
		self._search_timer = self.after(300, self._filter_catalog)

	def _add_first_filtered(self):
		q = self._entry_search.get().lower().strip()
		filtered = [
			v
			for v in self._variants
			if not q
			or q in v['name'].lower()
			or q in v['attribute'].lower()
			or q in v['barcode'].lower()
		]

		if filtered:
			self._add_one_to_queue(filtered[0], render=True)
			self._entry_search.delete(0, 'end')
			self._filter_catalog()
		else:
			self._entry_search.configure(border_color=RED)
			self.after(800, lambda: self._entry_search.configure(border_color=BORDER))

	def _load_catalog(self):
		if not self.winfo_exists():
			return

		def _fetch_data():
			try:
				from database.models import Article, ArticleVariant

				Session = sessionmaker(bind=self.ctx.db_engine)
				with Session() as s:
					rows = (
						s.query(
							ArticleVariant.id,
							Article.name,
							ArticleVariant.attribute_1,
							ArticleVariant.attribute_2,
							ArticleVariant.barcode,
							ArticleVariant.selling_price,
							ArticleVariant.selling_price_b,
							ArticleVariant.discount_pct,
							ArticleVariant.discount_until,
						)
						.join(Article)
						.filter(
							Article.tenant_id == self.ctx.tenant_id,
							Article.is_active == True,  # noqa: E712
							ArticleVariant.is_active == True,  # noqa: E712
						)
						.order_by(Article.name)
						.all()
					)

					variants_data = []
					for v_id, a_name, a1, a2, barcode, price, price_b, disc_pct, disc_until in rows:
						attr = ' '.join(filter(None, [a1, a2]))
						variants_data.append(
							{
								'variant_id': v_id,
								'name': a_name,
								'attribute': attr,
								'barcode': barcode or '',
								'price': float(price),
								'selling_price_b': float(price_b) if price_b else None,
								'display': f'{a_name}{"  –  " + attr if attr else ""}',
								'discount_pct': float(disc_pct) if disc_pct else None,
								'discount_until': disc_until,
							}
						)

					if self.winfo_exists():
						self.after(0, lambda: self._on_catalog_loaded(variants_data))
			except Exception as e:
				logger.error(f'Error cargando catálogo: {e}', exc_info=True)
				if self.winfo_exists():
					self.after(0, lambda: self._on_catalog_loaded([]))

		threading.Thread(target=_fetch_data, daemon=True).start()

	def _on_catalog_loaded(self, data: list[dict]):
		self._variants = data
		self._filter_catalog()

	def _filter_catalog(self):
		if not self.winfo_exists():
			return
		q = self._entry_search.get().lower().strip()
		filtered = [
			v
			for v in self._variants
			if not q
			or q in v['name'].lower()
			or q in v['attribute'].lower()
			or q in v['barcode'].lower()
		]
		self._render_catalog(filtered)

	def _render_catalog(self, variants: list[dict]):
		if not self.winfo_exists():
			return

		for w in list(self._catalog_frame.winfo_children()):
			try:
				w.destroy()
			except Exception:
				pass

		self._catalog_rows = []

		if not variants:
			ctk.CTkLabel(
				self._catalog_frame,
				text='Sin resultados',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
			).pack(pady=20)
			return

		render_limit = 50
		display_variants = variants[:render_limit]

		for i, v in enumerate(display_variants):
			bg = SURFACE2 if i % 2 == 0 else SURFACE1
			row = ctk.CTkFrame(self._catalog_frame, fg_color=bg, corner_radius=6)
			row.pack(fill='x', pady=2, padx=4)
			row.grid_columnconfigure(1, weight=1)

			is_checked = v['variant_id'] in self._selected_variants
			check_var = ctk.BooleanVar(value=is_checked)

			def _on_check_toggle(var=check_var, vid=v['variant_id']):
				if var.get():
					self._selected_variants.add(vid)
				else:
					self._selected_variants.discard(vid)

			ctk.CTkCheckBox(
				row,
				variable=check_var,
				text='',
				width=24,
				height=24,
				fg_color=ACCENT,
				hover_color=ACCENT_HOVER,
				border_color=SURFACE4,
				checkmark_color='white',
				command=_on_check_toggle,
			).grid(row=0, column=0, padx=(PAD_SM, PAD_XS), pady=PAD_XS)

			info = ctk.CTkFrame(row, fg_color='transparent')
			info.grid(row=0, column=1, sticky='ew', pady=4)

			ctk.CTkLabel(
				info,
				text=v['display'][:40],
				font=FONT_LABEL_BOLD,
				text_color=TEXT_PRIMARY,
				anchor='w',
			).pack(fill='x')

			meta_parts = []
			if v['barcode']:
				meta_parts.append(f'#{v["barcode"]}')
			meta_parts.append(fmt_price(v['price']))

			ctk.CTkLabel(
				info,
				text='  '.join(meta_parts),
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
				anchor='w',
			).pack(fill='x')

			btn_add = ctk.CTkButton(
				row,
				text='+',
				width=30,
				height=30,
				fg_color=SURFACE3,
				hover_color=ACCENT,
				text_color=TEXT_PRIMARY,
				font=FONT_LABEL_BOLD,
			)

			def _do_add(vv=v, btn=btn_add):
				self._add_one_to_queue(vv)
				orig_color = btn.cget('fg_color')
				btn.configure(fg_color=GREEN)
				self.after(
					300,
					lambda: btn.winfo_exists() and btn.configure(fg_color=orig_color),
				)

			btn_add.configure(command=_do_add)
			btn_add.grid(row=0, column=2, padx=(PAD_XS, PAD_SM))

			self._catalog_rows.append({'check_var': check_var, 'data': v})

		if len(variants) > render_limit:
			ctk.CTkLabel(
				self._catalog_frame,
				text=f'Mostrando {render_limit} de {len(variants)} resultados. Refiná la búsqueda.',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
			).pack(pady=10)

	def _add_selected_to_queue(self):
		if not self._selected_variants:
			self.show_warning(
				'Marcá los artículos que querés agregar.', 'Sin selección'
			)
			return

		selected_data = [
			v for v in self._variants if v['variant_id'] in self._selected_variants
		]

		for v in selected_data:
			self._add_one_to_queue(v, render=False)

		self._selected_variants.clear()
		self._filter_catalog()
		self._render_queue()

	def _add_all_to_queue(self):
		filtered_txt = self._entry_search.get().lower().strip()
		targets = [
			v
			for v in self._variants
			if not filtered_txt
			or filtered_txt in v['name'].lower()
			or filtered_txt in v['barcode'].lower()
		]
		for v in targets:
			self._add_one_to_queue(v, render=False)
		self._render_queue()

	def _open_custom_article_dialog(self):
		if hasattr(self, '_custom_dialog'):
			try:
				if self._custom_dialog.winfo_exists():
					self._custom_dialog.focus()
					return
			except Exception:
				pass

		dlg = ctk.CTkToplevel(self)
		dlg.title('Artículo manual')
		dlg.geometry('440x290')
		dlg.grab_set()
		dlg.resizable(False, False)
		self._custom_dialog = dlg

		frame = ctk.CTkFrame(dlg, fg_color=SURFACE1)
		frame.pack(fill='both', expand=True, padx=PAD_MD, pady=PAD_MD)
		frame.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(frame, text='Nombre:', font=FONT_LABEL_BOLD, text_color=TEXT_PRIMARY, anchor='w').grid(
			row=0, column=0, sticky='w', padx=(PAD_MD, PAD_SM), pady=(PAD_MD, PAD_XS)
		)
		entry_name = ctk.CTkEntry(frame, placeholder_text='Ej: Sandwich de miga', height=34, font=FONT_BODY)
		entry_name.grid(row=0, column=1, sticky='ew', padx=(0, PAD_MD), pady=(PAD_MD, PAD_XS))

		ctk.CTkLabel(frame, text='Precio:', font=FONT_LABEL_BOLD, text_color=TEXT_PRIMARY, anchor='w').grid(
			row=1, column=0, sticky='w', padx=(PAD_MD, PAD_SM), pady=PAD_XS
		)
		entry_price = ctk.CTkEntry(frame, placeholder_text='0.00', height=34, font=FONT_BODY)
		entry_price.grid(row=1, column=1, sticky='ew', padx=(0, PAD_MD), pady=PAD_XS)

		ctk.CTkLabel(frame, text='Código:', font=FONT_LABEL_BOLD, text_color=TEXT_PRIMARY, anchor='w').grid(
			row=2, column=0, sticky='w', padx=(PAD_MD, PAD_SM), pady=PAD_XS
		)
		bc_row = ctk.CTkFrame(frame, fg_color='transparent')
		bc_row.grid(row=2, column=1, sticky='ew', padx=(0, PAD_MD), pady=PAD_XS)
		bc_row.grid_columnconfigure(0, weight=1)

		entry_bc = ctk.CTkEntry(bc_row, height=34, font=FONT_BODY_BOLD)
		entry_bc.insert(0, self._ctrl.generate_internal_barcode())
		entry_bc.grid(row=0, column=0, sticky='ew')

		ctk.CTkButton(
			bc_row, text='↻', width=36, height=34,
			fg_color=SURFACE3, hover_color=ACCENT_DIM, font=FONT_BODY_BOLD, text_color=TEXT_PRIMARY,
			command=lambda: (entry_bc.delete(0, 'end'), entry_bc.insert(0, self._ctrl.generate_internal_barcode())),
		).grid(row=0, column=1, padx=(PAD_XS, 0))

		ctk.CTkLabel(frame, text='Copias:', font=FONT_LABEL_BOLD, text_color=TEXT_PRIMARY, anchor='w').grid(
			row=3, column=0, sticky='w', padx=(PAD_MD, PAD_SM), pady=PAD_XS
		)
		entry_copies = ctk.CTkEntry(frame, placeholder_text='1', height=34, font=FONT_BODY)
		entry_copies.insert(0, '1')
		entry_copies.grid(row=3, column=1, sticky='ew', padx=(0, PAD_MD), pady=PAD_XS)

		def _confirm():
			name = entry_name.get().strip()
			if not name:
				entry_name.configure(border_color=RED)
				return
			try:
				price_val = float(entry_price.get().replace(',', '.'))
			except ValueError:
				entry_price.configure(border_color=RED)
				return
			bc = entry_bc.get().strip() or self._ctrl.generate_internal_barcode()
			try:
				copies_val = max(1, int(entry_copies.get()))
			except ValueError:
				copies_val = 1
			mode = getattr(self, '_current_price_mode', 'retail')
			new_item = {
				'variant_id': f'manual_{bc}',
				'name': name,
				'attribute': '',
				'barcode': bc,
				'price': price_val,
				'selling_price_b': None,
				'display': name,
				'copies': copies_val,
				'price_mode': mode,
			}
			existing = next((x for x in self._queue if x['variant_id'] == new_item['variant_id']), None)
			if existing:
				existing['copies'] += copies_val
			else:
				self._queue.append(new_item)
			self._render_queue()
			dlg.destroy()

		ctk.CTkButton(
			frame, text='Agregar a cola de impresión',
			height=40, fg_color=GREEN, hover_color=GREEN_HOVER, font=FONT_BODY_BOLD,
			command=_confirm,
		).grid(row=4, column=0, columnspan=2, sticky='ew', padx=PAD_MD, pady=(PAD_MD, PAD_SM))

		entry_name.focus()
		dlg.bind('<Return>', lambda e: _confirm())

	def _add_one_to_queue(self, variant: dict, render: bool = True):
		for item in self._queue:
			if item['variant_id'] == variant['variant_id']:
				item['copies'] += 1
				if render:
					self._render_queue()
				return
		mode = getattr(self, '_current_price_mode', 'retail')
		entry = {**variant, 'copies': 1, 'price_mode': mode, 'discount_price': None}

		if not entry.get('barcode'):
			entry['barcode'] = self._ctrl.generate_internal_barcode()

		# Normalizar discount_until (datetime → string dd/mm/AAAA para el date picker)
		raw_until = entry.get('discount_until')
		if isinstance(raw_until, datetime):
			entry['discount_until'] = raw_until.strftime('%d/%m/%Y')
		else:
			entry['discount_until'] = ''

		# Auto-poblar discount_price si el descuento del artículo está vigente
		disc_pct = entry.get('discount_pct')
		if disc_pct and disc_pct > 0:
			until_str = entry['discount_until']
			still_valid = True
			if until_str:
				try:
					still_valid = datetime.strptime(until_str, '%d/%m/%Y') >= datetime.now()
				except ValueError:
					still_valid = False
			if still_valid:
				entry['discount_price'] = round(entry['price'] * (1 - disc_pct / 100), 2)

		self._queue.append(entry)
		if render:
			self._render_queue()

	def _update_queue_total(self):
		total = sum(it['copies'] for it in self._queue)
		if self._lbl_total.winfo_exists():
			self._lbl_total.configure(
				text=f'{total} etiqueta{"s" if total != 1 else ""}',
				text_color=ACCENT_TEXT if total > 0 else TEXT_MUTED,
			)

	def _get_item_display_price(self, item: dict) -> float:
		base = float(item.get('price', 0))
		mode = item.get('price_mode', 'retail')
		if mode == 'price_b':
			price_b = item.get('selling_price_b')
			if price_b:
				return float(price_b)
		return base

	def _render_queue(self):
		if not self.winfo_exists():
			return

		for w in list(self._queue_frame.winfo_children()):
			try:
				w.destroy()
			except Exception:
				pass

		self._update_queue_total()
		self._update_live_preview()

		if not self._queue:
			ctk.CTkLabel(
				self._queue_frame,
				text='La cola está vacía.\nUsá el botón + del catálogo para agregar artículos.',
				font=FONT_BODY,
				text_color=TEXT_MUTED,
				justify='center',
			).pack(pady=PAD_LG)
			return

		hd = ctk.CTkFrame(self._queue_frame, fg_color=SURFACE3, corner_radius=4)
		hd.pack(fill='x', pady=(0, PAD_XS))
		hd.grid_columnconfigure(0, weight=1)
		for ci, (txt, w) in enumerate(
			[('Artículo', 0), ('Precio', 80), ('Copias', 90), ('', 56)]
		):
			ctk.CTkLabel(
				hd, text=txt, font=FONT_LABEL_BOLD, text_color=TEXT_SECONDARY, width=w
			).grid(
				row=0,
				column=ci,
				padx=PAD_SM,
				pady=PAD_XS,
				sticky='w' if ci == 0 else 'e',
			)
		hd.grid_columnconfigure(0, weight=1)

		for idx, item in enumerate(self._queue):
			bg = SURFACE2 if idx % 2 == 0 else SURFACE1

			row = ctk.CTkFrame(self._queue_frame, fg_color=bg, corner_radius=4)
			row.pack(fill='x', pady=(2, 0))
			row.grid_columnconfigure(0, weight=1)

			name_txt = item['display'][:36]
			ctk.CTkLabel(
				row, text=name_txt, font=FONT_LABEL, text_color=TEXT_PRIMARY, anchor='w'
			).grid(row=0, column=0, padx=PAD_SM, pady=5, sticky='w')

			display_price = self._get_item_display_price(item)
			has_discount = bool(item.get('discount_price'))
			price_color = (
				RED_TEXT
				if has_discount
				else ORANGE_TEXT
				if item.get('price_mode', 'retail') != 'retail'
				else ACCENT_TEXT
			)
			price_display_txt = (
				f'~{fmt_price(display_price)}'
				if has_discount
				else fmt_price(display_price)
			)

			ctk.CTkLabel(
				row,
				text=price_display_txt,
				font=FONT_LABEL,
				text_color=price_color,
				width=80,
				anchor='e',
			).grid(row=0, column=1, padx=4)

			spin = ctk.CTkFrame(row, fg_color='transparent')
			spin.grid(row=0, column=2, padx=4)

			entry_copies = ctk.CTkEntry(
				spin,
				width=38,
				height=24,
				font=FONT_LABEL_BOLD,
				justify='center',
				fg_color=SURFACE1,
				border_color=BORDER,
				text_color=TEXT_PRIMARY,
			)
			entry_copies.bind(
				'<FocusIn>', lambda e, ent=entry_copies: ent.select_range(0, 'end')
			)

			def _on_copy_edit(e, i=idx, ent=entry_copies):
				if not ent.winfo_exists():
					return
				try:
					val = int(ent.get())
					self._queue[i]['copies'] = min(999, max(1, val))
					self._update_queue_total()
				except ValueError:
					pass

			entry_copies.insert(0, str(item['copies']))
			entry_copies.bind('<KeyRelease>', _on_copy_edit)

			ctk.CTkButton(
				spin,
				text='−',
				width=24,
				height=24,
				fg_color=SURFACE3,
				hover_color=SURFACE4,
				text_color=TEXT_PRIMARY,
				font=FONT_LABEL_BOLD,
				command=lambda i=idx, ent=entry_copies: self._dec_copies(i, ent),
			).pack(side='left', padx=2)

			entry_copies.pack(side='left', padx=2)

			ctk.CTkButton(
				spin,
				text='+',
				width=24,
				height=24,
				fg_color=SURFACE3,
				hover_color=SURFACE4,
				text_color=TEXT_PRIMARY,
				font=FONT_LABEL_BOLD,
				command=lambda i=idx, ent=entry_copies: self._inc_copies(i, ent),
			).pack(side='left', padx=2)

			ctk.CTkButton(
				row,
				text='✕',
				width=28,
				height=28,
				fg_color=RED_DIM,
				hover_color=RED,
				text_color=RED_TEXT,
				font=FONT_LABEL,
				command=lambda i=idx: self._remove_from_queue(i),
			).grid(row=0, column=3, padx=(PAD_XS, PAD_SM))

			disc_bg = SURFACE0
			disc_row = ctk.CTkFrame(
				self._queue_frame, fg_color=disc_bg, corner_radius=0
			)
			disc_row.pack(fill='x', pady=(0, 2))

			ctk.CTkLabel(
				disc_row,
				text='%  Descuento:',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
				width=95,
				anchor='w',
			).pack(side='left', padx=(PAD_MD, PAD_XS), pady=3)

			entry_disc = ctk.CTkEntry(
				disc_row,
				width=75,
				height=22,
				font=FONT_LABEL,
				placeholder_text='precio desc.',
				fg_color=SURFACE2,
				border_color=BORDER,
				text_color=RED_TEXT,
			)
			if item.get('discount_price'):
				entry_disc.insert(0, str(item['discount_price']))
			entry_disc.pack(side='left', padx=(0, PAD_SM))

			ctk.CTkLabel(
				disc_row,
				text='Válido hasta:',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
				width=80,
				anchor='w',
			).pack(side='left', padx=(0, PAD_XS))

			entry_until = CTkDatePicker(disc_row, width=155, height=26)
			if item.get('discount_until'):
				entry_until.set_text(str(item['discount_until']))
			entry_until.pack(side='left', padx=(0, PAD_SM))

			def _on_disc_change(e, i=idx, de=entry_disc, du=entry_until):
				try:
					val = float(de.get())
					self._queue[i]['discount_price'] = val if val > 0 else None
				except (ValueError, TypeError):
					self._queue[i]['discount_price'] = None
				self._queue[i]['discount_until'] = du.get().strip()
				if i == 0:
					self._update_live_preview()

			entry_disc.bind('<KeyRelease>', _on_disc_change)
			entry_until.bind('<KeyRelease>', _on_disc_change)
			entry_disc.bind(
				'<FocusIn>', lambda e, ent=entry_disc: ent.select_range(0, 'end')
			)
			entry_until.bind(
				'<FocusIn>', lambda e, ent=entry_until: ent.select_range(0, 'end')
			)

	def _inc_copies(self, idx: int, ent: ctk.CTkEntry):
		if 0 <= idx < len(self._queue):
			self._queue[idx]['copies'] = min(999, self._queue[idx]['copies'] + 1)
			if ent.winfo_exists():
				ent.delete(0, 'end')
				ent.insert(0, str(self._queue[idx]['copies']))
			self._update_queue_total()

	def _dec_copies(self, idx: int, ent: ctk.CTkEntry):
		if 0 <= idx < len(self._queue):
			self._queue[idx]['copies'] = max(1, self._queue[idx]['copies'] - 1)
			if ent.winfo_exists():
				ent.delete(0, 'end')
				ent.insert(0, str(self._queue[idx]['copies']))
			self._update_queue_total()

	def _remove_from_queue(self, idx: int):
		if 0 <= idx < len(self._queue):
			self._queue.pop(idx)
		self._render_queue()

	def _confirm_clear_queue(self):
		if not self._queue:
			return
		from CTkMessagebox import CTkMessagebox
		r = CTkMessagebox(
			title='Limpiar cola',
			message=f'¿Eliminar {len(self._queue)} etiqueta(s) de la cola?',
			icon='warning', option_1='Cancelar', option_2='Limpiar',
		)
		if r.get() == 'Limpiar':
			self._clear_queue()

	def _clear_queue(self):
		if not self._queue:
			return
		self._queue.clear()
		self._render_queue()

	def _setup_bindings(self):
		if not self.winfo_exists():
			return
		self.top_level = self.winfo_toplevel()
		self.top_level.bind('<Control-p>', self._handle_print_shortcut)

	def _handle_print_shortcut(self, event=None):
		if self.winfo_exists():
			focus_widget = self.focus_displayof()
			if focus_widget and str(focus_widget).startswith(str(self)):
				self._print_labels()

	def _print_labels(self):
		if not self._queue:
			self.show_warning(
				'Agregá artículos a la cola antes de imprimir.', 'Cola vacía'
			)
			return

		total = sum(it['copies'] for it in self._queue)
		tpl = TEMPLATES[self._tpl_key]

		if self._btn_print.winfo_exists():
			self._btn_print.configure(text='⏳  Generando PDF...', state='disabled')

		items_snapshot = [dict(it) for it in self._queue]
		tpl_key = self._tpl_key

		def _run():
			ok, result = self._ctrl.generate_pdf(items_snapshot, tpl_key)
			if self.winfo_exists():
				self.after(0, lambda: self._on_pdf_done(ok, result, total, tpl))

		threading.Thread(target=_run, daemon=True).start()

	def _on_pdf_done(self, ok: bool, result: str, total: int, tpl: dict):
		if not self.winfo_exists():
			return
		if self._btn_print.winfo_exists():
			self._btn_print.configure(
				text='🖨  Generar PDF de etiquetas (Ctrl+P)', state='normal'
			)
		if ok:
			self.show_success(
				f'{total} etiqueta{"s" if total != 1 else ""} en formato "{tpl["label"]}" abierta{"s" if total != 1 else ""} automáticamente.',
				'PDF generado',
			)
		else:
			self.show_error(str(result), 'Error al generar etiquetas')

	def destroy(self):
		if hasattr(self, 'top_level') and self.top_level.winfo_exists():
			self.top_level.unbind('<Control-p>')

		if self._search_timer:
			try:
				self.after_cancel(self._search_timer)
			except Exception:
				pass

		super().destroy()
