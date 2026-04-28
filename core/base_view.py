from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from utils.styles import SURFACE1

if TYPE_CHECKING:
	from core.context import AppContext


class BaseView(ctk.CTkFrame):
	"""Base class for all application views.

	Provides access to AppContext and a uniform set of UI feedback helpers
	so individual views don't duplicate dialog calls or resource cleanup.
	"""

	def __init__(self, master, ctx: 'AppContext', **kwargs):
		kwargs.setdefault('fg_color', SURFACE1)
		super().__init__(master, **kwargs)
		self.ctx = ctx
		self._pending_jobs: list = []

	def load_data(self) -> None:
		"""Override in subclasses to (re)populate the view from the database."""

	def show_error(self, message: str, title: str = 'Error') -> None:
		CTkMessagebox(title=title, message=message, icon='cancel')

	def show_success(self, message: str, title: str = 'Éxito') -> None:
		CTkMessagebox(title=title, message=message, icon='check')

	def show_warning(self, message: str, title: str = 'Atención') -> None:
		CTkMessagebox(title=title, message=message, icon='warning')

	def confirm(self, message: str, title: str = 'Confirmar') -> bool:
		"""Returns True if the user confirms, False otherwise."""
		return (
			CTkMessagebox(
				title=title,
				message=message,
				icon='question',
				option_1='No',
				option_2='Sí',
			).get()
			== 'Sí'
		)

	def schedule(self, delay_ms: int, callback) -> str:
		"""Schedules a callback and tracks it for cleanup on destroy."""
		job = self.after(delay_ms, callback)
		self._pending_jobs.append(job)
		return job

	def destroy(self) -> None:
		for job in self._pending_jobs:
			try:
				self.after_cancel(job)
			except Exception:
				pass
		self._pending_jobs.clear()
		super().destroy()
