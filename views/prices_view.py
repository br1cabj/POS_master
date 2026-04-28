"""
views/prices_view.py
====================
Vista combinada de gestión de precios.
Contiene dos pestañas:
  · 💵 Precios al Dólar   (DollarPriceView)
  · 📈 Ajuste de Precios  (PriceUpdateView)
"""
import customtkinter as ctk

from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
    ACCENT, ACCENT_DIM, ACCENT_TEXT, BORDER,
    SURFACE0, SURFACE2, SURFACE3,
    TEXT_MUTED, TEXT_SECONDARY,
)

# Importaciones diferidas para evitar ciclos de importación
from views.dollar_price_view import DollarPriceView
from views.price_update_view import PriceUpdateView


_TABS = [
    ('💵', 'Precios al Dólar',  DollarPriceView),
    ('📈', 'Ajuste de Precios', PriceUpdateView),
]


class PricesView(BaseView):
    """Wrapper con tabs para las vistas de gestión de precios."""

    def __init__(self, master, ctx: AppContext):
        super().__init__(master, ctx)

        self._active_idx = 0
        self._tab_btns: list = []
        self._frames: list = []

        # ── Tab bar ───────────────────────────────────────────────────────
        tab_bar = ctk.CTkFrame(
            self, fg_color=SURFACE0, corner_radius=0,
            border_width=1, border_color=BORDER, height=46,
        )
        tab_bar.pack(fill='x')
        tab_bar.pack_propagate(False)

        inner_bar = ctk.CTkFrame(tab_bar, fg_color='transparent')
        inner_bar.pack(side='left', padx=12, fill='y')

        for i, (icon, label, _) in enumerate(_TABS):
            btn = ctk.CTkButton(
                inner_bar,
                text=f'{icon}  {label}',
                width=180, height=32,
                font=('Arial', 13, 'bold'),
                fg_color='transparent',
                hover_color=SURFACE3,
                text_color=TEXT_MUTED,
                border_width=0,
                corner_radius=8,
                command=lambda idx=i: self._switch_tab(idx),
            )
            btn.pack(side='left', padx=(0, 4), pady=7)
            self._tab_btns.append(btn)

        # ── Contenedor de sub-vistas ──────────────────────────────────────
        content = ctk.CTkFrame(self, fg_color='transparent', corner_radius=0)
        content.pack(fill='both', expand=True)

        for _, _, view_cls in _TABS:
            frame = ctk.CTkFrame(content, fg_color='transparent', corner_radius=0)
            view_cls(frame, ctx).pack(fill='both', expand=True)
            self._frames.append(frame)

        self._switch_tab(0)

    # ─────────────────────────────────────────────────────────────────────
    def _switch_tab(self, idx: int):
        self._active_idx = idx

        # Ocultar todos, mostrar el activo
        for i, frame in enumerate(self._frames):
            if i == idx:
                frame.pack(fill='both', expand=True)
            else:
                frame.pack_forget()

        # Resaltar botón activo
        for i, btn in enumerate(self._tab_btns):
            if i == idx:
                btn.configure(
                    fg_color=ACCENT_DIM,
                    text_color=ACCENT_TEXT,
                    border_width=1,
                    border_color=ACCENT,
                )
            else:
                btn.configure(
                    fg_color='transparent',
                    text_color=TEXT_MUTED,
                    border_width=0,
                )
