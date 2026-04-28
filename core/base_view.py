from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from utils.styles import SURFACE1

if TYPE_CHECKING:
	from core.context import AppContext


class BaseView(ctk.CTkFrame):
	"""Clase base para todas las vistas de la aplicación.

	Provee acceso al AppContext, utilidades de feedback visual (popups),
	recolección de basura de procesos en segundo plano (after_cancel) y
	controladores de concurrencia (debounce).
	"""

	def __init__(self, master, ctx: 'AppContext', **kwargs):
		kwargs.setdefault('fg_color', SURFACE1)
		super().__init__(master, **kwargs)
		self.ctx = ctx
		self._pending_jobs: list[str] = []
		self._debounce_timers: dict[str, str] = {}

	def load_data(self) -> None:
		"""Sobrescribir en las subclases para poblar la vista desde la base de datos."""
		pass

	# ── Utilidades de Interfaz ──────────────────────────────────────

	def show_error(self, message: str, title: str = 'Error') -> None:
		"""Muestra un mensaje de error garantizando que esté por encima de todo."""
		CTkMessagebox(title=title, message=message, icon='cancel', fade_in_duration=200)

	def show_success(self, message: str, title: str = 'Éxito') -> None:
		"""Muestra un mensaje de éxito."""
		CTkMessagebox(title=title, message=message, icon='check', fade_in_duration=200)

	def show_warning(self, message: str, title: str = 'Atención') -> None:
		"""Muestra una advertencia al usuario."""
		CTkMessagebox(
			title=title, message=message, icon='warning', fade_in_duration=200
		)

	def confirm(self, message: str, title: str = 'Confirmar') -> bool:
		"""Muestra un diálogo de Sí/No. Retorna True si el usuario confirma."""
		msg = CTkMessagebox(
			title=title,
			message=message,
			icon='question',
			option_1='No',
			option_2='Sí',
			fade_in_duration=200,
		)
		return msg.get() == 'Sí'

	# ── Controladores de Tiempo y Memoria ─────────────────────────────────────

	def schedule(self, delay_ms: int, callback: Callable) -> str:
		"""Programa un callback (after) y lo rastrea para limpiarlo si se destruye la vista."""
		job = self.after(delay_ms, callback)
		self._pending_jobs.append(job)
		return job

	def debounce(self, delay_ms: int, callback: Callable, key: str = 'default') -> None:
		"""
		Ejecuta un callback solo después de que hayan pasado `delay_ms` milisegundos
		sin que se vuelva a llamar a esta función con la misma `key`.
		Ideal para barras de búsqueda (KeyRelease).
		"""
		if key in self._debounce_timers:
			try:
				self.after_cancel(self._debounce_timers[key])
			except Exception:
				pass

		self._debounce_timers[key] = self.after(delay_ms, callback)

	def destroy(self) -> None:
		"""Destrucción segura de la vista limpiando todos los hilos pendientes."""
		for job in self._pending_jobs:
			try:
				self.after_cancel(job)
			except Exception:
				pass
		self._pending_jobs.clear()

		for timer_id in self._debounce_timers.values():
			try:
				self.after_cancel(timer_id)
			except Exception:
				pass
		self._debounce_timers.clear()

		super().destroy()
