# utils/styles.py
"""
Design System 2026 — CloudPOS Dark Pro
=======================================
Basado en tendencias 2026: true-black base, elevación por luminancia
(no shadows), accent glow, bento grid, tipografía ultra-jerárquica.

Paleta de elevación (surfaces van de oscuro → claro conforme "suben"):
  BASE      #0a0a0a   ventana / fondo del sistema operativo
  SURFACE0  #111111   sidebar
  SURFACE1  #171717   main area bg
  SURFACE2  #1e1e1e   cards, panels
  SURFACE3  #252525   hover states, inputs
  SURFACE4  #2e2e2e   dropdowns, borders activos
  BORDER    #ffffff0d borde sutilísimo (8% blanco)
  BORDER_HV #ffffff18 borde hover (10% blanco)
"""
from tkinter import ttk

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

# ── Accent — Azul eléctrico ───────────────────────────────────────────────────
ACCENT = '#2563eb'
ACCENT_HOVER = '#1d4ed8'
ACCENT_DIM = '#1a2744'        # fondo nav activo
ACCENT_TEXT = '#60a5fa'       # texto sobre fondo oscuro

# ── Accents semánticos ────────────────────────────────────────────────────────
GREEN = '#16a34a'
GREEN_TEXT = '#4ade80'
GREEN_DIM = '#052e16'
ORANGE = '#d97706'
ORANGE_TEXT = '#fbbf24'
ORANGE_DIM = '#2d1b00'
RED = '#dc2626'
RED_TEXT = '#f87171'
RED_DIM = '#2d0a0a'
PURPLE_TEXT = '#a78bfa'

# ── Texto ─────────────────────────────────────────────────────────────────────
TEXT_PRIMARY = '#f0f0f0'
TEXT_SECONDARY = '#888888'
TEXT_MUTED = '#555555'
TEXT_DISABLED = '#3a3a3a'

# ── Fuentes ───────────────────────────────────────────────────────────────────
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


# ── Treeview ──────────────────────────────────────────────────────────────────
def apply_treeview_style(style_name: str = 'Treeview') -> None:
    """
    Aplica el estilo dark-pro al ttk.Treeview.
    Llamar una vez en el __init__ de cada vista antes de crear el Treeview.
    """
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


# ── Card helpers ──────────────────────────────────────────────────────────────
def make_stat_card(parent, title: str, accent_color: str = ACCENT):
    """
    Crea una tarjeta de estadística estilo Dark Pro 2026.
    Devuelve (card_frame, value_label) para que la vista actualice el valor.

    Estructura visual:
      ┌─[accent 3px]────────────────────────┐
      │  TITULO (uppercase, muted)           │
      │  $0.00  (stat font, accent color)    │
      │  subtítulo (muted, small)            │
      └─────────────────────────────────────┘
    """
    import customtkinter as ctk

    outer = ctk.CTkFrame(parent, fg_color=SURFACE2, corner_radius=12,
                         border_width=1, border_color=BORDER)

    # Barra de acento izquierda (simulada con un frame estrecho)
    accent_bar = ctk.CTkFrame(outer, fg_color=accent_color,
                               width=4, corner_radius=0)
    accent_bar.pack(side='left', fill='y')

    content = ctk.CTkFrame(outer, fg_color='transparent')
    content.pack(side='left', fill='both', expand=True, padx=16, pady=14)

    lbl_title = ctk.CTkLabel(
        content,
        text=title.upper(),
        font=('Arial', 10, 'bold'),
        text_color=TEXT_MUTED,
    )
    lbl_title.pack(anchor='w')

    lbl_value = ctk.CTkLabel(
        content,
        text='—',
        font=FONT_STAT,
        text_color=accent_color,
    )
    lbl_value.pack(anchor='w', pady=(4, 0))

    lbl_sub = ctk.CTkLabel(
        content,
        text='',
        font=('Arial', 10),
        text_color=TEXT_MUTED,
    )
    lbl_sub.pack(anchor='w')

    return outer, lbl_value, lbl_sub


def make_section_label(parent, text: str):
    """Etiqueta de sección del sidebar (uppercase, muted, tiny)."""
    import customtkinter as ctk
    return ctk.CTkLabel(
        parent,
        text=text.upper(),
        font=('Arial', 9, 'bold'),
        text_color=TEXT_MUTED,
        anchor='w',
    )


def make_nav_button(parent, icon: str, label: str, command, active: bool = False):
    """
    Botón de navegación sidebar estilo pill.
    - Normal:  fondo transparente, texto gris
    - Hover:   fondo SURFACE3
    - Activo:  fondo ACCENT_DIM, texto ACCENT_TEXT
    """
    import customtkinter as ctk

    fg = ACCENT_DIM if active else 'transparent'
    txt = ACCENT_TEXT if active else TEXT_SECONDARY
    hover = SURFACE3

    btn = ctk.CTkButton(
        parent,
        text=f'  {icon}  {label}',
        anchor='w',
        fg_color=fg,
        hover_color=hover,
        text_color=txt,
        font=FONT_NAV,
        height=38,
        corner_radius=8,
        border_width=0,
        cursor='hand2',
        command=command,
    )
    return btn


def section_divider(parent):
    """Línea divisoria ultra-sutil para el sidebar."""
    import customtkinter as ctk
    return ctk.CTkFrame(parent, height=1, fg_color=BORDER, corner_radius=0)
