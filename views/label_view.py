import logging
import tkinter as tk

import customtkinter as ctk
from sqlalchemy.orm import sessionmaker

from controllers.label_controller import TEMPLATES, LabelController
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
	GREEN,
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


class LabelView(ctk.CTkFrame):
	def __init__(self, master, ctx: AppContext, **kwargs):
		super().__init__(master, fg_color=SURFACE1, **kwargs)
		self.ctx = ctx
		self._ctrl = LabelController()
		self._variants: list[dict] = []
		self._queue: list[dict] = []
		self._tpl_key = 'supermercado'
		self._search_timer = None

		self._build()

		self.after(120, self._load_catalog)
		self.after(100, self._setup_bindings)

	# ─────────────────────────────────────────────────────────────────────────
	# Layout Principal
	# ─────────────────────────────────────────────────────────────────────────

	def _build(self):
		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=3)
		self.grid_rowconfigure(0, weight=1)
		self._build_left()
		self._build_right()

	def _build_left(self):
		left = ctk.CTkFrame(self, fg_color=SURFACE0, corner_radius=0)
		left.grid(row=0, column=0, sticky='nsew')
		left.grid_rowconfigure(2, weight=1)
		left.grid_columnconfigure(0, weight=1)

		hdr = ctk.CTkFrame(left, fg_color='transparent')
		hdr.grid(row=0, column=0, sticky='ew', padx=PAD_MD, pady=(PAD_LG, PAD_SM))
		hdr.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			hdr,
			text='Catálogo de artículos',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
		).grid(row=0, column=0, sticky='w')

		srch = ctk.CTkFrame(left, fg_color='transparent')
		srch.grid(row=1, column=0, sticky='ew', padx=PAD_MD, pady=(0, PAD_SM))
		srch.grid_columnconfigure(0, weight=1)

		self._entry_search = ctk.CTkEntry(
			srch,
			placeholder_text='🔍  Buscar por nombre o barcode...',
			height=36,
			fg_color=SURFACE2,
			border_color=BORDER,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._entry_search.grid(row=0, column=0, sticky='ew', pady=(0, PAD_XS))
		self._entry_search.bind('<KeyRelease>', self._debounced_search)
		self._entry_search.bind('<Return>', lambda e: self._add_first_filtered())

		act = ctk.CTkFrame(srch, fg_color='transparent')
		act.grid(row=1, column=0, sticky='ew')
		act.grid_columnconfigure((0, 1), weight=1)

		ctk.CTkButton(
			act,
			text='Agregar selección',
			height=30,
			font=FONT_LABEL_BOLD,
			fg_color=ACCENT,
			hover_color='#1d4ed8',
			command=self._add_selected_to_queue,
		).grid(row=0, column=0, sticky='ew', padx=(0, 3))

		ctk.CTkButton(
			act,
			text='Agregar todos',
			height=30,
			font=FONT_LABEL_BOLD,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			command=self._add_all_to_queue,
		).grid(row=0, column=1, sticky='ew', padx=(3, 0))

		self._catalog_frame = ctk.CTkScrollableFrame(
			left,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
		)
		self._catalog_frame.grid(
			row=2, column=0, sticky='nsew', padx=PAD_SM, pady=(PAD_XS, PAD_SM)
		)
		self._catalog_frame.grid_columnconfigure(0, weight=1)
		self._catalog_rows: list[dict] = []

	def _build_right(self):
		right = ctk.CTkFrame(self, fg_color=SURFACE1, corner_radius=0)
		right.grid(row=0, column=1, sticky='nsew')
		right.grid_columnconfigure(0, weight=1)
		right.grid_rowconfigure(1, weight=1)

		tpl_outer = ctk.CTkFrame(right, fg_color=SURFACE2, corner_radius=10)
		tpl_outer.grid(row=0, column=0, sticky='ew', padx=PAD_LG, pady=(PAD_LG, PAD_SM))
		tpl_outer.grid_columnconfigure(tuple(range(len(TEMPLATES))), weight=1)

		ctk.CTkLabel(
			tpl_outer,
			text='Formato de etiqueta',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
		).grid(
			row=0,
			column=0,
			columnspan=len(TEMPLATES),
			sticky='w',
			padx=PAD_MD,
			pady=(PAD_SM, PAD_XS),
		)

		self._tpl_frames: dict[str, ctk.CTkFrame] = {}
		self._tpl_canvases: dict[str, tk.Canvas] = {}

		for col, (key, tpl) in enumerate(TEMPLATES.items()):
			f = ctk.CTkFrame(
				tpl_outer,
				fg_color=ACCENT_DIM if key == self._tpl_key else SURFACE3,
				corner_radius=8,
				cursor='hand2',
			)
			f.grid(row=1, column=col, padx=PAD_XS, pady=(0, PAD_MD), sticky='nsew')
			self._tpl_frames[key] = f

			cv = tk.Canvas(
				f,
				width=90,
				height=60,
				bg=SURFACE3 if key != self._tpl_key else '#1a274a',
				highlightthickness=0,
			)
			cv.pack(padx=PAD_SM, pady=(PAD_SM, PAD_XS))
			self._tpl_canvases[key] = cv
			self._draw_template_preview(cv, key)

			ctk.CTkLabel(
				f,
				text=tpl['icon'] + '  ' + tpl['label'],
				font=FONT_LABEL_BOLD,
				text_color=ACCENT_TEXT if key == self._tpl_key else TEXT_SECONDARY,
			).pack(padx=PAD_XS, pady=(0, 2))

			ctk.CTkLabel(
				f,
				text=tpl['desc'],
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
				wraplength=130,
			).pack(padx=PAD_XS, pady=(0, PAD_SM))

			def _sel(k=key):
				self._select_template(k)

			for widget in (f,):
				widget.bind('<Button-1>', lambda e, k=key: self._select_template(k))
			cv.bind('<Button-1>', lambda e, k=key: self._select_template(k))

		queue_outer = ctk.CTkFrame(right, fg_color=SURFACE2, corner_radius=10)
		queue_outer.grid(row=1, column=0, sticky='nsew', padx=PAD_LG, pady=(0, PAD_SM))
		queue_outer.grid_columnconfigure(0, weight=1)
		queue_outer.grid_rowconfigure(1, weight=1)

		qhdr = ctk.CTkFrame(queue_outer, fg_color='transparent')
		qhdr.grid(row=0, column=0, sticky='ew', padx=PAD_MD, pady=(PAD_SM, PAD_XS))
		qhdr.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			qhdr,
			text='Cola de impresión',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_PRIMARY,
		).grid(row=0, column=0, sticky='w')

		self._lbl_total = ctk.CTkLabel(
			qhdr,
			text='0 etiquetas',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		)
		self._lbl_total.grid(row=0, column=1)

		ctk.CTkButton(
			qhdr,
			text='Limpiar todo',
			width=90,
			height=28,
			font=FONT_LABEL,
			fg_color=SURFACE3,
			hover_color=RED_DIM,
			text_color=TEXT_SECONDARY,
			command=self._clear_queue,
		).grid(row=0, column=2, padx=(PAD_SM, 0))

		self._queue_frame = ctk.CTkScrollableFrame(
			queue_outer,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
		)
		self._queue_frame.grid(
			row=1, column=0, sticky='nsew', padx=PAD_SM, pady=(0, PAD_SM)
		)
		self._queue_frame.grid_columnconfigure(0, weight=1)

		footer = ctk.CTkFrame(right, fg_color='transparent')
		footer.grid(row=2, column=0, sticky='ew', padx=PAD_LG, pady=(0, PAD_MD))
		footer.grid_columnconfigure(0, weight=1)

		self._btn_print = ctk.CTkButton(
			footer,
			text='🖨  Generar PDF de etiquetas (Ctrl+P)',
			height=46,
			fg_color=GREEN,
			hover_color='#15803d',
			font=FONT_BODY_BOLD,
			command=self._print_labels,
		)
		self._btn_print.grid(row=0, column=0, sticky='ew')

	# ─────────────────────────────────────────────────────────────────────────
	# Renderizado y Visualización de Templates
	# ─────────────────────────────────────────────────────────────────────────

	def _draw_template_preview(self, cv: tk.Canvas, key: str):
		if not cv.winfo_exists():
			return

		cv.delete('all')
		tpl = TEMPLATES[key]
		W, H = 90, 60

		lw = tpl['w_mm']
		lh = tpl['h_mm']
		scale = min((W - 16) / lw, (H - 12) / lh)
		lw_px = lw * scale
		lh_px = lh * scale
		x0 = (W - lw_px) / 2
		y0 = (H - lh_px) / 2

		cv.create_rectangle(
			x0, y0, x0 + lw_px, y0 + lh_px, fill='#f4f4f5', outline='#cbd5e1', width=2
		)

		cx = x0 + lw_px / 2

		if key == 'supermercado':
			cv.create_rectangle(
				x0 + 2, y0 + 2, x0 + lw_px - 2, y0 + 8, fill='#94a3b8', outline=''
			)
			cv.create_rectangle(
				x0 + 6, y0 + 10, x0 + lw_px - 6, y0 + 14, fill='#475569', outline=''
			)
			for i in range(12):
				bx = x0 + 8 + i * ((lw_px - 16) / 12)
				cv.create_line(bx, y0 + 16, bx, y0 + 26, fill='#334155', width=1.5)
			cv.create_text(
				cx,
				y0 + lh_px - 6,
				text='$000',
				fill='#0f172a',
				font=('Arial', 9, 'bold'),
			)

		elif key == 'producto':
			cv.create_rectangle(
				x0 + 4, y0 + 4, x0 + 14, y0 + 12, fill='#94a3b8', outline=''
			)
			cv.create_rectangle(
				x0 + 16, y0 + 6, x0 + lw_px - 4, y0 + 10, fill='#475569', outline=''
			)
			cv.create_line(x0 + 4, y0 + 14, x0 + lw_px - 4, y0 + 14, fill='#cbd5e1')
			cv.create_rectangle(
				x0 + 6, y0 + 16, x0 + lw_px - 6, y0 + 20, fill='#475569', outline=''
			)
			cv.create_rectangle(
				x0 + 10, y0 + 22, x0 + lw_px - 10, y0 + 24, fill='#94a3b8', outline=''
			)
			for i in range(10):
				bx = x0 + 10 + i * ((lw_px - 20) / 10)
				cv.create_line(bx, y0 + 26, bx, y0 + 34, fill='#334155', width=1.5)
			cv.create_text(
				cx,
				y0 + lh_px - 6,
				text='$000',
				fill='#0f172a',
				font=('Arial', 9, 'bold'),
			)

		elif key == 'precio':
			cv.create_rectangle(
				x0 + 6, y0 + 4, x0 + lw_px - 6, y0 + 10, fill='#475569', outline=''
			)
			cv.create_text(
				cx, y0 + 20, text='$0000', fill='#0f172a', font=('Arial', 12, 'bold')
			)
			for i in range(8):
				bx = x0 + 12 + i * ((lw_px - 24) / 8)
				cv.create_line(bx, y0 + 28, bx, y0 + 34, fill='#334155', width=1.5)

		elif key == 'mini':
			for i in range(10):
				bx = x0 + 6 + i * ((lw_px - 12) / 10)
				cv.create_line(bx, y0 + 4, bx, y0 + 16, fill='#334155', width=1.5)
			cv.create_rectangle(
				x0 + 6, y0 + 18, x0 + lw_px - 6, y0 + 22, fill='#475569', outline=''
			)
			cv.create_text(
				cx,
				y0 + lh_px - 5,
				text='$00',
				fill='#0f172a',
				font=('Arial', 8, 'bold'),
			)

	def _select_template(self, key: str):
		if not self.winfo_exists():
			return
		self._tpl_key = key
		for k, f in self._tpl_frames.items():
			if not f.winfo_exists():
				continue
			active = k == key
			f.configure(fg_color=ACCENT_DIM if active else SURFACE3)
			cv_bg = '#1a274a' if active else SURFACE3

			if self._tpl_canvases[k].winfo_exists():
				self._tpl_canvases[k].configure(bg=cv_bg)
				self._draw_template_preview(self._tpl_canvases[k], k)

			for child in f.winfo_children():
				if isinstance(child, ctk.CTkLabel):
					if 'icon' in child.cget('text') or any(
						t['icon'] in child.cget('text') for t in TEMPLATES.values()
					):
						child.configure(
							text_color=ACCENT_TEXT if active else TEXT_SECONDARY
						)

	# ─────────────────────────────────────────────────────────────────────────
	# Catálogo y Lógica de Búsqueda
	# ─────────────────────────────────────────────────────────────────────────

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

	def _load_catalog(self):
		if not self.winfo_exists():
			return
		try:
			from database.models import Article, ArticleVariant

			Session = sessionmaker(bind=self.ctx.db_engine)
			with Session() as s:
				rows = (
					s.query(ArticleVariant)
					.join(Article)
					.filter(
						Article.tenant_id == self.ctx.tenant_id,
						Article.is_active,
						ArticleVariant.is_active,
					)
					.order_by(Article.name)
					.all()
				)
				self._variants = []
				for v in rows:
					name = v.article.name
					attr = ' '.join(filter(None, [v.attribute_1, v.attribute_2]))
					self._variants.append(
						{
							'variant_id': v.id,
							'name': name,
							'attribute': attr,
							'barcode': v.barcode or '',
							'price': float(v.selling_price),
							'display': f'{name}{"  –  " + attr if attr else ""}',
						}
					)
		except Exception as e:
			logger.error(f'Error cargando catálogo: {e}', exc_info=True)
			self._variants = []

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

		for i, v in enumerate(variants):
			check_var = ctk.BooleanVar(value=False)
			bg = SURFACE2 if i % 2 == 0 else '#1c1c1c'

			row = ctk.CTkFrame(self._catalog_frame, fg_color=bg, corner_radius=6)
			row.pack(fill='x', pady=2, padx=4)
			row.grid_columnconfigure(1, weight=1)

			ctk.CTkCheckBox(
				row,
				variable=check_var,
				text='',
				width=24,
				height=24,
				fg_color=ACCENT,
				hover_color='#1d4ed8',
				border_color=SURFACE4,
				checkmark_color='white',
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

	def _add_selected_to_queue(self):
		selected = [r['data'] for r in self._catalog_rows if r['check_var'].get()]
		if not selected:
			self.show_warning(
				'Marcá los artículos que querés agregar.', 'Sin selección'
			)
			return
		for v in selected:
			self._add_one_to_queue(v, render=False)
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

	def _add_one_to_queue(self, variant: dict, render: bool = True):
		for item in self._queue:
			if item['variant_id'] == variant['variant_id']:
				item['copies'] += 1
				if render:
					self._render_queue()
				return
		self._queue.append({**variant, 'copies': 1})
		if render:
			self._render_queue()

	# ─────────────────────────────────────────────────────────────────────────
	# Configuración de Cola y Entradas Dinámicas
	# ─────────────────────────────────────────────────────────────────────────

	def _update_queue_total(self):
		total = sum(it['copies'] for it in self._queue)
		if self._lbl_total.winfo_exists():
			self._lbl_total.configure(
				text=f'{total} etiqueta{"s" if total != 1 else ""}',
				text_color=ACCENT_TEXT if total > 0 else TEXT_MUTED,
			)

	def _render_queue(self):
		if not self.winfo_exists():
			return

		for w in list(self._queue_frame.winfo_children()):
			try:
				w.destroy()
			except Exception:
				pass

		self._update_queue_total()

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
			bg = SURFACE2 if idx % 2 == 0 else '#1c1c1c'
			row = ctk.CTkFrame(self._queue_frame, fg_color=bg, corner_radius=4)
			row.pack(fill='x', pady=1)
			row.grid_columnconfigure(0, weight=1)

			name_txt = item['display'][:36]
			ctk.CTkLabel(
				row, text=name_txt, font=FONT_LABEL, text_color=TEXT_PRIMARY, anchor='w'
			).grid(row=0, column=0, padx=PAD_SM, pady=5, sticky='w')

			ctk.CTkLabel(
				row,
				text=fmt_price(item['price']),
				font=FONT_LABEL,
				text_color=ACCENT_TEXT,
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

	def _clear_queue(self):
		if not self._queue:
			return
		self._queue.clear()
		self._render_queue()

	# ─────────────────────────────────────────────────────────────────────────
	# Integración con el Controlador y Atajos del Entorno
	# ─────────────────────────────────────────────────────────────────────────

	def _setup_bindings(self):
		if not self.winfo_exists():
			return
		self.top_level = self.winfo_toplevel()
		self.top_level.bind('<Control-p>', self._handle_print_shortcut)

	def _handle_print_shortcut(self, event=None):
		if self.winfo_exists():
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
			self._btn_print.configure(text='Generando PDF...', state='disabled')
			self.update_idletasks()

		ok, result = self._ctrl.generate_pdf(self._queue, self._tpl_key)

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
