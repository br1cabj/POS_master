"""
views/settings_view.py
======================
Página de configuración del negocio — Design System Dark Pro 2026.
Secciones: Empresa · Moneda · Ventas · Base de Datos
"""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

import utils.settings_manager as cfg
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
)

logger = logging.getLogger(__name__)

# Símbolos de moneda rápidos
CURRENCY_SYMBOLS = ['$', '€', 'S/.', '£', 'R$', '₱', '¥', '₩']


def _section_card(parent, title: str, icon: str) -> ctk.CTkFrame:
	"""Crea una card con header de sección."""
	card = ctk.CTkFrame(
		parent, fg_color=SURFACE2, corner_radius=12, border_width=1, border_color=BORDER
	)

	hdr = ctk.CTkFrame(card, fg_color='transparent')
	hdr.pack(fill='x', padx=16, pady=(14, 4))
	ctk.CTkLabel(
		hdr,
		text=f'{icon}  {title}',
		font=('Arial', 13, 'bold'),
		text_color=TEXT_PRIMARY,
		anchor='w',
	).pack(side='left')

	ctk.CTkFrame(card, height=1, fg_color=BORDER, corner_radius=0).pack(
		fill='x', padx=14, pady=(0, 10)
	)
	return card


def _field_row(parent, label: str, widget_factory):
	"""Fila label + widget dentro de una card."""
	row = ctk.CTkFrame(parent, fg_color='transparent')
	row.pack(fill='x', padx=16, pady=(0, 10))
	row.grid_columnconfigure(1, weight=1)

	ctk.CTkLabel(
		row,
		text=label,
		font=('Arial', 11),
		text_color=TEXT_SECONDARY,
		anchor='w',
		width=180,
	).grid(row=0, column=0, sticky='w')

	widget = widget_factory(row)
	widget.grid(row=0, column=1, sticky='ew', padx=(8, 0))
	return widget


def _make_entry(parent, value='', placeholder=''):
	e = ctk.CTkEntry(
		parent,
		placeholder_text=placeholder,
		fg_color=SURFACE3,
		border_color=BORDER_ACTIVE,
		text_color=TEXT_PRIMARY,
		height=34,
	)
	if value:
		e.insert(0, str(value))
	return e


class SettingsView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.db_engine = ctx.db_engine
		self._settings = cfg.load()

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		# ── Header ────────────────────────────────────────────────────────
		hdr = ctk.CTkFrame(self, fg_color='transparent')
		hdr.grid(row=0, column=0, sticky='ew', padx=20, pady=(20, 0))

		ctk.CTkLabel(
			hdr,
			text='⚙  Configuración',
			font=('Arial', 22, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		ctk.CTkLabel(
			hdr,
			text='Los cambios se aplican al guardar',
			font=('Arial', 11),
			text_color=TEXT_MUTED,
		).pack(side='left', padx=14)

		ctk.CTkButton(
			hdr,
			text='💾  Guardar Cambios',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			width=160,
			height=36,
			corner_radius=8,
			command=self._save_all,
		).pack(side='right')

		# ── Cuerpo scrollable ─────────────────────────────────────────────
		scroll = ctk.CTkScrollableFrame(
			self,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
		)
		scroll.grid(row=1, column=0, sticky='nsew', padx=20, pady=14)
		scroll.grid_columnconfigure(0, weight=1)
		scroll.grid_columnconfigure(1, weight=1)

		# ── Columna izquierda ─────────────────────────────────────────────
		left = ctk.CTkFrame(scroll, fg_color='transparent')
		left.grid(row=0, column=0, sticky='nsew', padx=(0, 8))

		self._build_empresa(left)
		self._build_datos(left)

		# ── Columna derecha ───────────────────────────────────────────────
		right = ctk.CTkFrame(scroll, fg_color='transparent')
		right.grid(row=0, column=1, sticky='nsew', padx=(8, 0))

		self._build_moneda(right)
		self._build_ventas(right)

	# =========================================================
	# SECCIÓN: EMPRESA
	# =========================================================
	def _build_empresa(self, parent):
		card = _section_card(parent, 'EMPRESA', '🏪')
		card.pack(fill='x', pady=(0, 12))

		self.entry_company_name = _field_row(
			card,
			'Nombre del negocio',
			lambda p: _make_entry(p, self._settings.get('company_name', '')),
		)
		self.entry_company_address = _field_row(
			card,
			'Dirección',
			lambda p: _make_entry(
				p, self._settings.get('company_address', ''), 'Calle, número, ciudad'
			),
		)
		self.entry_company_phone = _field_row(
			card,
			'Teléfono / WhatsApp',
			lambda p: _make_entry(
				p, self._settings.get('company_phone', ''), '+54 11 ...'
			),
		)

		# ── Logo del negocio ──────────────────────────────────────────
		logo_row = ctk.CTkFrame(card, fg_color='transparent')
		logo_row.pack(fill='x', padx=16, pady=(0, 10))
		logo_row.grid_columnconfigure(1, weight=1)
		ctk.CTkLabel(
			logo_row,
			text='Logo del negocio',
			font=('Arial', 11),
			text_color=TEXT_SECONDARY,
			anchor='w',
			width=180,
		).grid(row=0, column=0, sticky='w')

		logo_inner = ctk.CTkFrame(logo_row, fg_color='transparent')
		logo_inner.grid(row=0, column=1, sticky='ew', padx=(8, 0))
		logo_inner.grid_columnconfigure(0, weight=1)

		current_logo = self._settings.get('company_logo_path', '')
		logo_name = os.path.basename(current_logo) if current_logo else 'Sin logo'
		self._lbl_logo_name = ctk.CTkLabel(
			logo_inner,
			text=logo_name,
			font=('Arial', 10),
			text_color=TEXT_MUTED,
			anchor='w',
		)
		self._lbl_logo_name.grid(row=0, column=0, sticky='ew')

		btn_row = ctk.CTkFrame(logo_inner, fg_color='transparent')
		btn_row.grid(row=1, column=0, sticky='w', pady=(4, 0))
		ctk.CTkButton(
			btn_row,
			text='📁  Seleccionar imagen',
			height=30,
			font=('Arial', 11),
			corner_radius=6,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			command=self._pick_logo,
		).pack(side='left', padx=(0, 6))
		ctk.CTkButton(
			btn_row,
			text='✕ Quitar',
			height=30,
			font=('Arial', 10),
			corner_radius=6,
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			command=self._remove_logo,
		).pack(side='left')
		ctk.CTkLabel(
			logo_inner,
			text='PNG / JPG recomendado · tamaño máx. 2 MB',
			font=('Arial', 9),
			text_color=TEXT_MUTED,
		).grid(row=2, column=0, sticky='w', pady=(2, 0))

		# Spacer bottom
		ctk.CTkFrame(card, height=4, fg_color='transparent').pack()

	def _pick_logo(self):
		from tkinter import filedialog

		path = filedialog.askopenfilename(
			title='Seleccionar logo',
			filetypes=[
				('Imágenes', '*.png *.jpg *.jpeg *.gif *.bmp'),
				('Todos', '*.*'),
			],
		)
		if not path:
			return
		if os.path.getsize(path) > 2 * 1024 * 1024:
			CTkMessagebox(
				title='Archivo muy grande',
				message='El logo debe pesar menos de 2 MB.',
				icon='warning',
			)
			return
		# Copiar el logo a la carpeta del proyecto para portabilidad
		dest_dir = os.path.join(
			os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets'
		)
		os.makedirs(dest_dir, exist_ok=True)
		ext = os.path.splitext(path)[1].lower()
		dest = os.path.join(dest_dir, f'logo{ext}')
		shutil.copy2(path, dest)
		self._settings['company_logo_path'] = dest
		cfg.save(self._settings)
		self._lbl_logo_name.configure(
			text=os.path.basename(dest), text_color=GREEN_TEXT
		)
		CTkMessagebox(
			title='Logo guardado',
			message='El logo se guardó y se usará en los presupuestos PDF.',
			icon='check',
		)

	def _remove_logo(self):
		self._settings['company_logo_path'] = ''
		cfg.save(self._settings)
		self._lbl_logo_name.configure(text='Sin logo', text_color=TEXT_MUTED)

	# =========================================================
	# SECCIÓN: MONEDA
	# =========================================================
	def _build_moneda(self, parent):
		card = _section_card(parent, 'MONEDA', '💱')
		card.pack(fill='x', pady=(0, 12))

		# Quick-pick símbolo
		sym_row = ctk.CTkFrame(card, fg_color='transparent')
		sym_row.pack(fill='x', padx=16, pady=(0, 8))
		ctk.CTkLabel(
			sym_row,
			text='Símbolo de moneda',
			font=('Arial', 11),
			text_color=TEXT_SECONDARY,
			anchor='w',
			width=180,
		).pack(side='left')

		self._sym_var = ctk.StringVar(value=self._settings.get('currency_symbol', '$'))
		btn_frame = ctk.CTkFrame(sym_row, fg_color='transparent')
		btn_frame.pack(side='left', fill='x', expand=True, padx=(8, 0))

		for sym in CURRENCY_SYMBOLS:
			active = sym == self._sym_var.get()
			btn = ctk.CTkButton(
				btn_frame,
				text=sym,
				width=40,
				height=30,
				fg_color=ACCENT_DIM if active else SURFACE3,
				hover_color=ACCENT if active else SURFACE4,
				text_color=ACCENT_TEXT if active else TEXT_SECONDARY,
				border_width=1,
				border_color=ACCENT if active else BORDER,
				corner_radius=6,
				command=lambda s=sym: self._pick_symbol(s),
			)
			btn.pack(side='left', padx=2)

		# Custom symbol
		custom_row = ctk.CTkFrame(card, fg_color='transparent')
		custom_row.pack(fill='x', padx=16, pady=(0, 10))
		ctk.CTkLabel(
			custom_row,
			text='Símbolo personalizado',
			font=('Arial', 11),
			text_color=TEXT_SECONDARY,
			anchor='w',
			width=180,
		).pack(side='left')
		self.entry_custom_sym = ctk.CTkEntry(
			custom_row,
			width=80,
			height=34,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			placeholder_text='Ej: Bs.',
		)
		if self._sym_var.get() not in CURRENCY_SYMBOLS:
			self.entry_custom_sym.insert(0, self._sym_var.get())
		self.entry_custom_sym.pack(side='left', padx=(8, 0))

		ctk.CTkButton(
			custom_row,
			text='Usar',
			width=56,
			height=34,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			corner_radius=6,
			command=self._use_custom_sym,
		).pack(side='left', padx=(6, 0))

		# Decimales
		dec_row = ctk.CTkFrame(card, fg_color='transparent')
		dec_row.pack(fill='x', padx=16, pady=(0, 10))
		ctk.CTkLabel(
			dec_row,
			text='Formato de precios',
			font=('Arial', 11),
			text_color=TEXT_SECONDARY,
			anchor='w',
			width=180,
		).pack(side='left')

		self._dec_var = ctk.IntVar(value=self._settings.get('currency_decimals', 0))
		seg = ctk.CTkSegmentedButton(
			dec_row,
			values=['Sin decimales  ($1.500)', 'Con decimales  ($1.500,00)'],
			variable=None,
			fg_color=SURFACE3,
			selected_color=ACCENT_DIM,
			selected_hover_color=ACCENT,
			unselected_color=SURFACE3,
			unselected_hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			text_color_disabled=TEXT_MUTED,
			command=self._pick_decimals,
		)
		seg.set(
			'Sin decimales  ($1.500)'
			if self._dec_var.get() == 0
			else 'Con decimales  ($1.500,00)'
		)
		seg.pack(side='left', padx=(8, 0))
		self._dec_seg = seg

		# Preview
		self.lbl_currency_preview = ctk.CTkLabel(
			card,
			text='',
			font=('Arial', 13, 'bold'),
			text_color=ACCENT_TEXT,
		)
		self.lbl_currency_preview.pack(anchor='w', padx=16, pady=(0, 12))
		self._update_currency_preview()

	def _pick_symbol(self, sym: str):
		self._sym_var.set(sym)
		self._update_currency_preview()
		# Rebuild section to refresh button colors (easiest approach)
		# We just store the value; visual refresh on next open
		# For immediate feedback we update preview label
		self._update_currency_preview()

	def _use_custom_sym(self):
		val = self.entry_custom_sym.get().strip()
		if val:
			self._sym_var.set(val)
			self._update_currency_preview()

	def _pick_decimals(self, val: str):
		self._dec_var.set(0 if 'Sin' in val else 2)
		self._update_currency_preview()

	def _update_currency_preview(self):
		sym = self._sym_var.get()
		dec = self._dec_var.get()
		sample = 1500.0
		if dec == 0:
			preview = f'{sym}{sample:,.0f}'
		else:
			preview = f'{sym}{sample:,.{dec}f}'
		self.lbl_currency_preview.configure(text=f'Vista previa:  {preview}')

	# =========================================================
	# SECCIÓN: VENTAS
	# =========================================================
	def _build_ventas(self, parent):
		card = _section_card(parent, 'VENTAS Y ALERTAS', '🛒')
		card.pack(fill='x', pady=(0, 12))

		self.entry_tax = _field_row(
			card,
			'IVA / Impuesto por defecto (%)',
			lambda p: _make_entry(
				p, str(self._settings.get('tax_rate', 0.0)), '0 = sin impuesto'
			),
		)

		self.entry_low_stock = _field_row(
			card,
			'Umbral de stock crítico (unid.)',
			lambda p: _make_entry(
				p, str(self._settings.get('low_stock_threshold', 5)), '5'
			),
		)

		# Toggle: pedir cliente en cada venta
		req_row = ctk.CTkFrame(card, fg_color='transparent')
		req_row.pack(fill='x', padx=16, pady=(0, 12))
		ctk.CTkLabel(
			req_row,
			text='Pedir cliente en cada venta',
			font=('Arial', 11),
			text_color=TEXT_SECONDARY,
			anchor='w',
			width=180,
		).pack(side='left')
		self._req_customer_var = ctk.BooleanVar(
			value=self._settings.get('require_customer', False)
		)
		ctk.CTkSwitch(
			req_row,
			text='',
			variable=self._req_customer_var,
			onvalue=True,
			offvalue=False,
			progress_color=ACCENT,
		).pack(side='left', padx=(8, 0))

		# Toggle: barra de atajos
		bar_row = ctk.CTkFrame(card, fg_color='transparent')
		bar_row.pack(fill='x', padx=16, pady=(0, 12))
		ctk.CTkLabel(
			bar_row,
			text='Mostrar barra de atajos',
			font=('Arial', 11),
			text_color=TEXT_SECONDARY,
			anchor='w',
			width=180,
		).pack(side='left')
		self._show_bar_var = ctk.BooleanVar(
			value=self._settings.get('show_shortcuts_bar', True)
		)
		ctk.CTkSwitch(
			bar_row,
			text='',
			variable=self._show_bar_var,
			onvalue=True,
			offvalue=False,
			progress_color=ACCENT,
		).pack(side='left', padx=(8, 0))

	# =========================================================
	# SECCIÓN: BASE DE DATOS
	# =========================================================
	def _build_datos(self, parent):
		card = _section_card(parent, 'BASE DE DATOS', '💾')
		card.pack(fill='x', pady=(0, 12))

		db_path = Path('pos_system.db').resolve()
		ctk.CTkLabel(
			card,
			text=f'Archivo: {db_path.name}',
			font=('Consolas', 11),
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=16, pady=(0, 4))
		ctk.CTkLabel(
			card,
			text=f'Ubicación: {db_path.parent}',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
			wraplength=360,
			anchor='w',
			justify='left',
		).pack(anchor='w', padx=16, pady=(0, 12))

		ctk.CTkButton(
			card,
			text='📂  Hacer Respaldo Ahora',
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			height=38,
			corner_radius=8,
			command=self._backup_db,
		).pack(fill='x', padx=16, pady=(0, 14))

	def _backup_db(self):
		src = Path('pos_system.db')
		if not src.exists():
			CTkMessagebox(
				title='No encontrado',
				message='No se encontró la base de datos pos_system.db',
				icon='cancel',
			)
			return

		timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
		backup_name = f'backup_{timestamp}.db'
		dest = src.parent / backup_name

		try:
			shutil.copy2(src, dest)
			CTkMessagebox(
				title='Respaldo creado',
				message=f'✅ Respaldo guardado como:\n{backup_name}',
				icon='check',
			)
		except Exception as e:
			CTkMessagebox(
				title='Error',
				message=f'No se pudo crear el respaldo:\n{e}',
				icon='cancel',
			)

	# =========================================================
	# GUARDAR TODO
	# =========================================================
	def _save_all(self):
		errors = []

		try:
			tax = float(self.entry_tax.get().strip().replace(',', '.') or '0')
		except ValueError:
			errors.append('IVA debe ser un número (ej: 21)')
			tax = 0.0

		try:
			threshold = int(self.entry_low_stock.get().strip() or '5')
		except ValueError:
			errors.append('Umbral de stock debe ser un número entero')
			threshold = 5

		if errors:
			CTkMessagebox(
				title='Errores de validación',
				message='\n'.join(f'• {e}' for e in errors),
				icon='warning',
			)
			return

		# Construir dict final
		new_settings = {
			'company_name': self.entry_company_name.get().strip(),
			'company_address': self.entry_company_address.get().strip(),
			'company_phone': self.entry_company_phone.get().strip(),
			'currency_symbol': self._sym_var.get(),
			'currency_decimals': self._dec_var.get(),
			'tax_rate': tax,
			'low_stock_threshold': threshold,
			'require_customer': self._req_customer_var.get(),
			'show_shortcuts_bar': self._show_bar_var.get(),
		}

		if cfg.save(new_settings):
			CTkMessagebox(
				title='Configuración guardada',
				message='✅ Los cambios fueron guardados correctamente.',
				icon='check',
			)
		else:
			CTkMessagebox(
				title='Error',
				message='No se pudo guardar la configuración. Verificá los permisos del directorio.',
				icon='cancel',
			)
