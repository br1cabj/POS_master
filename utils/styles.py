# utils/styles.py
"""
Centralized UI style utilities for the POS application.
Import apply_treeview_style() in every view instead of repeating
the 18-line ttk.Style block.
"""
from tkinter import ttk

# ── Colour palette ────────────────────────────────────────────────────────────
BG_DARK = '#2b2b2b'
BG_PANEL = '#1e1e1e'
ACCENT_BLUE = '#1f538d'
ACCENT_GREEN = '#5cb85c'
ACCENT_ORANGE = '#e68a00'
ACCENT_RED = '#c0392b'
FG_WHITE = 'white'
FG_GRAY = 'gray'
HEADING_BG = '#565b5e'
ROW_HEIGHT = 30

# ── Font constants ────────────────────────────────────────────────────────────
FONT_NORMAL = ('Arial', 10)
FONT_BOLD = ('Arial', 10, 'bold')
FONT_HEADING = ('Arial', 10, 'bold')
FONT_LARGE = ('Arial', 14, 'bold')
FONT_TITLE = ('Arial', 18, 'bold')


def apply_treeview_style(style_name: str = 'Treeview') -> None:
    """
    Apply the standard dark-theme style to ttk.Treeview widgets.

    Call this once per view's __init__, before creating any Treeview:

        from utils.styles import apply_treeview_style
        apply_treeview_style()

    An optional *style_name* lets you create a scoped style variant
    (e.g. 'MyView.Treeview') without affecting other views.
    """
    style = ttk.Style()
    style.theme_use('default')
    style.configure(
        style_name,
        background=BG_DARK,
        foreground=FG_WHITE,
        rowheight=ROW_HEIGHT,
        fieldbackground=BG_DARK,
        borderwidth=0,
    )
    style.map(style_name, background=[('selected', ACCENT_BLUE)])
    style.configure(
        f'{style_name}.Heading',
        background=HEADING_BG,
        foreground=FG_WHITE,
        relief='flat',
        font=FONT_HEADING,
    )
