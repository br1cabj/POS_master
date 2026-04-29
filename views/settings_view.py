import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

import utils.settings_manager as cfg
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_HEADING,
	FONT_LABEL,
	FONT_LABEL_BOLD,
	FONT_TITLE,
	GREEN,
	GREEN_DIM,
	GREEN_TEXT,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	PAD_LG,
	PAD_MD,
	PAD_SM,
	PAD_XS,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	make_form_label,
)

logger = logging.getLogger(__name__)

CURRENCY_SYMBOLS = ['$', '€', 'S/.', '£', 'R$', '₱', '¥', '₩']


class SettingsView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.db_engine = ctx.db_engine
		self._settings = cfg.load()
		self._saved = True

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		hdr = ctk.CTkFrame(self, fg_color='transparent')
		hdr.grid(row=0, column=0, sticky='ew', padx=PAD_LG, pady=(PAD_LG, 0))

		ctk.CTkLabel(
			hdr,
			text='⚙  Configuración',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')
		ctk.CTkLabel(
			hdr,
			text='Los cambios se aplican al guardar',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(side='left', padx=PAD_MD)

		self.btn_save = ctk.CTkButton(
			hdr,
			text='\U0001f4be  Guardar Cambios',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			width=160,
			height=36,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self._save_all,
		)
		self.btn_save.pack(side='right')

		scroll = ctk.CTkScrollableFrame(
			self, fg_color='transparent', scrollbar_button_color=SURFACE3
		)
		scroll.grid(row=1, column=0, sticky='nsew', padx=PAD_MD, pady=PAD_MD)
		scroll.grid_columnconfigure(0, weight=1)
		scroll.grid_columnconfigure(1, weight=1)

		left = ctk.CTkFrame(scroll, fg_color='transparent')
		left.grid(row=0, column=0, sticky='nsew', padx=(0, PAD_SM))
		self._build_empresa(left)
		self._build_reportes(left)
		self._build_datos(left)

		right = ctk.CTkFrame(scroll, fg_color='transparent')
		right.grid(row=0, column=1, sticky='nsew', padx=(PAD_SM, 0))
		self._build_moneda(right)
		self._build_ventas(right)

		for entry in (
			self.entry_company_name,
			self.entry_company_address,
			self.entry_company_phone,
			self.entry_tax,
			self.entry_low_stock,
		):
			entry.bind('<KeyRelease>', self._mark_dirty)

	def _section_card(self, parent, title, icon):
		card = ctk.CTkFrame(
			parent,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		hdr = ctk.CTkFrame(card, fg_color='transparent')
		hdr.pack(fill='x', padx=PAD_MD, pady=(PAD_MD, PAD_XS))
		ctk.CTkLabel(
			hdr,
			text=f'{icon}  {title}',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')
		ctk.CTkFrame(card, height=1, fg_color=BORDER, corner_radius=0).pack(
			fill='x', padx=PAD_MD, pady=(0, PAD_SM)
		)
		return card

	def _mark_dirty(self, event=None):
		if self._saved:
			self._saved = False
			self.btn_save.configure(fg_color=GREEN, text_color='white')

	def has_unsaved_changes(self):
		return not self._saved

	def _build_empresa(self, parent):
		card = self._section_card(parent, 'EMPRESA', '\U0001f3ea')
		card.pack(fill='x', pady=(0, PAD_MD))

		make_form_label(card, 'Nombre del negocio').pack(
			anchor='w', padx=PAD_MD, pady=(0, PAD_XS)
		)
		self.entry_company_name = ctk.CTkEntry(
			card,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
			font=FONT_BODY,
		)
		self.entry_company_name.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		self.entry_company_name.insert(0, self._settings.get('company_name', ''))

		make_form_label(card, 'Dirección').pack(
			anchor='w', padx=PAD_MD, pady=(PAD_XS, PAD_XS)
		)
		self.entry_company_address = ctk.CTkEntry(
			card,
			placeholder_text='Calle, número, ciudad',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
			font=FONT_BODY,
		)
		self.entry_company_address.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		self.entry_company_address.insert(0, self._settings.get('company_address', ''))

		make_form_label(card, 'Teléfono / WhatsApp').pack(
			anchor='w', padx=PAD_MD, pady=(PAD_XS, PAD_XS)
		)
		self.entry_company_phone = ctk.CTkEntry(
			card,
			placeholder_text='+54 11 ...',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
			font=FONT_BODY,
		)
		self.entry_company_phone.pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))
		self.entry_company_phone.insert(0, self._settings.get('company_phone', ''))

		ctk.CTkFrame(card, height=1, fg_color=BORDER).pack(
			fill='x', padx=PAD_MD, pady=(0, PAD_SM)
		)
		make_form_label(card, 'Logo del negocio').pack(
			anchor='w', padx=PAD_MD, pady=(0, PAD_XS)
		)

		logo_inner = ctk.CTkFrame(card, fg_color='transparent')
		logo_inner.pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		current_logo = self._settings.get('company_logo_path', '')
		logo_name = os.path.basename(current_logo) if current_logo else 'Sin logo'
		self._lbl_logo_name = ctk.CTkLabel(
			logo_inner,
			text=logo_name,
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			anchor='w',
		)
		self._lbl_logo_name.grid(row=0, column=0, sticky='ew')

		btn_row = ctk.CTkFrame(logo_inner, fg_color='transparent')
		btn_row.grid(row=1, column=0, sticky='w', pady=(4, 0))

		ctk.CTkButton(
			btn_row,
			text='\U0001f4c1  Seleccionar imagen',
			height=30,
			font=FONT_LABEL_BOLD,
			corner_radius=6,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			command=self._pick_logo,
		).pack(side='left', padx=(0, PAD_XS))
		ctk.CTkButton(
			btn_row,
			text='✕ Quitar',
			height=30,
			font=FONT_LABEL,
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
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).grid(row=2, column=0, sticky='w', pady=(PAD_XS, 0))

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
			self.show_warning('El logo debe pesar menos de 2 MB.', 'Archivo muy grande')
			return
		dest_dir = os.path.join(
			os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets'
		)
		os.makedirs(dest_dir, exist_ok=True)
		ext = os.path.splitext(path)[1].lower()
		dest = os.path.join(dest_dir, f'logo{ext}')
		shutil.copy2(path, dest)
		self._settings['company_logo_path'] = dest
		self._mark_dirty()
		self._lbl_logo_name.configure(
			text=os.path.basename(dest), text_color=GREEN_TEXT
		)

	def _remove_logo(self):
		self._settings['company_logo_path'] = ''
		self._mark_dirty()
		self._lbl_logo_name.configure(text='Sin logo', text_color=TEXT_MUTED)

	def _build_moneda(self, parent):
		card = self._section_card(parent, 'MONEDA', '\U0001f4b1')
		card.pack(fill='x', pady=(0, PAD_MD))

		make_form_label(card, 'Símbolo de moneda').pack(
			anchor='w', padx=PAD_MD, pady=(0, PAD_XS)
		)

		sym_row = ctk.CTkFrame(card, fg_color='transparent')
		sym_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))

		self._sym_var = ctk.StringVar(value=self._settings.get('currency_symbol', '$'))

		for sym in CURRENCY_SYMBOLS:
			active = sym == self._sym_var.get()
			ctk.CTkButton(
				sym_row,
				text=sym,
				width=40,
				height=34,
				font=FONT_BODY_BOLD,
				fg_color=ACCENT_DIM if active else SURFACE3,
				hover_color=ACCENT if active else SURFACE4,
				text_color=ACCENT_TEXT if active else TEXT_SECONDARY,
				border_width=1,
				border_color=ACCENT if active else BORDER,
				corner_radius=6,
				command=lambda s=sym: self._pick_symbol(s),
			).pack(side='left', padx=(0, PAD_XS))

		make_form_label(card, 'Símbolo personalizado').pack(
			anchor='w', padx=PAD_MD, pady=(PAD_XS, PAD_XS)
		)
		custom_row = ctk.CTkFrame(card, fg_color='transparent')
		custom_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))

		self.entry_custom_sym = ctk.CTkEntry(
			custom_row,
			width=80,
			height=34,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			placeholder_text='Ej: Bs.',
			font=FONT_BODY,
		)
		if self._sym_var.get() not in CURRENCY_SYMBOLS:
			self.entry_custom_sym.insert(0, self._sym_var.get())
		self.entry_custom_sym.pack(side='left', padx=(0, PAD_XS))

		ctk.CTkButton(
			custom_row,
			text='Usar',
			width=56,
			height=34,
			font=FONT_LABEL_BOLD,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			corner_radius=6,
			command=self._use_custom_sym,
		).pack(side='left')

		make_form_label(card, 'Formato de precios').pack(
			anchor='w', padx=PAD_MD, pady=(PAD_XS, PAD_XS)
		)

		self._dec_var = ctk.IntVar(
			value=int(self._settings.get('currency_decimals', 0))
		)
		seg = ctk.CTkSegmentedButton(
			card,
			values=['Sin decimales  ($1.500)', 'Con decimales  ($1.500,00)'],
			variable=None,
			font=FONT_BODY,
			height=34,
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
		seg.pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		self.lbl_currency_preview = ctk.CTkLabel(
			card, text='', font=FONT_HEADING, text_color=ACCENT_TEXT
		)
		self.lbl_currency_preview.pack(anchor='w', padx=PAD_MD, pady=(0, PAD_MD))
		self._update_currency_preview()

	def _pick_symbol(self, sym):
		self._sym_var.set(sym)
		self._mark_dirty()
		self._update_currency_preview()

	def _use_custom_sym(self):
		val = self.entry_custom_sym.get().strip()
		if val:
			self._sym_var.set(val)
			self._mark_dirty()
			self._update_currency_preview()

	def _pick_decimals(self, val):
		self._dec_var.set(0 if 'Sin' in val else 2)
		self._mark_dirty()
		self._update_currency_preview()

	def _update_currency_preview(self):
		sym = self._sym_var.get()
		dec = self._dec_var.get()
		sample = 1500.0
		if dec == 0:
			preview = f'{sym}{sample:,.0f}'.replace(',', '.')
		else:
			preview = (
				f'{sym}{sample:,.{dec}f}'.replace(',', 'X')
				.replace('.', ',')
				.replace('X', '.')
			)
		self.lbl_currency_preview.configure(text=f'Vista previa:  {preview}')

	def _build_ventas(self, parent):
		card = self._section_card(parent, 'VENTAS Y ALERTAS', '\U0001f6d2')
		card.pack(fill='x', pady=(0, PAD_MD))

		make_form_label(card, 'IVA / Impuesto por defecto (%)').pack(
			anchor='w', padx=PAD_MD, pady=(0, PAD_XS)
		)
		self.entry_tax = ctk.CTkEntry(
			card,
			placeholder_text='0 = sin impuesto',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
			font=FONT_BODY,
		)
		self.entry_tax.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		self.entry_tax.insert(0, str(self._settings.get('tax_rate', 0.0)))

		make_form_label(card, 'Umbral de stock crítico (unid.)').pack(
			anchor='w', padx=PAD_MD, pady=(PAD_XS, PAD_XS)
		)
		self.entry_low_stock = ctk.CTkEntry(
			card,
			placeholder_text='5',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
			font=FONT_BODY,
		)
		self.entry_low_stock.pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))
		self.entry_low_stock.insert(
			0, str(self._settings.get('low_stock_threshold', 5))
		)

		ctk.CTkFrame(card, height=1, fg_color=BORDER).pack(
			fill='x', padx=PAD_MD, pady=(0, PAD_SM)
		)

		req_row = ctk.CTkFrame(card, fg_color='transparent')
		req_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_SM))
		ctk.CTkLabel(
			req_row,
			text='Pedir cliente en cada venta',
			font=FONT_BODY,
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
			progress_color=ACCENT,
			command=self._mark_dirty,
		).pack(side='left', padx=(PAD_SM, 0))

		bar_row = ctk.CTkFrame(card, fg_color='transparent')
		bar_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))
		ctk.CTkLabel(
			bar_row,
			text='Mostrar barra de atajos',
			font=FONT_BODY,
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
			progress_color=ACCENT,
			command=self._mark_dirty,
		).pack(side='left', padx=(PAD_SM, 0))

	def _build_reportes(self, parent):
		card = self._section_card(parent, 'CARPETA DE REPORTES', '\U0001f4c1')
		card.pack(fill='x', pady=(0, PAD_MD))

		ctk.CTkLabel(
			card,
			text='Los reportes, PDFs, CSV y exportaciones se guardarán en esta carpeta.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			wraplength=360,
			anchor='w',
			justify='left',
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		current_path = cfg.get('reports_path', '') or cfg.get_reports_path()
		self._lbl_reports_path = ctk.CTkLabel(
			card,
			text=current_path,
			font=('Consolas', 11),
			text_color=TEXT_SECONDARY,
			wraplength=340,
			anchor='w',
			justify='left',
		)
		self._lbl_reports_path.pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		btn_row = ctk.CTkFrame(card, fg_color='transparent')
		btn_row.pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

		ctk.CTkButton(
			btn_row,
			text='\U0001f4c1  Elegir Carpeta',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=36,
			corner_radius=8,
			font=FONT_LABEL_BOLD,
			command=self._pick_reports_path,
		).pack(side='left', padx=(0, PAD_SM))
		ctk.CTkButton(
			btn_row,
			text='↺ Restaurar Desktop',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			border_width=1,
			border_color=BORDER,
			height=36,
			corner_radius=8,
			font=FONT_LABEL,
			command=self._reset_reports_path,
		).pack(side='left')

	def _pick_reports_path(self):
		from tkinter import filedialog

		path = filedialog.askdirectory(
			title='Seleccionar carpeta de reportes', initialdir=cfg.get_reports_path()
		)
		if not path:
			return
		self._settings['reports_path'] = path
		self._mark_dirty()
		self._lbl_reports_path.configure(text=path)

	def _reset_reports_path(self):
		self._settings['reports_path'] = ''
		self._mark_dirty()
		self._lbl_reports_path.configure(text=cfg.get_reports_path())

	def _build_datos(self, parent):
		card = self._section_card(parent, 'BASE DE DATOS', '\U0001f4be')
		card.pack(fill='x', pady=(0, PAD_MD))

		db_path = Path('pos_system.db').resolve()
		ctk.CTkLabel(
			card,
			text=f'Archivo: {db_path.name}',
			font=('Consolas', 11),
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_XS))
		ctk.CTkLabel(
			card,
			text=f'Ubicación: {db_path.parent}',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			wraplength=360,
			anchor='w',
			justify='left',
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		ctk.CTkButton(
			card,
			text='\U0001f4c2  Hacer Respaldo Ahora',
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			height=38,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self._backup_db,
		).pack(fill='x', padx=PAD_MD, pady=(0, PAD_MD))

	def _backup_db(self):
		db_path = Path('pos_system.db').resolve()
		if not db_path.exists():
			self.show_error(
				"No se encontró el archivo de base de datos 'pos_system.db'."
			)
			return
		dest_folder = cfg.get_reports_path()
		timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
		backup_name = f'respaldo_CloudPOS_{timestamp}.db'
		dest_path = Path(dest_folder) / backup_name
		try:
			shutil.copy2(db_path, dest_path)
			self.show_success(f'Respaldo creado con éxito en:\n{dest_path}')
		except Exception as e:
			logger.error(f'Fallo al respaldar BD: {e}', exc_info=True)
			self.show_error(f'Error al crear el respaldo:\n{e}')

	def _save_all(self):
		self._settings['company_name'] = self.entry_company_name.get().strip()
		self._settings['company_address'] = self.entry_company_address.get().strip()
		self._settings['company_phone'] = self.entry_company_phone.get().strip()
		self._settings['currency_symbol'] = self._sym_var.get()
		self._settings['currency_decimals'] = self._dec_var.get()

		try:
			self._settings['tax_rate'] = float(self.entry_tax.get().replace(',', '.'))
			self._settings['low_stock_threshold'] = int(self.entry_low_stock.get())
		except ValueError:
			self.show_error(
				'El IVA y el Umbral de Stock Crítico deben ser números válidos.'
			)
			return

		self._settings['require_customer'] = self._req_customer_var.get()
		self._settings['show_shortcuts_bar'] = self._show_bar_var.get()

		if cfg.save(self._settings):
			self._saved = True
			self.btn_save.configure(fg_color=GREEN_DIM, text_color=GREEN_TEXT)
			self.show_success('Configuración actualizada correctamente.')
			if hasattr(self.ctx, 'navigate'):
				pass
		else:
			self.show_error('No se pudo guardar la configuración en el disco.')
