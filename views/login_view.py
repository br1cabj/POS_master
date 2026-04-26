import logging

import customtkinter as ctk

from controllers.auth_controller import AuthController
from utils.styles import (
    ACCENT, ACCENT_DIM, ACCENT_TEXT, BORDER, BORDER_ACTIVE,
    GREEN, GREEN_DIM, GREEN_TEXT, RED_TEXT,
    SURFACE1, SURFACE2, SURFACE3,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)

logger = logging.getLogger(__name__)


class LoginView(ctk.CTkFrame):
    def __init__(self, master, db_engine, on_login_success):
        super().__init__(master, fg_color=SURFACE1)
        self.db_engine = db_engine
        self.on_login_success = on_login_success
        self.auth_ctrl = AuthController(db_engine)

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(2, weight=1)

        # ── Tarjeta central ───────────────────────────────────────────────
        self.login_frame = ctk.CTkFrame(
            self,
            corner_radius=16,
            fg_color=SURFACE2,
            border_width=1,
            border_color=BORDER,
        )
        self.login_frame.grid(row=1, column=1, padx=20, pady=20, ipadx=24, ipady=24)

        # Logo y título
        ctk.CTkLabel(
            self.login_frame,
            text='☁ CloudPOS',
            font=('Arial', 38, 'bold'),
            text_color=ACCENT_TEXT,
        ).pack(pady=(24, 0))

        ctk.CTkLabel(
            self.login_frame,
            text='Sistema de Gestión',
            font=('Arial', 14),
            text_color=TEXT_MUTED,
        ).pack(pady=(2, 28))

        # Campos
        self.entry_tenant = ctk.CTkEntry(
            self.login_frame,
            width=300, height=42,
            placeholder_text='Código de Empresa  (Ej: 1)',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY,
        )
        self.entry_tenant.pack(pady=(0, 10), padx=36)
        self.entry_tenant.insert(0, '1')

        self.entry_username = ctk.CTkEntry(
            self.login_frame,
            width=300, height=42,
            placeholder_text='Usuario',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY,
        )
        self.entry_username.pack(pady=(0, 10), padx=36)

        self.entry_password = ctk.CTkEntry(
            self.login_frame,
            width=300, height=42,
            placeholder_text='Contraseña',
            show='*',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY,
        )
        self.entry_password.pack(pady=(0, 6), padx=36)

        self.check_show_pass = ctk.CTkCheckBox(
            self.login_frame,
            text='Mostrar contraseña',
            font=('Arial', 12),
            text_color=TEXT_MUTED,
            command=self.toggle_password,
        )
        self.check_show_pass.pack(pady=(0, 18), padx=36, anchor='w')

        self.btn_login = ctk.CTkButton(
            self.login_frame,
            text='INICIAR SESIÓN',
            width=300, height=46,
            font=('Arial', 14, 'bold'),
            fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=ACCENT_TEXT,
            border_width=1, border_color=ACCENT,
            corner_radius=10,
            command=self.trigger_login,
        )
        self.btn_login.pack(pady=(0, 8), padx=36)

        self.lbl_error = ctk.CTkLabel(
            self.login_frame,
            text='',
            text_color=RED_TEXT,
            font=('Arial', 12, 'bold'),
        )
        self.lbl_error.pack(pady=(0, 18))

        # ── Eventos de teclado ────────────────────────────────────────────
        self.entry_tenant.bind('<Return>', self.handle_tenant_return)
        self.entry_username.bind('<Return>', self.handle_username_return)
        self.entry_password.bind('<Return>', lambda e: self.trigger_login())

        self.entry_username.focus()

    def toggle_password(self):
        if self.check_show_pass.get():
            self.entry_password.configure(show='')
        else:
            self.entry_password.configure(show='*')

    def handle_tenant_return(self, event):
        if not self.entry_username.get():
            self.entry_username.focus()
        else:
            self.handle_username_return(event)

    def handle_username_return(self, event):
        if not self.entry_password.get():
            self.entry_password.focus()
        else:
            self.trigger_login()

    def trigger_login(self):
        self.lbl_error.configure(text='')

        tenant_val = self.entry_tenant.get().strip()
        user = self.entry_username.get().strip()
        pwd = self.entry_password.get().strip()

        if not tenant_val or not user or not pwd:
            self.show_error('Por favor, completá todos los campos.')
            return

        try:
            tenant_id = int(tenant_val)
        except ValueError:
            self.show_error('El código de empresa debe ser un número.')
            return

        self.btn_login.configure(state='disabled', text='CONECTANDO...')
        self.after(50, lambda: self._execute_login(tenant_id, user, pwd))

    def _execute_login(self, tenant_id: int, username: str, pwd: str):
        try:
            user_dict = self.auth_ctrl.login(username, pwd, tenant_id=tenant_id)
            if user_dict:
                self.on_login_success(user_dict)
            else:
                self.show_error('Usuario o contraseña incorrectos.')
        except Exception as e:
            logger.error(f'Error inesperado durante el login: {e}', exc_info=True)
            self.show_error('Error de conexión a la base de datos.')

    def show_error(self, message):
        self.lbl_error.configure(text=message)
        self.btn_login.configure(state='normal', text='INICIAR SESIÓN')
