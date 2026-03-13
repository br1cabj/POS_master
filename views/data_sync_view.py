import os
import platform
import subprocess
from tkinter import filedialog

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.data_sync_controller import DataSyncController


class DataSyncView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = DataSyncController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=1)
		self.grid_rowconfigure(0, weight=1)

		# === PANEL IZQUIERDO: EXPORTAR (BAJAR EXCEL) ===
		self.left_panel = ctk.CTkFrame(self)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.left_panel,
			text='📤 Exportar Datos',
			font=('Arial', 20, 'bold'),
			text_color='#00aaff',
		).pack(pady=(20, 5))
		ctk.CTkLabel(
			self.left_panel,
			text='Descarga listas para el contador o úsalas como\nplantilla para actualizar precios masivamente.',
			text_color='gray',
		).pack(pady=(0, 20))

		ctk.CTkLabel(
			self.left_panel, text='¿Qué deseas exportar?', font=('Arial', 14)
		).pack(pady=10)

		self.combo_export_type = ctk.CTkComboBox(
			self.left_panel, values=['Artículos', 'Clientes'], width=250
		)
		self.combo_export_type.pack(pady=5)

		self.btn_export = ctk.CTkButton(
			self.left_panel,
			text='💾 Descargar Archivo Excel',
			fg_color='#1f538d',
			height=45,
			command=self.handle_export,
		)
		self.btn_export.pack(pady=30)

		# === PANEL DERECHO: IMPORTAR (SUBIR EXCEL) ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.right_panel,
			text='📥 Importar Datos',
			font=('Arial', 20, 'bold'),
			text_color='#5cb85c',
		).pack(pady=(20, 5))
		ctk.CTkLabel(
			self.right_panel,
			text='Sube tu Excel modificado. Si el código de barras ya\nexiste, se actualizará el precio. Si no, se creará.',
			text_color='gray',
		).pack(pady=(0, 20))

		ctk.CTkLabel(
			self.right_panel, text='¿Qué datos vas a importar?', font=('Arial', 14)
		).pack(pady=10)

		self.combo_import_type = ctk.CTkComboBox(
			self.right_panel, values=['Artículos'], width=250
		)
		self.combo_import_type.pack(pady=5)

		self.btn_select_file = ctk.CTkButton(
			self.right_panel,
			text='📁 Seleccionar archivo .xlsx',
			fg_color='#444444',
			height=40,
			command=self.select_file,
		)
		self.btn_select_file.pack(pady=20)

		self.lbl_file_path = ctk.CTkLabel(
			self.right_panel,
			text='Ningún archivo seleccionado',
			text_color='gray',
			wraplength=300,
		)
		self.lbl_file_path.pack(pady=5)
		self.selected_file = None

		self.btn_import = ctk.CTkButton(
			self.right_panel,
			text='🚀 INICIAR IMPORTACIÓN',
			fg_color='#5cb85c',
			hover_color='#4cae4c',
			height=50,
			font=('Arial', 14, 'bold'),
			state='disabled',
			command=self.handle_import,
		)
		self.btn_import.pack(pady=20)

	def _get_tenant_id(self):
		return (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

	def handle_export(self):
		entity_type = self.combo_export_type.get()
		tenant_id = self._get_tenant_id()

		# Abrir ventana de diálogo para elegir dónde guardar
		file_path = filedialog.asksaveasfilename(
			defaultextension='.xlsx',
			filetypes=[('Excel files', '*.xlsx')],
			title='Guardar Plantilla como...',
			initialfile=f'Exportacion_{entity_type}.xlsx',
		)

		if not file_path:
			return  # El usuario canceló

		success, msg = self.controller.export_template(
			tenant_id, entity_type, file_path
		)

		if success:
			CTkMessagebox(title='¡Exportación Exitosa!', message=msg, icon='check')

			# 🐛 SOLUCIÓN: Apertura Multiplataforma y Excepción Limpia
			try:
				if platform.system() == 'Windows':
					os.startfile(file_path)
				elif platform.system() == 'Darwin':  # macOS
					subprocess.call(['open', file_path])
				else:  # Linux (Ubuntu, Mint, etc.)
					subprocess.call(['xdg-open', file_path])
			except Exception as e:
				# Si falla abrir el Excel (ej. no tiene Office instalado), no pasa nada
				print(f'Nota: No se pudo abrir el archivo automáticamente. {e}')
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')

	def select_file(self):
		file_path = filedialog.askopenfilename(
			title='Seleccionar archivo Excel',
			filetypes=[('Excel files', '*.xlsx *.xls')],
		)

		if file_path:
			self.selected_file = file_path
			self.lbl_file_path.configure(
				text=os.path.basename(file_path), text_color='white'
			)
			self.btn_import.configure(state='normal')

	def handle_import(self):
		if not self.selected_file:
			return

		entity_type = self.combo_import_type.get()

		if entity_type != 'Artículos':
			CTkMessagebox(
				title='Próximamente',
				message='La importación masiva de esta entidad estará disponible pronto.',
				icon='info',
			)
			return

		confirm = CTkMessagebox(
			title='Confirmar Importación',
			message='¿Estás seguro de procesar este archivo? Este proceso actualizará tus precios y creará nuevos productos en la base de datos.',
			icon='warning',
			option_1='Cancelar',
			option_2='Sí, Importar',
		)

		if confirm.get() == 'Sí, Importar':
			tenant_id = self._get_tenant_id()
			user_id = (
				self.current_user.get('id')
				if isinstance(self.current_user, dict)
				else self.current_user.id
			)

			# Desactivamos el botón para evitar dobles clics mientras carga
			self.btn_import.configure(state='disabled', text='Procesando...')
			self.update()  # Fuerza a la UI a actualizarse visualmente

			success, msg = self.controller.import_articles_from_excel(
				tenant_id, user_id, self.selected_file
			)

			if success:
				CTkMessagebox(
					title='¡Importación Finalizada!', message=msg, icon='check'
				)
				self.lbl_file_path.configure(
					text='Ningún archivo seleccionado', text_color='gray'
				)
				self.selected_file = None
			else:
				CTkMessagebox(title='Error', message=msg, icon='cancel')

			self.btn_import.configure(state='disabled', text='🚀 INICIAR IMPORTACIÓN')
