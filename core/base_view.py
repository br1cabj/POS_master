from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from utils.styles import (
	BORDER,
	FONT_NAV,
	RED_TEXT,
	SURFACE1,
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
		self.ctx = ctx

		# 1. EXTRACCIÓN SEGURA: Sacamos los argumentos de CloudPOS antes de que CTk los vea.
		self._show_toast_cb = kwargs.pop('show_toast', None)
		self.navigate = kwargs.pop('navigate', None)
		self.context_data = kwargs.pop('context_data', None)

		# 2. INICIALIZACIÓN PREVENTIVA: Se declaran antes de super() por si ocurre un crash.
		self._pending_jobs: list[str] = []
		self._debounce_timers: dict[str, str] = {}

		# 3. CONSTRUCCIÓN
		kwargs.setdefault('fg_color', SURFACE1)
		super().__init__(master, **kwargs)

	def load_data(self) -> None:
		pass

	def set_initial_focus(self) -> None:
		pass

	# ── Gestión de Treeviews ─────────────────────────────────────────────────

	def init_treeview(self, tree: 'ttk.Treeview') -> None:
		setup_treeview_tags(tree)

	def insert_tree_row(
		self, tree: 'ttk.Treeview', index: int, values: tuple, tags: tuple = ()
	) -> str:
		stripe_tag = 'evenrow' if index % 2 == 0 else 'oddrow'
		final_tags = (stripe_tag,) + tags
		return tree.insert('', 'end', values=values, tags=final_tags)

	# ── Utilidades de Interfaz ───────────────────────────────────────────────

	def show_error(self, message: str, title: str = 'Error') -> None:
		CTkMessagebox(master=self, title=title, message=message, icon='cancel', fade_in_duration=150)

	def show_success(self, message: str, title: str = 'Éxito') -> None:
		CTkMessagebox(master=self, title=title, message=message, icon='check', fade_in_duration=150)

	def show_warning(self, message: str, title: str = 'Atención') -> None:
		CTkMessagebox(
			master=self, title=title, message=message, icon='warning', fade_in_duration=150
		)

	def show_toast(
		self, message: str, type_: str = 'success', duration: int = 3000
	) -> None:
		if self._show_toast_cb:
			self._show_toast_cb(message, type_=type_, duration=duration)
		else:
			icon = 'check' if type_ == 'success' else 'cancel'
			CTkMessagebox(
				master=self, title='Aviso', message=message, icon=icon, fade_in_duration=150
			)

	def show_empty_state(
		self,
		container: ctk.CTkFrame,
		message: str = 'No hay datos para mostrar.',
		icon: str = '📭',
	) -> None:
		for w in list(container.winfo_children()):
			try:
				w.destroy()
			except Exception:
				pass

		lbl = ctk.CTkLabel(
			container,
			text=f'{icon}\n{message}',
			font=FONT_NAV,
			text_color='#64748b',
			justify='center',
		)
		lbl.pack(expand=True, pady=40)

	def set_loading(
		self, btn: ctk.CTkButton, loading: bool, original_text: str = ''
	) -> None:
		if loading:
			btn._loading_original = btn.cget('text')
			btn.configure(state='disabled', text='Procesando…')
		else:
			text = original_text or getattr(btn, '_loading_original', '')
			btn.configure(state='normal', text=text)

	def mark_field_error(self, entry: ctk.CTkEntry, message: str | None = None) -> None:
		entry.configure(border_color=RED_TEXT)
		entry.focus()

	def clear_field_errors(self, *entries: ctk.CTkEntry) -> None:
		for entry in entries:
			try:
				entry.configure(border_color=BORDER)
			except Exception:
				pass

	# ── Gestión de Estados ───────────────────────────────────────────────────

	def has_unsaved_changes(self) -> bool:
		return False

	def confirm(self, message: str, title: str = 'Confirmar') -> bool:
		msg = CTkMessagebox(
			title=title,
			message=message,
			icon='question',
			option_1='No',
			option_2='Sí',
			fade_in_duration=150,
		)
		return msg.get() == 'Sí'

	# ── Controladores de Tiempo y Memoria ────────────────────────────────────

	def schedule(self, delay_ms: int, callback: Callable) -> str:
		job = self.after(delay_ms, callback)
		self._pending_jobs.append(job)
		return job

	def debounce(self, delay_ms: int, callback: Callable, key: str = 'default') -> None:
		if key in self._debounce_timers:
			try:
				self.after_cancel(self._debounce_timers[key])
			except Exception:
				pass
		self._debounce_timers[key] = self.after(delay_ms, callback)

	def destroy(self) -> None:
		for job in list(getattr(self, '_pending_jobs', [])):
			try:
				self.after_cancel(job)
			except Exception:
				pass
		if hasattr(self, '_pending_jobs'):
			self._pending_jobs.clear()

		for timer_id in getattr(self, '_debounce_timers', {}).values():
			try:
				self.after_cancel(timer_id)
			except Exception:
				pass
		if hasattr(self, '_debounce_timers'):
			self._debounce_timers.clear()

		super().destroy()
