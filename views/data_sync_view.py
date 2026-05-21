"""
views/data_sync_view.py
=======================
Vista para exportación e importación masiva de datos (Excel).
Layout en tabs (Exportar / Importar). Mapa de referencia colapsable.
El preview del archivo se ejecuta en hilo de fondo para evitar lag.
"""

import logging
import os
import platform
import subprocess
import threading
from tkinter import filedialog

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.data_sync_controller import COLUMN_SPEC, DataSyncController
from core.base_view import BaseView
from core.context import AppContext
from utils.settings_manager import get_reports_path
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
	FONT_NAV_BOLD,
	FONT_SMALL,
	FONT_TITLE,
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

_TAB_EXPORT = '  ↓  Exportar  '
_TAB_IMPORT = '  ↑  Importar  '


class DataSyncView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = DataSyncController(ctx.db_engine)
		self.selected_file = None
		self._ref_expanded = False
		self._ref_built = False

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(0, weight=1)

		self._build_ui()

		top = self.winfo_toplevel()
		self._bind_id_e = top.bind(
			'<Control-e>',
			lambda e: self.handle_export() if self.winfo_exists() else None,
		)
		self._bind_id_i = top.bind(
			'<Control-i>',
			lambda e: (
				self.handle_import()
				if self.winfo_exists() and self.btn_import.cget('state') == 'normal'
				else None
			),
		)

	def destroy_custom(self):
		top = self.winfo_toplevel()
		try:
			top.unbind('<Control-e>', self._bind_id_e)
		except Exception:
			pass
		try:
			top.unbind('<Control-i>', self._bind_id_i)
		except Exception:
			pass

	# ═══════════════════════════════════════════════════════════════════════════
	# LAYOUT PRINCIPAL
	# ═══════════════════════════════════════════════════════════════════════════

	def _build_ui(self):
		self._tabview = ctk.CTkTabview(
			self,
			fg_color=SURFACE2,
			segmented_button_fg_color=SURFACE3,
			segmented_button_selected_color=ACCENT_DIM,
			segmented_button_selected_hover_color=ACCENT,
			segmented_button_unselected_color=SURFACE3,
			segmented_button_unselected_hover_color=SURFACE4,
			text_color=TEXT_PRIMARY,
			border_width=1,
			border_color=BORDER,
			corner_radius=12,
		)
		self._tabview.grid(row=0, column=0, sticky='nsew', padx=16, pady=16)
		self._tabview.add(_TAB_EXPORT)
		self._tabview.add(_TAB_IMPORT)

		self._build_export_tab(self._tabview.tab(_TAB_EXPORT))
		self._build_import_tab(self._tabview.tab(_TAB_IMPORT))

	# ═══════════════════════════════════════════════════════════════════════════
	# TAB: EXPORTAR
	# ═══════════════════════════════════════════════════════════════════════════

	def _build_export_tab(self, parent):
		parent.grid_columnconfigure(0, weight=1)
		parent.grid_rowconfigure(0, weight=1)

		scroll = ctk.CTkScrollableFrame(
			parent,
			fg_color='transparent',
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		scroll.grid(row=0, column=0, sticky='nsew')
		scroll.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			scroll,
			text='Exportar Datos',
			font=FONT_TITLE,
			text_color=ACCENT_TEXT,
			anchor='w',
		).pack(padx=24, pady=(24, 4), anchor='w')

		ctk.CTkLabel(
			scroll,
			text='Descargá tus datos como Excel para editarlos o compartirlos con tu contador.',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=24, pady=(0, 20), anchor='w')

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
			text='↓  Descargar Excel (Ctrl+E)',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=44,
			corner_radius=8,
			font=FONT_BODY_BOLD,
			command=self.handle_export,
		)
		self.btn_export.pack(pady=(0, 24), padx=24, fill='x')

		ctk.CTkFrame(scroll, height=1, fg_color=BORDER).pack(
			fill='x', padx=24, pady=(0, 16)
		)

		ctk.CTkLabel(
			scroll,
			text='📌  Tip',
			font=FONT_LABEL_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
		).pack(padx=24, anchor='w')

		ctk.CTkLabel(
			scroll,
			text=(
				'El archivo exportado incluye todos los registros activos con sus valores actuales.\n'
				'Podés editarlo y volver a importarlo para actualizar precios en masa.'
			),
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			justify='left',
			anchor='w',
		).pack(padx=24, pady=(4, 8), anchor='w')

		ctk.CTkLabel(scroll, text='', height=8).pack()

	# ═══════════════════════════════════════════════════════════════════════════
	# TAB: IMPORTAR
	# ═══════════════════════════════════════════════════════════════════════════

	def _build_import_tab(self, parent):
		parent.grid_columnconfigure(0, weight=1)
		parent.grid_rowconfigure(2, weight=1)  # preview se expande

		# ── Pasos 1 y 2 (fijo arriba) ──
		steps = ctk.CTkFrame(parent, fg_color='transparent')
		steps.grid(row=0, column=0, sticky='ew', pady=(0, 10))
		steps.grid_columnconfigure(0, weight=1)
		steps.grid_columnconfigure(2, weight=2)

		# Paso 1: tipo
		box1 = ctk.CTkFrame(
			steps,
			fg_color=SURFACE3,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		box1.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
		box1.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			box1,
			text='①  Tipo de datos',
			font=FONT_LABEL_BOLD,
			text_color=ACCENT_TEXT,
			anchor='w',
		).grid(row=0, column=0, padx=14, pady=(10, 4), sticky='w')

		self.combo_import_type = ctk.CTkComboBox(
			box1,
			values=['Articulos', 'Clientes'],
			fg_color=SURFACE2,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
			state='readonly',
			command=self._on_import_type_changed,
		)
		self.combo_import_type.set('Articulos')
		self.combo_import_type.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 10))

		# Flecha separadora
		ctk.CTkLabel(steps, text='→', font=FONT_HEADING, text_color=TEXT_MUTED).grid(
			row=0, column=1, padx=4
		)

		# Paso 2: archivo
		box2 = ctk.CTkFrame(
			steps,
			fg_color=SURFACE3,
			corner_radius=10,
			border_width=1,
			border_color=BORDER,
		)
		box2.grid(row=0, column=2, sticky='nsew', padx=(5, 0))
		box2.grid_columnconfigure(0, weight=1)

		ctk.CTkLabel(
			box2,
			text='②  Archivo Excel',
			font=FONT_LABEL_BOLD,
			text_color=ACCENT_TEXT,
			anchor='w',
		).grid(row=0, column=0, padx=14, pady=(10, 4), sticky='w')

		self.btn_select_file = ctk.CTkButton(
			box2,
			text='📁  Seleccionar .xlsx',
			fg_color=SURFACE2,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=34,
			corner_radius=8,
			font=FONT_LABEL_BOLD,
			command=self.select_file,
		)
		self.btn_select_file.grid(row=1, column=0, sticky='ew', padx=14, pady=(0, 4))

		self.lbl_file_path = ctk.CTkLabel(
			box2,
			text='Ningún archivo seleccionado',
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			anchor='w',
		)
		self.lbl_file_path.grid(row=2, column=0, sticky='w', padx=14, pady=(0, 10))

		# ── Encabezado paso 3 (fijo) ──
		ctk.CTkLabel(
			parent,
			text='③  Vista previa',
			font=FONT_LABEL_BOLD,
			text_color=ACCENT_TEXT,
			anchor='w',
		).grid(row=1, column=0, sticky='w', pady=(0, 4))

		# ── Preview (se expande para llenar el espacio) ──
		self.frame_preview = ctk.CTkScrollableFrame(
			parent,
			fg_color=SURFACE1,
			corner_radius=8,
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		self.frame_preview.grid(row=2, column=0, sticky='nsew', pady=(0, 10))
		self.frame_preview.grid_columnconfigure(0, weight=1)

		self._show_preview_placeholder(
			'Seleccioná un archivo para ver la vista previa.'
		)

		# ── Botón importar (siempre visible) ──
		self.btn_import = ctk.CTkButton(
			parent,
			text='INICIAR IMPORTACIÓN (Ctrl+I)',
			fg_color=GREEN_DIM,
			hover_color=GREEN,
			text_color=GREEN_TEXT,
			border_width=1,
			border_color=GREEN,
			height=48,
			font=FONT_HEADING,
			corner_radius=8,
			state='disabled',
			command=self.handle_import,
		)
		self.btn_import.grid(row=3, column=0, sticky='ew', pady=(0, 6))

		# ── Referencia colapsable ──
		self._btn_toggle_ref = ctk.CTkButton(
			parent,
			text='▶  Ver guía de columnas',
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			anchor='w',
			height=28,
			corner_radius=6,
			font=FONT_SMALL,
			command=self._toggle_reference,
		)
		self._btn_toggle_ref.grid(row=4, column=0, sticky='ew', pady=(0, 0))

		self._ref_container = ctk.CTkScrollableFrame(
			parent,
			fg_color=SURFACE1,
			corner_radius=8,
			height=260,
			scrollbar_button_color=SURFACE3,
			scrollbar_button_hover_color=SURFACE4,
		)
		self._ref_container.grid_columnconfigure(0, weight=1)
		# Arranca colapsado — se hace grid solo al abrir

	# ─────────────────────────────────────────────────────────────────────────
	# HELPERS DE PREVIEW
	# ─────────────────────────────────────────────────────────────────────────

	def _show_preview_placeholder(self, text: str, color: str = TEXT_MUTED):
		for w in self.frame_preview.winfo_children():
			w.destroy()
		ctk.CTkLabel(
			self.frame_preview,
			text=text,
			font=FONT_BODY,
			text_color=color,
			wraplength=400,
		).pack(pady=32)

	# ─────────────────────────────────────────────────────────────────────────
	# REFERENCIA COLAPSABLE
	# ─────────────────────────────────────────────────────────────────────────

	def _toggle_reference(self):
		if self._ref_expanded:
			self._ref_container.grid_remove()
			self._btn_toggle_ref.configure(text='▶  Ver guía de columnas')
			self._ref_expanded = False
		else:
			if not self._ref_built:
				self._fill_reference(self._ref_container)
				self._ref_built = True
			self._ref_container.grid(row=5, column=0, sticky='ew', pady=(4, 4))
			self._btn_toggle_ref.configure(text='▼  Ocultar guía de columnas')
			self._ref_expanded = True

	def _fill_reference(self, parent):
		ctk.CTkLabel(
			parent,
			text='Mapa de columnas — Artículos',
			font=FONT_BODY_BOLD,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(padx=16, pady=(12, 8), anchor='w')

		for spec in COLUMN_SPEC:
			self._build_column_spec_card(parent, spec)

		ctk.CTkFrame(parent, height=1, fg_color=BORDER).pack(
			fill='x', padx=16, pady=(10, 8)
		)

		ctk.CTkLabel(
			parent,
			text='Alias aceptados por columna',
			font=FONT_BODY_BOLD,
			text_color=TEXT_SECONDARY,
			anchor='w',
		).pack(padx=16, anchor='w', pady=(0, 6))

		aliases_info = [
			('Nombre', 'name, articulo, producto, descripcion, item'),
			('Codigo_Barras', 'barcode, sku, ean, codigo, cod, ref, referencia'),
			('Costo', 'cost, precio_costo, costo_unitario, p_costo'),
			('Precio_Venta', 'precio, price, pvp, venta, p_venta'),
			('Stock', 'cantidad, quantity, qty, existencias, inventario'),
			('Proveedor', 'supplier, vendor, marca, fabricante'),
		]

		for col, aliases in aliases_info:
			row = ctk.CTkFrame(parent, fg_color='transparent')
			row.pack(fill='x', padx=16, pady=(0, 4))
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
				font=FONT_LABEL,
				text_color=TEXT_MUTED,
				anchor='w',
			).pack(side='left', padx=(4, 0))

		ctk.CTkLabel(parent, text='', height=8).pack()

	def _build_column_spec_card(self, parent, spec):
		is_required = spec['required']
		card = ctk.CTkFrame(
			parent,
			fg_color=SURFACE2,
			corner_radius=8,
			border_width=1,
			border_color=BORDER,
		)
		card.pack(fill='x', padx=16, pady=(0, 6))
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

		ctk.CTkLabel(
			header,
			text='Obligatoria' if is_required else 'Opcional',
			font=('Arial', 9, 'bold'),
			fg_color=GREEN_DIM if is_required else ORANGE_DIM,
			text_color=GREEN_TEXT if is_required else ORANGE_TEXT,
			corner_radius=4,
			padx=6,
			pady=1,
		).pack(side='left', padx=(8, 0))

		ctk.CTkLabel(
			header,
			text=f'  {spec["type"]}',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(side='left', padx=(8, 0))

		detail = ctk.CTkFrame(card, fg_color='transparent')
		detail.grid(row=1, column=1, sticky='w', padx=(10, 8), pady=(0, 8))

		ctk.CTkLabel(
			detail,
			text=spec['description'],
			font=FONT_LABEL,
			text_color=TEXT_SECONDARY,
		).pack(side='left')

		ctk.CTkLabel(
			detail,
			text=f'  Ej: {spec["example"]}',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(side='left')

	# ═══════════════════════════════════════════════════════════════════════════
	# EVENTOS DE IMPORTACIÓN
	# ═══════════════════════════════════════════════════════════════════════════

	def _on_import_type_changed(self, choice):
		self.selected_file = None
		self.lbl_file_path.configure(
			text='Ningún archivo seleccionado', text_color=TEXT_MUTED
		)
		self.btn_import.configure(state='disabled', text='INICIAR IMPORTACIÓN (Ctrl+I)')
		self._show_preview_placeholder(
			f'Tipo cambiado a {choice}. Seleccioná un nuevo archivo.'
		)

	def select_file(self):
		file_path = filedialog.askopenfilename(
			initialdir=get_reports_path(),
			title='Seleccionar archivo Excel',
			filetypes=[('Excel files', '*.xlsx *.xls')],
		)
		if not file_path:
			return

		self.selected_file = file_path
		self.lbl_file_path.configure(
			text=os.path.basename(file_path), text_color=TEXT_PRIMARY
		)

		if self.combo_import_type.get() == 'Articulos':
			self._start_preview_loading(file_path)
		else:
			self._show_preview_placeholder('Vista previa no disponible para Clientes.')
			self.btn_import.configure(
				state='normal', text='🚀  INICIAR IMPORTACIÓN (Ctrl+I)'
			)

	def _start_preview_loading(self, file_path):
		self.btn_select_file.configure(state='disabled')
		self.btn_import.configure(state='disabled', text='INICIAR IMPORTACIÓN (Ctrl+I)')
		self._show_preview_placeholder('⏳  Leyendo archivo…')

		def worker():
			col_status, rows, error = self.controller.preview_import_file(file_path)
			self.after(0, lambda: self._on_preview_done(col_status, rows, error))

		threading.Thread(target=worker, daemon=True).start()

	def _on_preview_done(self, col_status, rows, error):
		if not self.winfo_exists():
			return
		self.btn_select_file.configure(state='normal')
		self._render_preview(col_status, rows, error)

	def _render_preview(self, col_status, rows, error):
		for w in self.frame_preview.winfo_children():
			w.destroy()

		if error:
			ctk.CTkLabel(
				self.frame_preview,
				text=f'Error al leer el archivo:\n{error}',
				font=FONT_BODY,
				text_color=RED_TEXT,
				wraplength=400,
			).pack(pady=24)
			self.btn_import.configure(
				state='disabled', text='INICIAR IMPORTACIÓN (Ctrl+I)'
			)
			return

		ctk.CTkLabel(
			self.frame_preview,
			text='Detección de columnas',
			font=FONT_NAV_BOLD,
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
				font=FONT_NAV_BOLD,
				text_color=TEXT_PRIMARY,
				anchor='w',
			).pack(anchor='w', padx=12, pady=(0, 6))

			for i, row in enumerate(rows):
				self._build_preview_row(i + 1, row)

		if has_errors:
			ctk.CTkLabel(
				self.frame_preview,
				text='Faltan columnas obligatorias. Consultá la guía de columnas.',
				font=FONT_BODY_BOLD,
				text_color=RED_TEXT,
			).pack(pady=(12, 4))
			self.btn_import.configure(
				state='disabled', text='FALTAN COLUMNAS OBLIGATORIAS'
			)
		else:
			self.btn_import.configure(
				state='normal', text='🚀  INICIAR IMPORTACIÓN (Ctrl+I)'
			)

		ctk.CTkLabel(self.frame_preview, text='', height=8).pack()

	def _build_column_status_row(self, cs):
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
			font=FONT_LABEL_BOLD,
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
			label = f'detectada como "{cs["original_col"]}"'
			color = ORANGE_TEXT
		elif found:
			label = 'nombre exacto'
			color = TEXT_MUTED
		elif not required:
			label = 'opcional, no encontrada'
			color = TEXT_MUTED
		else:
			label = 'OBLIGATORIA — no encontrada'
			color = RED_TEXT

		ctk.CTkLabel(
			row,
			text=label,
			font=FONT_LABEL_BOLD if (not found and required) else FONT_LABEL,
			text_color=color,
		).pack(side='left', padx=(4, 0))

	def _build_preview_row(self, num, row_data):
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
			font=FONT_SMALL,
			text_color=TEXT_MUTED,
			width=28,
		).pack(side='left', padx=(8, 4), pady=6)

		for col_name, val in row_data.items():
			if len(str(val)) > 15:
				val = str(val)[:13] + '..'
			ctk.CTkLabel(
				card,
				text=val,
				font=('Arial', 11, 'bold' if col_name == 'Nombre' else 'normal'),
				text_color=TEXT_PRIMARY if val != '-' else TEXT_MUTED,
				anchor='w',
				width=80,
			).pack(side='left', padx=4, pady=6)

	# ═══════════════════════════════════════════════════════════════════════════
	# EXPORTAR
	# ═══════════════════════════════════════════════════════════════════════════

	def handle_export(self):
		from datetime import datetime

		entity_type = self.combo_export_type.get()
		tenant_id = self.ctx.tenant_id
		file_path = os.path.join(
			get_reports_path(),
			f'Exportacion_{entity_type}_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx',
		)

		self.btn_export.configure(state='disabled', text='⏳  Generando archivo...')

		def worker():
			try:
				success, msg = self.controller.export_template(
					tenant_id, entity_type, file_path
				)
			except Exception as e:
				success, msg = False, f'Error del sistema: {str(e)}'
			self.after(0, lambda: self._on_export_done(success, msg, file_path))

		threading.Thread(target=worker, daemon=True).start()

	def _on_export_done(self, success, msg, file_path):
		if not self.winfo_exists():
			return

		self.btn_export.configure(state='normal', text='↓  Descargar Excel (Ctrl+E)')

		if success:
			self.show_toast(f'{msg}  ·  {file_path}', 'success', 4000)
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
			self.show_toast(msg, 'error')

	# ═══════════════════════════════════════════════════════════════════════════
	# IMPORTAR
	# ═══════════════════════════════════════════════════════════════════════════

	def handle_import(self):
		if not self.selected_file:
			return

		entity_type = self.combo_import_type.get()

		confirm = CTkMessagebox(
			title='Confirmar Importación',
			message=(
				'Este proceso actualizará precios y creará nuevos productos.\n'
				'Los cambios no se pueden deshacer automáticamente. ¿Continuar?'
			),
			icon='warning',
			option_1='Cancelar',
			option_2='Sí, Importar',
		)
		if confirm.get() != 'Sí, Importar':
			return

		self.btn_import.configure(
			state='disabled', text='⏳  Procesando… Por favor, esperá.'
		)
		self.btn_select_file.configure(state='disabled')

		tenant_id = self.ctx.tenant_id
		user_id = self.ctx.user_id

		def worker():
			try:
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
			except Exception as e:
				success, msg = False, f'Error en procesamiento: {str(e)}'
			self.after(0, lambda: self._on_import_done(success, msg, entity_type))

		threading.Thread(target=worker, daemon=True).start()

	def _on_import_done(self, success, msg, entity_type):
		if not self.winfo_exists():
			return

		self.btn_select_file.configure(state='normal')

		if success:
			CTkMessagebox(title='Importación Finalizada', message=msg, icon='check')
			self._on_import_type_changed(entity_type)
		else:
			self.show_toast(msg, 'error')
			self.btn_import.configure(
				state='normal', text='🚀  REINTENTAR IMPORTACIÓN (Ctrl+I)'
			)
