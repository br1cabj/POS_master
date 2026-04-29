import logging

import bcrypt
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from sqlalchemy.orm import sessionmaker

from controllers.license_controller import LicenseController
from database.models import Base, Branch, Tenant, User, Warehouse
from utils.config import make_engine
from utils.settings_manager import (
	get_reports_path,
)
from utils.settings_manager import (
	load as _cfg_load,
)
from utils.settings_manager import (
	save as _cfg_save,
)
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

_STEPS = ['Licencia', 'Tu Negocio', 'Tu Usuario']


class SetupWizard(ctk.CTkFrame):
	"""Wizard multi-paso para el primer arranque de la aplicación."""

	def __init__(self, master, on_complete_callback):
		super().__init__(master, fg_color=SURFACE1)
		self.on_complete_callback = on_complete_callback
		self.license_ctrl = LicenseController()
		self._busy = False
		self._step = 1

		# ── Datos recolectados entre pasos ───────────────────────────────────
		self._license_mode: str | None = None  # 'DEMO' | 'PRO'
		self._license_key: str = ''

		# Paso 2
		self._d_store = ''
		self._d_address = ''
		self._d_phone = ''
		self._d_currency = '$'
		self._d_decimals = '0  (enteros)'
		self._d_tax = '21'
		self._d_reports_path = ''

		# Paso 3
		self._d_username = ''
		self._d_password = ''
		self._d_pin = ''  # CORRECCIÓN: Agregado PIN de recuperación

		# ── Layout raíz ──────────────────────────────────────────────────────
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
			text='← Atrás',
			width=130,
			height=42,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self._go_back,
		)
		self._btn_back.grid(row=0, column=0, padx=PAD_LG, pady=PAD_MD)

		self._btn_next = ctk.CTkButton(
			nav,
			text='Siguiente →',
			width=175,
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

	# =========================================================
	# HEADER — indicador de pasos
	# =========================================================
	def _build_header(self):
		header = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=0,
			border_width=1,
			border_color=BORDER,
			height=70,
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

		for i, name in enumerate(_STEPS):
			col = ctk.CTkFrame(steps_frame, fg_color='transparent')
			col.pack(side='left')

			circ = ctk.CTkFrame(
				col, width=28, height=28, corner_radius=14, fg_color=SURFACE3
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
				ctk.CTkLabel(
					steps_frame,
					text='  ───  ',
					font=('Arial', 9),
					text_color=BORDER_ACTIVE,
				).pack(side='left')

	def _update_step_indicator(self):
		for i, (circ, circ_lbl, name_lbl) in enumerate(self._step_indicators):
			step_num = i + 1
			if step_num < self._step:
				circ.configure(fg_color=GREEN)
				circ_lbl.configure(text='✓', text_color='white')
				name_lbl.configure(text_color=GREEN_TEXT)
			elif step_num == self._step:
				circ.configure(fg_color=ACCENT)
				circ_lbl.configure(text=str(step_num), text_color='white')
				name_lbl.configure(text_color=ACCENT_TEXT)
			else:
				circ.configure(fg_color=SURFACE3)
				circ_lbl.configure(text=str(step_num), text_color=TEXT_MUTED)
				name_lbl.configure(text_color=TEXT_MUTED)

	# =========================================================
	# NAVEGACIÓN
	# =========================================================
	def _go_back(self):
		if self._step > 1 and not self._busy:
			self._show_step(self._step - 1)

	def _go_next(self):
		if self._busy:
			return
		if self._step == 1:
			if not self._validate_step1():
				return
			self._show_step(2)
		elif self._step == 2:
			if not self._validate_step2():
				return
			self._show_step(3)
		elif self._step == 3:
			self._finish()

	def _show_step(self, step: int):
		self._step = step

		for w in self._content.winfo_children():
			w.destroy()

		self._update_step_indicator()

		if step == 1:
			self._btn_back.configure(state='disabled', text_color=BORDER_ACTIVE)
		else:
			self._btn_back.configure(state='normal', text_color=TEXT_SECONDARY)

		if step == 3:
			self._btn_next.configure(
				text='✓  Finalizar',
				fg_color=GREEN_DIM,
				hover_color=GREEN,
				text_color=GREEN_TEXT,
				border_color=GREEN,
			)
		else:
			self._btn_next.configure(
				text='Siguiente →',
				fg_color=ACCENT_DIM,
				hover_color=ACCENT,
				text_color=ACCENT_TEXT,
				border_color=ACCENT,
			)

		builders = {1: self._build_step1, 2: self._build_step2, 3: self._build_step3}
		builders[step]()

	# =========================================================
	# PASO 1 — LICENCIA
	# =========================================================
	def _build_step1(self):
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
		# CORRECCIÓN: Uso de constantes de padding
		card.grid(row=0, column=0, padx=100, pady=PAD_XL, sticky='ew')
		card.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			card,
			text='🎟️  Activación del sistema',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
		).grid(row=0, column=0, pady=(PAD_XL, PAD_SM), padx=PAD_XL, sticky='w')

		ctk.CTkLabel(
			card,
			text='Elegí cómo querés comenzar a usar CloudPOS.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
		).grid(row=1, column=0, pady=(0, PAD_XL), padx=PAD_XL, sticky='w')

		self._btn_demo = ctk.CTkButton(
			card,
			text='🎁  Iniciar Prueba Gratis  —  7 días sin costo',
			width=460,
			height=60,
			font=FONT_HEADING,
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=2,
			border_color=ORANGE,
			corner_radius=10,
			command=self._select_demo,
		)
		self._btn_demo.grid(row=2, column=0, pady=(0, PAD_MD), padx=PAD_XL)

		ctk.CTkLabel(
			card,
			text='─────  o activar con código de compra  ─────',
			font=FONT_LABEL,
			text_color=BORDER_ACTIVE,
		).grid(row=3, column=0, pady=(0, PAD_MD))

		self._btn_pro = ctk.CTkButton(
			card,
			text='✅  Tengo un código de licencia Pro',
			width=460,
			height=52,
			font=FONT_BODY_BOLD,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER_ACTIVE,
			corner_radius=10,
			command=self._select_pro,
		)
		self._btn_pro.grid(row=4, column=0, pady=(0, PAD_MD), padx=PAD_XL)

		self._pro_frame = ctk.CTkFrame(card, fg_color='transparent')
		self._pro_frame.grid(
			row=5, column=0, padx=PAD_XL, pady=(0, PAD_MD), sticky='ew'
		)
		self._pro_frame.grid_columnconfigure(0, weight=1)

		self._entry_license = ctk.CTkEntry(
			self._pro_frame,
			height=40,
			placeholder_text='XXXX-XXXX-XXXX',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._entry_license.grid(row=0, column=0, sticky='ew')
		self._entry_license.bind('<Return>', lambda e: self._go_next())

		self._lbl_lic_status = ctk.CTkLabel(
			card, text='', font=FONT_BODY, text_color=TEXT_MUTED
		)
		self._lbl_lic_status.grid(row=6, column=0, pady=(0, PAD_XL))

		if self._license_mode == 'DEMO':
			self._select_demo()
		elif self._license_mode == 'PRO':
			self._select_pro()
			if self._license_key:
				self._entry_license.insert(0, self._license_key)
		else:
			self._pro_frame.grid_remove()

	def _select_demo(self):
		self._license_mode = 'DEMO'
		self._btn_demo.configure(
			fg_color=ORANGE, text_color='white', border_color=ORANGE
		)
		self._btn_pro.configure(
			fg_color=SURFACE3, text_color=TEXT_SECONDARY, border_color=BORDER_ACTIVE
		)
		self._pro_frame.grid_remove()
		self._lbl_lic_status.configure(
			text='✓  Prueba gratuita de 7 días seleccionada', text_color=ORANGE_TEXT
		)

	def _select_pro(self):
		self._license_mode = 'PRO'
		self._btn_pro.configure(fg_color=GREEN, text_color='white', border_color=GREEN)
		self._btn_demo.configure(
			fg_color=ORANGE_DIM, text_color=ORANGE_TEXT, border_color=ORANGE
		)
		self._pro_frame.grid()
		self._lbl_lic_status.configure(
			text='Ingresá tu código de licencia Pro', text_color=GREEN_TEXT
		)
		self._entry_license.focus()

	def _validate_step1(self) -> bool:
		if self._license_mode is None:
			CTkMessagebox(
				title='Selección requerida',
				message='Elegí una opción de licencia para continuar.',
				icon='cancel',
			)
			return False
		if self._license_mode == 'PRO':
			key = self._entry_license.get().strip()
			if not key:
				CTkMessagebox(
					title='Código requerido',
					message='Ingresá el código de licencia Pro.',
					icon='cancel',
				)
				return False
			self._license_key = key
		return True

	# =========================================================
	# PASO 2 — DATOS DEL NEGOCIO
	# =========================================================
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
		card.grid(row=0, column=0, padx=80, pady=PAD_XL, sticky='ew')
		card.grid_columnconfigure(0, weight=1)
		card.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(
			card,
			text='🏪  Tu Negocio',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
		).grid(
			row=0,
			column=0,
			columnspan=2,
			pady=(PAD_XL, PAD_XS),
			padx=PAD_XL,
			sticky='w',
		)

		ctk.CTkLabel(
			card,
			text='Estos datos aparecerán en los recibos y reportes.\nPodés editarlos después en Configuración.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			justify='left',
			anchor='w',
		).grid(row=1, column=0, columnspan=2, pady=(0, PAD_LG), padx=PAD_XL, sticky='w')

		# CORRECCIÓN: Usando el make_form_label global en lugar de mk_field
		make_form_label(card, 'Nombre del Comercio', required=True).grid(
			row=2, column=0, sticky='w', padx=(PAD_XL, PAD_MD), pady=(PAD_SM, PAD_XS)
		)
		self._e_store = ctk.CTkEntry(
			card,
			placeholder_text='Ej: Kiosco Carlitos',
			height=38,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_store.grid(
			row=3, column=0, sticky='ew', padx=(PAD_XL, PAD_MD), pady=(0, PAD_XS)
		)
		if self._d_store:
			self._e_store.insert(0, self._d_store)

		make_form_label(card, 'Dirección').grid(
			row=2, column=1, sticky='w', padx=(PAD_MD, PAD_XL), pady=(PAD_SM, PAD_XS)
		)
		self._e_address = ctk.CTkEntry(
			card,
			placeholder_text='Ej: Av. Siempre Viva 123',
			height=38,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_address.grid(
			row=3, column=1, sticky='ew', padx=(PAD_MD, PAD_XL), pady=(0, PAD_XS)
		)
		if self._d_address:
			self._e_address.insert(0, self._d_address)

		make_form_label(card, 'Teléfono / WhatsApp').grid(
			row=4, column=0, sticky='w', padx=(PAD_XL, PAD_MD), pady=(PAD_SM, PAD_XS)
		)
		self._e_phone = ctk.CTkEntry(
			card,
			placeholder_text='Ej: +54 388 444-4444',
			height=38,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_phone.grid(
			row=5, column=0, sticky='ew', padx=(PAD_XL, PAD_MD), pady=(0, PAD_XS)
		)
		if self._d_phone:
			self._e_phone.insert(0, self._d_phone)

		make_form_label(card, 'Símbolo de moneda', required=True).grid(
			row=4, column=1, sticky='w', padx=(PAD_MD, PAD_XL), pady=(PAD_SM, PAD_XS)
		)
		self._e_currency = ctk.CTkEntry(
			card,
			placeholder_text='Ej: $, €, S/.',
			height=38,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_currency.grid(
			row=5, column=1, sticky='ew', padx=(PAD_MD, PAD_XL), pady=(0, PAD_XS)
		)
		if self._d_currency:
			self._e_currency.insert(0, self._d_currency)

		make_form_label(card, 'DECIMALES EN PRECIOS').grid(
			row=6, column=0, sticky='w', padx=(PAD_XL, PAD_MD), pady=(PAD_SM, PAD_XS)
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
		)
		self._seg_decimals.grid(
			row=7, column=0, sticky='ew', padx=(PAD_XL, PAD_MD), pady=(0, PAD_XS)
		)
		self._seg_decimals.set(self._d_decimals)

		make_form_label(card, 'IMPUESTO / IVA (%)').grid(
			row=6, column=1, sticky='w', padx=(PAD_MD, PAD_XL), pady=(PAD_SM, PAD_XS)
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
			row=7, column=1, sticky='ew', padx=(PAD_MD, PAD_XL), pady=(0, PAD_XS)
		)
		self._e_tax.insert(0, self._d_tax)

		ctk.CTkFrame(card, height=1, fg_color=BORDER).grid(
			row=8, column=0, columnspan=2, sticky='ew', padx=PAD_XL, pady=(PAD_LG, 0)
		)

		make_form_label(card, 'CARPETA DE REPORTES Y EXPORTACIONES').grid(
			row=9,
			column=0,
			columnspan=2,
			sticky='w',
			padx=PAD_XL,
			pady=(PAD_MD, PAD_XS),
		)
		ctk.CTkLabel(
			card,
			text='Todos los PDFs, CSV y Excel generados se guardarán aquí.\nPodés dejarlo en blanco para usar el Desktop.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			justify='left',
			anchor='w',
		).grid(
			row=10, column=0, columnspan=2, sticky='w', padx=PAD_XL, pady=(0, PAD_SM)
		)

		reports_row = ctk.CTkFrame(card, fg_color='transparent')
		reports_row.grid(
			row=11, column=0, columnspan=2, sticky='ew', padx=PAD_XL, pady=(0, PAD_XL)
		)
		reports_row.grid_columnconfigure(0, weight=1)

		self._lbl_reports_path = ctk.CTkLabel(
			reports_row,
			text=self._d_reports_path or get_reports_path(),
			font=('Consolas', 11),
			text_color=TEXT_SECONDARY,
			anchor='w',
			wraplength=420,
			justify='left',
		)
		self._lbl_reports_path.grid(row=0, column=0, sticky='ew', pady=(0, PAD_SM))

		btn_row = ctk.CTkFrame(reports_row, fg_color='transparent')
		btn_row.grid(row=1, column=0, sticky='w')

		ctk.CTkButton(
			btn_row,
			text='📁  Elegir Carpeta',
			height=34,
			font=FONT_LABEL_BOLD,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			corner_radius=8,
			command=self._pick_reports_folder,
		).pack(side='left', padx=(0, PAD_SM))

		ctk.CTkButton(
			btn_row,
			text='↺ Usar Desktop',
			height=34,
			font=FONT_LABEL,
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			corner_radius=8,
			command=self._reset_reports_folder,
		).pack(side='left')

		self._e_store.focus()

	def _validate_step2(self) -> bool:
		store = self._e_store.get().strip()
		if not store:
			CTkMessagebox(
				title='Campo requerido',
				message='El nombre del comercio es obligatorio.',
				icon='cancel',
			)
			self._e_store.focus()
			return False

		currency = self._e_currency.get().strip()
		if not currency:
			CTkMessagebox(
				title='Campo requerido',
				message='Ingresá el símbolo de moneda (Ej: $).',
				icon='cancel',
			)
			self._e_currency.focus()
			return False

		tax_str = self._e_tax.get().strip().replace(',', '.')
		try:
			float(tax_str)
		except ValueError:
			CTkMessagebox(
				title='Valor inválido',
				message='El impuesto debe ser un número (Ej: 21).',
				icon='cancel',
			)
			self._e_tax.focus()
			return False

		self._d_store = store
		self._d_address = self._e_address.get().strip()
		self._d_phone = self._e_phone.get().strip()
		self._d_currency = currency
		self._d_decimals = self._seg_decimals.get()
		self._d_tax = tax_str
		return True

	def _pick_reports_folder(self):
		from tkinter import filedialog

		path = filedialog.askdirectory(
			title='Elegir carpeta de reportes',
			initialdir=self._d_reports_path or get_reports_path(),
		)
		if not path:
			return
		self._d_reports_path = path
		self._lbl_reports_path.configure(text=path)

	def _reset_reports_folder(self):
		self._d_reports_path = ''
		self._lbl_reports_path.configure(text=get_reports_path())

	# =========================================================
	# PASO 3 — USUARIO ADMINISTRADOR
	# =========================================================
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
		card.grid(row=0, column=0, padx=100, pady=PAD_XL, sticky='ew')
		card.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			card,
			text='👤  Tu Usuario Administrador',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
		).grid(row=0, column=0, pady=(PAD_XL, PAD_XS), padx=PAD_XL, sticky='w')

		ctk.CTkLabel(
			card,
			text='Con estos datos vas a iniciar sesión en el sistema.',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			anchor='w',
			justify='left',
		).grid(row=1, column=0, pady=(0, PAD_LG), padx=PAD_XL, sticky='w')

		make_form_label(card, 'NOMBRE DE USUARIO', required=True).grid(
			row=2, column=0, sticky='w', padx=PAD_XL, pady=(0, PAD_XS)
		)
		self._e_username = ctk.CTkEntry(
			card,
			placeholder_text='Ej: admin, carlos, gerente',
			height=42,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_username.grid(
			row=3, column=0, sticky='ew', padx=PAD_XL, pady=(0, PAD_XS)
		)
		if self._d_username:
			self._e_username.insert(0, self._d_username)

		ctk.CTkLabel(
			card,
			text='Sin espacios ni caracteres especiales. Mínimo 3 caracteres.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=4, column=0, sticky='w', padx=PAD_XL, pady=(0, PAD_MD))

		# CORRECCIÓN: Solicitamos el PIN de recuperación de cuenta
		make_form_label(card, 'PIN DE RECUPERACIÓN (4 DÍGITOS)', required=True).grid(
			row=5, column=0, sticky='w', padx=PAD_XL, pady=(0, PAD_XS)
		)
		self._e_pin = ctk.CTkEntry(
			card,
			placeholder_text='Ej: 1234',
			show='*',
			height=42,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_pin.grid(row=6, column=0, sticky='ew', padx=PAD_XL, pady=(0, PAD_XS))
		if self._d_pin:
			self._e_pin.insert(0, self._d_pin)

		ctk.CTkLabel(
			card,
			text='Fundamental para recuperar tu cuenta si olvidás la contraseña.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=7, column=0, sticky='w', padx=PAD_XL, pady=(0, PAD_MD))

		make_form_label(card, 'CONTRASEÑA', required=True).grid(
			row=8, column=0, sticky='w', padx=PAD_XL, pady=(0, PAD_XS)
		)
		self._e_pass = ctk.CTkEntry(
			card,
			placeholder_text='Mínimo 6 caracteres',
			show='*',
			height=42,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_pass.grid(row=9, column=0, sticky='ew', padx=PAD_XL, pady=(0, PAD_MD))

		make_form_label(card, 'CONFIRMAR CONTRASEÑA', required=True).grid(
			row=10, column=0, sticky='w', padx=PAD_XL, pady=(0, PAD_XS)
		)
		self._e_pass2 = ctk.CTkEntry(
			card,
			placeholder_text='Repetí la contraseña',
			show='*',
			height=42,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self._e_pass2.grid(row=11, column=0, sticky='ew', padx=PAD_XL, pady=(0, PAD_SM))
		self._e_pass2.bind('<Return>', lambda e: self._go_next())

		self._chk_show = ctk.CTkCheckBox(
			card,
			text='Mostrar contraseñas y PIN',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			command=self._toggle_pass,
		)
		self._chk_show.grid(row=12, column=0, sticky='w', padx=PAD_XL, pady=(0, PAD_LG))

		req = ctk.CTkFrame(card, fg_color=SURFACE3, corner_radius=8)
		req.grid(row=13, column=0, sticky='ew', padx=PAD_XL, pady=(0, PAD_XL))

		ctk.CTkLabel(
			req,
			text='Requisitos:',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
		).pack(anchor='w', padx=PAD_MD, pady=(PAD_SM, PAD_XS))

		for txt in [
			'Nombre de usuario: mínimo 3 caracteres, sin espacios',
			'PIN de recuperación: exactamente 4 números',
			'Contraseña: al menos 6 caracteres',
		]:
			ctk.CTkLabel(
				req,
				text=f'  ·  {txt}',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
				anchor='w',
			).pack(anchor='w', padx=PAD_MD, pady=1)
		ctk.CTkLabel(req, text='', height=8).pack()

		self._e_username.focus()

	def _toggle_pass(self):
		show = '' if self._chk_show.get() else '*'
		self._e_pin.configure(show=show)
		self._e_pass.configure(show=show)
		self._e_pass2.configure(show=show)

	def _validate_step3(self) -> bool:
		username = self._e_username.get().strip()
		if len(username) < 3 or ' ' in username:
			CTkMessagebox(
				title='Usuario inválido',
				message='El nombre de usuario debe tener al menos 3 caracteres sin espacios.',
				icon='cancel',
			)
			self._e_username.focus()
			return False

		pin = self._e_pin.get().strip()
		if len(pin) != 4 or not pin.isdigit():
			CTkMessagebox(
				title='PIN inválido',
				message='El PIN de recuperación debe ser de exactamente 4 números.',
				icon='cancel',
			)
			self._e_pin.focus()
			return False

		password = self._e_pass.get()
		if len(password) < 6:
			CTkMessagebox(
				title='Contraseña muy corta',
				message='La contraseña debe tener al menos 6 caracteres.',
				icon='cancel',
			)
			self._e_pass.focus()
			return False

		if password != self._e_pass2.get():
			CTkMessagebox(
				title='Error', message='Las contraseñas no coinciden.', icon='cancel'
			)
			self._e_pass2.focus()
			return False

		self._d_username = username
		self._d_password = password
		self._d_pin = pin
		return True

	# =========================================================
	# FINALIZAR — crear BD y settings
	# =========================================================
	def _finish(self):
		# CORRECCIÓN: Eliminación de bloque de código duplicado e integración de la creación de BD
		if self._busy:
			return
		if not self._validate_step3():
			return

		self._busy = True
		self._btn_next.configure(state='disabled', text='Configurando…')
		self._btn_back.configure(state='disabled')
		self.update_idletasks()  # Asegura que la UI muestre el estado de carga antes de trabarse

		# Activar licencia
		if self._license_mode == 'DEMO':
			success, msg = self.license_ctrl.activate_demo()
		else:
			success, msg = self.license_ctrl.activate_license(self._license_key)

		if not success:
			CTkMessagebox(title='Licencia rechazada', message=msg, icon='cancel')
			self._busy = False
			self._btn_next.configure(state='normal', text='✓  Finalizar')
			self._btn_back.configure(state='normal')
			return

		try:
			self._setup_database()
			self._save_settings()
			CTkMessagebox(
				title='¡Todo listo!',
				message=f'Tu sistema CloudPOS está configurado.\n¡Bienvenido, {self._d_username}!',
				icon='check',
			).get()
			self.after(100, self.on_complete_callback)
		except Exception as e:
			logger.error(f'Error al crear la base de datos: {e}', exc_info=True)
			CTkMessagebox(
				title='Error Fatal',
				message=f'Falló la creación de la base de datos:\n{str(e)}',
				icon='cancel',
			)
			self._busy = False
			self._btn_next.configure(state='normal', text='✓  Finalizar')
			self._btn_back.configure(state='normal')

	def _setup_database(self):
		"""Crea pos_system.db con Tenant, Branch, Warehouse y usuario admin."""
		engine = make_engine()
		Base.metadata.create_all(engine)
		Session = sessionmaker(bind=engine)

		with Session() as session:
			tenant = Tenant(name=self._d_store)
			session.add(tenant)
			session.flush()

			branch = Branch(name='Sede Principal', tenant_id=tenant.id)
			session.add(branch)
			session.flush()

			warehouse = Warehouse(
				name='Depósito General', branch_id=branch.id, tenant_id=tenant.id
			)
			session.add(warehouse)

			# Hash de la contraseña y del PIN de seguridad
			pwd_hashed = bcrypt.hashpw(
				self._d_password.encode('utf-8'), bcrypt.gensalt()
			).decode('utf-8')
			pin_hashed = bcrypt.hashpw(
				self._d_pin.encode('utf-8'), bcrypt.gensalt()
			).decode('utf-8')

			admin = User(
				tenant_id=tenant.id,
				username=self._d_username,
				password_hash=pwd_hashed,
				recovery_pin_hash=pin_hashed,  # CORRECCIÓN: Persistencia del PIN agregado
				role='admin',
				is_active=True,
			)
			session.add(admin)
			session.commit()

	def _save_settings(self):
		"""Persiste en settings.json los datos del negocio recolectados en paso 2."""
		cfg = _cfg_load()
		cfg['company_name'] = self._d_store
		cfg['company_address'] = self._d_address
		cfg['company_phone'] = self._d_phone
		cfg['currency_symbol'] = self._d_currency
		cfg['currency_decimals'] = 0 if self._d_decimals.startswith('0') else 2
		cfg['tax_rate'] = float(self._d_tax)
		cfg['reports_path'] = self._d_reports_path
		_cfg_save(cfg)
