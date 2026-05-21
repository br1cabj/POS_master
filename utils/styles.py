"""
Design System 2026 — CloudPOS Dark Pro
=======================================
Sistema de diseño basado en elevación por luminancia, accent glow,
bento grid y tipografía jerárquica para interfaces POS.
"""

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional, Tuple, Union

import customtkinter as ctk

WidgetParent = Union[ctk.CTkBaseClass, tk.Widget]

BASE = '#0a0a0a'
SURFACE0 = '#111111'
SURFACE1 = '#171717'
SURFACE2 = '#1e1e1e'
SURFACE3 = '#252525'
SURFACE4 = '#2e2e2e'

BORDER = '#2a2a2a'
BORDER_ACTIVE = '#3a3a3a'

ACCENT = '#2563eb'
ACCENT_HOVER = '#1d4ed8'
ACCENT_DIM = '#1a2744'
ACCENT_TEXT = '#60a5fa'

GREEN = '#16a34a'
GREEN_TEXT = '#4ade80'
GREEN_DIM = '#052e16'
GREEN_HOVER = '#15803d'
GREEN_MID = '#14532d'

ORANGE = '#d97706'
ORANGE_TEXT = '#fbbf24'
ORANGE_DIM = '#2d1b00'
RED = '#dc2626'
RED_HOVER = '#b91c1c'
RED_TEXT = '#f87171'
RED_DIM = '#2d0a0a'
PURPLE = '#7e22ce'
PURPLE_TEXT = '#a78bfa'
PURPLE_DIM = '#2d1a4a'

# Colores específicos para etiquetas (Labels)
LBL_HEADER_DARK = '#1e293b'
LBL_HEADER_DEEP = '#0f172a'
LBL_HEADER_ORANGE = '#f77f00'
LBL_BLUE = '#2563eb'
LBL_RED = '#dc2626'

TEXT_PRIMARY = '#f0f0f0'
TEXT_SECONDARY = '#888888'
TEXT_MUTED = '#737373'
TEXT_DISABLED = '#525252'

PAD_XS = 4
PAD_SM = 8
PAD_MD = 16
PAD_LG = 24
PAD_XL = 32

FONT_FAMILY = 'Arial'
FONT_FAMILY_MONO = 'Consolas'

FONT_LABEL = (FONT_FAMILY, 10)
FONT_LABEL_BOLD = (FONT_FAMILY, 10, 'bold')
FONT_SMALL = (FONT_FAMILY, 11)
FONT_SMALL_BOLD = (FONT_FAMILY, 11, 'bold')
FONT_BODY = (FONT_FAMILY, 12)
FONT_BODY_BOLD = (FONT_FAMILY, 12, 'bold')
FONT_SUBHEADING = (FONT_FAMILY, 14)
FONT_HEADING = (FONT_FAMILY, 14, 'bold')
FONT_TITLE = (FONT_FAMILY, 18, 'bold')
FONT_LOGO = (FONT_FAMILY, 38, 'bold')
FONT_NAV = (FONT_FAMILY, 13)
FONT_NAV_BOLD = (FONT_FAMILY, 13, 'bold')
FONT_STAT = (FONT_FAMILY, 32, 'bold')
FONT_STAT_LG = (FONT_FAMILY, 40, 'bold')
FONT_MONO = (FONT_FAMILY_MONO, 11)

FONT_SUBHEADING_BOLD = (FONT_FAMILY, 15, 'bold')
FONT_TITLE_SM = (FONT_FAMILY, 16, 'bold')
FONT_INPUT_LG = (FONT_FAMILY, 18)
FONT_XL_BOLD = (FONT_FAMILY, 20, 'bold')
FONT_AMOUNT = (FONT_FAMILY, 24)
FONT_AMOUNT_BOLD = (FONT_FAMILY, 24, 'bold')
FONT_DISPLAY = (FONT_FAMILY, 44, 'bold')
FONT_DISPLAY_LG = (FONT_FAMILY, 46, 'bold')


def apply_treeview_style(style_name: str = 'Treeview') -> None:
	style = ttk.Style()
	style.theme_use('default')

	style.layout(style_name, [(f'{style_name}.treearea', {'sticky': 'nswe'})])

	style.configure(
		style_name,
		background=SURFACE2,
		foreground=TEXT_PRIMARY,
		rowheight=32,
		fieldbackground=SURFACE2,
		borderwidth=0,
		font=FONT_SMALL,
	)
	style.map(style_name, background=[('selected', ACCENT_DIM)])
	style.map(style_name, foreground=[('selected', ACCENT_TEXT)])

	style.configure(
		f'{style_name}.Heading',
		background=SURFACE3,
		foreground=TEXT_SECONDARY,
		relief='flat',
		font=FONT_LABEL_BOLD,
	)
	style.map(
		f'{style_name}.Heading',
		background=[('active', SURFACE4)],
	)


def setup_treeview_tags(tree: ttk.Treeview) -> None:
	tree.tag_configure('oddrow', background=SURFACE2, foreground=TEXT_PRIMARY)
	tree.tag_configure('evenrow', background=SURFACE1, foreground=TEXT_PRIMARY)
	tree.tag_configure('danger', foreground=RED_TEXT)
	tree.tag_configure('success', foreground=GREEN_TEXT)
	tree.tag_configure('warning', foreground=ORANGE_TEXT)


def make_stat_card(
	parent: WidgetParent, title: str, accent_color: str = ACCENT
) -> Tuple[ctk.CTkFrame, ctk.CTkLabel, ctk.CTkLabel]:
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


def make_section_label(parent: WidgetParent, text: str) -> ctk.CTkLabel:
	return ctk.CTkLabel(
		parent,
		text=text.upper(),
		font=FONT_LABEL_BOLD,
		text_color=TEXT_MUTED,
		anchor='w',
	)


def make_form_label(
	parent: WidgetParent, text: str, required: bool = False
) -> Tuple[ctk.CTkFrame, ctk.CTkLabel]:
	container = ctk.CTkFrame(parent, fg_color='transparent')

	lbl = ctk.CTkLabel(
		container,
		text=text.upper(),
		font=FONT_LABEL_BOLD,
		text_color=TEXT_MUTED,
	)
	lbl.pack(side='left')

	if required:
		ctk.CTkLabel(
			container,
			text=' *',
			font=FONT_LABEL_BOLD,
			text_color=RED_TEXT,
		).pack(side='left')

	return container, lbl


def make_nav_button(
	parent: WidgetParent,
	icon: str,
	label: str,
	command: Callable,
	active: bool = False,
	shortcut: Optional[str] = None,
) -> ctk.CTkButton:
	fg = ACCENT_DIM if active else 'transparent'
	txt = ACCENT_TEXT if active else TEXT_SECONDARY
	display_text = (
		f'  {icon}  {label}  [{shortcut}]' if shortcut else f'  {icon}  {label}'
	)

	return ctk.CTkButton(
		parent,
		text=display_text,
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


def make_toggle_button(
	parent: WidgetParent, text: str, command: Callable, active: bool = False
) -> ctk.CTkButton:
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


def section_divider(parent: WidgetParent) -> ctk.CTkFrame:
	return ctk.CTkFrame(parent, height=1, fg_color=BORDER, corner_radius=0)


def make_input_field(parent: WidgetParent, placeholder: str = '') -> ctk.CTkEntry:
	return ctk.CTkEntry(
		parent,
		placeholder_text=placeholder,
		font=FONT_BODY,
		fg_color=SURFACE1,
		border_color=BORDER,
		text_color=TEXT_PRIMARY,
		placeholder_text_color=TEXT_MUTED,
		height=38,
		corner_radius=6,
		border_width=1,
	)


def make_action_button(
	parent: WidgetParent,
	text: str,
	command: Callable,
	variant: str = 'primary',
	shortcut: Optional[str] = None,
) -> ctk.CTkButton:
	if variant == 'primary':
		fg = ACCENT
		hover = ACCENT_HOVER
		txt = TEXT_PRIMARY
	elif variant == 'danger':
		fg = RED
		hover = RED_HOVER
		txt = TEXT_PRIMARY
	else:
		fg = SURFACE3
		hover = SURFACE4
		txt = TEXT_PRIMARY

	display_text = f'{text}  [{shortcut}]' if shortcut else text

	return ctk.CTkButton(
		parent,
		text=display_text,
		command=command,
		font=FONT_BODY_BOLD,
		fg_color=fg,
		hover_color=hover,
		text_color=txt,
		height=42,
		corner_radius=6,
	)
