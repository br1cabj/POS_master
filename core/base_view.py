from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from utils.styles import BORDER, SURFACE1, setup_treeview_tags

if TYPE_CHECKING:
	from tkinter import ttk

	from core.context import AppContext


class BaseView(ctk.CTkFrame):
	"""
	Clase base para todas las vistas de la aplicación.
	Provee contexto, utilidades visuales, gestión de tablas y control de hilos.
	"""

	def __init__(self, master, ctx: 'AppContext', **kwargs):
		kwargs.setdefault('fg_color', SURFACE1)
		super().__init__(master, **kwargs)
		self.ctx = ctx
		self._pending_jobs: list[str] = []
		self._debounce_timers: dict[str, str] = {}

	def load_data(self) -> None:
		"""Sobrescribir en subclases para poblar la vista desde la base de datos."""
		pass

	# ── Gestión de Treeviews (Zebra Striping y Tags) ─────────────────────────

	def init_treeview(self, tree: ttk.Treeview) -> None:
		"""Aplica las configuraciones de diseño base al Treeview."""
		setup_treeview_tags(tree)

	def insert_tree_row(
		self, tree: ttk.Treeview, index: int, values: tuple, tags: tuple = ()
	) -> str:
		"""
		Inserta una fila manejando automáticamente el color alterno (zebra striping)
		y combinándolo con tags adicionales (ej: 'danger', 'success').
		"""
		stripe_tag = 'evenrow' if index % 2 == 0 else 'oddrow'
		final_tags = (stripe_tag,) + tags
		return tree.insert('', 'end', values=values, tags=final_tags)

	# ── Utilidades de Interfaz ───────────────────────────────────────────────

	def show_error(self, message: str, title: str = 'Error') -> None:
		"""Muestra mensaje de error en capa superior."""
		CTkMessagebox(title=title, message=message, icon='cancel', fade_in_duration=200)

	def show_success(self, message: str, title: str = 'Éxito') -> None:
		"""Muestra mensaje de éxito."""
		CTkMessagebox(title=title, message=message, icon='check', fade_in_duration=200)

	def show_warning(self, message: str, title: str = 'Atención') -> None:
		"""Muestra advertencia."""
		CTkMessagebox(
			title=title, message=message, icon='warning', fade_in_duration=200
		)

	# ── Feedback Visual Inline ───────────────────────────────────────────────

	def set_loading(
		self, btn: ctk.CTkButton, loading: bool, original_text: str = ''
	) -> None:
		"""Alterna estado de carga en botones para operaciones asíncronas."""
		if loading:
			btn.configure(state='disabled', text='Procesando…')
		else:
			btn.configure(state='normal', text=original_text)

	def mark_field_error(self, entry: ctk.CTkEntry, message: str | None = None) -> None:
		"""Resalta un input con error de validación."""
		entry.configure(border_color='#f87171')
		entry.focus()

	def clear_field_errors(self, *entries: ctk.CTkEntry) -> None:
		"""Restaura el estado visual normal de los inputs."""
		for entry in entries:
			try:
				entry.configure(border_color=BORDER)
			except Exception:
				pass

	def show_empty_state(
		self,
		container: ctk.CTkFrame,
		message: str = 'No hay datos para mostrar.',
		icon: str = '📭',
	) -> None:
		"""Renderiza un estado vacío centrado en el contenedor proporcionado."""
		lbl = ctk.CTkLabel(
			container,
			text=f'{icon}\n{message}',
			font=('Arial', 13),
			text_color='#64748b',
			justify='center',
		)
		lbl.pack(expand=True, pady=40)

	# ── Gestión de Estados ───────────────────────────────────────────────────

	def has_unsaved_changes(self) -> bool:
		"""Retorna True si la vista tiene formularios sucios."""
		return False

	def confirm(self, message: str, title: str = 'Confirmar') -> bool:
		"""Despliega diálogo de confirmación booleano."""
		msg = CTkMessagebox(
			title=title,
			message=message,
			icon='question',
			option_1='No',
			option_2='Sí',
			fade_in_duration=200,
		)
		return msg.get() == 'Sí'

	# ── Controladores de Tiempo y Memoria ────────────────────────────────────

	def schedule(self, delay_ms: int, callback: Callable) -> str:
		"""Programa ejecución diferida rastreable para limpieza segura."""
		job = self.after(delay_ms, callback)
		self._pending_jobs.append(job)
		return job

	def debounce(self, delay_ms: int, callback: Callable, key: str = 'default') -> None:
		"""Limita la tasa de ejecución de una función (ej: tipeo en barra de búsqueda)."""
		if key in self._debounce_timers:
			try:
				self.after_cancel(self._debounce_timers[key])
			except Exception:
				pass

		self._debounce_timers[key] = self.after(delay_ms, callback)

	def destroy(self) -> None:
		"""Destructor seguro: limpia colas de eventos antes de eliminar la UI."""
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
