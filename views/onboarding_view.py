"""
views/onboarding_view.py
========================
Pantalla de bienvenida que aparece una sola vez luego del primer login exitoso.
Muestra un checklist de pasos iniciales y permite navegar directamente a cada sección.
Se marca como vista con el flag 'onboarding_shown' en settings.json.
"""

import customtkinter as ctk

from core.base_view import BaseView
from core.context import AppContext
from utils.settings_manager import load as _cfg_load
from utils.settings_manager import save as _cfg_save
from utils.styles import (
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	SURFACE1,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
)

_CHECKLIST = [
	(
		'✅',
		'Sistema configurado',
		'Tu negocio, moneda e impuestos quedaron guardados desde el asistente.',
		True,
		None,
	),
	(
		'🚚',
		'Agregá tu primer proveedor',
		'Los proveedores te permiten asociar artículos a su origen y filtrar por ellos.',
		False,
		'suppliers',
	),
	(
		'📦',
		'Cargá tu primer producto',
		'Agregá artículos con código de barras, precio de costo y precio de venta.',
		False,
		'articles',
	),
	(
		'💵',
		'Abrí tu primera sesión de caja',
		'Registrá el saldo inicial y empezá a vender.',
		False,
		'cash',
	),
]


class OnboardingView(BaseView):
	"""Vista de bienvenida post-primer-login con checklist de inicio rápido."""

	def __init__(self, master, ctx: AppContext, on_done):
		super().__init__(master, ctx)
		self._on_done = on_done

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(0, weight=1)

		scroll = ctk.CTkScrollableFrame(
			self,
			fg_color=SURFACE1,
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		scroll.grid(row=0, column=0, sticky='nsew')
		scroll.grid_columnconfigure(0, weight=1)

		self._build_content(scroll)

	def _build_content(self, parent):
		# ── Encabezado ────────────────────────────────────────────────────────
		header = ctk.CTkFrame(
			parent,
			fg_color=ACCENT_DIM,
			corner_radius=16,
			border_width=1,
			border_color=ACCENT_DIM,  # Borde sutil
		)
		header.grid(row=0, column=0, sticky='ew', padx=60, pady=(48, 0))
		header.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			header,
			text='🎉  ¡Bienvenido a CloudPOS!',
			font=('Arial', 28, 'bold'),
			text_color=ACCENT_TEXT,
		).grid(row=0, column=0, pady=(28, 6), padx=40, sticky='w')

		ctk.CTkLabel(
			header,
			text=(
				'Tu sistema está configurado y listo para usar. '
				'Completá estos pasos iniciales para sacarle el máximo provecho.'
			),
			font=('Arial', 13),
			text_color=ACCENT_TEXT,
			wraplength=700,
			justify='left',
			anchor='w',
		).grid(row=1, column=0, pady=(0, 24), padx=40, sticky='w')

		# ── Checklist ─────────────────────────────────────────────────────────
		for i, (icon, title, desc, done, section) in enumerate(_CHECKLIST):
			self._build_checklist_item(
				parent,
				row=i + 1,
				icon=icon,
				title=title,
				desc=desc,
				done=done,
				section=section,
			)

		# ── Botón principal ────────────────────────────────────────────────────
		ctk.CTkButton(
			parent,
			text='Ir al Dashboard  →',
			height=54,
			font=('Arial', 16, 'bold'),
			fg_color=GREEN_DIM,
			hover_color=GREEN,  # Cambio a verde afirmativo
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			corner_radius=10,
			command=lambda: self._done(None),
		).grid(row=len(_CHECKLIST) + 1, column=0, padx=60, pady=(28, 48), sticky='ew')

	def _build_checklist_item(self, parent, row, icon, title, desc, done, section):
		card = ctk.CTkFrame(
			parent,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		card.grid(row=row, column=0, sticky='ew', padx=60, pady=(16, 0))
		card.grid_columnconfigure(1, weight=1)

		status_color = GREEN if done else SURFACE3
		indicator = ctk.CTkFrame(card, fg_color=status_color, width=5, corner_radius=0)
		indicator.grid(row=0, column=0, rowspan=2, sticky='ns')

		lbl_icon = ctk.CTkLabel(card, text=icon, font=('Arial', 28))
		lbl_icon.grid(row=0, column=1, rowspan=2, padx=(20, 8), pady=20, sticky='w')

		text_frame = ctk.CTkFrame(card, fg_color='transparent')
		text_frame.grid(
			row=0, column=2, rowspan=2, sticky='nsew', padx=(0, 16), pady=16
		)
		text_frame.grid_columnconfigure(0, weight=1)

		title_color = GREEN_TEXT if done else TEXT_PRIMARY
		lbl_title = ctk.CTkLabel(
			text_frame,
			text=title,
			font=('Arial', 15, 'bold'),
			text_color=title_color,
			anchor='w',
		)
		lbl_title.grid(row=0, column=0, sticky='w')

		lbl_desc = ctk.CTkLabel(
			text_frame,
			text=desc,
			font=('Arial', 11),
			text_color=TEXT_MUTED,
			wraplength=520,
			justify='left',
			anchor='w',
		)
		lbl_desc.grid(row=1, column=0, sticky='w', pady=(2, 0))

		if done:
			lbl_done = ctk.CTkLabel(
				card,
				text='✓  Completado',
				font=('Arial', 12, 'bold'),
				text_color=GREEN_TEXT,
			)
			lbl_done.grid(row=0, column=3, rowspan=2, padx=(0, 24), pady=20)
		else:
			btn_action = ctk.CTkButton(
				card,
				text='Ir ahora →',
				width=120,
				height=36,
				font=('Arial', 12, 'bold'),
				fg_color=ORANGE_DIM,
				hover_color=ORANGE,
				text_color=ORANGE_TEXT,
				border_width=1,
				border_color=ORANGE,
				corner_radius=8,
				command=lambda s=section: self._done(s),
			)
			btn_action.grid(row=0, column=3, rowspan=2, padx=(0, 24), pady=20)

			# --- Interactividad de la tarjeta (Hover y Click) ---
			def on_enter(e, widget=card):
				widget.configure(fg_color=SURFACE3)

			def on_leave(e, widget=card):
				widget.configure(fg_color=SURFACE2)

			def on_click(e, s=section):
				self._done(s)

			for w in (card, lbl_icon, text_frame, lbl_title, lbl_desc):
				w.bind('<Enter>', on_enter)
				w.bind('<Leave>', on_leave)
				w.bind('<Button-1>', on_click)
				w.configure(cursor='hand2')

	def _done(self, section: str | None):
		cfg = _cfg_load()
		cfg['onboarding_shown'] = True
		_cfg_save(cfg)
		self._on_done(section)
