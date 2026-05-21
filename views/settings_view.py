"""
views/settings_view.py
======================
Panel de configuración del sistema — navegación lateral por secciones.
"""

import glob
import logging
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from tkinter import filedialog

try:
	from PIL import Image as _PIL_Image
except ImportError:
	_PIL_Image = None

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
	FONT_SMALL,
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
	('perifericos', '🔌', 'Periféricos'),
	('datos', '📁', 'Datos'),
	('respaldo', '💾', 'Respaldo'),
	('licencia', '🔑', 'Licencia'),
]


class SettingsView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
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

		self._ctrl_s_funcid = self.winfo_toplevel().bind(
			'<Control-s>',
			lambda e: self._save_all() if self.winfo_exists() else None,
			add='+',
		)

	def destroy(self):
		if getattr(self, '_ctrl_s_funcid', None):
			try:
				self.winfo_toplevel().unbind('<Control-s>', self._ctrl_s_funcid)
			except Exception:
				pass
			self._ctrl_s_funcid = None
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

		import utils.settings_manager as _sm
		_is_cashier = _sm.get('terminal_mode', 'primary') == 'cashier'
		_hidden = {'respaldo'} if _is_cashier else set()

		_row = 1  # contador independiente para no dejar gaps en el grid
		for key, icon, label in _SECTIONS:
			if key in _hidden:
				continue
			row_f = ctk.CTkFrame(self._sidebar, fg_color='transparent')
			row_f.grid(row=_row, column=0, sticky='ew', padx=PAD_SM, pady=2)
			_row += 1
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
			row=_row + 1, column=0, sticky='ew', padx=PAD_MD, pady=PAD_MD
		)
		ctk.CTkLabel(
			self._sidebar,
			text='CloudPOS v1.0',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=_row + 2, column=0, padx=PAD_MD, sticky='w')

	# =========================================================
	# CONTENT AREA
	# =========================================================
	def _build_content_wrapper(self):
		self._content_wrapper = ctk.CTkFrame(self, fg_color='transparent')
		self._content_wrapper.grid(row=1, column=1, sticky='nsew')
		self._content_wrapper.grid_columnconfigure(0, weight=1)
		self._content_wrapper.grid_rowconfigure(0, weight=1)

	def _show_section(self, key: str):
		# En modo cajero la sección de respaldo no existe — redirigir a empresa.
		import utils.settings_manager as _sm
		if key == 'respaldo' and _sm.get('terminal_mode', 'primary') == 'cashier':
			key = 'empresa'
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
			'perifericos': self._build_sec_perifericos,
			'datos': self._build_sec_datos,
			'respaldo': self._build_sec_respaldo,
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

		elif sec == 'perifericos':
			s = self._settings
			_DETECTING = 'Detectando…'
			# Impresora tickets
			if v := getattr(self, '_peri_ticket_printer_var', None):
				val = v.get()
				if val != _DETECTING:
					s['printer_ticket_name'] = val
			if v := getattr(self, '_peri_ticket_type_var', None):
				s['printer_ticket_type'] = v.get()
			if w := getattr(self, '_peri_ticket_chars_entry', None):
				try:
					s['printer_ticket_chars'] = int(w.get())
				except ValueError:
					pass
			# Impresora etiquetas
			if v := getattr(self, '_peri_label_printer_var', None):
				val = v.get()
				if val != _DETECTING:
					s['printer_label_name'] = val
			# Balanza
			if v := getattr(self, '_peri_scale_enabled_var', None):
				s['scale_enabled'] = v.get()
			if v := getattr(self, '_peri_scale_port_var', None):
				s['scale_port'] = v.get()
			if v := getattr(self, '_peri_scale_baud_var', None):
				s['scale_baud'] = v.get()
			if v := getattr(self, '_peri_scale_proto_var', None):
				s['scale_protocol'] = v.get()
			# Lector código de barras
			if v := getattr(self, '_peri_barcode_mode_var', None):
				s['barcode_mode'] = v.get()
			if v := getattr(self, '_peri_barcode_port_var', None):
				s['barcode_port'] = v.get()
			if v := getattr(self, '_peri_barcode_baud_var', None):
				s['barcode_baud'] = v.get()
			if w := getattr(self, '_peri_barcode_prefix_entry', None):
				s['barcode_prefix'] = w.get()
			if v := getattr(self, '_peri_barcode_suffix_var', None):
				s['barcode_suffix'] = v.get()
			# Cajón de dinero
			if v := getattr(self, '_peri_cashdrawer_conn_var', None):
				s['cashdrawer_connection'] = v.get()
			if v := getattr(self, '_peri_cashdrawer_port_var', None):
				s['cashdrawer_port'] = v.get()
			# Pantalla de cliente
			if v := getattr(self, '_peri_poledisplay_enabled_var', None):
				s['poledisplay_enabled'] = v.get()
			if v := getattr(self, '_peri_poledisplay_port_var', None):
				s['poledisplay_port'] = v.get()
			if v := getattr(self, '_peri_poledisplay_baud_var', None):
				s['poledisplay_baud'] = v.get()
			if w := getattr(self, '_peri_poledisplay_line1_entry', None):
				s['poledisplay_line1'] = w.get()
			if w := getattr(self, '_peri_poledisplay_line2_entry', None):
				s['poledisplay_line2'] = w.get()

		elif sec == 'datos':
			pass  # paths se persisten directamente en sus callbacks

	# =========================================================
	# DIRTY TRACKING
	# =========================================================
	def _mark_dirty(self, event=None, section: str | None = None):
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
		if path and os.path.exists(path) and _PIL_Image is not None:
			try:
				img = _PIL_Image.open(path)
				img.thumbnail((76, 76))
				ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(76, 76))
				self._logo_preview.configure(image=ctk_img, text='')
				self._logo_ctk_image = ctk_img
				return
			except Exception:
				pass
		self._logo_preview.configure(image=None, text='📷\nSin logo')

	def _pick_logo(self):
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
	# SECCIÓN: PERIFÉRICOS
	# =========================================================

	def _get_system_printers(self) -> list:
		"""Detecta impresoras instaladas en el sistema. Llamar solo desde hilo de fondo."""
		try:
			result = subprocess.run(
				[
					'powershell',
					'-Command',
					'Get-Printer | Select-Object -ExpandProperty Name',
				],
				capture_output=True,
				text=True,
				timeout=3,
			)
			printers = [
				line.strip() for line in result.stdout.splitlines() if line.strip()
			]
			if printers:
				return printers
		except Exception:
			pass
		return []

	def _get_com_ports(self) -> list:
		"""Retorna lista de puertos COM disponibles."""
		try:
			import serial.tools.list_ports

			return sorted(p.device for p in serial.tools.list_ports.comports()) or [
				f'COM{i}' for i in range(1, 13)
			]
		except ImportError:
			pass
		# Fallback: leer desde el registro de Windows
		try:
			import winreg

			key = winreg.OpenKey(
				winreg.HKEY_LOCAL_MACHINE, r'HARDWARE\DEVICEMAP\SERIALCOMM'
			)
			ports, i = [], 0
			while True:
				try:
					ports.append(winreg.EnumValue(key, i)[1])
					i += 1
				except OSError:
					break
			return sorted(ports) if ports else [f'COM{i}' for i in range(1, 13)]
		except Exception:
			return [f'COM{i}' for i in range(1, 13)]

	def _peri_option_row(
		self,
		parent,
		label: str,
		var: ctk.StringVar,
		options: list,
		section: str = 'perifericos',
	) -> ctk.CTkOptionMenu:
		"""Fila label + OptionMenu reutilizable para la sección periféricos."""
		row = ctk.CTkFrame(parent, fg_color='transparent')
		row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		row.grid_columnconfigure(1, weight=1)
		ctk.CTkLabel(
			row,
			text=label,
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
			width=140,
		).grid(row=0, column=0, sticky='w')
		om = ctk.CTkOptionMenu(
			row,
			variable=var,
			values=options if options else ['—'],
			fg_color=SURFACE3,
			button_color=SURFACE4,
			button_hover_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
			command=lambda _: self._mark_dirty(section=section),
		)
		om.grid(row=0, column=1, sticky='ew', padx=(PAD_SM, 0))
		return om

	def _peri_status_label(self, parent) -> ctk.CTkLabel:
		lbl = ctk.CTkLabel(
			parent,
			text='',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		)
		lbl.pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))
		return lbl

	def _build_sec_perifericos(self, parent):
		def dirty(e=None):
			self._mark_dirty(section='perifericos')

		s = self._settings
		_BAUDS = ['1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200']

		# Usar caché si ya detectamos; de lo contrario mostrar el valor guardado como
		# placeholder y lanzar la detección en segundo plano.
		cached_printers = getattr(self, '_cached_printers', None)
		cached_ports = getattr(self, '_cached_com_ports', None)

		_DETECT = ['Detectando…']
		printer_opts = cached_printers if cached_printers is not None else _DETECT
		port_opts = cached_ports if cached_ports is not None else _DETECT

		# Guarda referencias a los OptionMenus que dependen de detección,
		# para actualizarlos cuando el hilo termine.
		self._peri_printer_oms: list = []  # (OptionMenu, StringVar, settings_key)
		self._peri_port_oms: list = []

		def _printer_om(parent_w, var, key):
			om = self._peri_option_row(parent_w, 'Impresora:', var, printer_opts)
			self._peri_printer_oms.append((om, var, key))
			return om

		def _port_om(parent_w, var, key):
			om = self._peri_option_row(parent_w, 'Puerto COM:', var, port_opts)
			self._peri_port_oms.append((om, var, key))
			return om

		# ── Indicador de detección ────────────────────────────
		if cached_printers is None or cached_ports is None:
			self._peri_detect_lbl = ctk.CTkLabel(
				parent,
				text='🔍  Detectando dispositivos…',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
				anchor='w',
			)
			self._peri_detect_lbl.pack(anchor='w', padx=PAD_XS, pady=(0, PAD_SM))
		else:
			self._peri_detect_lbl = None

		# ── Impresora de Tickets ──────────────────────────────
		tc = self._card(parent, 'Impresora de Tickets', '🖨️')
		ctk.CTkLabel(
			tc,
			text='Impresora usada para generar recibos y facturas.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		saved_ticket = s.get('printer_ticket_name', '')
		self._peri_ticket_printer_var = ctk.StringVar(
			value=saved_ticket or printer_opts[0]
		)
		_printer_om(tc, self._peri_ticket_printer_var, 'printer_ticket_name')

		type_row = ctk.CTkFrame(tc, fg_color='transparent')
		type_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		ctk.CTkLabel(
			type_row,
			text='Tipo de papel:',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
			width=140,
		).pack(side='left')
		self._peri_ticket_type_var = ctk.StringVar(
			value=s.get('printer_ticket_type', '80mm')
		)
		for val, lbl in [('58mm', '58 mm'), ('80mm', '80 mm'), ('laser', 'A4 / Laser')]:
			ctk.CTkRadioButton(
				type_row,
				text=lbl,
				variable=self._peri_ticket_type_var,
				value=val,
				fg_color=ACCENT,
				font=FONT_BODY,
				command=dirty,
			).pack(side='left', padx=(0, PAD_MD))

		chars_row = ctk.CTkFrame(tc, fg_color='transparent')
		chars_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		ctk.CTkLabel(
			chars_row,
			text='Chars por línea:',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
			width=140,
		).pack(side='left')
		self._peri_ticket_chars_entry = ctk.CTkEntry(
			chars_row,
			width=70,
			height=32,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._peri_ticket_chars_entry.insert(0, str(s.get('printer_ticket_chars', 48)))
		self._peri_ticket_chars_entry.bind('<KeyRelease>', dirty)
		self._peri_ticket_chars_entry.pack(side='left')
		ctk.CTkLabel(
			chars_row,
			text='(58mm≈32  |  80mm≈48)',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(side='left', padx=(PAD_SM, 0))

		self._peri_ticket_status = self._peri_status_label(tc)
		ctk.CTkButton(
			tc,
			text='🖨  Imprimir ticket de prueba',
			height=34,
			corner_radius=8,
			font=FONT_LABEL_BOLD,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			command=self._test_ticket_print,
		).pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		# ── Impresora de Etiquetas ────────────────────────────
		lc = self._card(parent, 'Impresora de Etiquetas', '🏷️')
		ctk.CTkLabel(
			lc,
			text='Impresora dedicada para etiquetas de productos (Zebra, Dymo, etc.).',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		saved_label = s.get('printer_label_name', '')
		self._peri_label_printer_var = ctk.StringVar(
			value=saved_label or printer_opts[0]
		)
		_printer_om(lc, self._peri_label_printer_var, 'printer_label_name')

		self._peri_label_status = self._peri_status_label(lc)
		ctk.CTkButton(
			lc,
			text='🏷  Imprimir etiqueta de prueba',
			height=34,
			corner_radius=8,
			font=FONT_LABEL_BOLD,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			command=self._test_label_print,
		).pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		# ── Balanza ───────────────────────────────────────────
		sc = self._card(parent, 'Balanza', '⚖️')

		self._peri_scale_enabled_var = ctk.BooleanVar(
			value=s.get('scale_enabled', False)
		)
		self._toggle_row(
			sc,
			'Balanza habilitada',
			'Activa la lectura de peso desde el puerto serial.',
			self._peri_scale_enabled_var,
			section='perifericos',
		)

		self._peri_scale_port_var = ctk.StringVar(value=s.get('scale_port', 'COM1'))
		_port_om(sc, self._peri_scale_port_var, 'scale_port')

		self._peri_scale_baud_var = ctk.StringVar(
			value=str(s.get('scale_baud', '9600'))
		)
		self._peri_option_row(
			sc, 'Velocidad (baud):', self._peri_scale_baud_var, _BAUDS
		)

		self._peri_scale_proto_var = ctk.StringVar(
			value=s.get('scale_protocol', 'toledo')
		)
		proto_row = ctk.CTkFrame(sc, fg_color='transparent')
		proto_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		ctk.CTkLabel(
			proto_row,
			text='Protocolo:',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
			width=140,
		).pack(side='left')
		for val, lbl in [
			('toledo', 'Toledo / Filizola'),
			('fairbanks', 'Fairbanks'),
			('generic', 'Genérico'),
		]:
			ctk.CTkRadioButton(
				proto_row,
				text=lbl,
				variable=self._peri_scale_proto_var,
				value=val,
				fg_color=ACCENT,
				font=FONT_BODY,
				command=dirty,
			).pack(side='left', padx=(0, PAD_MD))

		self._peri_scale_status = self._peri_status_label(sc)
		ctk.CTkButton(
			sc,
			text='📡  Probar conexión con balanza',
			height=34,
			corner_radius=8,
			font=FONT_LABEL_BOLD,
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			command=self._test_scale,
		).pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		# ── Lector de código de barras ───────────────────────
		bc = self._card(parent, 'Lector de Código de Barras', '📷')

		self._peri_barcode_mode_var = ctk.StringVar(value=s.get('barcode_mode', 'hid'))
		mode_row = ctk.CTkFrame(bc, fg_color='transparent')
		mode_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		ctk.CTkLabel(
			mode_row,
			text='Modo de conexión:',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
			width=140,
		).pack(side='left')
		for val, lbl in [('hid', 'HID / USB'), ('serial', 'Puerto Serial')]:
			ctk.CTkRadioButton(
				mode_row,
				text=lbl,
				variable=self._peri_barcode_mode_var,
				value=val,
				fg_color=ACCENT,
				font=FONT_BODY,
				command=dirty,
			).pack(side='left', padx=(0, PAD_MD))

		self._peri_barcode_port_var = ctk.StringVar(value=s.get('barcode_port', 'COM2'))
		_port_om(bc, self._peri_barcode_port_var, 'barcode_port')

		self._peri_barcode_baud_var = ctk.StringVar(
			value=str(s.get('barcode_baud', '9600'))
		)
		self._peri_option_row(
			bc, 'Velocidad (baud):', self._peri_barcode_baud_var, _BAUDS
		)

		pref_suf_row = ctk.CTkFrame(bc, fg_color='transparent')
		pref_suf_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		pref_suf_row.grid_columnconfigure(1, weight=1)
		pref_suf_row.grid_columnconfigure(3, weight=1)
		ctk.CTkLabel(
			pref_suf_row,
			text='Prefijo:',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
		).grid(row=0, column=0, sticky='w', padx=(0, PAD_XS))
		self._peri_barcode_prefix_entry = ctk.CTkEntry(
			pref_suf_row,
			width=80,
			height=32,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
			placeholder_text='vacío',
		)
		self._peri_barcode_prefix_entry.insert(0, s.get('barcode_prefix', ''))
		self._peri_barcode_prefix_entry.bind('<KeyRelease>', dirty)
		self._peri_barcode_prefix_entry.grid(
			row=0, column=1, sticky='ew', padx=(0, PAD_MD)
		)
		ctk.CTkLabel(
			pref_suf_row,
			text='Sufijo:',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
		).grid(row=0, column=2, sticky='w', padx=(0, PAD_XS))
		self._peri_barcode_suffix_var = ctk.StringVar(
			value=s.get('barcode_suffix', 'CR')
		)
		ctk.CTkOptionMenu(
			pref_suf_row,
			variable=self._peri_barcode_suffix_var,
			values=['none', 'CR', 'TAB', 'CRLF'],
			fg_color=SURFACE3,
			button_color=SURFACE4,
			button_hover_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
			command=lambda _: dirty(),
		).grid(row=0, column=3, sticky='ew')

		self._peri_barcode_status = self._peri_status_label(bc)
		ctk.CTkButton(
			bc,
			text='🔍  Probar lectura de código',
			height=34,
			corner_radius=8,
			font=FONT_LABEL_BOLD,
			fg_color=PURPLE_DIM,
			hover_color=PURPLE,
			text_color=PURPLE_TEXT,
			border_width=1,
			border_color=PURPLE,
			command=self._test_barcode,
		).pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		# ── Cajón de dinero ───────────────────────────────────
		cdc = self._card(parent, 'Cajón de Dinero', '💵')
		ctk.CTkLabel(
			cdc,
			text='El cajón puede abrirse vía la impresora (ESC/POS) o un puerto COM propio.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		self._peri_cashdrawer_conn_var = ctk.StringVar(
			value=s.get('cashdrawer_connection', 'printer')
		)
		conn_row = ctk.CTkFrame(cdc, fg_color='transparent')
		conn_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		ctk.CTkLabel(
			conn_row,
			text='Conexión:',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
			width=140,
		).pack(side='left')
		for val, lbl in [
			('printer', 'Vía impresora de tickets'),
			('com', 'Puerto COM propio'),
		]:
			ctk.CTkRadioButton(
				conn_row,
				text=lbl,
				variable=self._peri_cashdrawer_conn_var,
				value=val,
				fg_color=ACCENT,
				font=FONT_BODY,
				command=dirty,
			).pack(side='left', padx=(0, PAD_MD))

		self._peri_cashdrawer_port_var = ctk.StringVar(
			value=s.get('cashdrawer_port', 'COM3')
		)
		_port_om(cdc, self._peri_cashdrawer_port_var, 'cashdrawer_port')

		self._peri_cashdrawer_status = self._peri_status_label(cdc)
		ctk.CTkButton(
			cdc,
			text='💵  Probar apertura del cajón',
			height=34,
			corner_radius=8,
			font=FONT_LABEL_BOLD,
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			command=self._test_cashdrawer,
		).pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		# ── Pantalla de cliente (Pole Display) ───────────────
		pdc = self._card(parent, 'Pantalla de Cliente (Pole Display)', '🖥️')

		self._peri_poledisplay_enabled_var = ctk.BooleanVar(
			value=s.get('poledisplay_enabled', False)
		)
		self._toggle_row(
			pdc,
			'Pantalla de cliente habilitada',
			'Muestra precios y mensajes en la pantalla orientada al cliente.',
			self._peri_poledisplay_enabled_var,
			section='perifericos',
		)

		self._peri_poledisplay_port_var = ctk.StringVar(
			value=s.get('poledisplay_port', 'COM4')
		)
		_port_om(pdc, self._peri_poledisplay_port_var, 'poledisplay_port')

		self._peri_poledisplay_baud_var = ctk.StringVar(
			value=str(s.get('poledisplay_baud', '9600'))
		)
		self._peri_option_row(
			pdc, 'Velocidad (baud):', self._peri_poledisplay_baud_var, _BAUDS
		)

		ctk.CTkLabel(
			pdc,
			text='Mensaje de bienvenida',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
		).pack(anchor='w', padx=PAD_MD, pady=(0, 2))
		self._peri_poledisplay_line1_entry = ctk.CTkEntry(
			pdc,
			height=34,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
			placeholder_text='Línea 1',
		)
		self._peri_poledisplay_line1_entry.insert(
			0, s.get('poledisplay_line1', 'Bienvenido!')
		)
		self._peri_poledisplay_line1_entry.bind('<KeyRelease>', dirty)
		self._peri_poledisplay_line1_entry.pack(fill='x', padx=PAD_MD, pady=(0, PAD_XS))
		self._peri_poledisplay_line2_entry = ctk.CTkEntry(
			pdc,
			height=34,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
			placeholder_text='Línea 2 (opcional)',
		)
		self._peri_poledisplay_line2_entry.insert(0, s.get('poledisplay_line2', ''))
		self._peri_poledisplay_line2_entry.bind('<KeyRelease>', dirty)
		self._peri_poledisplay_line2_entry.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))

		self._peri_poledisplay_status = self._peri_status_label(pdc)
		ctk.CTkButton(
			pdc,
			text='📡  Enviar texto de prueba',
			height=34,
			corner_radius=8,
			font=FONT_LABEL_BOLD,
			fg_color=PURPLE_DIM,
			hover_color=PURPLE,
			text_color=PURPLE_TEXT,
			border_width=1,
			border_color=PURPLE,
			command=self._test_poledisplay,
		).pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		# Lanzar detección en segundo plano si aún no tenemos caché
		if cached_printers is None or cached_ports is None:
			self._start_peri_detection()

	# ── Helpers de test ──────────────────────────────────────

	def _start_peri_detection(self):
		"""Detecta impresoras y puertos COM en un hilo de fondo. Nunca bloquea la UI."""
		if getattr(self, '_peri_detecting', False):
			return
		self._peri_detecting = True

		def _detect():
			printers = self._get_system_printers()
			com_ports = self._get_com_ports()
			self._cached_printers = printers or ['(Sin impresoras detectadas)']
			self._cached_com_ports = com_ports or [f'COM{i}' for i in range(1, 13)]
			self._peri_detecting = False
			try:
				self.after(
					0,
					lambda: self._update_peri_dropdowns(
						self._cached_printers, self._cached_com_ports
					),
				)
			except Exception:
				pass

		threading.Thread(target=_detect, daemon=True).start()

	def _update_peri_dropdowns(self, printers: list, com_ports: list):
		"""Actualiza los OptionMenus de impresoras y puertos con los valores detectados.
		Siempre se llama desde el hilo principal vía after()."""
		s = self._settings

		for om, var, key in getattr(self, '_peri_printer_oms', []):
			try:
				if not om.winfo_exists():
					continue
				opts = printers or ['(Sin impresoras detectadas)']
				saved = s.get(key, '')
				if saved and saved not in opts:
					opts = [saved] + opts
				om.configure(values=opts)
				if saved and saved in opts:
					var.set(saved)
				elif var.get() in ('Detectando…', '') or var.get() not in opts:
					var.set(opts[0])
			except Exception:
				pass

		for om, var, key in getattr(self, '_peri_port_oms', []):
			try:
				if not om.winfo_exists():
					continue
				opts = com_ports or [f'COM{i}' for i in range(1, 13)]
				saved = s.get(key, '')
				if saved and saved not in opts:
					opts = [saved] + opts
				om.configure(values=opts)
				if saved and saved in opts:
					var.set(saved)
				elif var.get() in ('Detectando…', '') or var.get() not in opts:
					var.set(opts[0])
			except Exception:
				pass

		lbl = getattr(self, '_peri_detect_lbl', None)
		if lbl:
			try:
				if lbl.winfo_exists():
					n_printers = len(printers)
					n_ports = len(com_ports)
					lbl.configure(
						text=f'✔  {n_printers} impresora(s)  ·  {n_ports} puerto(s) detectado(s)',
						text_color=TEXT_MUTED,
					)
			except Exception:
				pass

	def _set_peri_status(self, lbl: ctk.CTkLabel, text: str, ok: bool):
		"""Actualiza el label de estado de un periférico."""
		if lbl and lbl.winfo_exists():
			lbl.configure(
				text=text,
				text_color=GREEN_TEXT if ok else RED_TEXT,
			)

	def _test_ticket_print(self):
		self._persist_current_section()
		name = self._settings.get('printer_ticket_name', '')
		chars = int(self._settings.get('printer_ticket_chars', 48))
		if not name or name.startswith('('):
			self._set_peri_status(
				self._peri_ticket_status, '✕  Seleccioná una impresora primero.', False
			)
			return
		try:
			import win32print

			sep = '─' * chars
			lines = [
				sep,
				'TICKET DE PRUEBA'.center(chars),
				'CloudPOS'.center(chars),
				sep,
				f'Impresora: {name}',
				f'Papel: {self._settings.get("printer_ticket_type", "80mm")}  |  {chars} chars',
				sep,
				'*** Impresión exitosa ***'.center(chars),
				sep,
				'',
				'',
			]
			hprinter = win32print.OpenPrinter(name)
			try:
				win32print.StartDocPrinter(
					hprinter, 1, ('Prueba CloudPOS', None, 'RAW')
				)
				win32print.StartPagePrinter(hprinter)
				win32print.WritePrinter(
					hprinter, ('\n'.join(lines) + '\n').encode('cp1252', 'replace')
				)
				win32print.EndPagePrinter(hprinter)
				win32print.EndDocPrinter(hprinter)
			finally:
				win32print.ClosePrinter(hprinter)
			self._set_peri_status(
				self._peri_ticket_status, '✔  Ticket enviado correctamente.', True
			)
		except ImportError:
			self._set_peri_status(
				self._peri_ticket_status,
				'⚠  Instala pywin32 para imprimir directamente (pip install pywin32).',
				False,
			)
		except Exception as e:
			self._set_peri_status(self._peri_ticket_status, f'✕  Error: {e}', False)

	def _test_label_print(self):
		self._persist_current_section()
		name = self._settings.get('printer_label_name', '')
		if not name or name.startswith('('):
			self._set_peri_status(
				self._peri_label_status,
				'✕  Seleccioná una impresora de etiquetas primero.',
				False,
			)
			return
		try:
			import win32print

			zpl = '^XA^FO50,50^A0N,40,40^FDCloudPOS - Prueba^FS^FO50,110^A0N,30,30^FDEtiqueta OK^FS^XZ'
			hprinter = win32print.OpenPrinter(name)
			try:
				win32print.StartDocPrinter(
					hprinter, 1, ('Etiqueta prueba', None, 'RAW')
				)
				win32print.StartPagePrinter(hprinter)
				win32print.WritePrinter(hprinter, zpl.encode('ascii'))
				win32print.EndPagePrinter(hprinter)
				win32print.EndDocPrinter(hprinter)
			finally:
				win32print.ClosePrinter(hprinter)
			self._set_peri_status(self._peri_label_status, '✔  Etiqueta enviada.', True)
		except ImportError:
			self._set_peri_status(
				self._peri_label_status,
				'⚠  Instala pywin32 para imprimir directamente.',
				False,
			)
		except Exception as e:
			self._set_peri_status(self._peri_label_status, f'✕  Error: {e}', False)

	def _test_scale(self):
		self._persist_current_section()
		port = self._settings.get('scale_port', 'COM1')
		baud = int(self._settings.get('scale_baud', 9600))
		try:
			import serial
		except ImportError:
			self._set_peri_status(
				self._peri_scale_status,
				'⚠  Instala pyserial: pip install pyserial',
				False,
			)
			return
		try:
			with serial.Serial(port, baud, timeout=2) as ser:
				raw = ser.read(32)
			if raw:
				self._set_peri_status(
					self._peri_scale_status,
					f'✔  Conexión OK · datos recibidos: {raw!r}',
					True,
				)
			else:
				self._set_peri_status(
					self._peri_scale_status,
					f'⚠  Puerto {port} abierto pero sin respuesta en 2s. Verificá que la balanza esté encendida.',
					False,
				)
		except Exception as e:
			self._set_peri_status(self._peri_scale_status, f'✕  {e}', False)

	def _test_barcode(self):
		self._persist_current_section()
		mode = self._settings.get('barcode_mode', 'hid')
		if mode == 'hid':
			self.show_success(
				'El lector HID/USB no requiere configuración.\n'
				'Si funciona en el sistema operativo, funciona en CloudPOS automáticamente.',
				'Lector HID',
			)
			return
		port = self._settings.get('barcode_port', 'COM2')
		baud = int(self._settings.get('barcode_baud', 9600))
		try:
			import serial
		except ImportError:
			self._set_peri_status(
				self._peri_barcode_status,
				'⚠  Instala pyserial: pip install pyserial',
				False,
			)
			return
		try:
			with serial.Serial(port, baud, timeout=3):
				self._set_peri_status(
					self._peri_barcode_status,
					f'✔  Puerto {port} abierto a {baud} baud. Escaneá un código para verificar.',
					True,
				)
		except Exception as e:
			self._set_peri_status(self._peri_barcode_status, f'✕  {e}', False)

	def _test_cashdrawer(self):
		self._persist_current_section()
		conn = self._settings.get('cashdrawer_connection', 'printer')
		ESC_POS_KICK = b'\x1b\x70\x00\x19\xfa'

		if conn == 'printer':
			name = self._settings.get('printer_ticket_name', '')
			if not name or name.startswith('('):
				self._set_peri_status(
					self._peri_cashdrawer_status,
					'✕  Configurá la impresora de tickets primero.',
					False,
				)
				return
			try:
				import win32print

				hprinter = win32print.OpenPrinter(name)
				try:
					win32print.StartDocPrinter(hprinter, 1, ('CashDrawer', None, 'RAW'))
					win32print.StartPagePrinter(hprinter)
					win32print.WritePrinter(hprinter, ESC_POS_KICK)
					win32print.EndPagePrinter(hprinter)
					win32print.EndDocPrinter(hprinter)
				finally:
					win32print.ClosePrinter(hprinter)
				self._set_peri_status(
					self._peri_cashdrawer_status,
					'✔  Comando enviado a la impresora.',
					True,
				)
			except ImportError:
				self._set_peri_status(
					self._peri_cashdrawer_status,
					'⚠  Instala pywin32: pip install pywin32',
					False,
				)
			except Exception as e:
				self._set_peri_status(self._peri_cashdrawer_status, f'✕  {e}', False)
		else:
			port = self._settings.get('cashdrawer_port', 'COM3')
			try:
				import serial

				with serial.Serial(port, 9600, timeout=1) as ser:
					ser.write(ESC_POS_KICK)
				self._set_peri_status(
					self._peri_cashdrawer_status, f'✔  Comando enviado a {port}.', True
				)
			except ImportError:
				self._set_peri_status(
					self._peri_cashdrawer_status,
					'⚠  Instala pyserial: pip install pyserial',
					False,
				)
			except Exception as e:
				self._set_peri_status(self._peri_cashdrawer_status, f'✕  {e}', False)

	def _test_poledisplay(self):
		self._persist_current_section()
		port = self._settings.get('poledisplay_port', 'COM4')
		baud = int(self._settings.get('poledisplay_baud', 9600))
		line1 = self._settings.get('poledisplay_line1', 'Bienvenido!')
		line2 = self._settings.get('poledisplay_line2', '')
		try:
			import serial
		except ImportError:
			self._set_peri_status(
				self._peri_poledisplay_status,
				'⚠  Instala pyserial: pip install pyserial',
				False,
			)
			return
		try:
			msg = f'{line1:<20}{line2:<20}'.encode('ascii', 'replace')
			with serial.Serial(port, baud, timeout=1) as ser:
				ser.write(msg)
			self._set_peri_status(
				self._peri_poledisplay_status,
				f'✔  Mensaje enviado a {port}.',
				True,
			)
		except Exception as e:
			self._set_peri_status(self._peri_poledisplay_status, f'✕  {e}', False)

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
		import sqlite3
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
			# sqlite3.backup() maneja WAL correctamente a diferencia de shutil.copy2
			src = sqlite3.connect(str(db_path))
			dst = sqlite3.connect(str(dest_path))
			src.backup(dst)
			dst.close()
			src.close()
			self.show_success(f'Respaldo creado correctamente:\n{dest_path}')
		except Exception as e:
			logger.error(f'Fallo al respaldar BD: {e}', exc_info=True)
			self.show_error(f'Error al crear el respaldo:\n{e}')

	# =========================================================
	# =========================================================
	# SECCIÓN: RESPALDO
	# =========================================================
	def _build_sec_respaldo(self, parent):
		import os
		import threading
		from tkinter import filedialog

		from controllers.backup_controller import BackupController

		bk = BackupController(self.ctx.db_engine)

		# ── Estado del último respaldo ──
		card_status = self._card(parent, 'Respaldo automático', '💾')

		status_box = ctk.CTkFrame(card_status, fg_color=SURFACE3, corner_radius=8)
		status_box.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))

		last = bk.get_last_backup_str()
		self._lbl_backup_date = ctk.CTkLabel(
			status_box,
			text=f'Último respaldo: {last}' if last else 'Sin respaldos aún',
			font=FONT_BODY_BOLD,
			text_color=GREEN_TEXT if last else TEXT_MUTED,
			anchor='w',
		)
		self._lbl_backup_date.pack(anchor='w', padx=PAD_MD, pady=(PAD_SM, 0))

		backup_path_str = str(bk.backup_dir())
		ctk.CTkLabel(
			status_box,
			text=f'Carpeta: {backup_path_str}',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			anchor='w',
			wraplength=440,
		).pack(anchor='w', padx=PAD_MD, pady=(2, PAD_SM))

		self._btn_backup_now = ctk.CTkButton(
			card_status,
			text='💾  Respaldar ahora',
			height=36,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=lambda: self._do_backup(bk),
		)
		self._btn_backup_now.pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		# ── Restaurar ──
		card_restore = self._card(parent, 'Restaurar datos', '↩️')

		ctk.CTkLabel(
			card_restore,
			text=(
				'Seleccioná un archivo de respaldo para reemplazar la base de datos actual.\n'
				'Se guardará una copia de seguridad del estado actual antes de restaurar.\n'
				'La aplicación se reiniciará automáticamente al finalizar.'
			),
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			anchor='w',
			justify='left',
			wraplength=440,
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		ctk.CTkLabel(
			card_restore,
			text='⚠️  Esta acción reemplaza TODOS los datos actuales.',
			font=FONT_SMALL,
			text_color=ORANGE_TEXT,
			anchor='w',
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		ctk.CTkButton(
			card_restore,
			text='↩️  Seleccionar respaldo para restaurar…',
			height=36,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=lambda: self._do_restore(bk),
		).pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		# ── Restaurar desde la nube ──
		from utils.config import DATABASE_CLOUD_URL
		if DATABASE_CLOUD_URL:
			card_cloud = self._card(parent, 'Restaurar desde la nube', '☁️')

			ctk.CTkLabel(
				card_cloud,
				text=(
					'Descarga todos los datos sincronizados desde Supabase y reemplaza\n'
					'la base de datos local. Requiere plan cloud activo.\n'
					'Se crea un respaldo automático antes de comenzar.'
				),
				font=FONT_SMALL,
				text_color=TEXT_MUTED,
				anchor='w',
				justify='left',
				wraplength=440,
			).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

			ctk.CTkLabel(
				card_cloud,
				text='⚠️  Esta acción reemplaza TODOS los datos locales con los de la nube.',
				font=FONT_SMALL,
				text_color=ORANGE_TEXT,
				anchor='w',
			).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

			self._lbl_cloud_restore_status = ctk.CTkLabel(
				card_cloud,
				text='',
				font=FONT_SMALL,
				text_color=TEXT_MUTED,
				anchor='w',
				wraplength=440,
			)
			self._lbl_cloud_restore_status.pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

			self._btn_cloud_restore = ctk.CTkButton(
				card_cloud,
				text='☁️  Restaurar desde la nube…',
				height=36,
				fg_color=PURPLE_DIM,
				hover_color=PURPLE,
				text_color=PURPLE_TEXT,
				border_width=1,
				border_color=PURPLE,
				corner_radius=8,
				font=FONT_BODY_BOLD,
				command=lambda: self._do_cloud_restore(bk),
			)
			self._btn_cloud_restore.pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

	def _do_backup(self, bk):
		from controllers.backup_controller import BackupController
		self._btn_backup_now.configure(state='disabled', text='⏳  Respaldando…')

		def worker():
			ok, result = bk.create_backup()
			self.after(0, lambda: self._on_backup_done(ok, result))

		import threading
		threading.Thread(target=worker, daemon=True).start()

	def _on_backup_done(self, ok: bool, result: str):
		if not self.winfo_exists():
			return
		self._btn_backup_now.configure(state='normal', text='💾  Respaldar ahora')
		if ok:
			lbl = getattr(self, '_lbl_backup_date', None)
			if lbl and lbl.winfo_exists():
				lbl.configure(
					text=f'Último respaldo: {result}',
					text_color=GREEN_TEXT,
				)
			self.show_toast('Respaldo creado correctamente.', 'success')
		else:
			self.show_toast(f'Error al respaldar: {result}', 'error')

	def _do_cloud_restore(self, bk):
		from CTkMessagebox import CTkMessagebox

		confirm = CTkMessagebox(
			title='Confirmar restauración desde la nube',
			message=(
				'Esta acción descargará todos los datos desde Supabase\n'
				'y reemplazará la base de datos local.\n\n'
				'Se creará un respaldo automático antes de comenzar.\n'
				'La aplicación se reiniciará al finalizar.\n\n'
				'¿Continuar?'
			),
			icon='warning',
			option_1='Cancelar',
			option_2='Sí, restaurar desde la nube',
		)
		if confirm.get() != 'Sí, restaurar desde la nube':
			return

		self._btn_cloud_restore.configure(state='disabled', text='⏳  Descargando…')
		self._lbl_cloud_restore_status.configure(text='Iniciando restauración…', text_color=TEXT_MUTED)

		def _progress(msg: str):
			if self.winfo_exists():
				self.after(0, lambda m=msg: self._lbl_cloud_restore_status.configure(text=m))

		def worker():
			ok, result = bk.restore_from_cloud(progress_cb=_progress)
			if self.winfo_exists():
				self.after(0, lambda: self._on_cloud_restore_done(ok, result))

		import threading
		threading.Thread(target=worker, daemon=True, name='CloudRestore').start()

	def _on_cloud_restore_done(self, ok: bool, result: str):
		if not self.winfo_exists():
			return
		btn = getattr(self, '_btn_cloud_restore', None)
		if btn and btn.winfo_exists():
			btn.configure(state='normal', text='☁️  Restaurar desde la nube…')

		if ok:
			from CTkMessagebox import CTkMessagebox
			CTkMessagebox(
				title='Restauración completada',
				message='Los datos fueron restaurados desde la nube.\nLa aplicación se reiniciará ahora.',
				icon='check',
			)
			self._restart_app()
		else:
			lbl = getattr(self, '_lbl_cloud_restore_status', None)
			if lbl and lbl.winfo_exists():
				lbl.configure(text=f'Error: {result}', text_color=RED_TEXT)
			self.show_toast(f'Error al restaurar: {result}', 'error')

	def _do_restore(self, bk):
		from tkinter import filedialog

		from CTkMessagebox import CTkMessagebox

		backup_dir = str(bk.backup_dir())
		path = filedialog.askopenfilename(
			initialdir=backup_dir,
			title='Seleccionar archivo de respaldo',
			filetypes=[('Base de datos', '*.db'), ('Todos', '*.*')],
		)
		if not path:
			return

		import os
		confirm = CTkMessagebox(
			title='Confirmar restauración',
			message=(
				f'Se restaurará:\n{os.path.basename(path)}\n\n'
				'Todos los datos actuales serán reemplazados.\n'
				'¿Continuar?'
			),
			icon='warning',
			option_1='Cancelar',
			option_2='Sí, restaurar',
		)
		if confirm.get() != 'Sí, restaurar':
			return

		ok, msg = bk.restore_backup(path)
		if ok:
			CTkMessagebox(
				title='Restauración completa',
				message='Los datos fueron restaurados. La aplicación se reiniciará ahora.',
				icon='check',
			)
			self._restart_app()
		else:
			self.show_toast(f'Error al restaurar: {msg}', 'error')

	def _restart_app(self):
		import subprocess
		import sys
		subprocess.Popen([sys.executable] + sys.argv[1:])
		self.winfo_toplevel().destroy()

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

		# Tenant ID local — siempre visible para que el cliente lo comparta con el proveedor
		tid_box = ctk.CTkFrame(cloud_card, fg_color=SURFACE3, corner_radius=8)
		tid_box.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		tid_box.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			tid_box,
			text='Tu Tenant ID (compartilo con tu proveedor para activar el plan cloud)',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=0, column=0, columnspan=2, padx=PAD_MD, pady=(PAD_SM, 2), sticky='w')

		local_tid = self.ctx.tenant_id or '—'
		lbl_local_tid = ctk.CTkLabel(
			tid_box,
			text=local_tid,
			font=(FONT_FAMILY_MONO, 11),
			text_color=TEXT_PRIMARY,
			anchor='w',
		)
		lbl_local_tid.grid(row=1, column=0, padx=PAD_MD, pady=(0, PAD_SM), sticky='w')

		def _copy_tid():
			self.clipboard_clear()
			self.clipboard_append(local_tid)
			btn_copy_tid.configure(text='✓  Copiado')
			self.after(1500, lambda: btn_copy_tid.configure(text='Copiar'))

		btn_copy_tid = ctk.CTkButton(
			tid_box,
			text='Copiar',
			width=70,
			height=26,
			fg_color=SURFACE4,
			hover_color=BORDER_ACTIVE,
			text_color=TEXT_SECONDARY,
			corner_radius=6,
			font=FONT_SMALL,
			command=_copy_tid,
		)
		btn_copy_tid.grid(row=1, column=1, padx=(0, PAD_MD), pady=(0, PAD_SM))

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
		"""Actualiza el estado cloud en un hilo daemon para no bloquear la UI."""
		def _run():
			try:
				active, msg = self._cloud_ctrl.check_status()
				tid = self._cloud_ctrl.get_tenant_id() or '' if active else ''
			except Exception as e:
				logger.warning('Error al verificar estado cloud: %s', e)
				active, msg, tid = False, 'Error al conectar', ''

			def _update():
				lbl_status = getattr(self, '_lbl_cloud_status', None)
				lbl_tenant = getattr(self, '_lbl_cloud_tenant', None)
				if not lbl_status or not lbl_status.winfo_exists():
					return
				if active:
					lbl_status.configure(text=f'✅  {msg}', text_color=PURPLE_TEXT)
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

			try:
				self.after(0, _update)
			except Exception:
				pass

		threading.Thread(target=_run, daemon=True, name='CloudStatusRefresh').start()

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
			worker = getattr(self.ctx, 'sync_worker', None)
			if worker and not worker.is_running:
				try:
					worker.start()
					msg += '\n\nEl sync cloud ha iniciado. No es necesario reiniciar.'
				except Exception:
					msg += '\n\nReiniciá la app para que el sync comience.'
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
