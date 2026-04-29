"""
views/data_sync_view.py
=======================
Vista para la exportación e importación masiva de datos (Excel).
Incluye mapa de referencia de columnas, detección automática de alias,
vista previa de datos y prevención de errores mediante validación estricta.
"""

import logging
import os
import platform
import subprocess
from tkinter import filedialog

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.data_sync_controller import COLUMN_SPEC, DataSyncController
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


class DataSyncView(BaseView):
	"""
	Gestiona la interfaz de usuario para la sincronización de archivos Excel.
	Aplica bloqueos de estado y validación visual antes de invocar al controlador.
	"""

	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = DataSyncController(ctx.db_engine)
		self.selected_file = None

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		self._build_export_panel()
		self._build_import_panel()

		# Atajos de teclado globales para agilizar el flujo operativo
		self.bind('<Control-e>', lambda e: self.handle_export())
		self.bind(
			'<Control-i>',
			lambda e: (
				self.handle_import()
				if self.btn_import.cget('state') == 'normal'
				else None
			),
		)

	def _get_desktop_path(self):
		"""Resuelve la ruta absoluta al escritorio del usuario en distintos SO e idiomas."""
		desktop = os.path.join(os.path.expanduser('~'), 'Desktop')
		if not os.path.exists(desktop):
			desktop = os.path.join(os.path.expanduser('~'), 'Escritorio')
		return desktop

	# ===========================================================
	# CONSTRUCCIÓN DE INTERFAZ: PANEL IZQUIERDO (EXPORTACIÓN)
	# ===========================================================
	def _build_export_panel(self):
		"""Inicializa los controles para la generación y descarga de plantillas Excel."""
		scroll = ctk.CTkScrollableFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		scroll.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)
		scroll.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			scroll,
			text='Exportar Datos',
			font=('Arial', 18, 'bold'),
			text_color=ACCENT_TEXT,
			anchor='w',
		).pack(padx=24, pady=(24, 2), anchor='w')

		ctk.CTkLabel(
			scroll,
			text='Descarga tus datos como Excel para editarlos\no compartirlos con tu contador.',
			font=('Arial', 11),
			text_color=TEXT_MUTED,
			justify='left',
			anchor='w',
		).pack(padx=24, pady=(0, 14), anchor='w')

		ctk.CTkLabel(
			scroll,
			text='QUÉ DATOS EXPORTAR',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=24, anchor='w')

		self.combo_export_type = ctk.CTkComboBox(
			scroll,
			values=['Articulos', 'Clientes'],
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			state='readonly',
		)
		self.combo_export_type.set('Articulos')
		self.combo_export_type.pack(pady=(2, 12), padx=24, fill='x')

		self.btn_export = ctk.CTkButton(
			scroll,
			text='Descargar Archivo Excel (Ctrl+E)',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=44,
			corner_radius=8,
			command=self.handle_export,
		)
		self.btn_export.pack(pady=(0, 20), padx=24, fill='x')

		ctk.CTkFrame(scroll, height=1, fg_color=BORDER).pack(
			fill='x', padx=24, pady=(0, 20)
		)

		# Mapa de Referencia Documental
		ctk.CTkLabel(
			scroll,
			text='Mapa de Referencia - Artículos',
			font=('Arial', 14, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(padx=24, anchor='w', pady=(0, 4))

		ctk.CTkLabel(
			scroll,
			text='El sistema acepta estas columnas al importar.\nLos nombres alternativos (alias) también funcionan.',
			font=('Arial', 11),
			text_color=TEXT_MUTED,
			justify='left',
			anchor='w',
		).pack(padx=24, anchor='w', pady=(0, 12))

		for spec in COLUMN_SPEC:
			self._build_column_spec_card(scroll, spec)

		ctk.CTkFrame(scroll, height=1, fg_color=BORDER).pack(
			fill='x', padx=24, pady=(16, 12)
		)

		ctk.CTkLabel(
			scroll,
			text='Alias aceptados por columna',
			font=('Arial', 12, 'bold'),
			text_color=TEXT_SECONDARY,
			anchor='w',
		).pack(padx=24, anchor='w', pady=(0, 8))

		aliases_info = [
			('Nombre', 'name, articulo, producto, descripcion, item'),
			('Codigo_Barras', 'barcode, sku, ean, codigo, cod, ref, referencia'),
			('Costo', 'cost, precio_costo, costo_unitario, p_costo'),
			('Precio_Venta', 'precio, price, pvp, venta, p_venta'),
			('Stock', 'cantidad, quantity, qty, existencias, inventario'),
			('Proveedor', 'supplier, vendor, marca, fabricante'),
		]

		for col, aliases in aliases_info:
			row = ctk.CTkFrame(scroll, fg_color='transparent')
			row.pack(fill='x', padx=24, pady=(0, 4))
			ctk.CTkLabel(
				row,
				text=col,
				font=('Consolas', 11, 'bold'),
				text_color=ACCENT_TEXT,
				width=110,
				anchor='w',
			).pack(side='left')
			ctk.CTkLabel(
				row,
				text=aliases,
				font=('Arial', 10),
				text_color=TEXT_MUTED,
				anchor='w',
			).pack(side='left', padx=(4, 0))

		ctk.CTkLabel(scroll, text='', height=8).pack()

	def _build_column_spec_card(self, parent, spec):
		"""Genera un componente visual detallando la especificación de una columna de importación."""
		is_required = spec['required']
		card = ctk.CTkFrame(
			parent,
			fg_color=SURFACE1,
			corner_radius=8,
			border_width=1,
			border_color=BORDER,
		)
		card.pack(fill='x', padx=24, pady=(0, 6))
		card.grid_columnconfigure(1, weight=1)

		accent = GREEN if is_required else ORANGE
		ctk.CTkFrame(card, width=4, fg_color=accent, corner_radius=0).grid(
			row=0, column=0, rowspan=2, sticky='ns'
		)

		header = ctk.CTkFrame(card, fg_color='transparent')
		header.grid(row=0, column=1, sticky='w', padx=(10, 8), pady=(8, 2))

		ctk.CTkLabel(
			header,
			text=spec['canonical'],
			font=('Consolas', 12, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(side='left')

		badge_color = GREEN_DIM if is_required else ORANGE_DIM
		badge_text_color = GREEN_TEXT if is_required else ORANGE_TEXT
		badge_text = 'Obligatoria' if is_required else 'Opcional'

		ctk.CTkLabel(
			header,
			text=badge_text,
			font=('Arial', 9, 'bold'),
			fg_color=badge_color,
			text_color=badge_text_color,
			corner_radius=4,
			padx=6,
			pady=1,
		).pack(side='left', padx=(8, 0))

		ctk.CTkLabel(
			header,
			text=f'  {spec["type"]}',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
		).pack(side='left', padx=(8, 0))

		detail = ctk.CTkFrame(card, fg_color='transparent')
		detail.grid(row=1, column=1, sticky='w', padx=(10, 8), pady=(0, 8))

		ctk.CTkLabel(
			detail,
			text=spec['description'],
			font=('Arial', 10),
			text_color=TEXT_SECONDARY,
		).pack(side='left')

		ctk.CTkLabel(
			detail,
			text=f'  Ej: {spec["example"]}',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
		).pack(side='left')

	# ===========================================================
	# CONSTRUCCIÓN DE INTERFAZ: PANEL DERECHO (IMPORTACIÓN)
	# ===========================================================
	def _build_import_panel(self):
		"""Inicializa los controles para la validación e ingesta de archivos Excel locales."""
		self.right_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=16)
		self.right_panel.grid_columnconfigure(0, weight=1)
		self.right_panel.grid_rowconfigure(2, weight=1)

		header = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		header.grid(row=0, column=0, sticky='ew', padx=24, pady=(24, 0))
		header.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			header,
			text='Importar Datos',
			font=('Arial', 18, 'bold'),
			text_color=GREEN_TEXT,
			anchor='w',
		).grid(row=0, column=0, sticky='w')

		ctk.CTkLabel(
			header,
			text='Sube tu Excel con productos. Si el código de barras ya existe se\nactualiza el precio. Si no existe, se crea el artículo nuevo.',
			font=('Arial', 11),
			text_color=TEXT_MUTED,
			justify='left',
			anchor='w',
		).grid(row=1, column=0, sticky='w', pady=(4, 14))

		form = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		form.grid(row=1, column=0, sticky='ew', padx=24, pady=(0, 0))
		form.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			form,
			text='QUÉ DATOS VAS A IMPORTAR',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).grid(row=0, column=0, sticky='w')

		self.combo_import_type = ctk.CTkComboBox(
			form,
			values=['Articulos', 'Clientes'],
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			state='readonly',
			command=self._on_import_type_changed,
		)
		self.combo_import_type.set('Articulos')
		self.combo_import_type.grid(row=1, column=0, sticky='ew', pady=(2, 10))

		self.btn_select_file = ctk.CTkButton(
			form,
			text='Seleccionar archivo .xlsx',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=40,
			corner_radius=8,
			command=self.select_file,
		)
		self.btn_select_file.grid(row=2, column=0, sticky='ew', pady=(0, 6))

		self.lbl_file_path = ctk.CTkLabel(
			form,
			text='Ningún archivo seleccionado',
			font=('Arial', 11),
			text_color=TEXT_MUTED,
			anchor='w',
		)
		self.lbl_file_path.grid(row=3, column=0, sticky='w', pady=(0, 12))

		# Panel para renderizar resultados de la validación previa del archivo
		self.frame_preview = ctk.CTkScrollableFrame(
			self.right_panel,
			fg_color=SURFACE1,
			corner_radius=8,
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		self.frame_preview.grid(row=2, column=0, sticky='nsew', padx=24, pady=(0, 12))
		self.frame_preview.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			self.frame_preview,
			text='Selecciona un archivo para ver la detección de columnas.',
			font=('Arial', 12),
			text_color=TEXT_MUTED,
		).pack(pady=32)

		self.btn_import = ctk.CTkButton(
			self.right_panel,
			text='INICIAR IMPORTACIÓN (Ctrl+I)',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			height=52,
			font=('Arial', 14, 'bold'),
			corner_radius=8,
			state='disabled',
			command=self.handle_import,
		)
		self.btn_import.grid(row=3, column=0, sticky='ew', padx=24, pady=(0, 24))

	# ===========================================================
	# LÓGICA DE NEGOCIO Y EVENTOS
	# ===========================================================
	def _on_import_type_changed(self, choice):
		"""Invalida el archivo cargado para prevenir la inyección cruzada de datos entre entidades."""
		self.selected_file = None
		self.lbl_file_path.configure(
			text='Ningún archivo seleccionado', text_color=TEXT_MUTED
		)
		self.btn_import.configure(state='disabled')
		self._clear_preview()

		ctk.CTkLabel(
			self.frame_preview,
			text=f'Modo cambiado a {choice}. Selecciona un nuevo archivo.',
			font=('Arial', 12),
			text_color=TEXT_MUTED,
		).pack(pady=32)

	def select_file(self):
		"""Invoca el diálogo del SO para seleccionar un archivo, e inicia el proceso de validación."""
		file_path = filedialog.askopenfilename(
			initialdir=self._get_desktop_path(),
			title='Seleccionar archivo Excel',
			filetypes=[('Excel files', '*.xlsx *.xls')],
		)
		if not file_path:
			return

		self.selected_file = file_path
		filename = os.path.basename(file_path)
		self.lbl_file_path.configure(text=filename, text_color=TEXT_PRIMARY)

		entity = self.combo_import_type.get()
		if entity == 'Articulos':
			self._show_file_preview(file_path)
		else:
			self._clear_preview()
			ctk.CTkLabel(
				self.frame_preview,
				text='Vista previa no disponible para Clientes.',
				font=('Arial', 12),
				text_color=TEXT_MUTED,
			).pack(pady=32)
			self.btn_import.configure(state='normal')

	def _clear_preview(self):
		"""Elimina todos los widgets hijos del panel de validación visual."""
		for w in self.frame_preview.winfo_children():
			w.destroy()

	def _show_file_preview(self, file_path):
		"""Solicita el análisis estructural del Excel al controlador y dibuja los resultados."""
		self._clear_preview()
		col_status, rows, error = self.controller.preview_import_file(file_path)

		if error:
			ctk.CTkLabel(
				self.frame_preview,
				text=f'Error al leer el archivo:\n{error}',
				font=('Arial', 12),
				text_color=RED_TEXT,
				wraplength=400,
			).pack(pady=24)
			self.btn_import.configure(state='disabled')
			return

		ctk.CTkLabel(
			self.frame_preview,
			text='Detección de columnas',
			font=('Arial', 13, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(anchor='w', padx=12, pady=(12, 6))

		has_errors = False
		for cs in col_status:
			self._build_column_status_row(cs)
			if cs['required'] and not cs['found']:
				has_errors = True

		if rows:
			ctk.CTkFrame(self.frame_preview, height=1, fg_color=BORDER).pack(
				fill='x', padx=12, pady=(12, 8)
			)
			ctk.CTkLabel(
				self.frame_preview,
				text=f'Primeras {len(rows)} filas detectadas',
				font=('Arial', 13, 'bold'),
				text_color=TEXT_PRIMARY,
				anchor='w',
			).pack(anchor='w', padx=12, pady=(0, 6))

			for i, row in enumerate(rows):
				self._build_preview_row(i + 1, row)

		if has_errors:
			self.btn_import.configure(
				state='disabled', text='FALTAN DATOS (Ver arriba)'
			)
			ctk.CTkLabel(
				self.frame_preview,
				text='Faltan columnas obligatorias. Revisa el Mapa de Referencia.',
				font=('Arial', 12, 'bold'),
				text_color=RED_TEXT,
			).pack(pady=(12, 4))
		else:
			self.btn_import.configure(
				state='normal', text='🚀  INICIAR IMPORTACIÓN (Ctrl+I)'
			)

		ctk.CTkLabel(self.frame_preview, text='', height=8).pack()

	def _build_column_status_row(self, cs):
		"""Dibuja el estado de detección (éxito/fracaso) de una columna individual."""
		found = cs['found']
		required = cs['required']

		if found:
			icon, icon_color, fg = 'OK', GREEN_TEXT, GREEN_DIM
		elif not required:
			icon, icon_color, fg = '--', TEXT_MUTED, SURFACE3
		else:
			icon, icon_color, fg = 'NO', RED_TEXT, SURFACE3

		row = ctk.CTkFrame(self.frame_preview, fg_color='transparent')
		row.pack(fill='x', padx=12, pady=(0, 4))

		ctk.CTkLabel(
			row,
			text=icon,
			font=('Arial', 10, 'bold'),
			text_color=icon_color,
			fg_color=fg,
			corner_radius=4,
			padx=6,
			width=32,
		).pack(side='left', padx=(0, 8))

		ctk.CTkLabel(
			row,
			text=cs['canonical'],
			font=('Consolas', 11, 'bold'),
			text_color=TEXT_PRIMARY if found else TEXT_MUTED,
			width=120,
			anchor='w',
		).pack(side='left')

		if found and cs['original_col'] and cs['original_col'] != cs['canonical']:
			ctk.CTkLabel(
				row,
				text=f'detectada como "{cs["original_col"]}"',
				font=('Arial', 10),
				text_color=ORANGE_TEXT,
			).pack(side='left', padx=(4, 0))
		elif found:
			ctk.CTkLabel(
				row,
				text='nombre exacto',
				font=('Arial', 10),
				text_color=TEXT_MUTED,
			).pack(side='left', padx=(4, 0))
		elif not required:
			ctk.CTkLabel(
				row,
				text='opcional, no encontrada',
				font=('Arial', 10),
				text_color=TEXT_MUTED,
			).pack(side='left', padx=(4, 0))
		else:
			ctk.CTkLabel(
				row,
				text='OBLIGATORIA - no encontrada',
				font=('Arial', 10, 'bold'),
				text_color=RED_TEXT,
			).pack(side='left', padx=(4, 0))

	def _build_preview_row(self, num, row_data):
		"""Renderiza dinámicamente una fila de previsualización basada en el diccionario entregado."""
		card = ctk.CTkFrame(
			self.frame_preview,
			fg_color=SURFACE2,
			corner_radius=6,
			border_width=1,
			border_color=BORDER,
		)
		card.pack(fill='x', padx=12, pady=(0, 4))

		ctk.CTkLabel(
			card,
			text=f'#{num}',
			font=('Arial', 11),
			text_color=TEXT_MUTED,
			width=28,
		).pack(side='left', padx=(8, 4), pady=6)

		for col_name, val in row_data.items():
			if len(str(val)) > 15:
				val = str(val)[:13] + '..'

			is_name_col = col_name == 'Nombre'
			ctk.CTkLabel(
				card,
				text=val,
				font=('Arial', 11, 'bold' if is_name_col else 'normal'),
				text_color=TEXT_PRIMARY if val != '-' else TEXT_MUTED,
				anchor='w',
				width=80,
			).pack(side='left', padx=4, pady=6)

	def handle_export(self):
		"""Verifica parámetros, bloquea el hilo gráfico y solicita el volcado Excel al controlador."""
		entity_type = self.combo_export_type.get()
		tenant_id = self.ctx.tenant_id

		file_path = filedialog.asksaveasfilename(
			initialdir=self._get_desktop_path(),
			defaultextension='.xlsx',
			filetypes=[('Excel files', '*.xlsx')],
			title='Guardar como...',
			initialfile=f'Exportacion_{entity_type}.xlsx',
		)
		if not file_path:
			return

		self.btn_export.configure(state='disabled', text='Generando archivo...')
		self.update_idletasks()

		success, msg = self.controller.export_template(
			tenant_id, entity_type, file_path
		)
		self.btn_export.configure(
			state='normal', text='Descargar Archivo Excel (Ctrl+E)'
		)

		if success:
			CTkMessagebox(
				title='Exportación exitosa',
				message=f'{msg}\n\nUbicación: {file_path}',
				icon='check',
			)
			try:
				if platform.system() == 'Windows':
					os.startfile(file_path)
				elif platform.system() == 'Darwin':
					subprocess.call(['open', file_path])
				else:
					subprocess.call(['xdg-open', file_path])
			except Exception as e:
				logger.warning('No se pudo abrir el archivo automáticamente: %s', e)
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')

	def handle_import(self):
		"""Bloquea controles para evitar concurrencia y procesa el archivo subido en el controlador."""
		if not self.selected_file:
			return

		entity_type = self.combo_import_type.get()

		confirm = CTkMessagebox(
			title='Confirmar Importación',
			message='Este proceso actualizará precios y creará nuevos productos.\nLos cambios no se pueden deshacer automáticamente. ¿Continuar?',
			icon='warning',
			option_1='Cancelar',
			option_2='Sí, Importar',
		)
		if confirm.get() != 'Sí, Importar':
			return

		# Congelamiento intencional de la UI durante procesamiento
		self.btn_import.configure(
			state='disabled', text='⏳ Procesando... Por favor, esperá.'
		)
		self.btn_select_file.configure(state='disabled')
		self.update_idletasks()

		tenant_id = self.ctx.tenant_id
		user_id = self.ctx.user_id

		if entity_type == 'Articulos':
			success, msg = self.controller.import_articles_from_excel(
				tenant_id, user_id, self.selected_file
			)
		elif entity_type == 'Clientes':
			success, msg = self.controller.import_customers_from_excel(
				tenant_id, self.selected_file
			)
		else:
			success, msg = False, 'Tipo de importación no soportado.'

		self.btn_select_file.configure(state='normal')

		if success:
			CTkMessagebox(title='Importación completada', message=msg, icon='check')
			self._on_import_type_changed(entity_type)
		else:
			CTkMessagebox(title='Error en la importación', message=msg, icon='cancel')
			self.btn_import.configure(
				state='normal', text='🚀  REINTENTAR IMPORTACIÓN (Ctrl+I)'
			)
