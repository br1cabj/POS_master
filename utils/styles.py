"""
Design System 2026 — CloudPOS Dark Pro
=======================================
Sistema de diseño basado en elevación por luminancia, accent glow,
bento grid y tipografía jerárquica para interfaces POS.
"""

from tkinter import ttk

import customtkinter as ctk

# ── Surfaces ──────────────────────────────────────────────────────────────────
BASE = '#0a0a0a'
SURFACE0 = '#111111'
SURFACE1 = '#171717'
SURFACE2 = '#1e1e1e'
SURFACE3 = '#252525'
SURFACE4 = '#2e2e2e'

# ── Borders ───────────────────────────────────────────────────────────────────
BORDER = '#2a2a2a'
BORDER_ACTIVE = '#3a3a3a'

# ── Accents ───────────────────────────────────────────────────────────────────
ACCENT = '#2563eb'
ACCENT_HOVER = '#1d4ed8'
ACCENT_DIM = '#1a2744'
ACCENT_TEXT = '#60a5fa'

GREEN = '#16a34a'
GREEN_TEXT = '#4ade80'
GREEN_DIM = '#052e16'
ORANGE = '#d97706'
ORANGE_TEXT = '#fbbf24'
ORANGE_DIM = '#2d1b00'
RED = '#dc2626'
RED_TEXT = '#f87171'
RED_DIM = '#2d0a0a'
PURPLE = '#7e22ce'
PURPLE_TEXT = '#a78bfa'
PURPLE_DIM = '#2d1a4a'

# ── Typography Colors ─────────────────────────────────────────────────────────
TEXT_PRIMARY = '#f0f0f0'
TEXT_SECONDARY = '#888888'
TEXT_MUTED = '#555555'
TEXT_DISABLED = '#3a3a3a'

# ── Spacing System ──────────────────────────────────────
PAD_XS = 4  # Detalles mínimos, separaciones internas de íconos
PAD_SM = 8  # Separación entre inputs o botones agrupados
PAD_MD = 16  # Padding estándar de contenedores y frames
PAD_LG = 24  # Separación entre secciones distintas
PAD_XL = 32  # Márgenes principales de las vistas

# ── Fonts ───────────────────────────────────────────────
FONT_LABEL = ('Arial', 10)
FONT_LABEL_BOLD = ('Arial', 10, 'bold')
FONT_BODY = ('Arial', 12)
FONT_BODY_BOLD = ('Arial', 12, 'bold')
FONT_HEADING = ('Arial', 14, 'bold')
FONT_TITLE = ('Arial', 18, 'bold')
FONT_NAV = ('Arial', 13)
FONT_NAV_BOLD = ('Arial', 13, 'bold')
FONT_STAT = ('Arial', 32, 'bold')
FONT_STAT_LG = ('Arial', 40, 'bold')
FONT_MONO = ('Consolas', 11)


# ── Treeview Configuration ────────────────────────────────────────────────────
def apply_treeview_style(style_name: str = 'Treeview') -> None:
	"""Configura el estilo base del componente ttk.Treeview."""
	style = ttk.Style()
	style.theme_use('default')
	style.configure(
		style_name,
		background=SURFACE2,
		foreground=TEXT_PRIMARY,
		rowheight=32,
		fieldbackground=SURFACE2,
		borderwidth=0,
		font=('Arial', 11),
	)
	style.map(style_name, background=[('selected', ACCENT_DIM)])
	style.map(style_name, foreground=[('selected', ACCENT_TEXT)])
	style.configure(
		f'{style_name}.Heading',
		background=SURFACE3,
		foreground=TEXT_SECONDARY,
		relief='flat',
		font=('Arial', 10, 'bold'),
	)
	style.map(
		f'{style_name}.Heading',
		background=[('active', SURFACE4)],
	)


def setup_treeview_tags(tree: ttk.Treeview) -> None:
	"""Aplica las etiquetas semánticas y de estilo a las filas de un Treeview."""
	tree.tag_configure('oddrow', background=SURFACE2)
	tree.tag_configure('evenrow', background=SURFACE1)
	tree.tag_configure('danger', foreground=RED_TEXT)
	tree.tag_configure('success', foreground=GREEN_TEXT)
	tree.tag_configure('warning', foreground=ORANGE_TEXT)


# ── UI Components ─────────────────────────────────────────────────────────────
def make_stat_card(parent, title: str, accent_color: str = ACCENT):
	"""Crea una tarjeta de estadística de diseño bento."""
	outer = ctk.CTkFrame(
		parent, fg_color=SURFACE2, corner_radius=12, border_width=1, border_color=BORDER
	)

	accent_bar = ctk.CTkFrame(outer, fg_color=accent_color, width=4, corner_radius=0)
	accent_bar.pack(side='left', fill='y')

	content = ctk.CTkFrame(outer, fg_color='transparent')
	content.pack(side='left', fill='both', expand=True, padx=PAD_MD, pady=14)

	lbl_title = ctk.CTkLabel(
		content,
		text=title.upper(),
		font=FONT_LABEL_BOLD,
		text_color=TEXT_MUTED,
	)
	lbl_title.pack(anchor='w')

	lbl_value = ctk.CTkLabel(
		content,
		text='—',
		font=FONT_STAT,
		text_color=accent_color,
	)
	lbl_value.pack(anchor='w', pady=(PAD_XS, 0))

	lbl_sub = ctk.CTkLabel(
		content,
		text='',
		font=FONT_LABEL,
		text_color=TEXT_MUTED,
	)
	lbl_sub.pack(anchor='w')

	return outer, lbl_value, lbl_sub


def make_section_label(parent, text: str):
	"""Etiqueta de jerarquía secundaria para agrupar elementos."""
	return ctk.CTkLabel(
		parent,
		text=text.upper(),
		font=('Arial', 9, 'bold'),
		text_color=TEXT_MUTED,
		anchor='w',
	)


def make_form_label(parent, text: str, required: bool = False):
	"""Etiqueta para inputs de formulario con indicador visual de obligatoriedad."""
	container = ctk.CTkFrame(parent, fg_color='transparent')

	lbl = ctk.CTkLabel(
		container,
		text=text.upper(),
		font=('Arial', 9, 'bold'),
		text_color=TEXT_MUTED,
	)
	lbl.pack(side='left')

	if required:
		ast = ctk.CTkLabel(
			container,
			text=' *',
			font=FONT_LABEL_BOLD,
			text_color=RED_TEXT,
		)
		ast.pack(side='left')

	return container


def make_nav_button(parent, icon: str, label: str, command, active: bool = False):
	"""Botón de navegación primario (Sidebar)."""
	fg = ACCENT_DIM if active else 'transparent'
	txt = ACCENT_TEXT if active else TEXT_SECONDARY

	return ctk.CTkButton(
		parent,
		text=f'  {icon}  {label}',
		anchor='w',
		fg_color=fg,
		hover_color=SURFACE3,
		text_color=txt,
		font=FONT_NAV,
		height=38,
		corner_radius=8,
		border_width=0,
		cursor='hand2',
		command=command,
	)


def make_toggle_button(parent, text: str, command, active: bool = False):
	"""Botón de estado o filtro secundario."""
	fg = SURFACE4 if active else SURFACE2
	txt_color = TEXT_PRIMARY if active else TEXT_SECONDARY
	brd_color = BORDER_ACTIVE if active else BORDER

	return ctk.CTkButton(
		parent,
		text=text,
		fg_color=fg,
		hover_color=SURFACE3,
		text_color=txt_color,
		border_width=1,
		border_color=brd_color,
		height=32,
		corner_radius=6,
		command=command,
	)


def section_divider(parent):
	"""Separador de secciones."""
	return ctk.CTkFrame(parent, height=1, fg_color=BORDER, corner_radius=0)
