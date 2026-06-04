"""
views/setup_wizard_view.py
==========================
Wizard de primer arranque en 3 pasos:
  1. Licencia  — demo gratuita o código Pro
  2. Tu Negocio — datos del comercio
  3. Tu Usuario — credenciales del administrador
"""

import glob
import logging
import os
import re
import shutil
import sys

import bcrypt
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from sqlalchemy.orm import sessionmaker

from controllers.license_controller import LicenseController
from database.models import Base, Branch, Tenant, User, Warehouse
from utils.settings_manager import get_reports_path
from utils.settings_manager import load as _cfg_load
from utils.settings_manager import save as _cfg_save
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_FAMILY,
	FONT_HEADING,
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
	PAD_XL,
	PAD_XS,
	PURPLE,
	PURPLE_DIM,
	PURPLE_TEXT,
	RED,
	RED_TEXT,
	SURFACE1,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	make_form_label,
)

logger = logging.getLogger(__name__)

_STEPS = ['Terminal', 'Licencia', 'Tu Negocio', 'Tu Usuario']

_STEP_NEXT_LABELS = {
	1: 'Siguiente: Licencia  →',
	2: 'Siguiente: Tu Negocio  →',
	3: 'Siguiente: Tu Usuario  →',
	4: '✓  Finalizar y Comenzar',
}

_CURRENCY_SYMBOLS = ['$', '€', 'S/.', '£', 'Bs.', '₱']

_DEMO_FEATURES = [
	'✓  Ventas, compras y stock sin límites',
	'✓  Artículos, clientes y reportes',
	'✓  Exportaciones a Excel y PDF',
	'✓  Sin tarjeta de crédito requerida',
]

_PRO_FEATURES = [
	(
		'♾️',
		'Uso sin límite de tiempo',
		'Facturá y gestioná tu negocio sin restricciones',
	),
	('⚡', 'Activación inmediata', 'Tu código desbloquea todas las funciones locales'),
	(
		'📦',
		'Control de stock ilimitado',
		'Sin límite de artículos, variantes o categorías',
	),
	(
		'🛒',
		'Módulo de ventas ágil',
		'Alta velocidad para puntos de venta con alto volumen',
	),
	('💬', 'Soporte Técnico', 'Asistencia para clientes con licencias activas'),
]


class SetupWizard(ctk.CTkFrame):
	"""Wizard multi-paso para el primer arranque de la aplicación."""

	def __init__(self, master, on_complete_callback):
		super().__init__(master, fg_color=SURFACE1)
		self.on_complete_callback = on_complete_callback
		self.license_ctrl = LicenseController()
		self._busy = False
		self._step = 1

		self._terminal_mode_sel: str = 'primary'  # 'primary' | 'cashier'
		self._cashier_db_path: str = ''

		self._license_mode: str | None = None
		self._license_key: str = ''

		self._d_store = ''
		self._d_address = ''
		self._d_phone = ''
		self._d_currency = '$'
		self._d_decimals = '0  (enteros)'
		self._d_tax = '21'
		self._d_reports_path = ''
		self._d_logo_path: str | None = None

		self._d_username = ''
		self._d_password = ''
		self._d_pin = ''

		self.pack(fill='both', expand=True)
		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		self._build_header()

		self._content = ctk.CTkFrame(self, fg_color='transparent')
		self._content.grid(row=1, column=0, sticky='nsew')
		self._content.grid_columnconfigure(0, weight=1)
		self._content.grid_rowconfigure(0, weight=1)

		nav = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=0,
			border_width=1,
			border_color=BORDER,
		)
		nav.grid(row=2, column=0, sticky='ew')
		nav.grid_columnconfigure(1, weight=1)

		self._btn_back = ctk.CTkButton(
			nav,
			text='✕  Salir',
			width=140,
			height=42,
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self._handle_exit,
		)
		self._btn_back.grid(row=0, column=0, padx=PAD_LG, pady=PAD_MD)

		self._btn_next = ctk.CTkButton(
			nav,
			text=_STEP_NEXT_LABELS[1],
			width=230,
			height=42,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self._go_next,
		)
		self._btn_next.grid(row=0, column=2, padx=PAD_LG, pady=PAD_MD)

		self._show_step(1)

	# ═══════════════════════════════════════════════════════════════════════
	# HEADER
	# ═══════════════════════════════════════════════════════════════════════

	def _build_header(self):
		header = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=0,
			border_width=1,
			border_color=BORDER,
			height=72,
		)
		header.grid(row=0, column=0, sticky='ew')
		header.grid_propagate(False)
		header.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(
			header,
			text='🚀  CloudPOS',
			font=FONT_TITLE,
			text_color=ACCENT_TEXT,
		).grid(row=0, column=0, padx=PAD_XL, sticky='w')

		steps_frame = ctk.CTkFrame(header, fg_color='transparent')
		steps_frame.grid(row=0, column=2, padx=PAD_XL)

		self._step_indicators: list[tuple] = []
		self._step_lines: list = []

		for i, name in enumerate(_STEPS):
			col = ctk.CTkFrame(steps_frame, fg_color='transparent')
			col.pack(side='left')

			circ = ctk.CTkFrame(
				col, width=30, height=30, corner_radius=15, fg_color=SURFACE3
			)
			circ.pack_propagate(False)
			circ.pack(side='left')
			circ_lbl = ctk.CTkLabel(
				circ, text=str(i + 1), font=FONT_LABEL_BOLD, text_color=TEXT_MUTED
			)
			circ_lbl.place(relx=0.5, rely=0.5, anchor='center')

			name_lbl = ctk.CTkLabel(
				col, text=f'  {name}', font=FONT_BODY, text_color=TEXT_MUTED
			)
			name_lbl.pack(side='left')

			self._step_indicators.append((circ, circ_lbl, name_lbl))

			if i < len(_STEPS) - 1:
				line = ctk.CTkLabel(
					steps_frame,
					text='  ─────  ',
					font=('Arial', 9),
					text_color=BORDER_ACTIVE,
				)
				line.pack(side='left')
				self._step_lines.append(line)

		self._progress_bar = ctk.CTkProgressBar(
			header,
			height=3,
			corner_radius=0,
			fg_color=SURFACE3,
			progress_color=ACCENT,
		)
		self._progress_bar.grid(row=1, column=0, columnspan=3, sticky='ew')
		self._progress_bar.set(0)

	def _update_step_indicator(self):
		for i, (circ, circ_lbl, name_lbl) in enumerate(self._step_indicators):
			n = i + 1
			if n < self._step:
				circ.configure(fg_color=GREEN)
				circ_lbl.configure(text='✓', text_color='white')
				name_lbl.configure(text_color=GREEN_TEXT, font=FONT_BODY_BOLD)
			elif n == self._step:
				circ.configure(fg_color=ACCENT)
				circ_lbl.configure(text=str(n), text_color='white')
				name_lbl.configure(text_color=ACCENT_TEXT, font=FONT_BODY_BOLD)
			else:
				circ.configure(fg_color=SURFACE3)
				circ_lbl.configure(text=str(n), text_color=TEXT_MUTED)
				name_lbl.configure(text_color=TEXT_MUTED, font=FONT_BODY)

		for i, line in enumerate(self._step_lines):
			line.configure(
				text_color=GREEN_TEXT if self._step > i + 1 else BORDER_ACTIVE
			)

		self._progress_bar.set((self._step - 1) / len(_STEPS))

	# ═══════════════════════════════════════════════════════════════════════
	# NAVEGACIÓN
	# ═══════════════════════════════════════════════════════════════════════

	def _handle_exit(self):
		confirm = CTkMessagebox(
			title='Salir del asistente',
			message='¿Salir? El sistema no quedará configurado hasta completar este proceso.',
			icon='warning',
			option_1='Cancelar',
			option_2='Salir de todas formas',
		)
		if confirm.get() == 'Salir de todas formas':
			self.winfo_toplevel().destroy()

	def _go_back(self):
		if self._step > 1 and not self._busy:
			self._show_step(self._step - 1)

	def _go_next(self):
		if self._busy:
			return
		if self._step == 1:
			if self._validate_step_terminal():
				if self._terminal_mode_sel == 'cashier':
					self._finish_cashier()
				else:
					self._show_step(2)
		elif self._step == 2:
			if self._validate_step1():
				self._show_step(3)
		elif self._step == 3:
			if self._validate_step2():
				self._show_step(4)
		elif self._step == 4:
			self._finish()

	def _show_step(self, step: int):
		self._step = step
		for w in self._content.winfo_children():
			w.destroy()
		self._update_step_indicator()

		if step == 1:
			self._btn_back.configure(
				text='✕  Salir',
				command=self._handle_exit,
				text_color=TEXT_MUTED,
				fg_color='transparent',
				border_width=1,
				border_color=BORDER,
			)
		else:
			self._btn_back.configure(
				text='←  Atrás',
				command=self._go_back,
				text_color=TEXT_SECONDARY,
				fg_color=SURFACE3,
				border_width=0,
				state='normal',
			)

		if step == 4:
			self._btn_next.configure(
				text=_STEP_NEXT_LABELS[4],
				fg_color=GREEN_DIM,
				hover_color=GREEN,
				text_color=GREEN_TEXT,
				border_color=GREEN,
			)
		else:
			self._btn_next.configure(
				text=_STEP_NEXT_LABELS[step],
				fg_color=ACCENT_DIM,
				hover_color=ACCENT,
				text_color=ACCENT_TEXT,
				border_color=ACCENT,
			)

		{
			1: self._build_step_terminal,
			2: self._build_step1,
			3: self._build_step2,
			4: self._build_step3,
		}[step]()

	# ═══════════════════════════════════════════════════════════════════════
	# PASO 1 — LICENCIA
	# ═══════════════════════════════════════════════════════════════════════

	def _build_step1(self):
		scroll = ctk.CTkScrollableFrame(
			self._content,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		scroll.grid(row=0, column=0, sticky='nsew')
		scroll.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			scroll,
			text='¿Cómo querés comenzar?',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
		).pack(pady=(PAD_XL, PAD_XS))

		ctk.CTkLabel(
			scroll,
			text='Elegí la opción que mejor se adapta a vos. Podés cambiar a Pro en cualquier momento.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
		).pack(pady=(0, PAD_XL))

		cards_row = ctk.CTkFrame(scroll, fg_color='transparent')
		cards_row.pack(fill='x', padx=PAD_XL, pady=(0, PAD_MD))
		cards_row.grid_columnconfigure(0, weight=1)
		cards_row.grid_columnconfigure(1, weight=1)

		# ── CARD DEMO ────────────────────────────────────────────────────
		self._card_demo = ctk.CTkFrame(
			cards_row,
			fg_color=SURFACE2,
			corner_radius=16,
			border_width=1,
			border_color=BORDER,
		)
		self._card_demo.grid(row=0, column=0, sticky='nsew', padx=(0, PAD_MD))
		self._card_demo.grid_columnconfigure(0, weight=1)

		badge_d = ctk.CTkFrame(self._card_demo, fg_color=ORANGE_DIM, corner_radius=6)
		badge_d.grid(row=0, column=0, padx=PAD_LG, pady=(PAD_LG, 0), sticky='w')
		ctk.CTkLabel(
			badge_d, text='  GRATIS  ', font=FONT_LABEL_BOLD, text_color=ORANGE_TEXT
		).pack(padx=4, pady=3)

		ctk.CTkLabel(
			self._card_demo,
			text='🎁  Prueba Gratuita',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).grid(row=1, column=0, padx=PAD_LG, pady=(PAD_SM, 2), sticky='w')

		ctk.CTkLabel(
			self._card_demo,
			text='7 días completos para explorar todo el sistema',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=2, column=0, padx=PAD_LG, pady=(0, PAD_MD), sticky='w')

		ctk.CTkFrame(self._card_demo, height=1, fg_color=BORDER).grid(
			row=3, column=0, sticky='ew', padx=PAD_LG, pady=(0, PAD_MD)
		)

		for i, feat in enumerate(_DEMO_FEATURES):
			ctk.CTkLabel(
				self._card_demo,
				text=feat,
				font=FONT_BODY,
				text_color=TEXT_SECONDARY,
				anchor='w',
			).grid(row=4 + i, column=0, padx=PAD_LG, pady=(0, PAD_XS), sticky='w')

		ctk.CTkFrame(self._card_demo, height=PAD_MD, fg_color='transparent').grid(
			row=8, column=0
		)

		self._btn_start_demo = ctk.CTkButton(
			self._card_demo,
			text='🚀  Comenzar prueba gratuita',
			height=50,
			corner_radius=10,
			font=FONT_BODY_BOLD,
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=2,
			border_color=ORANGE,
			command=self._select_demo,
		)
		self._btn_start_demo.grid(
			row=9, column=0, padx=PAD_LG, pady=(0, PAD_LG), sticky='ew'
		)

		# ── CARD PRO ─────────────────────────────────────────────────────
		self._card_pro = ctk.CTkFrame(
			cards_row,
			fg_color=SURFACE2,
			corner_radius=16,
			border_width=1,
			border_color=BORDER,
		)
		self._card_pro.grid(row=0, column=1, sticky='nsew', padx=(PAD_MD, 0))
		self._card_pro.grid_columnconfigure(0, weight=1)

		badge_p = ctk.CTkFrame(self._card_pro, fg_color=PURPLE_DIM, corner_radius=6)
		badge_p.grid(row=0, column=0, padx=PAD_LG, pady=(PAD_LG, 0), sticky='w')
		ctk.CTkLabel(
			badge_p,
			text='  LICENCIA PRO  ',
			font=FONT_LABEL_BOLD,
			text_color=PURPLE_TEXT,
		).pack(padx=4, pady=3)

		ctk.CTkLabel(
			self._card_pro,
			text='⭐  Ya tengo un código',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).grid(row=1, column=0, padx=PAD_LG, pady=(PAD_SM, 2), sticky='w')

		ctk.CTkLabel(
			self._card_pro,
			text='Ingresá tu código Mensual, Anual o Vitalicio',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=2, column=0, padx=PAD_LG, pady=(0, PAD_MD), sticky='w')

		ctk.CTkFrame(self._card_pro, height=1, fg_color=BORDER).grid(
			row=3, column=0, sticky='ew', padx=PAD_LG, pady=(0, PAD_SM)
		)

		for i, (icon, title, desc) in enumerate(_PRO_FEATURES):
			row_f = ctk.CTkFrame(self._card_pro, fg_color='transparent')
			row_f.grid(row=4 + i, column=0, sticky='ew', padx=PAD_LG, pady=(0, PAD_XS))
			row_f.grid_columnconfigure(1, weight=1)

			ctk.CTkLabel(
				row_f,
				text=icon,
				font=(FONT_FAMILY, 15),
				width=26,
				anchor='w',
			).grid(row=0, column=0, rowspan=2, sticky='n', pady=(2, 0))

			ctk.CTkLabel(
				row_f,
				text=title,
				font=FONT_BODY_BOLD,
				text_color=PURPLE_TEXT,
				anchor='w',
			).grid(row=0, column=1, sticky='w', padx=(PAD_XS, 0))

			ctk.CTkLabel(
				row_f,
				text=desc,
				font=FONT_SMALL,
				text_color=TEXT_MUTED,
				anchor='w',
			).grid(row=1, column=1, sticky='w', padx=(PAD_XS, 0))

		ctk.CTkFrame(self._card_pro, height=1, fg_color=BORDER).grid(
			row=9, column=0, sticky='ew', padx=PAD_LG, pady=(PAD_SM, PAD_SM)
		)

		ctk.CTkLabel(
			self._card_pro,
			text='Código de activación (FULL o VITA)',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
		).grid(row=10, column=0, padx=PAD_LG, pady=(0, PAD_XS), sticky='w')

		self._entry_license = ctk.CTkEntry(
			self._card_pro,
			height=40,
			placeholder_text='TIPO-AAAAMMDD-FIRMA',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._entry_license.grid(
			row=11, column=0, padx=PAD_LG, sticky='ew', pady=(0, PAD_SM)
		)
		self._entry_license.bind('<Return>', lambda e: self._go_next())
		self._entry_license.bind('<FocusIn>', lambda e: self._select_pro())

		self._btn_activate_pro = ctk.CTkButton(
			self._card_pro,
			text='✅  Activar con este código',
			height=50,
			corner_radius=10,
			font=FONT_BODY_BOLD,
			fg_color=SURFACE3,
			hover_color=PURPLE,
			text_color=TEXT_SECONDARY,
			border_width=2,
			border_color=BORDER_ACTIVE,
			command=self._handle_activate_pro,
		)
		self._btn_activate_pro.grid(
			row=12, column=0, padx=PAD_LG, pady=(0, PAD_LG), sticky='ew'
		)

		# ── CLOUD INFO BANNER ────────────────────────────────────────────
		cloud_banner = ctk.CTkFrame(
			scroll,
			fg_color=SURFACE3,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		cloud_banner.pack(fill='x', padx=PAD_XL, pady=(0, PAD_MD))

		ctk.CTkLabel(
			cloud_banner,
			text='☁️  ¿Tenés también un Plan Cloud?',
			font=FONT_BODY_BOLD,
			text_color=ACCENT_TEXT,
		).pack(side='left', padx=(PAD_LG, PAD_XS), pady=PAD_MD)

		ctk.CTkLabel(
			cloud_banner,
			text='El complemento Cloud para backups y reportes web se activa desde Configuración > Licencia una vez dentro del sistema.',
			font=FONT_BODY,
			text_color=TEXT_SECONDARY,
		).pack(side='left', padx=(0, PAD_LG), pady=PAD_MD)

		self._lbl_lic_status = ctk.CTkLabel(
			scroll,
			text='',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
		)
		self._lbl_lic_status.pack(pady=(PAD_SM, 0))

		if self._license_mode == 'DEMO':
			self._select_demo()
		elif self._license_mode == 'PRO':
			self._select_pro()
			if self._license_key:
				self._entry_license.insert(0, self._license_key)

	def _select_demo(self):
		self._license_mode = 'DEMO'
		self._card_demo.configure(border_color=ORANGE, border_width=2)
		self._btn_start_demo.configure(fg_color=ORANGE, text_color='white')
		self._card_pro.configure(border_color=BORDER, border_width=1)
		self._btn_activate_pro.configure(
			fg_color=SURFACE3, text_color=TEXT_SECONDARY, border_color=BORDER_ACTIVE
		)
		self._lbl_lic_status.configure(
			text='✓  Prueba gratuita de 7 días seleccionada', text_color=ORANGE_TEXT
		)

	def _select_pro(self):
		self._license_mode = 'PRO'
		self._card_pro.configure(border_color=PURPLE, border_width=2)
		self._btn_activate_pro.configure(
			fg_color=PURPLE, text_color='white', border_color=PURPLE
		)
		self._card_demo.configure(border_color=BORDER, border_width=1)
		self._btn_start_demo.configure(fg_color=ORANGE_DIM, text_color=ORANGE_TEXT)
		self._lbl_lic_status.configure(
			text='Ingresá tu código y presioná Siguiente', text_color=PURPLE_TEXT
		)
		self._entry_license.focus()

	def _handle_activate_pro(self):
		self._select_pro()
		if self._entry_license.get().strip():
			self._go_next()

	def _validate_step1(self) -> bool:
		if self._license_mode is None:
			self._lbl_lic_status.configure(
				text='⚠  Elegí una opción para continuar', text_color=ORANGE_TEXT
			)
			return False
		if self._license_mode == 'PRO':
			key = self._entry_license.get().strip()
			if not key:
				self._entry_license.configure(border_color=RED)
				self._lbl_lic_status.configure(
					text='⚠  Ingresá el código de licencia Pro', text_color=RED_TEXT
				)
				self._entry_license.focus()
				return False

			if key.upper().startswith('CLOUD-'):
				self._entry_license.configure(border_color=ORANGE)
				self._lbl_lic_status.configure(
					text='⚠ Este es un código Cloud. Aquí debes activar el sistema base (o usar la Demo).\nEl Plan Cloud se activa después, desde el menú Configuración.', text_color=ORANGE_TEXT
				)
				self._entry_license.focus()
				return False

			success, msg = self.license_ctrl.validate_license_format(key)
			if not success:
				self._entry_license.configure(border_color=RED)
				self._lbl_lic_status.configure(
					text=f'⚠  {msg}', text_color=RED_TEXT
				)
				self._entry_license.focus()
				return False

			self._entry_license.configure(border_color=BORDER_ACTIVE)
			self._lbl_lic_status.configure(text='✓  Licencia válida', text_color=GREEN_TEXT)	
			self._license_key = key
		return True

	# ═══════════════════════════════════════════════════════════════════════
	# PASO 2 — DATOS DEL NEGOCIO
	# ═══════════════════════════════════════════════════════════════════════

	def _build_step2(self):
		scroll = ctk.CTkScrollableFrame(
			self._content,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		scroll.grid(row=0, column=0, sticky='nsew')
		scroll.grid_columnconfigure(0, weight=1)

		card = ctk.CTkFrame(
			scroll,
			fg_color=SURFACE2,
			corner_radius=16,
			border_width=1,
			border_color=BORDER,
		)
		card.grid(row=0, column=0, padx=PAD_XL, pady=PAD_XL, sticky='ew')
		card.grid_columnconfigure(0, weight=1)
		card.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(
			card,
			text='🏪  Tu Negocio',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).grid(
			row=0,
			column=0,
			columnspan=2,
			padx=PAD_XL,
			pady=(PAD_XL, PAD_XS),
			sticky='w',
		)

		ctk.CTkLabel(
			card,
			text='Personalizá la identidad de tu punto de venta.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=1, column=0, columnspan=2, padx=PAD_XL, pady=(0, PAD_LG), sticky='w')

		# ── Logo ──
		logo_frame = ctk.CTkFrame(card, fg_color=SURFACE3, corner_radius=12)
		logo_frame.grid(
			row=2, column=0, columnspan=2, padx=PAD_XL, pady=(0, PAD_LG), sticky='ew'
		)
		logo_frame.grid_columnconfigure(1, weight=1)

		self._lbl_logo_preview = ctk.CTkLabel(
			logo_frame,
			text='📷\nSin logo',
			width=90,
			height=90,
			fg_color=SURFACE4,
			corner_radius=10,
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		)
		self._lbl_logo_preview.grid(
			row=0, column=0, rowspan=3, padx=PAD_MD, pady=PAD_MD
		)
		self._update_logo_preview()

		ctk.CTkLabel(
			logo_frame,
			text='Logo del Negocio',
			font=FONT_BODY_BOLD,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).grid(row=0, column=1, sticky='sw', padx=(0, PAD_MD), pady=(PAD_MD, 0))

		ctk.CTkLabel(
			logo_frame,
			text='Aparece en tickets y reportes. PNG o JPG recomendado.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=1, column=1, sticky='w', padx=(0, PAD_MD))

		logo_btns = ctk.CTkFrame(logo_frame, fg_color='transparent')
		logo_btns.grid(
			row=2, column=1, sticky='w', padx=(0, PAD_MD), pady=(PAD_XS, PAD_MD)
		)

		ctk.CTkButton(
			logo_btns,
			text='📁  Seleccionar imagen',
			height=30,
			font=FONT_LABEL_BOLD,
			corner_radius=8,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			command=self._pick_logo,
		).pack(side='left', padx=(0, PAD_XS))

		ctk.CTkButton(
			logo_btns,
			text='✕ Quitar',
			height=30,
			font=FONT_LABEL,
			corner_radius=8,
			fg_color='transparent',
			hover_color=SURFACE4,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			command=self._remove_logo,
		).pack(side='left')

		# ── Nombre del comercio (full width) ──
		make_form_label(card, 'NOMBRE DEL COMERCIO', required=True)[0].grid(
			row=3, column=0, columnspan=2, sticky='w', padx=PAD_XL, pady=(0, PAD_XS)
		)
		self._e_store = ctk.CTkEntry(
			card,
			placeholder_text='Ej: Kiosco Carlitos, Farmacia San Martín…',
			height=40,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_store.grid(
			row=4, column=0, columnspan=2, sticky='ew', padx=PAD_XL, pady=(0, PAD_MD)
		)
		if self._d_store:
			self._e_store.insert(0, self._d_store)

		# ── Teléfono | Dirección ──
		make_form_label(card, 'TELÉFONO / WHATSAPP')[0].grid(
			row=5, column=0, sticky='w', padx=(PAD_XL, PAD_MD), pady=(0, PAD_XS)
		)
		self._e_phone = ctk.CTkEntry(
			card,
			placeholder_text='Ej: +54 9 388 4000000',
			height=38,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_phone.grid(
			row=6, column=0, sticky='ew', padx=(PAD_XL, PAD_MD), pady=(0, PAD_MD)
		)
		if self._d_phone:
			self._e_phone.insert(0, self._d_phone)

		make_form_label(card, 'DIRECCIÓN')[0].grid(
			row=5, column=1, sticky='w', padx=(PAD_MD, PAD_XL), pady=(0, PAD_XS)
		)
		self._e_address = ctk.CTkEntry(
			card,
			placeholder_text='Ej: Av. Siempre Viva 742',
			height=38,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_address.grid(
			row=6, column=1, sticky='ew', padx=(PAD_MD, PAD_XL), pady=(0, PAD_MD)
		)
		if self._d_address:
			self._e_address.insert(0, self._d_address)

		# ── Separador ──
		ctk.CTkFrame(card, height=1, fg_color=BORDER).grid(
			row=7, column=0, columnspan=2, sticky='ew', padx=PAD_XL, pady=(0, PAD_MD)
		)

		# ── Símbolo de moneda (botones) ──
		make_form_label(card, 'MONEDA')[0].grid(
			row=8, column=0, columnspan=2, sticky='w', padx=PAD_XL, pady=(0, PAD_XS)
		)
		sym_row = ctk.CTkFrame(card, fg_color='transparent')
		sym_row.grid(
			row=9, column=0, columnspan=2, sticky='w', padx=PAD_XL, pady=(0, PAD_MD)
		)

		self._sym_var = (
			self._d_currency if self._d_currency in _CURRENCY_SYMBOLS else '$'
		)
		self._sym_btns = {}

		for sym in _CURRENCY_SYMBOLS:
			active = sym == self._sym_var
			btn = ctk.CTkButton(
				sym_row,
				text=sym,
				width=54,
				height=40,
				font=FONT_BODY_BOLD,
				fg_color=ACCENT_DIM if active else SURFACE3,
				hover_color=ACCENT if not active else ACCENT_DIM,
				text_color=ACCENT_TEXT if active else TEXT_SECONDARY,
				border_width=2 if active else 1,
				border_color=ACCENT if active else BORDER,
				corner_radius=8,
				command=lambda s=sym: self._pick_currency_sym(s),
			)
			btn.pack(side='left', padx=(0, PAD_XS))
			self._sym_btns[sym] = btn

		ctk.CTkLabel(
			sym_row, text='Otro:', font=FONT_LABEL, text_color=TEXT_MUTED
		).pack(side='left', padx=(PAD_SM, PAD_XS))
		self._e_custom_sym = ctk.CTkEntry(
			sym_row,
			width=58,
			height=40,
			placeholder_text='Bs.',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_custom_sym.pack(side='left', padx=(0, PAD_XS))
		if self._d_currency not in _CURRENCY_SYMBOLS:
			self._e_custom_sym.insert(0, self._d_currency)

		ctk.CTkButton(
			sym_row,
			text='↵',
			width=36,
			height=40,
			font=FONT_BODY_BOLD,
			corner_radius=8,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			command=self._use_custom_sym,
		).pack(side='left')

		# ── Decimales | IVA ──
		make_form_label(card, 'DECIMALES EN PRECIOS')[0].grid(
			row=10, column=0, sticky='w', padx=(PAD_XL, PAD_MD), pady=(0, PAD_XS)
		)
		self._seg_decimals = ctk.CTkSegmentedButton(
			card,
			values=['0  (enteros)', '2  (centavos)'],
			font=FONT_BODY,
			height=38,
			fg_color=SURFACE3,
			selected_color=ACCENT,
			selected_hover_color=ACCENT,
			unselected_color=SURFACE3,
			unselected_hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			text_color_disabled=TEXT_MUTED,
			command=lambda v: self._update_currency_preview(),
		)
		self._seg_decimals.grid(
			row=11, column=0, sticky='ew', padx=(PAD_XL, PAD_MD), pady=(0, PAD_MD)
		)
		self._seg_decimals.set(self._d_decimals)

		make_form_label(card, 'IMPUESTO / IVA (%)')[0].grid(
			row=10, column=1, sticky='w', padx=(PAD_MD, PAD_XL), pady=(0, PAD_XS)
		)
		self._e_tax = ctk.CTkEntry(
			card,
			placeholder_text='Ej: 21',
			height=38,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_tax.grid(
			row=11, column=1, sticky='ew', padx=(PAD_MD, PAD_XL), pady=(0, PAD_MD)
		)
		self._e_tax.insert(0, self._d_tax)

		# ── Preview de moneda ──
		preview_frame = ctk.CTkFrame(card, fg_color=SURFACE3, corner_radius=12)
		preview_frame.grid(
			row=12, column=0, columnspan=2, padx=PAD_XL, pady=(0, PAD_MD), sticky='ew'
		)

		ctk.CTkLabel(
			preview_frame,
			text='Vista previa de precios',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
		).pack(pady=(PAD_SM, 0))

		self._lbl_currency_preview = ctk.CTkLabel(
			preview_frame,
			text='',
			font=(FONT_FAMILY, 26, 'bold'),
			text_color=ACCENT_TEXT,
		)
		self._lbl_currency_preview.pack(pady=(0, PAD_SM))
		self._update_currency_preview()

		# ── Separador ──
		ctk.CTkFrame(card, height=1, fg_color=BORDER).grid(
			row=13, column=0, columnspan=2, sticky='ew', padx=PAD_XL, pady=(0, PAD_XS)
		)

		# ── Configuración avanzada (colapsable) ──
		self._adv_expanded = False
		self._btn_toggle_adv = ctk.CTkButton(
			card,
			text='⚙  Configuración avanzada  ▶',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			anchor='w',
			height=32,
			corner_radius=6,
			font=FONT_LABEL_BOLD,
			command=self._toggle_advanced,
		)
		self._btn_toggle_adv.grid(
			row=14,
			column=0,
			columnspan=2,
			sticky='w',
			padx=PAD_XL,
			pady=(PAD_XS, PAD_MD),
		)

		self._adv_container = ctk.CTkFrame(card, fg_color='transparent')
		self._adv_container.grid_columnconfigure(0, weight=1)

		make_form_label(self._adv_container, 'CARPETA DE REPORTES Y EXPORTACIONES')[
			0
		].grid(row=0, column=0, sticky='w', padx=0, pady=(0, PAD_XS))
		ctk.CTkLabel(
			self._adv_container,
			text='Todos los PDFs, CSV y Excel generados se guardarán aquí.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=1, column=0, sticky='w', pady=(0, PAD_XS))

		self._lbl_reports_path = ctk.CTkLabel(
			self._adv_container,
			text=self._d_reports_path or get_reports_path(),
			font=FONT_MONO,
			text_color=TEXT_SECONDARY,
			anchor='w',
			wraplength=420,
			justify='left',
		)
		self._lbl_reports_path.grid(row=2, column=0, sticky='ew', pady=(0, PAD_XS))

		adv_btns = ctk.CTkFrame(self._adv_container, fg_color='transparent')
		adv_btns.grid(row=3, column=0, sticky='w', pady=(0, PAD_MD))

		ctk.CTkButton(
			adv_btns,
			text='📁  Elegir Carpeta',
			height=32,
			font=FONT_LABEL_BOLD,
			corner_radius=8,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			command=self._pick_reports_folder,
		).pack(side='left', padx=(0, PAD_SM))

		ctk.CTkButton(
			adv_btns,
			text='↺ Restaurar',
			height=32,
			font=FONT_LABEL,
			corner_radius=8,
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			command=self._reset_reports_folder,
		).pack(side='left')

		self._e_store.focus()

	def _toggle_advanced(self):
		if self._adv_expanded:
			self._adv_container.grid_remove()
			self._btn_toggle_adv.configure(text='⚙  Configuración avanzada  ▶')
			self._adv_expanded = False
		else:
			self._adv_container.grid(
				row=15,
				column=0,
				columnspan=2,
				sticky='ew',
				padx=PAD_XL,
				pady=(0, PAD_LG),
			)
			self._btn_toggle_adv.configure(text='⚙  Configuración avanzada  ▼')
			self._adv_expanded = True

	def _pick_currency_sym(self, sym: str):
		self._sym_var = sym
		self._update_currency_preview()
		for s, btn in self._sym_btns.items():
			active = s == sym
			btn.configure(
				fg_color=ACCENT_DIM if active else SURFACE3,
				hover_color=ACCENT if not active else ACCENT_DIM,
				text_color=ACCENT_TEXT if active else TEXT_SECONDARY,
				border_width=2 if active else 1,
				border_color=ACCENT if active else BORDER,
			)

	def _use_custom_sym(self):
		val = self._e_custom_sym.get().strip()
		if not val:
			return
		self._sym_var = val
		for btn in self._sym_btns.values():
			btn.configure(
				fg_color=SURFACE3,
				hover_color=SURFACE4,
				text_color=TEXT_SECONDARY,
				border_width=1,
				border_color=BORDER,
			)
		self._update_currency_preview()

	def _update_currency_preview(self):
		if (
			not hasattr(self, '_lbl_currency_preview')
			or not self._lbl_currency_preview.winfo_exists()
		):
			return
		sym = getattr(self, '_sym_var', '$') or '$'
		dec = (
			2
			if hasattr(self, '_seg_decimals') and '2' in self._seg_decimals.get()
			else 0
		)
		sample = 1250.5 if dec > 0 else 1250
		if dec == 0:
			num = f'{int(sample):,}'.replace(',', '.')
		else:
			num = f'{sample:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
		self._lbl_currency_preview.configure(text=f'{sym}{num}')

	def _pick_logo(self):
		from tkinter import filedialog

		path = filedialog.askopenfilename(
			title='Seleccionar logo',
			filetypes=[('Imágenes', '*.png *.jpg *.jpeg *.bmp *.webp')],
		)
		if path:
			self._d_logo_path = path
			self._update_logo_preview()

	def _remove_logo(self):
		self._d_logo_path = None
		if hasattr(self, '_lbl_logo_preview') and self._lbl_logo_preview.winfo_exists():
			self._lbl_logo_preview.configure(image=None, text='📷\nSin logo')

	def _update_logo_preview(self):
		if not self._d_logo_path:
			return
		try:
			from PIL import Image

			img = Image.open(self._d_logo_path)
			img.thumbnail((86, 86))
			ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(86, 86))
			self._lbl_logo_preview.configure(image=ctk_img, text='')
		except Exception as e:
			logger.error('Error cargando preview de logo: %s', e)

	def _pick_reports_folder(self):
		from tkinter import filedialog

		path = filedialog.askdirectory(
			title='Elegir carpeta de reportes',
			initialdir=self._d_reports_path or get_reports_path(),
		)
		if path:
			self._d_reports_path = path
			self._lbl_reports_path.configure(text=path)

	def _reset_reports_folder(self):
		self._d_reports_path = ''
		self._lbl_reports_path.configure(text=get_reports_path())

	def _validate_step2(self) -> bool:
		store = self._e_store.get().strip()
		if not store:
			self._e_store.configure(border_color=RED)
			self._e_store.focus()
			CTkMessagebox(
				title='Campo requerido',
				message='El nombre del comercio es obligatorio.',
				icon='cancel',
			)
			return False
		self._e_store.configure(border_color=BORDER_ACTIVE)

		tax_str = self._e_tax.get().strip().replace(',', '.')
		try:
			if float(tax_str) < 0:
				raise ValueError
		except ValueError:
			self._e_tax.configure(border_color=RED)
			self._e_tax.focus()
			CTkMessagebox(
				title='Valor inválido',
				message='El impuesto debe ser un número ≥ 0 (Ej: 21).',
				icon='cancel',
			)
			return False
		self._e_tax.configure(border_color=BORDER_ACTIVE)

		self._d_store = store
		self._d_address = self._e_address.get().strip()
		self._d_phone = self._e_phone.get().strip()
		self._d_currency = getattr(self, '_sym_var', '$') or '$'
		self._d_decimals = self._seg_decimals.get()
		self._d_tax = tax_str
		return True

	# ═══════════════════════════════════════════════════════════════════════
	# PASO 3 — USUARIO ADMINISTRADOR
	# ═══════════════════════════════════════════════════════════════════════

	def _build_step3(self):
		scroll = ctk.CTkScrollableFrame(
			self._content,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		scroll.grid(row=0, column=0, sticky='nsew')
		scroll.grid_columnconfigure(0, weight=1)

		card = ctk.CTkFrame(
			scroll,
			fg_color=SURFACE2,
			corner_radius=16,
			border_width=1,
			border_color=BORDER,
		)
		card.grid(row=0, column=0, padx=PAD_XL, pady=PAD_XL, sticky='ew')
		card.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			card,
			text='👤  Tu Usuario Administrador',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).grid(row=0, column=0, padx=PAD_XL, pady=(PAD_XL, PAD_XS), sticky='w')

		ctk.CTkLabel(
			card,
			text='Estas credenciales te permiten acceder y administrar todo el sistema.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=1, column=0, padx=PAD_XL, pady=(0, PAD_LG), sticky='w')

		form = ctk.CTkFrame(card, fg_color='transparent')
		form.grid(row=2, column=0, sticky='ew', padx=PAD_XL, pady=(0, PAD_XL))
		form.grid_columnconfigure(0, weight=1)

		# ── Usuario ──
		make_form_label(form, 'NOMBRE DE USUARIO', required=True)[0].pack(
			anchor='w', pady=(0, 2)
		)
		self._e_username = ctk.CTkEntry(
			form,
			placeholder_text='Ej: admin, carlos, gerente',
			height=42,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_username.pack(fill='x')
		if self._d_username:
			self._e_username.insert(0, self._d_username)
		self._err_username = ctk.CTkLabel(
			form, text='', font=FONT_SMALL, text_color=RED_TEXT, anchor='w'
		)
		self._err_username.pack(anchor='w', pady=(2, PAD_MD))

		# ── Contraseña ──
		make_form_label(form, 'CONTRASEÑA', required=True)[0].pack(
			anchor='w', pady=(0, 2)
		)
		self._e_pass = ctk.CTkEntry(
			form,
			placeholder_text='Mínimo 6 caracteres',
			show='*',
			height=42,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_pass.pack(fill='x')
		self._e_pass.bind('<KeyRelease>', self._update_password_strength)
		if self._d_password:
			self._e_pass.insert(0, self._d_password)

		strength_row = ctk.CTkFrame(form, fg_color='transparent')
		strength_row.pack(fill='x', pady=(4, 0))
		strength_row.grid_columnconfigure(0, weight=1)

		self._strength_bar = ctk.CTkProgressBar(
			strength_row,
			height=4,
			corner_radius=2,
			fg_color=SURFACE3,
			progress_color=SURFACE4,
		)
		self._strength_bar.grid(row=0, column=0, sticky='ew', padx=(0, PAD_SM))
		self._strength_bar.set(0)

		self._strength_lbl = ctk.CTkLabel(
			strength_row,
			text='',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			width=72,
			anchor='w',
		)
		self._strength_lbl.grid(row=0, column=1)

		self._err_pass = ctk.CTkLabel(
			form, text='', font=FONT_SMALL, text_color=RED_TEXT, anchor='w'
		)
		self._err_pass.pack(anchor='w', pady=(2, PAD_MD))

		# ── Confirmar contraseña ──
		make_form_label(form, 'CONFIRMAR CONTRASEÑA', required=True)[0].pack(
			anchor='w', pady=(0, 2)
		)
		self._e_pass2 = ctk.CTkEntry(
			form,
			placeholder_text='Repetí la contraseña',
			show='*',
			height=42,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_pass2.pack(fill='x')
		self._e_pass2.bind('<Return>', lambda e: self._go_next())
		if self._d_password:
			self._e_pass2.insert(0, self._d_password)
		self._err_pass2 = ctk.CTkLabel(
			form, text='', font=FONT_SMALL, text_color=RED_TEXT, anchor='w'
		)
		self._err_pass2.pack(anchor='w', pady=(2, PAD_SM))

		# ── Mostrar contraseñas ──
		self._chk_show = ctk.CTkCheckBox(
			form,
			text='Mostrar contraseñas y PIN',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			command=self._toggle_pass,
		)
		self._chk_show.pack(anchor='w', pady=(0, PAD_LG))

		ctk.CTkFrame(form, height=1, fg_color=BORDER).pack(fill='x', pady=(0, PAD_MD))

		# ── PIN al final ──
		pin_box = ctk.CTkFrame(
			form,
			fg_color=ORANGE_DIM,
			corner_radius=10,
			border_width=1,
			border_color=ORANGE,
		)
		pin_box.pack(fill='x', pady=(0, PAD_SM))

		pin_header = ctk.CTkFrame(pin_box, fg_color='transparent')
		pin_header.pack(fill='x', padx=PAD_MD, pady=(PAD_MD, PAD_XS))
		ctk.CTkLabel(
			pin_header,
			text='🔐  PIN DE RECUPERACIÓN',
			font=FONT_HEADING,
			text_color=ORANGE_TEXT,
			anchor='w',
		).pack(side='left')
		ctk.CTkLabel(
			pin_header,
			text='4 dígitos',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(side='right')

		ctk.CTkLabel(
			pin_box,
			text='Usalo para recuperar el acceso si olvidás tu contraseña. ¡Guardalo en un lugar seguro!',
			font=FONT_SMALL,
			text_color=ORANGE_TEXT,
			anchor='w',
			justify='left',
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		self._e_pin = ctk.CTkEntry(
			pin_box,
			placeholder_text='Ej: 1234',
			show='*',
			height=42,
			fg_color=SURFACE3,
			border_color=ORANGE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_pin.pack(fill='x', padx=PAD_MD, pady=(0, PAD_XS))
		self._e_pin.bind('<Return>', lambda e: self._go_next())
		if self._d_pin:
			self._e_pin.insert(0, self._d_pin)

		self._err_pin = ctk.CTkLabel(
			pin_box, text='', font=FONT_SMALL, text_color=RED_TEXT, anchor='w'
		)
		self._err_pin.pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		self._e_username.focus()
		if self._d_password:
			self._update_password_strength()

	def _update_password_strength(self, event=None):
		if not hasattr(self, '_strength_bar') or not self._strength_bar.winfo_exists():
			return
		pwd = self._e_pass.get()
		if not pwd:
			self._strength_bar.set(0)
			self._strength_lbl.configure(text='')
			return
		score = 0
		if len(pwd) >= 6:
			score += 1
		if len(pwd) >= 10:
			score += 1
		if any(c.isupper() for c in pwd):
			score += 1
		if any(c.isdigit() for c in pwd):
			score += 1
		if any(c in '!@#$%^&*-_' for c in pwd):
			score += 1
		level = min(score, 4)
		colors = [SURFACE4, RED, ORANGE, ORANGE, GREEN]
		labels = ['', 'Muy débil', 'Débil', 'Aceptable', 'Fuerte']
		tcolors = [TEXT_MUTED, RED_TEXT, ORANGE_TEXT, ORANGE_TEXT, GREEN_TEXT]
		self._strength_bar.configure(progress_color=colors[level])
		self._strength_bar.set(level / 4)
		self._strength_lbl.configure(text=labels[level], text_color=tcolors[level])

	def _toggle_pass(self):
		show = '' if self._chk_show.get() else '*'
		for e in (self._e_pin, self._e_pass, self._e_pass2):
			e.configure(show=show)

	def _show_field_error(self, entry, err_label, msg: str):
		entry.configure(border_color=RED)
		err_label.configure(text=f'⚠  {msg}')
		entry.focus()

	def _clear_field_errors(self):
		pairs = [
			(self._e_username, self._err_username),
			(self._e_pass, self._err_pass),
			(self._e_pass2, self._err_pass2),
			(self._e_pin, self._err_pin),
		]
		for entry, lbl in pairs:
			entry.configure(border_color=BORDER_ACTIVE)
			lbl.configure(text='')

	def _validate_step3(self) -> bool:
		self._clear_field_errors()

		username = self._e_username.get().strip()
		if len(username) < 3 or not re.match(r'^[a-zA-Z0-9_]+$', username):
			self._show_field_error(
				self._e_username,
				self._err_username,
				'Mínimo 3 caracteres, solo letras, números y guión bajo.',
			)
			return False

		password = self._e_pass.get()
		if len(password) < 6:
			self._show_field_error(self._e_pass, self._err_pass, 'Mínimo 6 caracteres.')
			return False

		if password != self._e_pass2.get():
			self._show_field_error(
				self._e_pass2, self._err_pass2, 'Las contraseñas no coinciden.'
			)
			return False

		pin = self._e_pin.get().strip()
		if len(pin) != 4 or not pin.isdigit():
			self._show_field_error(
				self._e_pin, self._err_pin, 'Debe ser exactamente 4 números.'
			)
			return False

		self._d_username = username
		self._d_password = password
		self._d_pin = pin
		return True

	# ═══════════════════════════════════════════════════════════════════════
	# FINALIZAR
	# ═══════════════════════════════════════════════════════════════════════

	def _finish(self):
		"""Finaliza el wizard para modo Terminal Principal."""
		if self._busy:
			return
		if not self._validate_step3():
			return

		self._busy = True
		self._btn_next.configure(state='disabled', text='Configurando…')
		self._btn_back.configure(state='disabled')
		self.update_idletasks()

		import threading

		def _run():
			if self._license_mode == 'DEMO':
				success, msg = self.license_ctrl.activate_demo()
			else:
				success, msg = self.license_ctrl.activate_license(self._license_key)

			if not success:
				if self.winfo_exists():
					self.after(0, lambda: self._on_finish_license_failed(msg))
				return

			try:
				self._setup_database()
				self._save_settings()
				if self.winfo_exists():
					self.after(0, lambda m=msg: self._on_finish_done(True, m))
			except Exception as e:
				logger.error('Error al crear la base de datos: %s', e, exc_info=True)
				try:
					lf = self.license_ctrl.license_file
					if os.path.exists(lf):
						os.remove(lf)
				except Exception:
					pass
				if self.winfo_exists():
					self.after(0, lambda err=str(e): self._on_finish_done(False, err))

		threading.Thread(target=_run, daemon=True).start()

	def _on_finish_license_failed(self, msg: str):
		if not self.winfo_exists():
			return
		CTkMessagebox(title='Licencia rechazada', message=msg, icon='cancel')
		self._busy = False
		self._btn_next.configure(state='normal', text=_STEP_NEXT_LABELS[4])
		self._btn_back.configure(state='normal')

	def _on_finish_done(self, success: bool, msg: str):
		if not self.winfo_exists():
			return
		if success:
			CTkMessagebox(
				title='¡Todo listo!',
				message=f'Tu sistema CloudPOS está configurado.\n¡Bienvenido, {self._d_username}!',
				icon='check',
			).get()
			self.winfo_toplevel().after(100, self.on_complete_callback)
		else:
			CTkMessagebox(
				title='Error Fatal',
				message=f'Falló la creación de la base de datos:\n{msg}',
				icon='cancel',
			)
			self._busy = False
			self._btn_next.configure(state='normal', text=_STEP_NEXT_LABELS[4])
			self._btn_back.configure(state='normal')

	def _setup_database(self):
		from utils.config import get_engine

		engine = get_engine()
		Base.metadata.create_all(engine)
		Session = sessionmaker(bind=engine)
		with Session() as session:
			tenant = Tenant(name=self._d_store)
			session.add(tenant)
			session.flush()

			branch = Branch(name='Sede Principal', tenant_id=tenant.id)
			session.add(branch)
			session.flush()

			session.add(
				Warehouse(
					name='Depósito General', branch_id=branch.id, tenant_id=tenant.id
				)
			)

			pwd_hash = bcrypt.hashpw(
				self._d_password.encode('utf-8'), bcrypt.gensalt()
			).decode('utf-8')
			pin_hash = bcrypt.hashpw(
				self._d_pin.encode('utf-8'), bcrypt.gensalt()
			).decode('utf-8')

			session.add(
				User(
					tenant_id=tenant.id,
					username=self._d_username,
					password_hash=pwd_hash,
					recovery_pin_hash=pin_hash,
					role='admin',
					is_active=True,
				)
			)
			session.commit()

	def _save_settings(self):
		cfg = _cfg_load()

		logo_final_path = ''
		if self._d_logo_path and os.path.exists(self._d_logo_path):
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
				ext = os.path.splitext(self._d_logo_path)[1].lower()
				dest = os.path.join(dest_dir, f'logo{ext}')
				shutil.copy2(self._d_logo_path, dest)
				logo_final_path = dest
			except Exception as e:
				logger.error('Error al copiar logo: %s', e)

		cfg['terminal_mode'] = 'primary'
		cfg['db_remote_path'] = ''
		cfg['company_name'] = self._d_store
		cfg['company_address'] = self._d_address
		cfg['company_phone'] = self._d_phone
		cfg['company_logo_path'] = logo_final_path
		cfg['currency_symbol'] = self._d_currency
		cfg['currency_decimals'] = 2 if '2' in self._d_decimals else 0
		cfg['tax_rate'] = float(self._d_tax) if self._d_tax else 0.0
		cfg['reports_path'] = self._d_reports_path
		_cfg_save(cfg)

	# ═══════════════════════════════════════════════════════════════════════
	# PASO 1 — SELECCIÓN DE TERMINAL  (nuevo primer paso)
	# ═══════════════════════════════════════════════════════════════════════

	def _build_step_terminal(self):
		scroll = ctk.CTkScrollableFrame(
			self._content,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		scroll.grid(row=0, column=0, sticky='nsew')
		scroll.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			scroll,
			text='¿Cómo funciona esta terminal?',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
		).pack(pady=(PAD_XL, PAD_XS))

		ctk.CTkLabel(
			scroll,
			text='Definí el rol de esta PC. Podés tener una Terminal Principal y múltiples cajeros.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
		).pack(pady=(0, PAD_XL))

		cards_row = ctk.CTkFrame(scroll, fg_color='transparent')
		cards_row.pack(fill='x', padx=PAD_XL, pady=(0, PAD_MD))
		cards_row.grid_columnconfigure(0, weight=1)
		cards_row.grid_columnconfigure(1, weight=1)

		# ── Card Terminal Principal ───────────────────────────────────────
		self._card_primary = ctk.CTkFrame(
			cards_row,
			fg_color=SURFACE2,
			corner_radius=16,
			border_width=1,
			border_color=BORDER,
		)
		self._card_primary.grid(row=0, column=0, sticky='nsew', padx=(0, PAD_MD))
		self._card_primary.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			self._card_primary,
			text='🖥️',
			font=(FONT_FAMILY, 34),
			anchor='w',
		).grid(row=0, column=0, padx=PAD_LG, pady=(PAD_LG, 0), sticky='w')

		ctk.CTkLabel(
			self._card_primary,
			text='Terminal Principal',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).grid(row=1, column=0, padx=PAD_LG, pady=(PAD_SM, 2), sticky='w')

		ctk.CTkLabel(
			self._card_primary,
			text='La base de datos vive en esta PC.\nBackup y sync a la nube incluidos.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			anchor='w',
			justify='left',
			wraplength=210,
		).grid(row=2, column=0, padx=PAD_LG, pady=(0, PAD_MD), sticky='w')

		for i, feat in enumerate(
			[
				'✓  Gestión completa del negocio',
				'✓  Reportes y estadísticas',
				'✓  Backup automático diario',
				'✓  Sync a la nube (plan cloud)',
			]
		):
			ctk.CTkLabel(
				self._card_primary,
				text=feat,
				font=FONT_BODY,
				text_color=TEXT_SECONDARY,
				anchor='w',
			).grid(row=3 + i, column=0, padx=PAD_LG, pady=(0, PAD_XS), sticky='w')

		ctk.CTkFrame(self._card_primary, height=PAD_MD, fg_color='transparent').grid(
			row=7, column=0
		)

		self._btn_sel_primary = ctk.CTkButton(
			self._card_primary,
			text='🖥️  Usar como Terminal Principal',
			height=46,
			corner_radius=10,
			font=FONT_BODY_BOLD,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=2,
			border_color=ACCENT,
			command=self._select_primary_terminal,
		)
		self._btn_sel_primary.grid(
			row=8, column=0, padx=PAD_LG, pady=(0, PAD_LG), sticky='ew'
		)

		# ── Card Terminal Cajero ──────────────────────────────────────────
		self._card_cashier = ctk.CTkFrame(
			cards_row,
			fg_color=SURFACE2,
			corner_radius=16,
			border_width=1,
			border_color=BORDER,
		)
		self._card_cashier.grid(row=0, column=1, sticky='nsew', padx=(PAD_MD, 0))
		self._card_cashier.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			self._card_cashier,
			text='🔗',
			font=(FONT_FAMILY, 34),
			anchor='w',
		).grid(row=0, column=0, padx=PAD_LG, pady=(PAD_LG, 0), sticky='w')

		ctk.CTkLabel(
			self._card_cashier,
			text='Terminal Cajero',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).grid(row=1, column=0, padx=PAD_LG, pady=(PAD_SM, 2), sticky='w')

		ctk.CTkLabel(
			self._card_cashier,
			text='Se conecta a la base de datos\nde la Terminal Principal por red local.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			anchor='w',
			justify='left',
			wraplength=210,
		).grid(row=2, column=0, padx=PAD_LG, pady=(0, PAD_MD), sticky='w')

		for i, (feat, ok) in enumerate(
			[
				('✓  Ventas y cobros', True),
				('✓  Consulta de precios y stock', True),
				('✓  Historial del turno', True),
				('✗  Sin reportes ni backup', False),
			]
		):
			ctk.CTkLabel(
				self._card_cashier,
				text=feat,
				font=FONT_BODY,
				text_color=TEXT_SECONDARY if ok else TEXT_MUTED,
				anchor='w',
			).grid(row=3 + i, column=0, padx=PAD_LG, pady=(0, PAD_XS), sticky='w')

		ctk.CTkFrame(self._card_cashier, height=1, fg_color=BORDER).grid(
			row=7, column=0, sticky='ew', padx=PAD_LG, pady=(PAD_SM, PAD_SM)
		)

		ctk.CTkLabel(
			self._card_cashier,
			text='RUTA A LA BASE DE DATOS',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
		).grid(row=8, column=0, padx=PAD_LG, pady=(0, 2), sticky='w')

		ctk.CTkLabel(
			self._card_cashier,
			text='Ruta al pos_system.db en la Terminal Principal (puede ser carpeta de red).',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			anchor='w',
			justify='left',
			wraplength=220,
		).grid(row=9, column=0, padx=PAD_LG, pady=(0, PAD_XS), sticky='w')

		path_row = ctk.CTkFrame(self._card_cashier, fg_color='transparent')
		path_row.grid(row=10, column=0, sticky='ew', padx=PAD_LG, pady=(0, PAD_SM))
		path_row.grid_columnconfigure(0, weight=1)

		self._entry_cashier_path = ctk.CTkEntry(
			path_row,
			placeholder_text=r'\\PC-PRINCIPAL\POS\pos_system.db',
			height=36,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_SMALL,
		)
		self._entry_cashier_path.grid(row=0, column=0, sticky='ew', padx=(0, PAD_XS))
		if self._cashier_db_path:
			self._entry_cashier_path.insert(0, self._cashier_db_path)
		self._entry_cashier_path.bind(
			'<FocusIn>', lambda e: self._select_cashier_terminal()
		)

		ctk.CTkButton(
			path_row,
			text='📁',
			width=36,
			height=36,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			corner_radius=6,
			font=FONT_BODY_BOLD,
			command=self._browse_cashier_db,
		).grid(row=0, column=1)

		self._btn_sel_cashier = ctk.CTkButton(
			self._card_cashier,
			text='🔗  Usar como Terminal Cajero',
			height=46,
			corner_radius=10,
			font=FONT_BODY_BOLD,
			fg_color=SURFACE3,
			hover_color=GREEN,
			text_color=TEXT_SECONDARY,
			border_width=2,
			border_color=BORDER_ACTIVE,
			command=self._select_cashier_terminal,
		)
		self._btn_sel_cashier.grid(
			row=11, column=0, padx=PAD_LG, pady=(0, PAD_LG), sticky='ew'
		)

		self._lbl_terminal_status = ctk.CTkLabel(
			scroll,
			text='',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
		)
		self._lbl_terminal_status.pack(pady=(PAD_SM, 0))

		# Restaurar selección previa
		if self._terminal_mode_sel == 'cashier':
			self._select_cashier_terminal()
		else:
			self._select_primary_terminal()

	def _select_primary_terminal(self):
		self._terminal_mode_sel = 'primary'
		self._card_primary.configure(border_color=ACCENT, border_width=2)
		self._btn_sel_primary.configure(fg_color=ACCENT, text_color='white')
		self._card_cashier.configure(border_color=BORDER, border_width=1)
		self._btn_sel_cashier.configure(
			fg_color=SURFACE3, text_color=TEXT_SECONDARY, border_color=BORDER_ACTIVE
		)
		self._lbl_terminal_status.configure(
			text='✓  Terminal Principal seleccionada', text_color=ACCENT_TEXT
		)
		self._btn_next.configure(
			text=_STEP_NEXT_LABELS[1],
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_color=ACCENT,
		)

	def _select_cashier_terminal(self):
		self._terminal_mode_sel = 'cashier'
		self._card_cashier.configure(border_color=GREEN, border_width=2)
		self._btn_sel_cashier.configure(
			fg_color=GREEN, text_color='white', border_color=GREEN
		)
		self._card_primary.configure(border_color=BORDER, border_width=1)
		self._btn_sel_primary.configure(fg_color=ACCENT_DIM, text_color=ACCENT_TEXT)
		self._lbl_terminal_status.configure(
			text='✓  Terminal Cajero — ingresá la ruta al archivo de la Terminal Principal',
			text_color=GREEN_TEXT,
		)
		self._btn_next.configure(
			text='✓  Guardar configuración',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_color=GREEN,
		)

	def _browse_cashier_db(self):
		from tkinter import filedialog

		self._select_cashier_terminal()
		path = filedialog.askopenfilename(
			title='Seleccionar base de datos de la Terminal Principal',
			filetypes=[('Base de datos SQLite', '*.db'), ('Todos los archivos', '*.*')],
		)
		if path:
			self._entry_cashier_path.delete(0, 'end')
			self._entry_cashier_path.insert(0, path)

	def _validate_step_terminal(self) -> bool:
		if self._terminal_mode_sel == 'primary':
			return True
		path = self._entry_cashier_path.get().strip()
		if not path:
			self._lbl_terminal_status.configure(
				text='⚠  Ingresá la ruta a la base de datos de la Terminal Principal',
				text_color=ORANGE_TEXT,
			)
			self._entry_cashier_path.configure(border_color=RED)
			return False
		if not os.path.exists(path):
			self._lbl_terminal_status.configure(
				text=f'⚠  No se encontró el archivo: {path}',
				text_color=RED_TEXT,
			)
			self._entry_cashier_path.configure(border_color=RED)
			return False
		self._cashier_db_path = path
		return True

	def _finish_cashier(self):
		"""Finaliza el wizard para modo Terminal Cajero (sin licencia ni BD propia)."""
		if self._busy:
			return
		if not self._validate_step_terminal():
			return

		self._busy = True
		self._btn_next.configure(state='disabled', text='Guardando…')
		self._btn_back.configure(state='disabled')

		try:
			cfg = _cfg_load()
			cfg['terminal_mode'] = 'cashier'
			cfg['db_remote_path'] = self._cashier_db_path
			_cfg_save(cfg)

			CTkMessagebox(
				title='Terminal Cajero configurada',
				message=(
					f'Esta PC se conectará a:\n{self._cashier_db_path}\n\n'
					'Asegurate de que la Terminal Principal esté encendida\n'
					'y accesible en la red antes de iniciar esta terminal.'
				),
				icon='check',
			).get()

			self.winfo_toplevel().after(100, self.on_complete_callback)
		except Exception:
			self._busy = False
			self._btn_next.configure(state='normal', text='Finalizar')
			self._btn_back.configure(state='normal')
			raise
