"""
views/report_view.py
=====================
Vista de Reporte de Cierre de Día (y de período personalizado).

Layout:
  ┌────────────────── Barra de período ──────────────────┐
  │  [Hoy] [Ayer] [Esta Semana] [Este Mes]   Desde [  ] Hasta [  ] [Generar]  │
  ├───────────────────────────────────────────────────────┤
  │  Frase resumen (50yo UX)                              │
  ├───────── 5 KPI cards ─────────────────────────────────┤
  │  [Ventas] [Ganancia] [Margen] [Tickets] [Prom.Ticket] │
  ├─── Desglose pago ────┬─── Cancelaciones ─────────────┤
  │  Efectivo …          │  X canceladas / devueltas      │
  ├─── Top productos ───────────────────────────────────── │
  │  Barra mini por cada producto                          │
  ├─── Movimientos de caja ──────────────────────────────── │
  │  Ingresos totales / Gastos totales                     │
  └──────────────────── Botones export ─────────────────────┘
"""

import logging
import threading
from datetime import date, datetime, timedelta

import customtkinter as ctk

from controllers.report_controller import ReportController
from utils.date_picker import CTkDatePicker
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_HOVER,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_BODY_BOLD,
	FONT_HEADING,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	FONT_NAV,
	FONT_SMALL,
	FONT_SMALL_BOLD,
	FONT_STAT,
	FONT_SUBHEADING,
	FONT_TITLE,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	PURPLE_TEXT,
	RED,
	RED_TEXT,
	SURFACE1,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
)

logger = logging.getLogger(__name__)

# ─── Colores para métodos de pago ─────────────────────────────────────────────
_METHOD_COLORS = {
	'efectivo': (GREEN, GREEN_TEXT, GREEN_DIM),
	'débito': (ACCENT, ACCENT_TEXT, ACCENT_DIM),
	'debito': (ACCENT, ACCENT_TEXT, ACCENT_DIM),
	'tarjeta': (ACCENT, ACCENT_TEXT, ACCENT_DIM),
	'fiado': (ORANGE, ORANGE_TEXT, ORANGE_DIM),
	'otro': ('#7c3aed', PURPLE_TEXT, '#1e0a3c'),
}
_DEFAULT_METHOD = (ACCENT, ACCENT_TEXT, ACCENT_DIM)


def _method_colors(method: str):
	return _METHOD_COLORS.get((method or '').lower(), _DEFAULT_METHOD)


def _pct_badge(curr, prev) -> tuple[str, str]:
	"""Devuelve (texto_badge, color). Verde si subió, rojo si bajó."""
	if prev == 0:
		return ('Sin datos ant.', TEXT_MUTED)
	pct = (curr - prev) / prev * 100
	if pct >= 0:
		return (f'▲ {pct:.1f}% vs anterior', GREEN_TEXT)
	return (f'▼ {abs(pct):.1f}% vs anterior', RED_TEXT)


class ReportView(BaseView):
	def __init__(self, master, ctx: AppContext, navigate=None):
		super().__init__(master, ctx)
		self.controller = ReportController(ctx.db_engine)
		self._navigate = navigate
		self._data = None  # último reporte cargado

		# Fechas por defecto: hoy
		self._date_from = date.today()
		self._date_to = date.today()

		self.configure(fg_color=SURFACE1)
		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)  # scrollable area crece

		self._build_toolbar()
		self._build_scrollable_body()
		self._build_export_bar()

		# Carga inicial
		self.after(200, lambda: self._load_report(show_spinner=True))

	# =========================================================
	# BARRA SUPERIOR (período)
	# =========================================================
	def _build_toolbar(self):
		bar = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=0,
			border_width=1,
			border_color=BORDER,
		)
		bar.grid(row=0, column=0, sticky='ew', padx=0, pady=(0, 1))
		bar.grid_columnconfigure(5, weight=1)  # spacer

		# Título
		ctk.CTkLabel(
			bar, text='📊 Reporte de Cierre', font=FONT_HEADING, text_color=TEXT_PRIMARY
		).grid(row=0, column=0, padx=(16, 24), pady=10)

		# Botones rápidos
		quick_btns = [
			('Hoy', self._set_today),
			('Ayer', self._set_yesterday),
			('Esta Semana', self._set_this_week),
			('Este Mes', self._set_this_month),
		]
		self._quick_buttons = {}
		for i, (label, cmd) in enumerate(quick_btns):
			btn = ctk.CTkButton(
				bar,
				text=label,
				width=90,
				height=30,
				fg_color=SURFACE3,
				hover_color=SURFACE4,
				text_color=TEXT_SECONDARY,
				font=FONT_SMALL,
				corner_radius=6,
				command=cmd,
			)
			btn.grid(row=0, column=i + 1, padx=4, pady=10)
			self._quick_buttons[label] = btn

		# Spacer
		ctk.CTkLabel(bar, text='', fg_color='transparent').grid(
			row=0, column=5, sticky='ew'
		)

		# Entradas de fecha manual
		ctk.CTkLabel(bar, text='Desde', font=FONT_LABEL, text_color=TEXT_MUTED).grid(
			row=0, column=6, padx=(8, 2)
		)
		self._entry_from = CTkDatePicker(bar, width=175, height=32)
		self._entry_from.grid(row=0, column=7, padx=(0, 8))
		self._entry_from.bind('<Return>', lambda e: self._on_generate_click())
		self._entry_from.bind('<KeyRelease>', self._clear_quick_filters)

		ctk.CTkLabel(bar, text='Hasta', font=FONT_LABEL, text_color=TEXT_MUTED).grid(
			row=0, column=8, padx=(0, 2)
		)
		self._entry_to = CTkDatePicker(bar, width=175, height=32)
		self._entry_to.grid(row=0, column=9, padx=(0, 8))
		self._entry_to.bind('<Return>', lambda e: self._on_generate_click())
		self._entry_to.bind('<KeyRelease>', self._clear_quick_filters)

		self._btn_generate = ctk.CTkButton(
			bar,
			text='Generar',
			width=90,
			height=30,
			fg_color=ACCENT,
			hover_color=ACCENT_HOVER,
			text_color='white',
			font=FONT_SMALL_BOLD,
			corner_radius=6,
			command=self._on_generate_click,
		)
		self._btn_generate.grid(row=0, column=10, padx=(0, 16))

		self._sync_date_entries()

	def _sync_date_entries(self):
		self._entry_from.set_date(self._date_from)
		self._entry_to.set_date(self._date_to)

	def _highlight_quick_btn(self, active_label: str):
		for label, btn in self._quick_buttons.items():
			if label == active_label:
				btn.configure(fg_color=ACCENT_DIM, text_color=ACCENT_TEXT)
			else:
				btn.configure(fg_color=SURFACE3, text_color=TEXT_SECONDARY)

	def _clear_quick_filters(self, event=None):
		"""Desmarca los botones de filtros rápidos si el usuario escribe manualmente."""
		if event and event.keysym in ('Return', 'KP_Enter', 'Tab'):
			return
		self._highlight_quick_btn('')

	# ─── Acciones rápidas ────────────────────────────────────────────────────
	def _set_today(self):
		self._date_from = self._date_to = date.today()
		self._sync_date_entries()
		self._highlight_quick_btn('Hoy')
		self._load_report()

	def _set_yesterday(self):
		yesterday = date.today() - timedelta(days=1)
		self._date_from = self._date_to = yesterday
		self._sync_date_entries()
		self._highlight_quick_btn('Ayer')
		self._load_report()

	def _set_this_week(self):
		today = date.today()
		self._date_from = today - timedelta(days=today.weekday())
		self._date_to = today
		self._sync_date_entries()
		self._highlight_quick_btn('Esta Semana')
		self._load_report()

	def _set_this_month(self):
		today = date.today()
		self._date_from = today.replace(day=1)
		self._date_to = today
		self._sync_date_entries()
		self._highlight_quick_btn('Este Mes')
		self._load_report()

	def _on_generate_click(self):
		"""Parsea las fechas ingresadas manualmente (más flexible) y genera el reporte."""
		try:
			df_str = self._entry_from.get().strip().replace('-', '/')
			dt_str = self._entry_to.get().strip().replace('-', '/')

			self._date_from = datetime.strptime(df_str, '%d/%m/%Y').date()
			self._date_to = datetime.strptime(dt_str, '%d/%m/%Y').date()
		except ValueError:
			self.show_error(
				'Formato de fecha inválido. Usá DD/MM/AAAA (ej: 02/05/2026)',
				'Error de formato',
			)
			self._btn_pdf.configure(state='disabled')
			self._btn_csv.configure(state='disabled')
			return

		if self._date_from > self._date_to:
			self.show_error(
				'La fecha "Desde" no puede ser mayor que "Hasta".',
				'Fechas incongruentes',
			)
			self._btn_pdf.configure(state='disabled')
			self._btn_csv.configure(state='disabled')
			return

		self._highlight_quick_btn('')
		self._load_report(show_spinner=True)

	# =========================================================
	# CUERPO SCROLLABLE
	# =========================================================
	def _build_scrollable_body(self):
		self._scroll = ctk.CTkScrollableFrame(
			self,
			fg_color=SURFACE1,
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		self._scroll.grid(row=1, column=0, sticky='nsew', padx=0, pady=0)
		self._scroll.grid_columnconfigure(0, weight=1)

		self._lbl_spinner = ctk.CTkLabel(
			self._scroll,
			text='⏳  Generando reporte…',
			font=FONT_SUBHEADING,
			text_color=TEXT_MUTED,
		)
		self._lbl_spinner.grid(row=0, column=0, pady=80)

	# =========================================================
	# BARRA INFERIOR (exportar)
	# =========================================================
	def _build_export_bar(self):
		bar = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=0,
			border_width=1,
			border_color=BORDER,
		)
		bar.grid(row=2, column=0, sticky='ew')

		self._btn_pdf = ctk.CTkButton(
			bar,
			text='📄  Exportar PDF',
			width=160,
			height=34,
			fg_color=RED,
			hover_color='#b91c1c',
			text_color='white',
			font=FONT_BODY_BOLD,
			corner_radius=6,
			state='disabled',
			command=self._export_pdf,
		)
		self._btn_pdf.pack(side='left', padx=16, pady=10)

		self._btn_csv = ctk.CTkButton(
			bar,
			text='📊  Exportar CSV',
			width=160,
			height=34,
			fg_color=GREEN,
			hover_color='#15803d',
			text_color='white',
			font=FONT_BODY_BOLD,
			corner_radius=6,
			state='disabled',
			command=self._export_csv,
		)
		self._btn_csv.pack(side='left', padx=4, pady=10)

		self._lbl_status = ctk.CTkLabel(
			bar,
			text='',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
		)
		self._lbl_status.pack(side='left', padx=16)

	# =========================================================
	# CARGA DE DATOS (hilos seguros)
	# =========================================================
	def _load_report(self, show_spinner=False):
		if not self.winfo_exists():
			return

		if show_spinner:
			self._clear_body()
			self._lbl_spinner = ctk.CTkLabel(
				self._scroll,
				text='⏳  Generando reporte…',
				font=FONT_SUBHEADING,
				text_color=TEXT_MUTED,
			)
			self._lbl_spinner.grid(row=0, column=0, pady=80)

		self._btn_generate.configure(state='disabled', text='Cargando…')
		self._btn_pdf.configure(state='disabled')
		self._btn_csv.configure(state='disabled')

		tenant_id = self.ctx.tenant_id
		date_from = self._date_from
		date_to = self._date_to

		def worker():
			data = self.controller.get_report_data(tenant_id, date_from, date_to)
			self.after(
				0, lambda: self._render_report(data) if self.winfo_exists() else None
			)

		threading.Thread(target=worker, daemon=True).start()

	def _render_report(self, data: dict):
		self._data = data
		self._clear_body()

		cur = data['current']
		prev = data['previous']
		top = data['top_products']
		movs = data['movements']
		cancels = data['cancellations']
		period = data['period']

		row = 0
		row = self._build_summary_phrase(row, cur, period)
		row = self._build_kpi_cards(row, cur, prev)
		row = self._build_mid_section(row, cur, cancels)
		if top:
			row = self._build_top_products(row, top)
		if movs['gastos'] or movs['ingresos']:
			row = self._build_movements(row, movs)

		self._btn_generate.configure(state='normal', text='Generar')
		self._btn_pdf.configure(state='normal')
		self._btn_csv.configure(state='normal')

	def _clear_body(self):
		for widget in self._scroll.winfo_children():
			try:
				widget.destroy()
			except Exception:
				pass

	# =========================================================
	# SECCIÓN: FRASE RESUMEN
	# =========================================================
	def _build_summary_phrase(self, row: int, cur: dict, period: dict) -> int:
		df = period['from'].strftime('%d/%m/%Y')
		dt = period['to'].strftime('%d/%m/%Y')
		period_label = 'hoy' if df == dt else f'del {df} al {dt}'

		revenue = cur['revenue']
		profit = cur['profit']
		tickets = cur['tickets']
		margin = cur['margin']

		if tickets == 0:
			phrase = f'No se registraron ventas {period_label}.'
		else:
			phrase = (
				f'Se realizaron  {tickets} venta{"s" if tickets != 1 else ""}  '
				f'{period_label},  totalizando  ${revenue:,.0f}  en ventas  '
				f'con  ${profit:,.0f}  de ganancia  ({margin:.1f}% de margen).'
			)

		frame = ctk.CTkFrame(
			self._scroll,
			fg_color=ACCENT_DIM,
			corner_radius=10,
			border_width=1,
			border_color=ACCENT,
		)
		frame.grid(row=row, column=0, sticky='ew', padx=16, pady=(16, 8))

		ctk.CTkLabel(
			frame,
			text=phrase,
			font=FONT_NAV,
			text_color=ACCENT_TEXT,
			wraplength=900,
			justify='left',
		).pack(anchor='w', padx=20, pady=14)

		return row + 1

	# =========================================================
	# SECCIÓN: KPI CARDS
	# =========================================================
	def _build_kpi_cards(self, row: int, cur: dict, prev: dict) -> int:
		frame = ctk.CTkFrame(self._scroll, fg_color='transparent')
		frame.grid(row=row, column=0, sticky='ew', padx=16, pady=8)
		for i in range(5):
			frame.grid_columnconfigure(i, weight=1)

		kpi_defs = [
			(
				'Total Ventas',
				f'${cur["revenue"]:,.0f}',
				cur['revenue'],
				prev['revenue'],
				ACCENT_TEXT,
			),
			(
				'Ganancia Neta',
				f'${cur["profit"]:,.0f}',
				cur['profit'],
				prev['profit'],
				GREEN_TEXT,
			),
			(
				'Margen (%)',
				f'{cur["margin"]:.1f}%',
				cur['margin'],
				prev['margin'],
				ORANGE_TEXT,
			),
			(
				'Tickets',
				str(cur['tickets']),
				cur['tickets'],
				prev['tickets'],
				ACCENT_TEXT,
			),
			(
				'Ticket Promedio',
				f'${cur["avg_ticket"]:,.0f}',
				cur['avg_ticket'],
				prev['avg_ticket'],
				GREEN_TEXT,
			),
		]

		for i, (title, value, curr_val, prev_val, color) in enumerate(kpi_defs):
			card = ctk.CTkFrame(
				frame,
				fg_color=SURFACE2,
				corner_radius=12,
				border_width=1,
				border_color=BORDER,
			)
			card.grid(row=0, column=i, sticky='nsew', padx=5, pady=4)

			ctk.CTkFrame(card, fg_color=color, width=4, corner_radius=0).pack(
				side='left', fill='y'
			)

			body = ctk.CTkFrame(card, fg_color='transparent')
			body.pack(side='left', fill='both', expand=True, padx=14, pady=12)

			ctk.CTkLabel(
				body,
				text=title.upper(),
				font=('Arial', 9, 'bold'),
				text_color=TEXT_MUTED,
			).pack(anchor='w')

			ctk.CTkLabel(
				body,
				text=value,
				font=('Arial', 26, 'bold'),
				text_color=color,
			).pack(anchor='w', pady=(4, 0))

			badge_text, badge_color = _pct_badge(curr_val, prev_val)
			ctk.CTkLabel(
				body,
				text=badge_text,
				font=('Arial', 9),
				text_color=badge_color,
			).pack(anchor='w')

		return row + 1

	# =========================================================
	# SECCIÓN: DESGLOSE PAGO + CANCELACIONES
	# =========================================================
	def _build_mid_section(self, row: int, cur: dict, cancels: dict) -> int:
		frame = ctk.CTkFrame(self._scroll, fg_color='transparent')
		frame.grid(row=row, column=0, sticky='ew', padx=16, pady=8)
		frame.grid_columnconfigure(0, weight=3)
		frame.grid_columnconfigure(1, weight=1)

		# ── Desglose por pago ──
		left = ctk.CTkFrame(
			frame,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		left.grid(row=0, column=0, sticky='nsew', padx=(0, 6), pady=4)

		ctk.CTkLabel(
			left,
			text='DESGLOSE POR MÉTODO DE PAGO',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=16, pady=(14, 8))

		methods = cur['by_method']
		total_revenue = cur['revenue'] or 1

		if not methods:
			ctk.CTkLabel(
				left,
				text='Sin ventas en el período.',
				font=FONT_SMALL,
				text_color=TEXT_MUTED,
			).pack(padx=16, pady=(0, 14))
		else:
			for method, info in sorted(
				methods.items(), key=lambda x: x[1]['total'], reverse=True
			):
				pct = (info['total'] / total_revenue) * 100
				_, txt_color, _ = _method_colors(method)
				row_f = ctk.CTkFrame(left, fg_color='transparent')
				row_f.pack(fill='x', padx=16, pady=3)

				ctk.CTkLabel(
					row_f,
					text=method.capitalize(),
					font=FONT_SMALL_BOLD,
					text_color=TEXT_PRIMARY,
					width=90,
					anchor='w',
				).pack(side='left')

				pb = ctk.CTkProgressBar(
					row_f,
					height=8,
					corner_radius=4,
					fg_color=SURFACE3,
					progress_color=txt_color,
				)
				pb.set(pct / 100)
				pb.pack(side='left', fill='x', expand=True, padx=8)

				ctk.CTkLabel(
					row_f,
					text=f'${info["total"]:,.0f}  ({info["count"]} t.)',
					font=FONT_SMALL,
					text_color=txt_color,
					width=150,
					anchor='e',
				).pack(side='right')

			ctk.CTkLabel(left, text='', height=6).pack()

		# ── Cancelaciones ──
		right = ctk.CTkFrame(
			frame,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		right.grid(row=0, column=1, sticky='nsew', padx=(6, 0), pady=4)

		ctk.CTkLabel(
			right,
			text='ANULACIONES Y DEVOLUCIONES',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=16, pady=(14, 8))

		count = cancels['count']
		total = cancels['total']
		color = RED_TEXT if count > 0 else GREEN_TEXT
		icon = '⚠' if count > 0 else '✓'

		ctk.CTkLabel(
			right,
			text=f'{icon}  {count}',
			font=FONT_STAT,
			text_color=color,
		).pack(padx=16, pady=(4, 0))

		ctk.CTkLabel(
			right,
			text='tickets cancelados / devueltos',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(padx=16)

		ctk.CTkLabel(
			right,
			text=f'${total:,.0f}',
			font=FONT_TITLE,
			text_color=color,
		).pack(padx=16, pady=(6, 2))

		ctk.CTkLabel(
			right,
			text='monto total involucrado',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(padx=16, pady=(0, 14))

		return row + 1

	# =========================================================
	# SECCIÓN: TOP PRODUCTOS
	# =========================================================
	def _build_top_products(self, row: int, top: list) -> int:
		frame = ctk.CTkFrame(
			self._scroll,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		frame.grid(row=row, column=0, sticky='ew', padx=16, pady=8)
		frame.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			frame,
			text=f'TOP {len(top)} PRODUCTOS DEL PERÍODO',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
		).grid(row=0, column=0, sticky='w', padx=16, pady=(14, 6))

		max_qty = max((p['quantity'] for p in top), default=1) or 1

		for i, product in enumerate(top):
			pct = product['quantity'] / max_qty
			qty = product['quantity']
			qty_str = f'{int(qty)}' if qty == int(qty) else f'{qty:.1f}'

			row_f = ctk.CTkFrame(frame, fg_color='transparent')
			row_f.grid(row=i + 1, column=0, sticky='ew', padx=16, pady=3)
			row_f.grid_columnconfigure(1, weight=1)

			ctk.CTkLabel(
				row_f,
				text=f'{i + 1:2d}.',
				font=FONT_SMALL_BOLD,
				text_color=TEXT_MUTED,
				width=26,
				anchor='e',
			).grid(row=0, column=0, padx=(0, 8))

			name = product['description'][:40]
			ctk.CTkLabel(
				row_f,
				text=name,
				font=FONT_SMALL,
				text_color=TEXT_PRIMARY,
				anchor='w',
				width=220,
			).grid(row=0, column=1, sticky='w')

			pb = ctk.CTkProgressBar(
				row_f,
				height=8,
				corner_radius=4,
				fg_color=SURFACE3,
				progress_color=ACCENT,
			)
			pb.set(pct)
			pb.grid(row=0, column=2, sticky='ew', padx=8)
			row_f.grid_columnconfigure(2, weight=1)

			ctk.CTkLabel(
				row_f,
				text=f'{qty_str} u  ·  ${product["revenue"]:,.0f}',
				font=FONT_SMALL,
				text_color=ACCENT_TEXT,
				width=160,
				anchor='e',
			).grid(row=0, column=3, padx=(8, 0))

		ctk.CTkLabel(frame, text='', height=6).grid(row=len(top) + 1, column=0)
		return row + 1

	# =========================================================
	# SECCIÓN: MOVIMIENTOS MANUALES
	# =========================================================
	def _build_movements(self, row: int, movs: dict) -> int:
		frame = ctk.CTkFrame(
			self._scroll,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		frame.grid(row=row, column=0, sticky='ew', padx=16, pady=(8, 16))
		frame.grid_columnconfigure(0, weight=1)
		frame.grid_columnconfigure(1, weight=1)

		ctk.CTkLabel(
			frame,
			text='MOVIMIENTOS MANUALES DE CAJA',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_MUTED,
		).grid(row=0, column=0, columnspan=2, sticky='w', padx=16, pady=(14, 8))

		# ── Ingresos ──
		ing_frame = ctk.CTkFrame(frame, fg_color='transparent')
		ing_frame.grid(row=1, column=0, sticky='nsew', padx=16, pady=(0, 14))

		ctk.CTkLabel(
			ing_frame,
			text=f'▲ INGRESOS  ${movs["total_ingresos"]:,.0f}',
			font=FONT_BODY_BOLD,
			text_color=GREEN_TEXT,
		).pack(anchor='w', pady=(0, 4))

		if not movs['ingresos']:
			ctk.CTkLabel(
				ing_frame,
				text='Sin ingresos manuales.',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
			).pack(anchor='w')
		else:
			for m in movs['ingresos']:
				t = m['time'].strftime('%H:%M') if m['time'] else '--:--'
				row_f = ctk.CTkFrame(ing_frame, fg_color='transparent')
				row_f.pack(fill='x', pady=1)
				ctk.CTkLabel(
					row_f, text=t, font=FONT_LABEL, text_color=TEXT_MUTED, width=40
				).pack(side='left')
				ctk.CTkLabel(
					row_f,
					text=(m['desc'] or '—')[:45],
					font=FONT_LABEL,
					text_color=TEXT_SECONDARY,
				).pack(side='left', padx=6)
				ctk.CTkLabel(
					row_f,
					text=f'${m["amount"]:,.0f}',
					font=FONT_LABEL_BOLD,
					text_color=GREEN_TEXT,
				).pack(side='right')

		# ── Gastos ──
		gas_frame = ctk.CTkFrame(frame, fg_color='transparent')
		gas_frame.grid(row=1, column=1, sticky='nsew', padx=16, pady=(0, 14))

		ctk.CTkLabel(
			gas_frame,
			text=f'▼ GASTOS  ${movs["total_gastos"]:,.0f}',
			font=FONT_BODY_BOLD,
			text_color=RED_TEXT,
		).pack(anchor='w', pady=(0, 4))

		if not movs['gastos']:
			ctk.CTkLabel(
				gas_frame,
				text='Sin gastos manuales.',
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
			).pack(anchor='w')
		else:
			for m in movs['gastos']:
				t = m['time'].strftime('%H:%M') if m['time'] else '--:--'
				row_f = ctk.CTkFrame(gas_frame, fg_color='transparent')
				row_f.pack(fill='x', pady=1)
				ctk.CTkLabel(
					row_f, text=t, font=FONT_LABEL, text_color=TEXT_MUTED, width=40
				).pack(side='left')
				ctk.CTkLabel(
					row_f,
					text=(m['desc'] or '—')[:45],
					font=FONT_LABEL,
					text_color=TEXT_SECONDARY,
				).pack(side='left', padx=6)
				ctk.CTkLabel(
					row_f,
					text=f'${m["amount"]:,.0f}',
					font=FONT_LABEL_BOLD,
					text_color=RED_TEXT,
				).pack(side='right')

		return row + 1

	# =========================================================
	# EXPORTACIONES (Hilos seguros)
	# =========================================================
	def _export_pdf(self):
		if not self._data:
			return
		self._lbl_status.configure(text='Generando PDF…', text_color=TEXT_MUTED)
		self._btn_pdf.configure(state='disabled')

		try:
			from utils.settings_manager import get as settings_get

			company = settings_get('company_name', 'Mi Negocio')
		except Exception:
			company = 'Mi Negocio'

		data = self._data

		def worker():
			try:
				path = self.controller.export_pdf(data, company_name=company)
				self.after(
					0,
					lambda p=path: (
						self._on_export_done(f'PDF guardado: {p}', True)
						if self.winfo_exists()
						else None
					),
				)
			except Exception as e:
				logger.error(f'Error exportando PDF: {e}', exc_info=True)
				err_msg = str(e)
				self.after(
					0,
					lambda msg=err_msg: (
						self._on_export_done(f'Error: {msg}', False)
						if self.winfo_exists()
						else None
					),
				)

		threading.Thread(target=worker, daemon=True).start()

	def _export_csv(self):
		if not self._data:
			return
		self._lbl_status.configure(text='Exportando CSV…', text_color=TEXT_MUTED)
		self._btn_csv.configure(state='disabled')

		data = self._data

		def worker():
			try:
				path = self.controller.export_csv(data)
				self.after(
					0,
					lambda p=path: (
						self._on_export_done(f'CSV guardado: {p}', True)
						if self.winfo_exists()
						else None
					),
				)
			except Exception as e:
				logger.error(f'Error exportando CSV: {e}', exc_info=True)
				err_msg = str(e)
				self.after(
					0,
					lambda msg=err_msg: (
						self._on_export_done(f'Error: {msg}', False)
						if self.winfo_exists()
						else None
					),
				)

		threading.Thread(target=worker, daemon=True).start()

	def _on_export_done(self, message: str, success: bool):
		color = GREEN_TEXT if success else RED_TEXT
		self._lbl_status.configure(text=message, text_color=color)
		self._btn_pdf.configure(state='normal')
		self._btn_csv.configure(state='normal')
		self.schedule(6000, lambda: self._lbl_status.configure(text=''))
