from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from utils.styles import (
	BORDER,
	FONT_NAV,
	RED_TEXT,
	SURFACE1,
	TEXT_MUTED,
	setup_treeview_tags,
)

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
		self._empty_state_widget: ctk.CTkLabel | None = None

	def load_data(self) -> None:
		"""Sobrescribir en subclases para poblar la vista desde la base de datos."""
		pass

	# ── Gestión de Treeviews (Zebra Striping y Tags) ─────────────────────────

	def init_treeview(self, tree: 'ttk.Treeview') -> None:
		"""Aplica las configuraciones de diseño base al Treeview."""
		setup_treeview_tags(tree)

	def insert_tree_row(
		self, tree: 'ttk.Treeview', index: int, values: tuple, tags: tuple = ()
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
		"""Muestra error — usa toast si está disponible, si no modal bloqueante."""
		if hasattr(self.ctx, 'show_toast') and callable(self.ctx.show_toast):
			self.ctx.show_toast(message, 'error')
		else:
			CTkMessagebox(
				title=title, message=message, icon='cancel', fade_in_duration=200
			)

	def show_success(self, message: str, title: str = 'Éxito') -> None:
		"""Muestra éxito — usa toast si está disponible, si no modal bloqueante."""
		if hasattr(self.ctx, 'show_toast') and callable(self.ctx.show_toast):
			self.ctx.show_toast(message, 'success')
		else:
			CTkMessagebox(
				title=title, message=message, icon='check', fade_in_duration=200
			)

	def show_warning(self, message: str, title: str = 'Atención') -> None:
		"""Muestra advertencia modal bloqueante (requiere atención del usuario)."""
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
		"""Resalta un input con error de validación y muestra el mensaje si se provee."""
		entry.configure(border_color=RED_TEXT)
		entry.focus()
		if message:
			self.show_warning(message)

	def clear_field_errors(self, *entries: ctk.CTkEntry) -> None:
		"""Restaura el estado visual normal de los inputs."""
		for entry in entries:
			try:
				entry.configure(border_color=BORDER)
			except Exception:
				pass

	def show_toast(
		self, message: str, type_: str = 'success', duration: int = 3000
	) -> None:
		"""
		Muestra notificación flotante no bloqueante (delega a ctx.show_toast).
		Fallback a modal si ctx.show_toast no está disponible aún (ej: login, wizard).
		"""
		if hasattr(self.ctx, 'show_toast') and callable(self.ctx.show_toast):
			self.ctx.show_toast(message, type_, duration)
		else:
			# Fallback para pantallas que no tienen MainDashboard activo
			icon_map = {
				'success': 'check',
				'error': 'cancel',
				'warning': 'warning',
				'info': 'info',
			}
			CTkMessagebox(
				title='Aviso',
				message=message,
				icon=icon_map.get(type_, 'info'),
				fade_in_duration=200,
			)

	def show_empty_state(
		self,
		container: ctk.CTkFrame,
		message: str = 'No hay datos para mostrar.',
		icon: str = '📭',
	) -> None:
		"""
		Renderiza un estado vacío centrado en el contenedor proporcionado.
		Destruye el widget anterior para evitar apilamiento de labels duplicados.
		"""
		if self._empty_state_widget is not None:
			try:
				self._empty_state_widget.destroy()
			except Exception:
				pass
			self._empty_state_widget = None

		self._empty_state_widget = ctk.CTkLabel(
			container,
			text=f'{icon}\n{message}',
			font=FONT_NAV,
			text_color=TEXT_MUTED,
			justify='center',
		)
		self._empty_state_widget.pack(expand=True, pady=40)

	def hide_empty_state(self) -> None:
		"""Oculta y destruye el estado vacío si existe."""
		if self._empty_state_widget is not None:
			try:
				self._empty_state_widget.destroy()
			except Exception:
				pass
			self._empty_state_widget = None

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
		"""
		Programa ejecución diferida rastreable para limpieza segura.
		El job se elimina automáticamente de la lista una vez ejecutado.
		"""
		job_id_holder: list[str] = []

		def _wrapped():
			try:
				callback()
			finally:
				job_id = job_id_holder[0] if job_id_holder else None
				if job_id and job_id in self._pending_jobs:
					self._pending_jobs.remove(job_id)

		job = self.after(delay_ms, _wrapped)
		job_id_holder.append(job)
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

		self._empty_state_widget = None

		super().destroy()
