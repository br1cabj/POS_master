"""Guía de inicio rápido para la primera sesión del administrador."""

from __future__ import annotations

import logging
from collections.abc import Iterable

import customtkinter as ctk
from sqlalchemy.orm import sessionmaker

from core.base_view import BaseView
from core.context import AppContext
from database.models import Article, CashSession, Supplier
from utils.settings_manager import load as _cfg_load
from utils.settings_manager import save as _cfg_save
from utils.styles import (
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	FONT_BODY_BOLD,
	FONT_NAV,
	FONT_SMALL,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	SURFACE1,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
)

logger = logging.getLogger(__name__)

_CHECKLIST = (
	(
		'system',
		'✅',
		'Sistema configurado',
		'Tu negocio, moneda e impuestos quedaron guardados desde el asistente.',
		None,
	),
	(
		'suppliers',
		'🚚',
		'Agregá tu primer proveedor',
		'Asociá artículos a su origen y mantené ordenadas tus compras.',
		'suppliers',
	),
	(
		'articles',
		'📦',
		'Cargá tu primer producto',
		'Agregá artículos con código de barras, precio de costo y precio de venta.',
		'articles',
	),
	(
		'cash',
		'💵',
		'Abrí tu primera sesión de caja',
		'Registrá el saldo inicial y empezá a vender.',
		'cash',
	),
)


def get_onboarding_progress(engine, tenant_id: str) -> dict[str, bool]:
	"""Obtiene el avance sin modificar datos ni contar filas innecesariamente."""
	progress = {'system': True, 'suppliers': False, 'articles': False, 'cash': False}
	if engine is None or not tenant_id:
		return progress

	try:
		Session = sessionmaker(bind=engine)
		with Session() as session:
			progress['suppliers'] = (
				session.query(Supplier.id)
				.filter(
					Supplier.tenant_id == tenant_id,
					Supplier.is_active.is_(True),
					Supplier.deleted_at.is_(None),
				)
				.first()
				is not None
			)
			progress['articles'] = (
				session.query(Article.id)
				.filter(
					Article.tenant_id == tenant_id,
					Article.is_active.is_(True),
					Article.deleted_at.is_(None),
				)
				.first()
				is not None
			)
			# Una caja cerrada también acredita el paso: ya fue abierta al menos una vez.
			progress['cash'] = (
				session.query(CashSession.id)
				.filter(CashSession.tenant_id == tenant_id)
				.first()
				is not None
			)
	except Exception:
		# La guía jamás debe impedir acceder al POS si la consulta de estado falla.
		logger.exception('No se pudo calcular el progreso del onboarding')

	return progress


class OnboardingView(BaseView):
	"""Vista de bienvenida reutilizable con pasos basados en la base local."""

	def __init__(self, master, ctx: AppContext, on_done):
		super().__init__(master, ctx)
		self._on_done = on_done
		self._transitioning = False
		self._action_buttons: list[ctk.CTkButton] = []
		self._hover_jobs: dict[ctk.CTkFrame, str] = {}

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(0, weight=1)

		scroll = ctk.CTkScrollableFrame(
			self,
			fg_color=SURFACE1,
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		scroll.grid(row=0, column=0, sticky='nsew')
		scroll.grid_columnconfigure(0, weight=1)

		self._items = self._checklist_items()
		self._build_content(scroll)
		self.after_idle(self._focus_primary_action)

	def _checklist_items(self) -> list[tuple[str, str, str, str, bool, str | None]]:
		progress = get_onboarding_progress(self.ctx.db_engine, self.ctx.tenant_id)
		return [
			(key, icon, title, description, progress[key], section)
			for key, icon, title, description, section in _CHECKLIST
		]

	def _build_content(self, parent):
		completed = sum(done for _, _, _, _, done, section in self._items if section)
		actionable_total = sum(1 for *_, section in self._items if section)

		header = ctk.CTkFrame(
			parent,
			fg_color=ACCENT_DIM,
			corner_radius=16,
			border_width=1,
			border_color=ACCENT_DIM,
		)
		header.grid(row=0, column=0, sticky='ew', padx=60, pady=(48, 0))
		header.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			header,
			text='🎉  ¡Bienvenido a CloudPOS!',
			font=('Arial', 28, 'bold'),
			text_color=ACCENT_TEXT,
		).grid(row=0, column=0, pady=(28, 6), padx=40, sticky='w')
		ctk.CTkLabel(
			header,
			text=(
				'Tu sistema está listo. Completá estos pasos iniciales para empezar '
				'a vender con toda la información ordenada.'
			),
			font=FONT_NAV,
			text_color=ACCENT_TEXT,
			wraplength=700,
			justify='left',
			anchor='w',
		).grid(row=1, column=0, pady=(0, 16), padx=40, sticky='w')
		ctk.CTkLabel(
			header,
			text=f'Progreso inicial: {completed} de {actionable_total} pasos completados',
			font=FONT_BODY_BOLD,
			text_color=ACCENT_TEXT,
			anchor='w',
		).grid(row=2, column=0, padx=40, sticky='w')
		progress_bar = ctk.CTkProgressBar(
			header, height=8, fg_color=SURFACE3, progress_color=GREEN, corner_radius=4
		)
		progress_bar.grid(row=3, column=0, padx=40, pady=(6, 26), sticky='ew')
		progress_bar.set(completed / actionable_total if actionable_total else 1)

		for row, (_, icon, title, description, done, section) in enumerate(self._items, start=1):
			self._build_checklist_item(
				parent, row, icon, title, description, done, section
			)

		footer = ctk.CTkFrame(parent, fg_color='transparent')
		footer.grid(row=len(self._items) + 1, column=0, padx=60, pady=(28, 48), sticky='ew')
		footer.grid_columnconfigure(0, weight=1)
		all_done = completed == actionable_total
		primary_text = '✓  Terminar inicio rápido' if all_done else 'Ir al Dashboard  →'
		self._primary_action = ctk.CTkButton(
			footer,
			text=primary_text,
			height=54,
			font=('Arial', 16, 'bold'),
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			corner_radius=10,
			command=self._finish,
		)
		self._primary_action.grid(row=0, column=0, sticky='ew')
		self._action_buttons.append(self._primary_action)
		self._bind_shortcuts(self._primary_action)
		self._skip_action = ctk.CTkButton(
			footer,
			text='Omitir este inicio rápido por ahora',
			font=FONT_SMALL,
			fg_color='transparent',
			hover_color=SURFACE2,
			text_color=TEXT_MUTED,
			height=34,
			command=self._finish,
		)
		self._skip_action.grid(row=1, column=0, pady=(8, 0))
		self._action_buttons.append(self._skip_action)
		self._bind_shortcuts(self._skip_action)
		ctk.CTkLabel(
			footer,
			text='Podés volver a abrir esta guía desde tu perfil en el menú lateral.',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
		).grid(row=2, column=0, pady=(4, 0))

	def _build_checklist_item(self, parent, row, icon, title, description, done, section):
		card = ctk.CTkFrame(
			parent,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		card.grid(row=row, column=0, sticky='ew', padx=60, pady=(16, 0))
		card.grid_columnconfigure(2, weight=1)
		ctk.CTkFrame(card, fg_color=GREEN if done else SURFACE3, width=5, corner_radius=0).grid(
			row=0, column=0, rowspan=2, sticky='ns'
		)
		icon_label = ctk.CTkLabel(card, text=icon, font=('Arial', 28))
		icon_label.grid(row=0, column=1, rowspan=2, padx=(20, 8), pady=20, sticky='w')
		text_frame = ctk.CTkFrame(card, fg_color='transparent')
		text_frame.grid(row=0, column=2, rowspan=2, sticky='nsew', padx=(0, 16), pady=16)
		text_frame.grid_columnconfigure(0, weight=1)
		ctk.CTkLabel(
			text_frame,
			text=title,
			font=('Arial', 15, 'bold'),
			text_color=GREEN_TEXT if done else TEXT_PRIMARY,
			anchor='w',
		).grid(row=0, column=0, sticky='w')
		ctk.CTkLabel(
			text_frame,
			text=description,
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			wraplength=520,
			justify='left',
			anchor='w',
		).grid(row=1, column=0, sticky='w', pady=(2, 0))

		if done:
			ctk.CTkLabel(
				card, text='✓  Completado', font=FONT_BODY_BOLD, text_color=GREEN_TEXT
			).grid(row=0, column=3, rowspan=2, padx=(0, 24), pady=20)
			return

		btn_action = ctk.CTkButton(
			card,
			text='Ir ahora →',
			width=120,
			height=36,
			font=FONT_BODY_BOLD,
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			corner_radius=8,
			command=lambda target=section: self._go_to_task(target),
		)
		btn_action.grid(row=0, column=3, rowspan=2, padx=(0, 24), pady=20)
		self._action_buttons.append(btn_action)
		self._bind_shortcuts(btn_action)
		self._wire_card_interaction(card, (icon_label, text_frame), section)

	def _wire_card_interaction(
		self, card: ctk.CTkFrame, widgets: Iterable[ctk.CTkBaseClass], section: str
	) -> None:
		"""Mantiene el hover al pasar entre hijos y deja la tarjeta clickeable."""

		def pointer_is_inside() -> bool:
			x, y = card.winfo_pointerx(), card.winfo_pointery()
			return (
				card.winfo_rootx() <= x < card.winfo_rootx() + card.winfo_width()
				and card.winfo_rooty() <= y < card.winfo_rooty() + card.winfo_height()
			)

		def on_enter(_event=None):
			job = self._hover_jobs.pop(card, None)
			if job:
				self.after_cancel(job)
			if not self._transitioning:
				card.configure(fg_color=SURFACE3)

		def on_leave(_event=None):
			def reset_if_outside():
				self._hover_jobs.pop(card, None)
				if not pointer_is_inside():
					card.configure(fg_color=SURFACE2)

			self._hover_jobs[card] = self.after(20, reset_if_outside)

		def on_click(_event=None):
			self._go_to_task(section)

		for widget in (card, *widgets):
			widget.bind('<Enter>', on_enter)
			widget.bind('<Leave>', on_leave)
			widget.bind('<Button-1>', on_click)

	def _bind_shortcuts(self, widget: ctk.CTkButton) -> None:
		"""Atajos disponibles cuando se navega la guía con Tab."""
		widget.bind('<Control-Return>', lambda _event: self._finish())
		widget.bind('<Escape>', lambda _event: self._finish())

	def _focus_primary_action(self):
		if not self._transitioning and self.winfo_exists():
			self._primary_action.focus_set()

	def _set_transitioning(self) -> None:
		self._transitioning = True
		for button in self._action_buttons:
			button.configure(state='disabled')

	def _go_to_task(self, section: str | None) -> None:
		if self._transitioning or not section:
			return
		self._set_transitioning()
		# No se persiste el cierre: al volver a ingresar se verá el progreso real.
		self._on_done(section)

	def _finish(self) -> None:
		"""Cierra explícitamente la guía y vuelve al dashboard."""
		if self._transitioning:
			return
		try:
			cfg = _cfg_load()
			cfg['onboarding_shown'] = True
			if not _cfg_save(cfg):
				raise OSError('No se pudo guardar la preferencia de inicio rápido.')
		except Exception:
			logger.exception('No se pudo guardar el cierre del onboarding')
			self.show_error(
				'No pudimos guardar tu preferencia. Revisá los permisos de la carpeta de datos e intentá nuevamente.',
				title='No se pudo cerrar la guía',
			)
			return

		self._set_transitioning()
		self._on_done(None)
