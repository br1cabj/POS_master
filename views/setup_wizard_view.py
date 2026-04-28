"""
views/setup_wizard_view.py
==========================
Wizard de configuración inicial — 3 pasos:

  Paso 1 · Licencia   — Demo 7 días o código Pro
  Paso 2 · Tu Negocio — nombre, dirección, moneda, impuesto
  Paso 3 · Tu Usuario — username personalizado, contraseña × 2

Al finalizar crea pos_system.db, license.dat y settings.json.
"""
import logging

import bcrypt
import customtkinter as ctk
from CTkMessagebox import CTkMessagebox
from sqlalchemy.orm import sessionmaker

from controllers.license_controller import LicenseController
from database.models import Base, Branch, Tenant, User, Warehouse
from utils.config import make_engine
from utils.settings_manager import load as _cfg_load, save as _cfg_save
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
	RED_TEXT,
	SURFACE1,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
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
		self._license_mode: str | None = None   # 'DEMO' | 'PRO'
		self._license_key: str = ''
		# Paso 2
		self._d_store = ''
		self._d_address = ''
		self._d_phone = ''
		self._d_currency = '$'
		self._d_decimals = '0  (enteros)'
		self._d_tax = '21'
		# Paso 3
		self._d_username = ''
		self._d_password = ''

		# ── Layout raíz ──────────────────────────────────────────────────────
		self.pack(fill='both', expand=True)
		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)  # fila de contenido crece

		self._build_header()

		# Área de contenido (se reemplaza en cada paso)
		self._content = ctk.CTkFrame(self, fg_color='transparent')
		self._content.grid(row=1, column=0, sticky='nsew')
		self._content.grid_columnconfigure(0, weight=1)
		self._content.grid_rowconfigure(0, weight=1)

		# Barra de navegación inferior
		nav = ctk.CTkFrame(
			self, fg_color=SURFACE2, corner_radius=0,
			border_width=1, border_color=BORDER,
		)
		nav.grid(row=2, column=0, sticky='ew')
		nav.grid_columnconfigure(1, weight=1)  # espaciador central

		self._btn_back = ctk.CTkButton(
			nav, text='← Atrás', width=130, height=42,
			fg_color=SURFACE3, hover_color=SURFACE4,
			text_color=TEXT_SECONDARY, corner_radius=8,
			command=self._go_back,
		)
		self._btn_back.grid(row=0, column=0, padx=24, pady=14)

		self._btn_next = ctk.CTkButton(
			nav, text='Siguiente →', width=175, height=42,
			fg_color=ACCENT_DIM, hover_color=ACCENT,
			text_color=ACCENT_TEXT, border_width=1,
			border_color=ACCENT, corner_radius=8,
			command=self._go_next,
		)
		self._btn_next.grid(row=0, column=2, padx=24, pady=14)

		self._show_step(1)

	# =========================================================
	# HEADER — indicador de pasos
	# =========================================================
	def _build_header(self):
		header = ctk.CTkFrame(
			self, fg_color=SURFACE2, corner_radius=0,
			border_width=1, border_color=BORDER, height=70,
		)
		header.grid(row=0, column=0, sticky='ew')
		header.grid_propagate(False)
		header.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(
			header, text='🚀  CloudPOS',
			font=('Arial', 20, 'bold'), text_color=ACCENT_TEXT,
		).grid(row=0, column=0, padx=28, sticky='w')

		steps_frame = ctk.CTkFrame(header, fg_color='transparent')
		steps_frame.grid(row=0, column=2, padx=28)

		self._step_indicators: list[tuple] = []

		for i, name in enumerate(_STEPS):
			col = ctk.CTkFrame(steps_frame, fg_color='transparent')
			col.pack(side='left')

			# Círculo numerado
			circ = ctk.CTkFrame(col, width=28, height=28, corner_radius=14, fg_color=SURFACE3)
			circ.pack_propagate(False)
			circ.pack(side='left')
			circ_lbl = ctk.CTkLabel(
				circ, text=str(i + 1), font=('Arial', 11, 'bold'), text_color=TEXT_MUTED,
			)
			circ_lbl.place(relx=0.5, rely=0.5, anchor='center')

			name_lbl = ctk.CTkLabel(
				col, text=f'  {name}', font=('Arial', 11), text_color=TEXT_MUTED,
			)
			name_lbl.pack(side='left')

			self._step_indicators.append((circ, circ_lbl, name_lbl))

			if i < len(_STEPS) - 1:
				ctk.CTkLabel(
					steps_frame, text='  ───  ', font=('Arial', 9), text_color=BORDER_ACTIVE,
				).pack(side='left')

	def _update_step_indicator(self):
		for i, (circ, circ_lbl, name_lbl) in enumerate(self._step_indicators):
			step_num = i + 1
			if step_num < self._step:           # completado
				circ.configure(fg_color=GREEN)
				circ_lbl.configure(text='✓', text_color='white')
				name_lbl.configure(text_color=GREEN_TEXT)
			elif step_num == self._step:        # activo
				circ.configure(fg_color=ACCENT)
				circ_lbl.configure(text=str(step_num), text_color='white')
				name_lbl.configure(text_color=ACCENT_TEXT)
			else:                               # pendiente
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

		# Destruir contenido anterior
		for w in self._content.winfo_children():
			w.destroy()

		self._update_step_indicator()

		# Botón atrás: deshabilitado en paso 1
		if step == 1:
			self._btn_back.configure(state='disabled', text_color=BORDER_ACTIVE)
		else:
			self._btn_back.configure(state='normal', text_color=TEXT_SECONDARY)

		# Botón siguiente: cambia a "Finalizar" en paso 3
		if step == 3:
			self._btn_next.configure(
				text='✓  Finalizar',
				fg_color=GREEN_DIM, hover_color=GREEN,
				text_color=GREEN_TEXT, border_color=GREEN,
			)
		else:
			self._btn_next.configure(
				text='Siguiente →',
				fg_color=ACCENT_DIM, hover_color=ACCENT,
				text_color=ACCENT_TEXT, border_color=ACCENT,
			)

		builders = {1: self._build_step1, 2: self._build_step2, 3: self._build_step3}
		builders[step]()

	# =========================================================
	# PASO 1 — LICENCIA
	# =========================================================
	def _build_step1(self):
		scroll = ctk.CTkScrollableFrame(
			self._content, fg_color='transparent',
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		scroll.grid(row=0, column=0, sticky='nsew')
		scroll.grid_columnconfigure(0, weight=1)

		card = ctk.CTkFrame(
			scroll, fg_color=SURFACE2, corner_radius=16,
			border_width=1, border_color=BORDER,
		)
		card.grid(row=0, column=0, padx=100, pady=44, sticky='ew')
		card.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			card, text='🎟️  Activación del sistema',
			font=('Arial', 22, 'bold'), text_color=TEXT_PRIMARY,
		).grid(row=0, column=0, pady=(36, 6), padx=48, sticky='w')

		ctk.CTkLabel(
			card, text='Elegí cómo querés comenzar a usar CloudPOS.',
			font=('Arial', 13), text_color=TEXT_MUTED,
		).grid(row=1, column=0, pady=(0, 30), padx=48, sticky='w')

		# ── Demo ─────────────────────────────────────────────────────────────
		self._btn_demo = ctk.CTkButton(
			card,
			text='🎁  Iniciar Prueba Gratis  —  7 días sin costo',
			width=460, height=60, font=('Arial', 14, 'bold'),
			fg_color=ORANGE_DIM, hover_color=ORANGE,
			text_color=ORANGE_TEXT, border_width=2, border_color=ORANGE,
			corner_radius=10, command=self._select_demo,
		)
		self._btn_demo.grid(row=2, column=0, pady=(0, 18), padx=48)

		ctk.CTkLabel(
			card, text='─────  o activar con código de compra  ─────',
			font=('Arial', 11), text_color=BORDER_ACTIVE,
		).grid(row=3, column=0, pady=(0, 16))

		# ── Pro ──────────────────────────────────────────────────────────────
		self._btn_pro = ctk.CTkButton(
			card,
			text='✅  Tengo un código de licencia Pro',
			width=460, height=52, font=('Arial', 13, 'bold'),
			fg_color=SURFACE3, hover_color=SURFACE4,
			text_color=TEXT_SECONDARY, border_width=1, border_color=BORDER_ACTIVE,
			corner_radius=10, command=self._select_pro,
		)
		self._btn_pro.grid(row=4, column=0, pady=(0, 12), padx=48)

		# Frame de clave Pro (visible sólo al seleccionar Pro)
		self._pro_frame = ctk.CTkFrame(card, fg_color='transparent')
		self._pro_frame.grid(row=5, column=0, padx=48, pady=(0, 12), sticky='ew')
		self._pro_frame.grid_columnconfigure(0, weight=1)

		self._entry_license = ctk.CTkEntry(
			self._pro_frame, height=40, placeholder_text='XXXX-XXXX-XXXX',
			fg_color=SURFACE3, border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY, font=('Arial', 13),
		)
		self._entry_license.grid(row=0, column=0, sticky='ew')
		self._entry_license.bind('<Return>', lambda e: self._go_next())

		# Label de estado
		self._lbl_lic_status = ctk.CTkLabel(
			card, text='', font=('Arial', 12), text_color=TEXT_MUTED,
		)
		self._lbl_lic_status.grid(row=6, column=0, pady=(0, 32))

		# ── Restaurar selección previa ────────────────────────────────────────
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
		self._btn_demo.configure(fg_color=ORANGE, text_color='white', border_color=ORANGE)
		self._btn_pro.configure(fg_color=SURFACE3, text_color=TEXT_SECONDARY, border_color=BORDER_ACTIVE)
		self._pro_frame.grid_remove()
		self._lbl_lic_status.configure(
			text='✓  Prueba gratuita de 7 días seleccionada',
			text_color=ORANGE_TEXT,
		)

	def _select_pro(self):
		self._license_mode = 'PRO'
		self._btn_pro.configure(fg_color=GREEN, text_color='white', border_color=GREEN)
		self._btn_demo.configure(fg_color=ORANGE_DIM, text_color=ORANGE_TEXT, border_color=ORANGE)
		self._pro_frame.grid()
		self._lbl_lic_status.configure(
			text='Ingresá tu código de licencia Pro',
			text_color=GREEN_TEXT,
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
			self._content, fg_color='transparent',
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		scroll.grid(row=0, column=0, sticky='nsew')
		scroll.grid_columnconfigure(0, weight=1)

		card = ctk.CTkFrame(
			scroll, fg_color=SURFACE2, corner_radius=16,
			border_width=1, border_color=BORDER,
		)
		card.grid(row=0, column=0, padx=80, pady=40, sticky='ew')
		card.grid_columnconfigure(0, weight=1)
		card.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(
			card, text='🏪  Tu Negocio',
			font=('Arial', 22, 'bold'), text_color=TEXT_PRIMARY,
		).grid(row=0, column=0, columnspan=2, pady=(34, 6), padx=40, sticky='w')

		ctk.CTkLabel(
			card,
			text='Estos datos aparecerán en los recibos y reportes.\nPodés editarlos después en Configuración.',
			font=('Arial', 12), text_color=TEXT_MUTED,
			justify='left', anchor='w',
		).grid(row=1, column=0, columnspan=2, pady=(0, 24), padx=40, sticky='w')

		# ── Helper para crear un campo de formulario ─────────────────────────
		def mk_field(row, col, label, ph, required=False, initial=''):
			tag = '  *' if required else ''
			pad_l = 40 if col == 0 else 12
			pad_r = 12 if col == 0 else 40
			ctk.CTkLabel(
				card, text=label.upper() + tag,
				font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
			).grid(row=row * 2 + 2, column=col, sticky='w',
				   padx=(pad_l, pad_r), pady=(10, 2))
			entry = ctk.CTkEntry(
				card, placeholder_text=ph, height=38,
				fg_color=SURFACE3, border_color=BORDER_ACTIVE,
				text_color=TEXT_PRIMARY, font=('Arial', 12),
			)
			entry.grid(row=row * 2 + 3, column=col, sticky='ew',
					   padx=(pad_l, pad_r), pady=(0, 2))
			if initial:
				entry.insert(0, initial)
			return entry

		self._e_store = mk_field(0, 0, 'Nombre del Comercio', 'Ej: Kiosco Carlitos',
								 required=True, initial=self._d_store)
		self._e_address = mk_field(0, 1, 'Dirección', 'Ej: Av. Siempre Viva 123',
								   initial=self._d_address)
		self._e_phone = mk_field(1, 0, 'Teléfono / WhatsApp', 'Ej: +54 388 444-4444',
								 initial=self._d_phone)
		self._e_currency = mk_field(1, 1, 'Símbolo de moneda', 'Ej: $, €, S/.',
									required=True, initial=self._d_currency)

		# ── Decimales ────────────────────────────────────────────────────────
		ctk.CTkLabel(
			card, text='DECIMALES EN PRECIOS',
			font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
		).grid(row=6, column=0, sticky='w', padx=(40, 12), pady=(10, 2))

		self._seg_decimals = ctk.CTkSegmentedButton(
			card, values=['0  (enteros)', '2  (centavos)'],
			font=('Arial', 12), height=38,
			fg_color=SURFACE3,
			selected_color=ACCENT, selected_hover_color=ACCENT,
			unselected_color=SURFACE3, unselected_hover_color=SURFACE4,
			text_color=TEXT_SECONDARY, text_color_disabled=TEXT_MUTED,
		)
		self._seg_decimals.grid(row=7, column=0, sticky='ew', padx=(40, 12), pady=(0, 2))
		self._seg_decimals.set(self._d_decimals)

		# ── IVA ──────────────────────────────────────────────────────────────
		ctk.CTkLabel(
			card, text='IMPUESTO / IVA (%)',
			font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
		).grid(row=6, column=1, sticky='w', padx=(12, 40), pady=(10, 2))

		self._e_tax = ctk.CTkEntry(
			card, placeholder_text='Ej: 21', height=38,
			fg_color=SURFACE3, border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY, font=('Arial', 12),
		)
		self._e_tax.grid(row=7, column=1, sticky='ew', padx=(12, 40), pady=(0, 32))
		self._e_tax.insert(0, self._d_tax)

		self._e_store.focus()

	def _validate_step2(self) -> bool:
		store = self._e_store.get().strip()
		if not store:
			CTkMessagebox(title='Campo requerido',
						  message='El nombre del comercio es obligatorio.', icon='cancel')
			self._e_store.focus()
			return False

		currency = self._e_currency.get().strip()
		if not currency:
			CTkMessagebox(title='Campo requerido',
						  message='Ingresá el símbolo de moneda (Ej: $).', icon='cancel')
			self._e_currency.focus()
			return False

		tax_str = self._e_tax.get().strip().replace(',', '.')
		try:
			float(tax_str)
		except ValueError:
			CTkMessagebox(title='Valor inválido',
						  message='El impuesto debe ser un número (Ej: 21).', icon='cancel')
			self._e_tax.focus()
			return False

		# Persistir
		self._d_store = store
		self._d_address = self._e_address.get().strip()
		self._d_phone = self._e_phone.get().strip()
		self._d_currency = currency
		self._d_decimals = self._seg_decimals.get()
		self._d_tax = tax_str
		return True

	# =========================================================
	# PASO 3 — USUARIO ADMINISTRADOR
	# =========================================================
	def _build_step3(self):
		scroll = ctk.CTkScrollableFrame(
			self._content, fg_color='transparent',
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		scroll.grid(row=0, column=0, sticky='nsew')
		scroll.grid_columnconfigure(0, weight=1)

		card = ctk.CTkFrame(
			scroll, fg_color=SURFACE2, corner_radius=16,
			border_width=1, border_color=BORDER,
		)
		card.grid(row=0, column=0, padx=100, pady=40, sticky='ew')
		card.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			card, text='👤  Tu Usuario Administrador',
			font=('Arial', 22, 'bold'), text_color=TEXT_PRIMARY,
		).grid(row=0, column=0, pady=(34, 6), padx=48, sticky='w')

		ctk.CTkLabel(
			card,
			text='Con estos datos vas a iniciar sesión. Guardá la contraseña en un lugar seguro.',
			font=('Arial', 12), text_color=TEXT_MUTED,
			anchor='w', justify='left',
		).grid(row=1, column=0, pady=(0, 24), padx=48, sticky='w')

		# ── Nombre de usuario ─────────────────────────────────────────────────
		ctk.CTkLabel(
			card, text='NOMBRE DE USUARIO  *',
			font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
		).grid(row=2, column=0, sticky='w', padx=48, pady=(0, 2))

		self._e_username = ctk.CTkEntry(
			card, placeholder_text='Ej: admin, carlos, gerente',
			height=42, fg_color=SURFACE3, border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY, font=('Arial', 13),
		)
		self._e_username.grid(row=3, column=0, sticky='ew', padx=48, pady=(0, 4))
		if self._d_username:
			self._e_username.insert(0, self._d_username)

		ctk.CTkLabel(
			card, text='Sin espacios ni caracteres especiales. Mínimo 3 caracteres.',
			font=('Arial', 10), text_color=TEXT_MUTED, anchor='w',
		).grid(row=4, column=0, sticky='w', padx=48, pady=(0, 18))

		# ── Contraseña ────────────────────────────────────────────────────────
		ctk.CTkLabel(
			card, text='CONTRASEÑA  *',
			font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
		).grid(row=5, column=0, sticky='w', padx=48, pady=(0, 2))

		self._e_pass = ctk.CTkEntry(
			card, placeholder_text='Mínimo 6 caracteres',
			show='*', height=42, fg_color=SURFACE3, border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY, font=('Arial', 13),
		)
		self._e_pass.grid(row=6, column=0, sticky='ew', padx=48, pady=(0, 14))

		# ── Confirmar contraseña ──────────────────────────────────────────────
		ctk.CTkLabel(
			card, text='CONFIRMAR CONTRASEÑA  *',
			font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
		).grid(row=7, column=0, sticky='w', padx=48, pady=(0, 2))

		self._e_pass2 = ctk.CTkEntry(
			card, placeholder_text='Repetí la contraseña',
			show='*', height=42, fg_color=SURFACE3, border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY, font=('Arial', 13),
		)
		self._e_pass2.grid(row=8, column=0, sticky='ew', padx=48, pady=(0, 8))
		self._e_pass2.bind('<Return>', lambda e: self._finish())

		# ── Toggle mostrar contraseña ─────────────────────────────────────────
		self._chk_show = ctk.CTkCheckBox(
			card, text='Mostrar contraseña',
			font=('Arial', 11), text_color=TEXT_MUTED,
			command=self._toggle_pass,
		)
		self._chk_show.grid(row=9, column=0, sticky='w', padx=48, pady=(0, 18))

		# ── Caja de requisitos ────────────────────────────────────────────────
		req = ctk.CTkFrame(card, fg_color=SURFACE3, corner_radius=8)
		req.grid(row=10, column=0, sticky='ew', padx=48, pady=(0, 36))

		ctk.CTkLabel(
			req, text='Requisitos:', font=('Arial', 10, 'bold'),
			text_color=TEXT_SECONDARY, anchor='w',
		).pack(anchor='w', padx=16, pady=(12, 4))

		for txt in [
			'Al menos 6 caracteres en la contraseña',
			'Nombre de usuario: mínimo 3 caracteres, sin espacios',
			'Las dos contraseñas deben coincidir exactamente',
		]:
			ctk.CTkLabel(
				req, text=f'  ·  {txt}', font=('Arial', 10),
				text_color=TEXT_MUTED, anchor='w',
			).pack(anchor='w', padx=16, pady=1)

		ctk.CTkLabel(req, text='', height=8).pack()

		self._e_username.focus()

	def _toggle_pass(self):
		show = '' if self._chk_show.get() else '*'
		self._e_pass.configure(show=show)
		self._e_pass2.configure(show=show)

	def _validate_step3(self) -> bool:
		username = self._e_username.get().strip()
		if len(username) < 3:
			CTkMessagebox(title='Usuario inválido',
						  message='El nombre de usuario debe tener al menos 3 caracteres.',
						  icon='cancel')
			self._e_username.focus()
			return False
		if ' ' in username:
			CTkMessagebox(title='Usuario inválido',
						  message='El nombre de usuario no puede contener espacios.',
						  icon='cancel')
			self._e_username.focus()
			return False

		password = self._e_pass.get()
		if len(password) < 6:
			CTkMessagebox(title='Contraseña muy corta',
						  message='La contraseña debe tener al menos 6 caracteres.',
						  icon='cancel')
			self._e_pass.focus()
			return False
		if password != self._e_pass2.get():
			CTkMessagebox(title='Error',
						  message='Las contraseñas no coinciden.',
						  icon='cancel')
			self._e_pass2.focus()
			return False

		self._d_username = username
		self._d_password = password
		return True

	# =========================================================
	# FINALIZAR — crear BD y settings
	# =========================================================
	def _finish(self):
		if self._busy:
			return
		if not self._validate_step3():
			return

		self._busy = True
		self._btn_next.configure(state='disabled', text='Configurando…')
		self._btn_back.configure(state='disabled')

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
				message=(
					f'Tu sistema CloudPOS está configurado.\n'
					f'¡Bienvenido, {self._d_username}!'
				),
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

			warehouse = Warehouse(name='Depósito General', branch_id=branch.id)
			session.add(warehouse)

			hashed = bcrypt.hashpw(
				self._d_password.encode('utf-8'), bcrypt.gensalt()
			).decode('utf-8')

			admin = User(
				tenant_id=tenant.id,
				username=self._d_username,
				password_hash=hashed,
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
		_cfg_save(cfg)
