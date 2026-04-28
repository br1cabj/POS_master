import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from controllers.dashboard_controller import DashboardController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	FONT_STAT,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
)

# ─── Paleta del gráfico (alineada con el design system) ───────────────────────
_CHART_BG = '#111111'
_BAR_NORMAL = '#1a2744'
_BAR_TODAY = ACCENT
_AXIS_COLOR = '#333333'
_GRID_COLOR = '#1e1e1e'
_TICK_COLOR = '#555555'


class HomeView(BaseView):
	def __init__(self, master, ctx: AppContext, navigate=None):
		super().__init__(master, ctx)
		self.controller = DashboardController(ctx.db_engine)
		self._navigate = navigate
		self._fig = None
		self.canvas_widget = None

		username = ctx.username

		# ── Configuración del grid (bento layout) ─────────────────────────
		self.grid_columnconfigure(0, weight=2)
		self.grid_columnconfigure(1, weight=1)
		self.grid_rowconfigure(0, weight=0)  # header
		self.grid_rowconfigure(1, weight=0)  # accesos rápidos
		self.grid_rowconfigure(2, weight=0)  # stat cards
		self.grid_rowconfigure(3, weight=1)  # gráfico + top5

		# ── Header ────────────────────────────────────────────────────────
		self._build_header(username)

		# ── Accesos rápidos ────────────────────────────────────────────────
		self._build_quick_actions()

		# ── Cards de estadísticas ─────────────────────────────────────────
		self._build_stat_cards()

		# ── Zona inferior: gráfico + top 5 ────────────────────────────────
		self._build_chart_area()
		self._build_top_products_area()

		# ── Carga de datos con pequeño delay ──────────────────────────────
		self.after(150, self.load_dashboard_data)

	# =========================================================
	# NAVEGACIÓN INTERNA
	# =========================================================
	def _go_to(self, view_name: str):
		"""Lazy-import y navegación para evitar imports circulares."""
		if not self._navigate:
			return
		lazy = {
			'sales': ('views.sales_view', 'SalesView', False),
			'cash': ('views.cash_view', 'CashView', False),
			'articles': ('views.articles_view', 'ArticlesView', True),
			'alerts': ('views.alerts_view', 'AlertsView', True),
			'customers': ('views.customers_view', 'CustomersView', True),
		}
		if view_name not in lazy:
			return
		module_path, class_name, requires_admin = lazy[view_name]
		import importlib

		module = importlib.import_module(module_path)
		cls = getattr(module, class_name)
		self._navigate(cls, requires_admin=requires_admin)

	# =========================================================
	# CONSTRUCCIÓN DE UI
	# =========================================================
	def _build_header(self, username):
		hdr = ctk.CTkFrame(self, fg_color='transparent')
		hdr.grid(row=0, column=0, columnspan=2, sticky='ew', padx=20, pady=(20, 0))

		left = ctk.CTkFrame(hdr, fg_color='transparent')
		left.pack(side='left', fill='y')

		ctk.CTkLabel(
			left,
			text=f'Buen día, {username.capitalize()} 👋',
			font=('Arial', 24, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(anchor='w')

		ctk.CTkLabel(
			left,
			text='Resumen de actividad del día',
			font=('Arial', 12),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w', pady=(2, 0))

		self.btn_refresh = ctk.CTkButton(
			hdr,
			text='↻  Actualizar',
			font=('Arial', 12, 'bold'),
			fg_color=SURFACE2,
			hover_color=SURFACE3,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			width=120,
			height=34,
			corner_radius=8,
			cursor='hand2',
			command=self.load_dashboard_data,
		)
		self.btn_refresh.pack(side='right')

	def _build_quick_actions(self):
		"""Fila de accesos directos grandes — tap-friendly."""
		qa_frame = ctk.CTkFrame(self, fg_color='transparent')
		qa_frame.grid(row=1, column=0, columnspan=2, sticky='ew', padx=20, pady=(14, 0))
		qa_frame.grid_columnconfigure((0, 1, 2, 3), weight=1)

		actions = [
			('🛒', 'Nueva Venta', 'F1', ACCENT_DIM, ACCENT, ACCENT_TEXT, 'sales'),
			('💵', 'Caja', 'F2', GREEN_DIM, GREEN, GREEN_TEXT, 'cash'),
			('📦', 'Artículos', 'F3', SURFACE2, SURFACE4, TEXT_PRIMARY, 'articles'),
			('👥', 'Clientes', '', SURFACE2, SURFACE4, TEXT_PRIMARY, 'customers'),
		]

		def _bind_tile(widget, target):
			widget.configure(cursor='hand2')
			widget.bind('<Button-1>', lambda e, t=target: self._go_to(t))
			try:
				for child in widget.winfo_children():
					_bind_tile(child, target)
			except Exception:
				pass

		for col, (icon, label, shortcut, bg, hover, fg, target) in enumerate(actions):
			btn_frame = ctk.CTkFrame(
				qa_frame,
				fg_color=bg,
				corner_radius=12,
				border_width=1,
				border_color=hover,
			)
			btn_frame.grid(
				row=0, column=col, sticky='ew', padx=(0, 8) if col < 3 else 0, pady=0
			)
			btn_frame.grid_propagate(False)
			btn_frame.configure(height=82)

			inner = ctk.CTkFrame(btn_frame, fg_color='transparent')
			inner.place(relx=0.5, rely=0.5, anchor='center')

			ctk.CTkLabel(
				inner,
				text=icon,
				font=('Arial', 22),
				text_color=fg,
			).pack()

			lbl_row = ctk.CTkFrame(inner, fg_color='transparent')
			lbl_row.pack()
			ctk.CTkLabel(
				lbl_row,
				text=label,
				font=('Arial', 12, 'bold'),
				text_color=fg,
			).pack(side='left')
			if shortcut:
				ctk.CTkLabel(
					lbl_row,
					text=f'  {shortcut}',
					font=('Arial', 10),
					text_color=TEXT_MUTED,
				).pack(side='left')

			# Bind completo: frame + todos sus descendientes
			_bind_tile(btn_frame, target)

	def _build_stat_cards(self):
		"""Tres tarjetas en fila — borde izquierdo de acento por color."""
		cards_frame = ctk.CTkFrame(self, fg_color='transparent')
		cards_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=20, pady=14)
		cards_frame.grid_columnconfigure((0, 1, 2), weight=1)

		# Card Ventas — acento verde
		self.card_ventas, self.lbl_ventas, self.lbl_ventas_sub = self._make_stat_card(
			cards_frame, 'Ventas de Hoy', GREEN
		)
		self.card_ventas.grid(row=0, column=0, sticky='ew', padx=(0, 8))

		# Card Ganancia — acento azul
		self.card_ganancia, self.lbl_ganancia, self.lbl_ganancia_sub = (
			self._make_stat_card(cards_frame, 'Ganancia', ACCENT)
		)
		self.card_ganancia.grid(row=0, column=1, sticky='ew', padx=4)

		# Card Tickets — acento naranja
		self.card_tickets, self.lbl_tickets, self.lbl_tickets_sub = (
			self._make_stat_card(cards_frame, 'Tickets', ORANGE)
		)
		self.card_tickets.grid(row=0, column=2, sticky='ew', padx=(8, 0))

	def _make_stat_card(self, parent, title: str, accent: str):
		"""Crea una tarjeta con borde de acento izquierdo."""
		outer = ctk.CTkFrame(
			parent,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		outer.grid_columnconfigure(1, weight=1)

		# Barra lateral de acento (4px)
		bar = ctk.CTkFrame(outer, fg_color=accent, width=4, corner_radius=0)
		bar.grid(row=0, column=0, sticky='ns', padx=(0, 0), pady=0)
		bar.grid_propagate(False)

		content = ctk.CTkFrame(outer, fg_color='transparent')
		content.grid(row=0, column=1, sticky='nsew', padx=14, pady=14)

		ctk.CTkLabel(
			content,
			text=title.upper(),
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(anchor='w')

		lbl_val = ctk.CTkLabel(
			content,
			text='—',
			font=FONT_STAT,
			text_color=accent,
			anchor='w',
		)
		lbl_val.pack(anchor='w', pady=(4, 0))

		lbl_sub = ctk.CTkLabel(
			content,
			text='',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
			anchor='w',
		)
		lbl_sub.pack(anchor='w', pady=(2, 0))

		return outer, lbl_val, lbl_sub

	def _build_chart_area(self):
		self.chart_frame = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.chart_frame.grid(
			row=3, column=0, sticky='nsew', padx=(20, 8), pady=(0, 20)
		)

	def _build_top_products_area(self):
		self.top_frame = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.top_frame.grid(row=3, column=1, sticky='nsew', padx=(8, 20), pady=(0, 20))

	# =========================================================
	# CARGA DE DATOS
	# =========================================================
	def load_dashboard_data(self):
		if hasattr(self, 'btn_refresh'):
			self.btn_refresh.configure(state='disabled', text='↻  Cargando...')

		tenant_id = self.ctx.tenant_id
		revenue, profit, tickets = self.controller.get_today_stats(tenant_id)

		rev_f = float(revenue)
		pro_f = float(profit)
		margin = (pro_f / rev_f * 100) if rev_f > 0 else 0.0

		self.lbl_ventas.configure(text=f'${rev_f:,.0f}')
		self.lbl_ventas_sub.configure(
			text=f'{int(tickets)} tickets · ${rev_f / max(tickets, 1):,.0f} prom.'
		)

		self.lbl_ganancia.configure(text=f'${pro_f:,.0f}')
		self.lbl_ganancia_sub.configure(text=f'Margen {margin:.1f}%')

		self.lbl_tickets.configure(text=str(tickets))
		self.lbl_tickets_sub.configure(text='ventas completadas hoy')

		self.draw_weekly_chart(tenant_id)
		self.draw_top_products(tenant_id)

		if hasattr(self, 'btn_refresh'):
			self.btn_refresh.configure(state='normal', text='↻  Actualizar')

	# =========================================================
	# GRÁFICO SEMANAL
	# =========================================================
	def draw_weekly_chart(self, tenant_id):
		# Limpieza correcta de memoria
		if self.canvas_widget:
			self.canvas_widget.destroy()
			self.canvas_widget = None
		if self._fig is not None:
			plt.close(self._fig)
			self._fig = None
		for w in self.chart_frame.winfo_children():
			w.destroy()

		dates, totals = self.controller.get_weekly_sales(tenant_id)

		# Header del panel
		hdr = ctk.CTkFrame(self.chart_frame, fg_color='transparent')
		hdr.pack(fill='x', padx=16, pady=(14, 0))
		ctk.CTkLabel(
			hdr,
			text='Ventas — últimos 7 días',
			font=('Arial', 13, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		if not dates:
			ctk.CTkLabel(
				self.chart_frame,
				text='No hay ventas registradas esta semana.',
				text_color=TEXT_MUTED,
				font=('Arial', 13),
			).pack(expand=True)
			return

		float_totals = [float(t) for t in totals]
		bar_colors = [
			_BAR_TODAY if i == len(dates) - 1 else _BAR_NORMAL
			for i in range(len(dates))
		]

		self._fig = Figure(figsize=(5, 3), dpi=100)
		self._fig.patch.set_facecolor(_CHART_BG)

		ax = self._fig.add_subplot(111)
		ax.set_facecolor(_CHART_BG)

		bars = ax.bar(
			dates,
			float_totals,
			color=bar_colors,
			width=0.55,
			edgecolor='none',
			zorder=2,
		)

		# Valor encima de la barra de hoy
		if float_totals:
			last_val = float_totals[-1]
			ax.text(
				len(dates) - 1,
				last_val * 1.04,
				f'${last_val:,.0f}',
				ha='center',
				va='bottom',
				color=ACCENT_TEXT,
				fontsize=8,
				fontweight='bold',
			)

		# Estilos del eje
		ax.yaxis.grid(True, color=_GRID_COLOR, linewidth=0.8, zorder=0)
		ax.set_axisbelow(True)
		ax.spines['top'].set_visible(False)
		ax.spines['right'].set_visible(False)
		ax.spines['bottom'].set_color(_AXIS_COLOR)
		ax.spines['left'].set_color(_AXIS_COLOR)
		ax.tick_params(axis='both', colors=_TICK_COLOR, labelsize=9)
		ax.yaxis.set_tick_params(labelcolor=_TICK_COLOR)

		self._fig.subplots_adjust(left=0.12, right=0.97, top=0.93, bottom=0.12)

		canvas = FigureCanvasTkAgg(self._fig, master=self.chart_frame)
		canvas.draw()
		self.canvas_widget = canvas.get_tk_widget()
		self.canvas_widget.configure(bg=_CHART_BG, highlightthickness=0)
		self.canvas_widget.pack(fill='both', expand=True, padx=10, pady=(6, 10))

	# =========================================================
	# TOP 5 PRODUCTOS
	# =========================================================
	def draw_top_products(self, tenant_id):
		for w in self.top_frame.winfo_children():
			w.destroy()

		# Header
		hdr = ctk.CTkFrame(self.top_frame, fg_color='transparent')
		hdr.pack(fill='x', padx=16, pady=(14, 8))
		ctk.CTkLabel(
			hdr,
			text='🏆 Top 5 Productos',
			font=('Arial', 13, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		top_items = self.controller.get_top_products(tenant_id)

		if not top_items:
			ctk.CTkLabel(
				self.top_frame,
				text='Aún no hay ventas\nregistradas.',
				text_color=TEXT_MUTED,
				font=('Arial', 12),
				justify='center',
			).pack(expand=True)
			return

		max_qty = float(top_items[0].get('quantity', 1)) if top_items else 1
		accent_colors = [ACCENT, ACCENT, ACCENT, TEXT_MUTED, TEXT_MUTED]

		for i, item in enumerate(top_items):
			desc = item.get('description', 'Desconocido')
			qty = float(item.get('quantity', 0))
			qty_str = f'{int(qty)}' if qty.is_integer() else f'{qty:.1f}'
			pct = int(qty / max_qty * 100) if max_qty > 0 else 0

			# Recortar nombre largo
			if len(desc) > 22:
				desc = desc[:19] + '…'

			row = ctk.CTkFrame(self.top_frame, fg_color='transparent')
			row.pack(fill='x', padx=14, pady=(0, 10))

			# Número de ranking
			ctk.CTkLabel(
				row,
				text=f'{i + 1}',
				font=('Arial', 10, 'bold'),
				text_color=accent_colors[i],
				width=18,
				anchor='center',
			).pack(side='left')

			col = ctk.CTkFrame(row, fg_color='transparent')
			col.pack(side='left', fill='x', expand=True, padx=(8, 0))

			name_row = ctk.CTkFrame(col, fg_color='transparent')
			name_row.pack(fill='x')

			ctk.CTkLabel(
				name_row,
				text=desc,
				font=('Arial', 11),
				text_color=TEXT_PRIMARY,
				anchor='w',
			).pack(side='left')

			ctk.CTkLabel(
				name_row,
				text=f'{qty_str} u',
				font=('Arial', 11, 'bold'),
				text_color=accent_colors[i],
				anchor='e',
			).pack(side='right')

			# Barra de progreso
			bar_bg = ctk.CTkFrame(col, fg_color=SURFACE3, height=6, corner_radius=3)
			bar_bg.pack(fill='x', pady=(3, 0))
			bar_fill_width = max(int(pct / 100 * 160), 4)
			ctk.CTkFrame(
				bar_bg,
				fg_color=accent_colors[i],
				height=6,
				width=bar_fill_width,
				corner_radius=3,
			).place(x=0, y=0)

	# =========================================================
	# DESTROY
	# =========================================================
	def destroy(self):
		if self._fig is not None:
			plt.close(self._fig)
			self._fig = None
		super().destroy()
