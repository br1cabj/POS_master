import logging
import os
import platform
import subprocess
from tkinter import filedialog

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from core.base_view import BaseView
from core.context import AppContext
from controllers.data_sync_controller import DataSyncController
from utils.styles import (
    ACCENT, ACCENT_DIM, ACCENT_TEXT, BORDER, BORDER_ACTIVE,
    GREEN, GREEN_DIM, GREEN_TEXT, SURFACE1, SURFACE2, SURFACE3, SURFACE4,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)

logger = logging.getLogger(__name__)


class DataSyncView(BaseView):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, ctx)
        self.controller = DataSyncController(ctx.db_engine)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Panel izquierdo: Exportar ────────────────────────────────────
        self.left_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)

        ctk.CTkLabel(
            self.left_panel, text='📤  Exportar Datos',
            font=('Arial', 20, 'bold'), text_color=ACCENT_TEXT,
        ).pack(pady=(24, 4))
        ctk.CTkLabel(
            self.left_panel,
            text='Descargá listas para el contador o usálas como\nplantilla para actualizar precios masivamente.',
            font=('Arial', 11), text_color=TEXT_MUTED, justify='center',
        ).pack(pady=(0, 20))

        ctk.CTkLabel(
            self.left_panel, text='¿QUÉ DESEÁS EXPORTAR?',
            font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
        ).pack(padx=24, anchor='w')
        self.combo_export_type = ctk.CTkComboBox(
            self.left_panel, values=['Artículos', 'Clientes'],
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
            button_color=SURFACE3, button_hover_color=SURFACE4,
            dropdown_fg_color=SURFACE2, dropdown_text_color=TEXT_PRIMARY,
        )
        self.combo_export_type.pack(pady=(2, 24), padx=24, fill='x')

        self.btn_export = ctk.CTkButton(
            self.left_panel, text='💾  Descargar Archivo Excel',
            fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=ACCENT_TEXT,
            border_width=1, border_color=ACCENT,
            height=46, corner_radius=8,
            command=self.handle_export,
        )
        self.btn_export.pack(pady=(0, 24), padx=24, fill='x')

        # ── Panel derecho: Importar ──────────────────────────────────────
        self.right_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.right_panel.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=16)

        ctk.CTkLabel(
            self.right_panel, text='📥  Importar Datos',
            font=('Arial', 20, 'bold'), text_color=GREEN_TEXT,
        ).pack(pady=(24, 4))
        ctk.CTkLabel(
            self.right_panel,
            text='Subí tu Excel modificado. Si el código de barras\nexiste, se actualizará el precio. Si no, se creará.',
            font=('Arial', 11), text_color=TEXT_MUTED, justify='center',
        ).pack(pady=(0, 20))

        ctk.CTkLabel(
            self.right_panel, text='¿QUÉ DATOS VAS A IMPORTAR?',
            font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
        ).pack(padx=24, anchor='w')
        self.combo_import_type = ctk.CTkComboBox(
            self.right_panel, values=['Artículos'],
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
            button_color=SURFACE3, button_hover_color=SURFACE4,
            dropdown_fg_color=SURFACE2, dropdown_text_color=TEXT_PRIMARY,
        )
        self.combo_import_type.pack(pady=(2, 16), padx=24, fill='x')

        self.btn_select_file = ctk.CTkButton(
            self.right_panel, text='📁  Seleccionar archivo .xlsx',
            fg_color=SURFACE3, hover_color=SURFACE4,
            text_color=TEXT_SECONDARY, border_width=1, border_color=BORDER,
            height=40, corner_radius=8,
            command=self.select_file,
        )
        self.btn_select_file.pack(pady=(0, 8), padx=24, fill='x')

        self.lbl_file_path = ctk.CTkLabel(
            self.right_panel,
            text='Ningún archivo seleccionado',
            font=('Arial', 11), text_color=TEXT_MUTED, wraplength=300,
        )
        self.lbl_file_path.pack(pady=(0, 16))

        self.selected_file = None

        self.btn_import = ctk.CTkButton(
            self.right_panel, text='🚀  INICIAR IMPORTACIÓN',
            fg_color=GREEN_DIM, hover_color=GREEN, text_color=GREEN_TEXT,
            border_width=1, border_color=GREEN,
            height=52, font=('Arial', 14, 'bold'), corner_radius=8,
            state='disabled',
            command=self.handle_import,
        )
        self.btn_import.pack(pady=(0, 24), padx=24, fill='x')

    def handle_export(self):
        entity_type = self.combo_export_type.get()
        tenant_id = self.ctx.tenant_id

        file_path = filedialog.asksaveasfilename(
            defaultextension='.xlsx',
            filetypes=[('Excel files', '*.xlsx')],
            title='Guardar Plantilla como...',
            initialfile=f'Exportacion_{entity_type}.xlsx',
        )
        if not file_path:
            return

        success, msg = self.controller.export_template(tenant_id, entity_type, file_path)

        if success:
            CTkMessagebox(title='¡Exportación Exitosa!', message=msg, icon='check')
            try:
                if platform.system() == 'Windows':
                    os.startfile(file_path)
                elif platform.system() == 'Darwin':
                    subprocess.call(['open', file_path])
                else:
                    subprocess.call(['xdg-open', file_path])
            except Exception as e:
                logger.warning(f'No se pudo abrir el archivo automáticamente: {e}')
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
                text=os.path.basename(file_path), text_color=TEXT_PRIMARY
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
            icon='warning', option_1='Cancelar', option_2='Sí, Importar',
        )

        if confirm.get() == 'Sí, Importar':
            tenant_id = self.ctx.tenant_id
            user_id = self.ctx.user_id

            self.btn_import.configure(state='disabled', text='Procesando...')
            self.update()

            success, msg = self.controller.import_articles_from_excel(
                tenant_id, user_id, self.selected_file
            )

            if success:
                CTkMessagebox(title='¡Importación Finalizada!', message=msg, icon='check')
                self.lbl_file_path.configure(
                    text='Ningún archivo seleccionado', text_color=TEXT_MUTED
                )
                self.selected_file = None
                self.btn_import.configure(state='disabled', text='🚀  INICIAR IMPORTACIÓN')
            else:
                CTkMessagebox(title='Error', message=msg, icon='cancel')
                self.btn_import.configure(state='normal', text='🚀  INICIAR IMPORTACIÓN')
