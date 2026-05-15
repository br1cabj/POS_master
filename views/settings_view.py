"""
views/settings_view.py
======================
Panel de configuración del sistema — navegación lateral por secciones.
"""

import glob
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

import utils.settings_manager as cfg
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_FAMILY,
	FONT_FAMILY_MONO,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	FONT_MONO,
	FONT_TITLE,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	PAD_LG,
	PAD_MD,
	PAD_SM,
	PAD_XS,
	PURPLE,
	PURPLE_DIM,
	PURPLE_TEXT,
	RED_DIM,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	make_form_label,
)

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS = ['$', '€', 'S/.', '£', 'R$', '₱', '¥', '₩']

_SECTIONS = [
	('empresa', '🏪', 'Empresa & Marca'),
	('moneda', '💱', 'Moneda'),
	('ventas', '🛒', 'Ventas'),
	('datos', '📁', 'Datos'),
	('licencia', '🔑', 'Licencia'),
]


class SettingsView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.db_engine = ctx.db_engine
		self._settings = cfg.load()
		self._saved = True
		self._is_rebuilding = False
		self._dirty_sections: dict = {k: False for k, *_ in _SECTIONS}
		self._active_section = 'empresa'
		self._nav_btns: dict = {}
		self._dot_lbls: dict = {}
		self._content_frame = None
		self._pending_logo_path = None
		self._logo_ctk_image = None
		self._lic_ctrl = None
		self._cloud_ctrl = None

		self.grid_columnconfigure(1, weight=1)
		self.grid_rowconfigure(1, weight=1)

		self._build_header()
		self._build_sidebar()
		self._build_content_wrapper()
		self._show_section('empresa')

		self.winfo_toplevel().bind('<Control-s>', lambda e: self._save_all())

	def destroy(self):
		try:
			self.winfo_toplevel().unbind('<Control-s>')
		except Exception:
			pass
		super().destroy()

	# =========================================================
	# HEADER
	# =========================================================
	def _build_header(self):
		hdr = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=0,
			border_width=1,
			border_color=BORDER,
		)
		hdr.grid(row=0, column=0, columnspan=2, sticky='ew')
		hdr.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(
			hdr,
			text='⚙  Configuración',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).grid(row=0, column=0, padx=(PAD_LG, PAD_MD), pady=14, sticky='w')

		ctk.CTkLabel(
			hdr,
			text='Ctrl+S para guardar',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=0, column=1, sticky='w')

		btn_row = ctk.CTkFrame(hdr, fg_color='transparent')
		btn_row.grid(row=0, column=2, padx=PAD_LG, pady=10, sticky='e')

		self.btn_discard = ctk.CTkButton(
			btn_row,
			text='Descartar',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			width=110,
			height=36,
			corner_radius=8,
			font=FONT_BODY,
			command=self._discard_changes,
			state='disabled',
		)
		self.btn_discard.pack(side='left', padx=(0, PAD_SM))

		self.btn_save = ctk.CTkButton(
			btn_row,
			text='💾  Guardar cambios',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			width=170,
			height=36,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self._save_all,
			state='disabled',
		)
		self.btn_save.pack(side='left')

	# =========================================================
	# SIDEBAR
	# =========================================================
	def _build_sidebar(self):
		self._sidebar = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=0,
			border_width=1,
			border_color=BORDER,
			width=200,
		)
		self._sidebar.grid(row=1, column=0, sticky='nsew')
		self._sidebar.grid_propagate(False)
		self._sidebar.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			self._sidebar,
			text='SECCIONES',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=0, column=0, padx=PAD_MD, pady=(PAD_MD, PAD_XS), sticky='w')

		for i, (key, icon, label) in enumerate(_SECTIONS):
			row_f = ctk.CTkFrame(self._sidebar, fg_color='transparent')
			row_f.grid(row=i + 1, column=0, sticky='ew', padx=PAD_SM, pady=2)
			row_f.grid_columnconfigure(0, weight=1)

			btn = ctk.CTkButton(
				row_f,
				text=f'  {icon}  {label}',
				anchor='w',
				fg_color='transparent',
				hover_color=SURFACE3,
				text_color=TEXT_SECONDARY,
				height=38,
				corner_radius=8,
				font=FONT_BODY,
				command=lambda k=key: self._show_section(k),
			)
			btn.grid(row=0, column=0, sticky='ew')
			self._nav_btns[key] = btn

			dot = ctk.CTkLabel(
				row_f,
				text='⬤',
				font=('Arial', 7),
				text_color=ORANGE,
				width=12,
			)
			dot.grid(row=0, column=1, padx=(2, PAD_XS))
			dot.grid_remove()
			self._dot_lbls[key] = dot

		# Separador + versión
		ctk.CTkFrame(self._sidebar, height=1, fg_color=BORDER).grid(
			row=len(_SECTIONS) + 1, column=0, sticky='ew', padx=PAD_MD, pady=PAD_MD
		)
		ctk.CTkLabel(
			self._sidebar,
			text='CloudPOS v1.0',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=len(_SECTIONS) + 2, column=0, padx=PAD_MD, sticky='w')

	# =========================================================
	# CONTENT AREA
	# =========================================================
	def _build_content_wrapper(self):
		self._content_wrapper = ctk.CTkFrame(self, fg_color='transparent')
		self._content_wrapper.grid(row=1, column=1, sticky='nsew')
		self._content_wrapper.grid_columnconfigure(0, weight=1)
		self._content_wrapper.grid_rowconfigure(0, weight=1)

	def _show_section(self, key: str):
		self._persist_current_section()

		if self._content_frame and self._content_frame.winfo_exists():
			self._content_frame.destroy()

		for k, btn in self._nav_btns.items():
			if k == key:
				btn.configure(
					fg_color=ACCENT_DIM,
					text_color=ACCENT_TEXT,
					font=FONT_BODY_BOLD,
					hover_color=ACCENT_DIM,
				)
			else:
				btn.configure(
					fg_color='transparent',
					text_color=TEXT_SECONDARY,
					font=FONT_BODY,
					hover_color=SURFACE3,
				)

		self._active_section = key

		scroll = ctk.CTkScrollableFrame(
			self._content_wrapper,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
		)
		scroll.grid(row=0, column=0, sticky='nsew', padx=PAD_LG, pady=PAD_LG)
		scroll.grid_columnconfigure(0, weight=1)
		self._content_frame = scroll

		{
			'empresa': self._build_sec_empresa,
			'moneda': self._build_sec_moneda,
			'ventas': self._build_sec_ventas,
			'datos': self._build_sec_datos,
			'licencia': self._build_sec_licencia,
		}[key](scroll)

	# =========================================================
	# PERSISTENCIA ENTRE SECCIONES
	# =========================================================
	def _persist_current_section(self):
		"""Guarda en _settings los valores de la sección activa antes de cambiar."""
		sec = self._active_section

		if sec == 'empresa':
			if w := getattr(self, 'entry_company_name', None):
				self._settings['company_name'] = w.get().strip()
			if w := getattr(self, 'entry_company_address', None):
				self._settings['company_address'] = w.get().strip()
			if w := getattr(self, 'entry_company_phone', None):
				self._settings['company_phone'] = w.get().strip()

		elif sec == 'moneda':
			if hasattr(self, '_sym_var'):
				self._settings['currency_symbol'] = self._sym_var.get()
			if hasattr(self, '_dec_var'):
				self._settings['currency_decimals'] = self._dec_var.get()

		elif sec == 'ventas':
			if w := getattr(self, 'entry_tax', None):
				try:
					self._settings['tax_rate'] = float(w.get().replace(',', '.'))
				except ValueError:
					pass
			if w := getattr(self, 'entry_low_stock', None):
				try:
					self._settings['low_stock_threshold'] = int(w.get())
				except ValueError:
					pass
			if hasattr(self, '_req_customer_var'):
				self._settings['require_customer'] = self._req_customer_var.get()
			if hasattr(self, '_show_bar_var'):
				self._settings['show_shortcuts_bar'] = self._show_bar_var.get()
			if w := getattr(self, '_entry_list_a_name', None):
				self._settings['price_list_a_name'] = w.get().strip() or 'Minorista'
			if w := getattr(self, '_entry_list_b_name', None):
				self._settings['price_list_b_name'] = w.get().strip() or 'Mayorista'

		elif sec == 'datos':
			pass  # paths se persisten directamente en sus callbacks

	# =========================================================
	# DIRTY TRACKING
	# =========================================================
	def _mark_dirty(self, event=None, section: str = None):
		if self._is_rebuilding:
			return
		sec = section or self._active_section
		self._dirty_sections[sec] = True
		self._saved = False
		if dot := self._dot_lbls.get(sec):
			dot.grid()
		self.btn_save.configure(
			fg_color=GREEN, text_color='white', text='💾  Guardar cambios  ●'
		)
		self.btn_discard.configure(state='normal', text_color=TEXT_PRIMARY)

	def _clear_dirty(self):
		for key in self._dirty_sections:
			self._dirty_sections[key] = False
			if dot := self._dot_lbls.get(key):
				dot.grid_remove()
		self._saved = True
		self.btn_save.configure(
			fg_color=GREEN_DIM, text_color=GREEN_TEXT, text='💾  Guardar cambios'
		)
		self.btn_discard.configure(state='disabled', text_color=TEXT_MUTED)

	def has_unsaved_changes(self):
		return not self._saved

	def _discard_changes(self):
		if not self.confirm(
			'¿Descartás todos los cambios sin guardar?', 'Descartar cambios'
		):
			return
		self._is_rebuilding = True
		try:
			self._settings = cfg.load()
		finally:
			self._is_rebuilding = False
		self._pending_logo_path = None
		self._clear_dirty()
		self._show_section(self._active_section)

	# =========================================================
	# HELPERS DE UI
	# =========================================================
	def _card(self, parent, title: str, icon: str) -> ctk.CTkFrame:
		card = ctk.CTkFrame(
			parent,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		card.pack(fill='x', pady=(0, PAD_MD))

		hdr = ctk.CTkFrame(card, fg_color='transparent')
		hdr.pack(fill='x', padx=PAD_MD, pady=(PAD_MD, 0))
		ctk.CTkLabel(
			hdr,
			text=f'{icon}  {title}',
			font=FONT_BODY_BOLD,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		ctk.CTkFrame(card, height=1, fg_color=BORDER).pack(
			fill='x', padx=PAD_MD, pady=(PAD_SM, PAD_SM)
		)
		return card

	def _field(self, parent, label: str, hint: str = '', **kw) -> ctk.CTkEntry:
		make_form_label(parent, label)[0].pack(anchor='w', padx=PAD_MD, pady=(0, 2))
		e = ctk.CTkEntry(
			parent,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
			**kw,
		)
		e.pack(fill='x', padx=PAD_MD, pady=(0, PAD_XS if hint else PAD_SM))
		if hint:
			ctk.CTkLabel(
				parent,
				text=hint,
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
				anchor='w',
			).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))
		return e

	def _toggle_row(
		self,
		parent,
		label: str,
		hint: str,
		var: ctk.BooleanVar,
		section: str = 'ventas',
	):
		row = ctk.CTkFrame(parent, fg_color=SURFACE3, corner_radius=8)
		row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		row.grid_columnconfigure(0, weight=1)

		txt = ctk.CTkFrame(row, fg_color='transparent')
		txt.grid(row=0, column=0, sticky='ew', padx=PAD_MD, pady=PAD_SM)
		ctk.CTkLabel(
			txt, text=label, font=FONT_BODY_BOLD, text_color=TEXT_PRIMARY, anchor='w'
		).pack(anchor='w')
		if hint:
			ctk.CTkLabel(
				txt, text=hint, font=FONT_LABEL, text_color=TEXT_MUTED, anchor='w'
			).pack(anchor='w')

		ctk.CTkSwitch(
			row,
			text='',
			variable=var,
			width=46,
			progress_color=ACCENT,
			command=lambda: self._mark_dirty(section=section),
		).grid(row=0, column=1, padx=PAD_MD)

	# =========================================================
	# SECCIÓN: EMPRESA & MARCA
	# =========================================================
	def _build_sec_empresa(self, parent):
		def dirty(e=None):
			self._mark_dirty(section='empresa')

		# ── Datos del negocio ──
		card = self._card(parent, 'Datos del negocio', '🏪')

		self.entry_company_name = self._field(
			card, 'Nombre del negocio', placeholder_text='Ej: Mi Negocio'
		)
		self.entry_company_name.insert(0, self._settings.get('company_name', ''))
		self.entry_company_name.bind('<KeyRelease>', dirty)

		self.entry_company_address = self._field(
			card, 'Dirección', placeholder_text='Calle, número, ciudad'
		)
		self.entry_company_address.insert(0, self._settings.get('company_address', ''))
		self.entry_company_address.bind('<KeyRelease>', dirty)

		self.entry_company_phone = self._field(
			card, 'Teléfono / WhatsApp', placeholder_text='+54 11 ...'
		)
		self.entry_company_phone.insert(0, self._settings.get('company_phone', ''))
		self.entry_company_phone.bind('<KeyRelease>', dirty)
		ctk.CTkFrame(card, height=6, fg_color='transparent').pack()

		# ── Logo ──
		logo_card = self._card(parent, 'Logo del negocio', '🖼')

		logo_inner = ctk.CTkFrame(logo_card, fg_color='transparent')
		logo_inner.pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))
		logo_inner.grid_columnconfigure(1, weight=1)

		self._logo_preview = ctk.CTkLabel(
			logo_inner,
			text='📷\nSin logo',
			width=80,
			height=80,
			fg_color=SURFACE3,
			corner_radius=10,
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			justify='center',
		)
		self._logo_preview.grid(
			row=0, column=0, rowspan=3, padx=(0, PAD_MD), sticky='ns'
		)
		self._load_logo_preview()

		logo_path = self._settings.get('company_logo_path', '')
		self._lbl_logo_name = ctk.CTkLabel(
			logo_inner,
			text=os.path.basename(logo_path) if logo_path else 'Sin logo',
			font=FONT_BODY_BOLD,
			text_color=TEXT_PRIMARY if logo_path else TEXT_MUTED,
			anchor='w',
		)
		self._lbl_logo_name.grid(row=0, column=1, sticky='w')

		ctk.CTkLabel(
			logo_inner,
			text='PNG / JPG recomendado  ·  máx. 2 MB',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=1, column=1, sticky='w')

		btns = ctk.CTkFrame(logo_inner, fg_color='transparent')
		btns.grid(row=2, column=1, sticky='w', pady=(PAD_XS, 0))

		ctk.CTkButton(
			btns,
			text='📁  Seleccionar imagen',
			height=32,
			font=FONT_LABEL_BOLD,
			corner_radius=8,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			command=self._pick_logo,
		).pack(side='left', padx=(0, PAD_XS))

		ctk.CTkButton(
			btns,
			text='✕ Quitar',
			height=32,
			font=FONT_LABEL,
			corner_radius=8,
			fg_color='transparent',
			hover_color=RED_DIM,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			command=self._remove_logo,
		).pack(side='left')

	def _load_logo_preview(self):
		path = self._pending_logo_path or self._settings.get('company_logo_path', '')
		if path and os.path.exists(path):
			try:
				from PIL import Image

				img = Image.open(path)
				img.thumbnail((76, 76))
				ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(76, 76))
				self._logo_preview.configure(image=ctk_img, text='')
				self._logo_ctk_image = ctk_img
				return
			except Exception:
				pass
		self._logo_preview.configure(image=None, text='📷\nSin logo')

	def _pick_logo(self):
		from tkinter import filedialog

		path = filedialog.askopenfilename(
			title='Seleccionar logo',
			filetypes=[
				('Imágenes', '*.png *.jpg *.jpeg *.gif *.bmp'),
				('Todos', '*.*'),
			],
		)
		if not path:
			return
		if os.path.getsize(path) > 2 * 1024 * 1024:
			self.show_warning('El logo debe pesar menos de 2 MB.', 'Archivo muy grande')
			return

		# File copy is deferred to _save_all() to keep discard fully reversible
		self._pending_logo_path = path
		self._lbl_logo_name.configure(
			text=os.path.basename(path), text_color=GREEN_TEXT
		)
		self._load_logo_preview()
		self._mark_dirty(section='empresa')

	def _remove_logo(self):
		self._pending_logo_path = None
		self._logo_ctk_image = None
		self._settings['company_logo_path'] = ''
		self._lbl_logo_name.configure(text='Sin logo', text_color=TEXT_MUTED)
		self._logo_preview.configure(image=None, text='📷\nSin logo')
		self._mark_dirty(section='empresa')

	# =========================================================
	# SECCIÓN: MONEDA & FORMATO
	# =========================================================
	def _build_sec_moneda(self, parent):
		def dirty(e=None):
			self._mark_dirty(section='moneda')

		# ── Símbolo ──
		sym_card = self._card(parent, 'Símbolo de moneda', '💱')

		ctk.CTkLabel(
			sym_card,
			text='Seleccioná el símbolo que aparecerá en precios y tickets.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		sym_row = ctk.CTkFrame(sym_card, fg_color='transparent')
		sym_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))

		self._sym_var = ctk.StringVar(value=self._settings.get('currency_symbol', '$'))
		self._sym_btns = {}

		for sym in CURRENCY_SYMBOLS:
			active = sym == self._sym_var.get()
			btn = ctk.CTkButton(
				sym_row,
				text=sym,
				width=46,
				height=40,
				font=FONT_BODY_BOLD,
				fg_color=ACCENT_DIM if active else SURFACE3,
				hover_color=ACCENT if active else SURFACE4,
				text_color=ACCENT_TEXT if active else TEXT_SECONDARY,
				border_width=2 if active else 1,
				border_color=ACCENT if active else BORDER,
				corner_radius=8,
				command=lambda s=sym: self._pick_symbol(s),
			)
			btn.pack(side='left', padx=(0, PAD_XS))
			self._sym_btns[sym] = btn

		ctk.CTkFrame(sym_card, height=1, fg_color=BORDER).pack(
			fill='x', padx=PAD_MD, pady=(PAD_SM, PAD_SM)
		)

		make_form_label(sym_card, 'Símbolo personalizado')[0].pack(
			anchor='w', padx=PAD_MD, pady=(0, 2)
		)
		custom_row = ctk.CTkFrame(sym_card, fg_color='transparent')
		custom_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		vcmd = (self.register(lambda s: len(s) <= 5), '%P')
		self.entry_custom_sym = ctk.CTkEntry(
			custom_row,
			width=100,
			height=36,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			placeholder_text='Ej: Bs.',
			font=FONT_BODY,
			validate='key',
			validatecommand=vcmd,
		)
		if self._sym_var.get() not in CURRENCY_SYMBOLS:
			self.entry_custom_sym.insert(0, self._sym_var.get())
		self.entry_custom_sym.pack(side='left', padx=(0, PAD_XS))

		ctk.CTkButton(
			custom_row,
			text='Usar este',
			width=90,
			height=36,
			font=FONT_LABEL_BOLD,
			corner_radius=8,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			command=self._use_custom_sym,
		).pack(side='left')

		# ── Formato de precios ──
		fmt_card = self._card(parent, 'Formato de precios', '🔢')

		self._dec_var = ctk.IntVar(
			value=int(self._settings.get('currency_decimals', 0))
		)

		for val, label, example in [
			(0, 'Sin decimales', '$1.500'),
			(2, 'Con decimales', '$1.500,00'),
		]:
			active = self._dec_var.get() == val
			opt = ctk.CTkFrame(
				fmt_card,
				fg_color=ACCENT_DIM if active else SURFACE3,
				corner_radius=8,
				border_width=2 if active else 1,
				border_color=ACCENT if active else BORDER,
			)
			opt.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
			opt.grid_columnconfigure(0, weight=1)

			ctk.CTkLabel(
				opt,
				text=label,
				font=FONT_BODY_BOLD,
				text_color=ACCENT_TEXT if active else TEXT_PRIMARY,
				anchor='w',
			).grid(row=0, column=0, padx=PAD_MD, pady=(PAD_SM, 0), sticky='w')

			ctk.CTkLabel(
				opt,
				text=f'Ejemplo: {example}',
				font=FONT_LABEL,
				text_color=ACCENT_TEXT if active else TEXT_MUTED,
				anchor='w',
			).grid(row=1, column=0, padx=PAD_MD, pady=(0, PAD_SM), sticky='w')

			rb = ctk.CTkRadioButton(
				opt,
				text='',
				variable=self._dec_var,
				value=val,
				radiobutton_width=20,
				radiobutton_height=20,
				fg_color=ACCENT,
				command=lambda: [self._update_currency_preview(), dirty()],
			)
			rb.grid(row=0, column=1, rowspan=2, padx=PAD_MD)

		# Preview
		preview_box = ctk.CTkFrame(fmt_card, fg_color=SURFACE3, corner_radius=8)
		preview_box.pack(fill='x', padx=PAD_MD, pady=(PAD_SM, PAD_MD))

		ctk.CTkLabel(
			preview_box,
			text='Vista previa',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(pady=(PAD_SM, 0))

		self.lbl_currency_preview = ctk.CTkLabel(
			preview_box,
			text='',
			font=(FONT_FAMILY, 28, 'bold'),
			text_color=ACCENT_TEXT,
		)
		self.lbl_currency_preview.pack(pady=(0, PAD_SM))
		self._update_currency_preview()

	def _pick_symbol(self, sym):
		self._sym_var.set(sym)
		self._mark_dirty(section='moneda')
		self._update_currency_preview()
		for s, btn in self._sym_btns.items():
			active = s == sym
			try:
				btn.configure(
					fg_color=ACCENT_DIM if active else SURFACE3,
					hover_color=ACCENT if active else SURFACE4,
					text_color=ACCENT_TEXT if active else TEXT_SECONDARY,
					border_width=2 if active else 1,
					border_color=ACCENT if active else BORDER,
				)
			except Exception:
				pass

	def _use_custom_sym(self):
		val = self.entry_custom_sym.get().strip()
		if val:
			self._sym_var.set(val)
			self._mark_dirty(section='moneda')
			self._update_currency_preview()

	def _update_currency_preview(self):
		sym = getattr(self, '_sym_var', None)
		dec = getattr(self, '_dec_var', None)
		if not sym or not dec:
			return
		s, d = sym.get(), dec.get()
		sample = 1500.0
		# Format only the number, then prepend symbol to avoid corrupting symbols that contain '.' or ','
		if d == 0:
			num_text = f'{sample:,.0f}'.replace(',', '.')
		else:
			num_text = (
				f'{sample:,.{d}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
			)
		text = f'{s}{num_text}'
		if (
			hasattr(self, 'lbl_currency_preview')
			and self.lbl_currency_preview.winfo_exists()
		):
			self.lbl_currency_preview.configure(text=text)

	# =========================================================
	# SECCIÓN: VENTAS
	# =========================================================
	def _build_sec_ventas(self, parent):
		def dirty(e=None):
			self._mark_dirty(section='ventas')

		# ── Impuesto ──
		tax_card = self._card(parent, 'Impuesto (IVA)', '📊')

		make_form_label(tax_card, 'Porcentaje de IVA por defecto (%)')[0].pack(
			anchor='w', padx=PAD_MD, pady=(0, 2)
		)
		tax_row = ctk.CTkFrame(tax_card, fg_color='transparent')
		tax_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_XS))
		tax_row.grid_columnconfigure(0, weight=1)

		self.entry_tax = ctk.CTkEntry(
			tax_row,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
			placeholder_text='0',
		)
		self.entry_tax.grid(row=0, column=0, sticky='ew', padx=(0, PAD_XS))
		self.entry_tax.insert(0, str(self._settings.get('tax_rate', 0.0)))
		self.entry_tax.bind('<KeyRelease>', dirty)

		ctk.CTkLabel(
			tax_row,
			text='%',
			font=FONT_BODY_BOLD,
			text_color=TEXT_MUTED,
		).grid(row=0, column=1)

		ctk.CTkLabel(
			tax_card,
			text='Se aplica al crear artículos nuevos. Valor 0 = sin impuesto.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', padx=PAD_MD, pady=(2, PAD_MD))

		# ── Alertas de stock ──
		stock_card = self._card(parent, 'Alertas de stock crítico', '📦')

		self.entry_low_stock = self._field(
			stock_card,
			'Umbral (unidades)',
			'Los productos con stock igual o menor a este valor se muestran en Alertas.',
			placeholder_text='5',
		)
		self.entry_low_stock.insert(
			0, str(self._settings.get('low_stock_threshold', 5))
		)
		self.entry_low_stock.bind('<KeyRelease>', dirty)
		ctk.CTkFrame(stock_card, height=6, fg_color='transparent').pack()

		# ── Comportamiento ──
		beh_card = self._card(parent, 'Comportamiento en ventas', '🛒')

		self._req_customer_var = ctk.BooleanVar(
			value=self._settings.get('require_customer', False)
		)
		self._toggle_row(
			beh_card,
			'Requerir cliente en cada venta',
			'Obliga al cajero a seleccionar un cliente antes de cobrar.',
			self._req_customer_var,
		)

		self._show_bar_var = ctk.BooleanVar(
			value=self._settings.get('show_shortcuts_bar', True)
		)
		self._toggle_row(
			beh_card,
			'Mostrar barra de atajos táctiles',
			'Panel de acceso rápido a productos en la pantalla de ventas.',
			self._show_bar_var,
		)
		ctk.CTkFrame(beh_card, height=8, fg_color='transparent').pack()

		# ── Listas de precios ──
		price_card = self._card(parent, 'Nombres de listas de precios', '💰')

		ctk.CTkLabel(
			price_card,
			text='Lista A = precio minorista (estándar).  Lista B = precio especial por cliente.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		names_row = ctk.CTkFrame(price_card, fg_color='transparent')
		names_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))
		names_row.grid_columnconfigure(0, weight=1)
		names_row.grid_columnconfigure(1, weight=1)

		for col, attr, label, key, placeholder in [
			(0, '_entry_list_a_name', 'Lista A', 'price_list_a_name', 'Minorista'),
			(1, '_entry_list_b_name', 'Lista B', 'price_list_b_name', 'Mayorista'),
		]:
			f = ctk.CTkFrame(names_row, fg_color='transparent')
			f.grid(
				row=0,
				column=col,
				sticky='ew',
				padx=(0 if col == 0 else PAD_SM, PAD_SM if col == 0 else 0),
			)
			ctk.CTkLabel(
				f, text=label, font=FONT_LABEL_BOLD, text_color=TEXT_MUTED, anchor='w'
			).pack(anchor='w', pady=(0, 2))
			entry = ctk.CTkEntry(
				f,
				placeholder_text=placeholder,
				height=36,
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				text_color=TEXT_PRIMARY,
				font=FONT_BODY,
			)
			entry.insert(0, self._settings.get(key, placeholder))
			entry.pack(fill='x')
			entry.bind('<KeyRelease>', dirty)
			setattr(self, attr, entry)

	# =========================================================
	# SECCIÓN: DATOS & ALMACENAMIENTO
	# =========================================================
	def _build_sec_datos(self, parent):
		# ── Carpeta de reportes ──
		rep_card = self._card(parent, 'Carpeta de reportes', '📁')

		ctk.CTkLabel(
			rep_card,
			text='Reportes PDF, CSV, Reporte Z y respaldos se guardan aquí.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		path_box = ctk.CTkFrame(rep_card, fg_color=SURFACE3, corner_radius=8)
		path_box.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))

		current_path = cfg.get('reports_path', '') or cfg.get_reports_path()
		self._lbl_reports_path = ctk.CTkLabel(
			path_box,
			text=current_path,
			font=FONT_MONO,
			text_color=TEXT_SECONDARY,
			wraplength=400,
			anchor='w',
			justify='left',
		)
		self._lbl_reports_path.pack(anchor='w', padx=PAD_MD, pady=PAD_SM)

		rep_btns = ctk.CTkFrame(rep_card, fg_color='transparent')
		rep_btns.pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		ctk.CTkButton(
			rep_btns,
			text='📁  Elegir carpeta',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=34,
			corner_radius=8,
			font=FONT_LABEL_BOLD,
			command=self._pick_reports_path,
		).pack(side='left', padx=(0, PAD_SM))

		ctk.CTkButton(
			rep_btns,
			text='↺ Restaurar',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			height=34,
			corner_radius=8,
			font=FONT_LABEL,
			command=self._reset_reports_path,
		).pack(side='left')

		# ── Base de datos ──
		db_card = self._card(parent, 'Base de datos', '🗄️')

		_db_dir = (
			os.path.dirname(sys.executable)
			if getattr(sys, 'frozen', False)
			else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
		)
		db_path = Path(os.path.join(_db_dir, 'pos_system.db'))

		info_box = ctk.CTkFrame(db_card, fg_color=SURFACE3, corner_radius=8)
		info_box.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))

		ctk.CTkLabel(
			info_box,
			text=f'📄  {db_path.name}',
			font=FONT_BODY_BOLD,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(anchor='w', padx=PAD_MD, pady=(PAD_SM, 2))

		ctk.CTkLabel(
			info_box,
			text=str(db_path.parent),
			font=(FONT_FAMILY_MONO, 10),
			text_color=TEXT_MUTED,
			wraplength=400,
			anchor='w',
			justify='left',
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		ctk.CTkButton(
			db_card,
			text='💾  Crear respaldo ahora',
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			height=38,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self._backup_db,
		).pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

	def _pick_reports_path(self):
		from tkinter import filedialog

		path = filedialog.askdirectory(
			title='Seleccionar carpeta de reportes', initialdir=cfg.get_reports_path()
		)
		if not path:
			return
		self._settings['reports_path'] = path
		self._mark_dirty(section='datos')
		self._lbl_reports_path.configure(text=path)

	def _reset_reports_path(self):
		self._settings['reports_path'] = ''
		self._mark_dirty(section='datos')
		self._lbl_reports_path.configure(text=cfg.get_reports_path())

	def _backup_db(self):
		_db_dir = (
			os.path.dirname(sys.executable)
			if getattr(sys, 'frozen', False)
			else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
		)
		db_path = Path(os.path.join(_db_dir, 'pos_system.db'))
		if not db_path.exists():
			self.show_error("No se encontró el archivo 'pos_system.db'.")
			return
		dest_folder = cfg.get_reports_path()
		timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
		dest_path = Path(dest_folder) / f'respaldo_CloudPOS_{timestamp}.db'
		try:
			shutil.copy2(db_path, dest_path)
			self.show_success(f'Respaldo creado correctamente:\n{dest_path}')
		except Exception as e:
			logger.error(f'Fallo al respaldar BD: {e}', exc_info=True)
			self.show_error(f'Error al crear el respaldo:\n{e}')

	# =========================================================
	# SECCIÓN: LICENCIA
	# =========================================================
	def _build_sec_licencia(self, parent):
		from controllers.cloud_license_controller import CloudLicenseController
		from controllers.license_controller import LicenseController

		if self._lic_ctrl is None:
			self._lic_ctrl = LicenseController()
		if self._cloud_ctrl is None:
			self._cloud_ctrl = CloudLicenseController()

		# ── Licencia local ──
		local_card = self._card(parent, 'Licencia local', '🔑')

		status_box = ctk.CTkFrame(local_card, fg_color=SURFACE3, corner_radius=8)
		status_box.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))

		self._lbl_local_status = ctk.CTkLabel(
			status_box,
			text='Verificando…',
			font=FONT_BODY_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
		)
		self._lbl_local_status.pack(anchor='w', padx=PAD_MD, pady=PAD_SM)

		make_form_label(local_card, 'Código de activación')[0].pack(
			anchor='w', padx=PAD_MD, pady=(0, 2)
		)
		self._entry_local_code = ctk.CTkEntry(
			local_card,
			placeholder_text='TIPO-AAAAMMDD-FIRMA',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		self._entry_local_code.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))

		ctk.CTkButton(
			local_card,
			text='✔  Activar licencia',
			height=36,
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self._activate_local,
		).pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		# ── Plan Cloud ──
		cloud_card = self._card(parent, 'Plan Cloud', '☁️')

		cloud_box = ctk.CTkFrame(cloud_card, fg_color=SURFACE3, corner_radius=8)
		cloud_box.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))

		self._lbl_cloud_status = ctk.CTkLabel(
			cloud_box,
			text='Verificando…',
			font=FONT_BODY_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
		)
		self._lbl_cloud_status.pack(anchor='w', padx=PAD_MD, pady=(PAD_SM, 0))

		self._lbl_cloud_tenant = ctk.CTkLabel(
			cloud_box,
			text='',
			font=(FONT_FAMILY_MONO, 10),
			text_color=TEXT_MUTED,
			anchor='w',
		)
		self._lbl_cloud_tenant.pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		make_form_label(cloud_card, 'Código de activación Cloud')[0].pack(
			anchor='w', padx=PAD_MD, pady=(0, 2)
		)
		self._entry_cloud_code = ctk.CTkEntry(
			cloud_card,
			placeholder_text='CLOUD-AAAAMMDD-TENANTID-FIRMA',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		self._entry_cloud_code.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))

		ctk.CTkButton(
			cloud_card,
			text='☁️  Activar Plan Cloud',
			height=36,
			fg_color=PURPLE_DIM,
			hover_color=PURPLE,
			text_color=PURPLE_TEXT,
			border_width=1,
			border_color=PURPLE,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self._activate_cloud,
		).pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		self._refresh_local_status()
		self._refresh_cloud_status()

	def _refresh_local_status(self):
		lbl = getattr(self, '_lbl_local_status', None)
		if not lbl or not lbl.winfo_exists():
			return
		valid, msg = self._lic_ctrl.check_license_status()
		if valid:
			text = '✅  Licencia vitalicia' if msg == 'VITALICIA' else f'✅  {msg}'
			color = GREEN_TEXT
		else:
			text = {
				'NO_LICENSE': '○  Sin licencia activa',
				'EXPIRED': '⚠  Licencia vencida',
			}.get(msg, '✕  Licencia inválida')
			color = RED_TEXT
		lbl.configure(text=text, text_color=color)

	def _refresh_cloud_status(self):
		lbl_status = getattr(self, '_lbl_cloud_status', None)
		lbl_tenant = getattr(self, '_lbl_cloud_tenant', None)
		if not lbl_status or not lbl_status.winfo_exists():
			return
		active, msg = self._cloud_ctrl.check_status()
		if active:
			lbl_status.configure(text=f'✅  {msg}', text_color=PURPLE_TEXT)
			tid = self._cloud_ctrl.get_tenant_id() or ''
			if lbl_tenant and lbl_tenant.winfo_exists():
				lbl_tenant.configure(text=f'Tenant ID: {tid}')
		else:
			color = (
				RED_TEXT
				if any(w in msg for w in ('vencido', 'inválido'))
				else TEXT_MUTED
			)
			lbl_status.configure(text=f'○  {msg}', text_color=color)
			if lbl_tenant and lbl_tenant.winfo_exists():
				lbl_tenant.configure(text='')

	def _activate_local(self):
		code = self._entry_local_code.get().strip()
		if not code:
			self.show_warning('Ingresá el código de licencia antes de continuar.')
			return
		ok, msg = self._lic_ctrl.activate_license(code)
		if ok:
			self._entry_local_code.delete(0, 'end')
			self._refresh_local_status()
			self.show_success(msg)
		else:
			self.show_error(msg)

	def _activate_cloud(self):
		code = self._entry_cloud_code.get().strip()
		if not code:
			self.show_warning('Ingresá el código de plan cloud antes de continuar.')
			return
		ok, msg = self._cloud_ctrl.activate(code)
		if ok:
			self._entry_cloud_code.delete(0, 'end')
			self._refresh_cloud_status()
			self.show_success(msg)
		else:
			self.show_error(msg)

	# =========================================================
	# GUARDAR TODO
	# =========================================================
	def _save_all(self):
		self._persist_current_section()

		if self._pending_logo_path:
			base = (
				os.path.dirname(sys.executable)
				if getattr(sys, 'frozen', False)
				else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
			)
			dest_dir = os.path.join(base, 'assets')
			try:
				os.makedirs(dest_dir, exist_ok=True)
				for old in glob.glob(os.path.join(dest_dir, 'logo.*')):
					try:
						os.remove(old)
					except Exception:
						pass
				ext = os.path.splitext(self._pending_logo_path)[1].lower()
				dest = os.path.join(dest_dir, f'logo{ext}')
				shutil.copy2(self._pending_logo_path, dest)
				self._settings['company_logo_path'] = dest
				self._pending_logo_path = None
			except OSError as e:
				self.show_error(f'No se pudo guardar el logo:\n{e}', 'Error')
				return

		if cfg.save(self._settings):
			self._clear_dirty()
			self.show_success(
				'Configuración guardada. Reiniciá la sesión para aplicar cambios visuales.'
			)
		else:
			self.show_error('No se pudo guardar la configuración en el disco.')
