"""
views/sales_history_view.py
============================
Vista combinada de ventas e historial.
Contiene dos pestañas:
  · 📜 Historial de Ventas  (HistoryView)
  · ↩  Devoluciones         (ReturnsView)
"""

import customtkinter as ctk

from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	FONT_NAV_BOLD,
	SURFACE0,
	SURFACE3,
	TEXT_MUTED,
)
from views.history_view import HistoryView
from views.returns_view import ReturnsView

_TABS = [
	('📜', 'Historial de Ventas', HistoryView),
	('↩', 'Devoluciones', ReturnsView),
]


class SalesHistoryView(BaseView):
	"""Wrapper con tabs para historial de ventas y devoluciones."""

	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)

		self._active_idx = 0
		self._tab_btns: list = []
		self._content_frame = None
		self._loaded_views = {}  # Mapea idx -> (frame, view_instance)

		# ── Tab bar ───────────────────────────────────────────────────────
		tab_bar = ctk.CTkFrame(
			self,
			fg_color=SURFACE0,
			corner_radius=0,
			border_width=1,
			border_color=BORDER,
			height=46,
		)
		tab_bar.pack(fill='x')
		tab_bar.pack_propagate(False)

		inner_bar = ctk.CTkFrame(tab_bar, fg_color='transparent')
		inner_bar.pack(side='left', padx=12, fill='y')

		for i, (icon, label, _) in enumerate(_TABS):
			btn = ctk.CTkButton(
				inner_bar,
				text=f'{icon}  {label}',
				width=190,
				height=32,
				font=FONT_NAV_BOLD,
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
		self._content_frame = ctk.CTkFrame(
			self, fg_color='transparent', corner_radius=0
		)
		self._content_frame.pack(fill='both', expand=True)

		# Cargar la primera pestaña por defecto
		self._switch_tab(0)

	# ─────────────────────────────────────────────────────────────────────
	def _switch_tab(self, idx: int):
		self._active_idx = idx

		# 1. Ocultar todas las vistas cargadas excepto la activa
		for i, (frame, _) in self._loaded_views.items():
			if i != idx:
				frame.pack_forget()

		# 2. Lazy load: Instanciar la vista solo si no ha sido cargada previamente
		already_loaded = idx in self._loaded_views
		if not already_loaded:
			_, _, view_cls = _TABS[idx]
			frame = ctk.CTkFrame(
				self._content_frame, fg_color='transparent', corner_radius=0
			)
			view_instance = view_cls(frame, self.ctx)
			view_instance.pack(fill='both', expand=True)
			self._loaded_views[idx] = (frame, view_instance)

		# 3. Mostrar el frame contenedor de la vista
		frame, view_instance = self._loaded_views[idx]
		frame.pack(fill='both', expand=True)

		# 4. Refrescar datos solo al volver a una pestaña ya cargada (evita doble carga en lazy init)
		if already_loaded:
			if hasattr(view_instance, 'load_history'):
				view_instance.load_history()
			elif hasattr(view_instance, 'load_sales'):
				view_instance.load_sales()

		# 5. Actualizar estilos visuales de los botones de las pestañas
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

		# 6. Mover el foco del teclado a la vista activa
		self.set_initial_focus()

	def destroy_custom(self):
		for _, view_instance in self._loaded_views.values():
			if hasattr(view_instance, 'destroy_custom'):
				try:
					view_instance.destroy_custom()
				except Exception:
					pass

	def set_initial_focus(self):
		"""Delega el enfoque inicial a la sub-vista que esté activa actualmente."""
		if self._active_idx in self._loaded_views:
			_, view_instance = self._loaded_views[self._active_idx]
			if hasattr(view_instance, 'set_initial_focus'):
				view_instance.set_initial_focus()
