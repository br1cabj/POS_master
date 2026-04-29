import logging

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.auth_controller import AuthController
from controllers.user_controller import UserController
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_HEADING,
	FONT_LOGO,
	FONT_SMALL,
	FONT_SMALL_BOLD,
	FONT_SUBHEADING,
	FONT_TITLE,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	RED_TEXT,
	SURFACE1,
	SURFACE2,
	SURFACE3,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	make_form_label,
)

logger = logging.getLogger(__name__)


class LoginView(ctk.CTkFrame):
	def __init__(self, master, db_engine, on_login_success):
		super().__init__(master, fg_color=SURFACE1)
		self.db_engine = db_engine
		self.on_login_success = on_login_success
		self.auth_ctrl = AuthController(db_engine)
		self.user_ctrl = UserController(db_engine)

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

		ctk.CTkLabel(
			self.login_frame,
			text='CloudPOS',
			font=FONT_LOGO,
			text_color=ACCENT_TEXT,
		).pack(pady=(24, 0))

		ctk.CTkLabel(
			self.login_frame,
			text='Sistema de Gestión',
			font=FONT_SUBHEADING,
			text_color=TEXT_MUTED,
		).pack(pady=(2, 28))

		self.entry_username = ctk.CTkEntry(
			self.login_frame,
			width=300,
			height=42,
			placeholder_text='Usuario',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
		)
		self.entry_username.pack(pady=(0, 10), padx=36)

		self.entry_password = ctk.CTkEntry(
			self.login_frame,
			width=300,
			height=42,
			placeholder_text='Contraseña',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
		)
		self.entry_password.pack(pady=(0, 6), padx=36)

		self.check_show_pass = ctk.CTkCheckBox(
			self.login_frame,
			text='Mostrar contraseña',
			font=FONT_BODY,
			text_color=TEXT_MUTED,
			command=self.toggle_password,
		)
		self.check_show_pass.pack(pady=(0, 18), padx=36, anchor='w')

		self.btn_login = ctk.CTkButton(
			self.login_frame,
			text='INICIAR SESIÓN',
			width=300,
			height=46,
			font=FONT_HEADING,
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			corner_radius=10,
			command=self.trigger_login,
		)
		self.btn_login.pack(pady=(0, 6), padx=36)

		self.btn_forgot = ctk.CTkButton(
			self.login_frame,
			text='Olvidé mi contraseña',
			width=300,
			height=28,
			font=FONT_SMALL,
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=TEXT_MUTED,
			corner_radius=6,
			command=self._open_recovery_dialog,
		)
		self.btn_forgot.pack(pady=(0, 4), padx=36)

		self.lbl_error = ctk.CTkLabel(
			self.login_frame,
			text='',
			text_color=RED_TEXT,
			font=FONT_BODY_BOLD,
		)
		self.lbl_error.pack(pady=(0, 18))

		self.entry_username.bind('<Return>', self._handle_username_return)
		self.entry_password.bind('<Return>', lambda e: self.trigger_login())
		self.entry_username.focus()

	# ── Login Normal ──────────────────────────────────────────────────────────
	def toggle_password(self):
		self.entry_password.configure(show='' if self.check_show_pass.get() else '*')

	def _handle_username_return(self, event):
		if not self.entry_password.get():
			self.entry_password.focus()
		else:
			self.trigger_login()

	def trigger_login(self):
		self.lbl_error.configure(text='')
		user = self.entry_username.get().strip()
		pwd = self.entry_password.get().strip()

		if not user or not pwd:
			self.show_error('Por favor, completa todos los campos.')
			return

		self.btn_login.configure(state='disabled', text='CONECTANDO...')
		tenant_id = self.auth_ctrl.get_first_tenant_id()
		self.after(50, lambda: self._execute_login(tenant_id, user, pwd))

	def _execute_login(self, tenant_id, username, pwd):
		try:
			user_dict = self.auth_ctrl.login(username, pwd, tenant_id=tenant_id)
			if user_dict:
				self.on_login_success(user_dict)
				return  # LoginView puede destruirse aquí — no tocar widgets
			if not self.winfo_exists():
				return
			self.show_error('Usuario o contraseña incorrectos.')
		except Exception as e:
			logger.error(f'Error inesperado durante el login: {e}', exc_info=True)
			if self.winfo_exists():
				self.show_error('Error de conexión a la base de datos.')

	def show_error(self, message):
		if not self.winfo_exists():
			return
		self.lbl_error.configure(text=message)
		self.btn_login.configure(state='normal', text='INICIAR SESIÓN')

	# ── Diálogo Recuperación de Contraseña ────────────────────────────────────
	def _open_recovery_dialog(self):
		dialog = ctk.CTkToplevel(self)
		dialog.title('Recuperar Contraseña')

		dialog.geometry('420x550')
		dialog.minsize(420, 480)
		dialog.grab_set()
		dialog.focus()

		container = ctk.CTkScrollableFrame(dialog, fg_color='transparent')
		container.pack(fill='both', expand=True, padx=0, pady=0)

		ctk.CTkLabel(
			container,
			text='Recuperar Contraseña',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
		).pack(pady=(28, 4))

		ctk.CTkLabel(
			container,
			text='Ingresá tu usuario y el PIN de recuperación\nque configuraste al crear tu cuenta.',
			font=FONT_BODY,
			text_color=TEXT_SECONDARY,
			justify='center',
		).pack(pady=(0, 16))

		make_form_label(container, 'NOMBRE DE USUARIO', required=True).pack(
			padx=32, anchor='w', pady=(0, 2)
		)
		entry_username = ctk.CTkEntry(
			container,
			placeholder_text='Tu nombre de usuario',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		entry_username.pack(padx=32, fill='x', pady=(0, 8))

		current_user = self.entry_username.get().strip()
		if current_user:
			entry_username.insert(0, current_user)
		entry_username.focus()

		make_form_label(container, 'PIN DE RECUPERACIÓN', required=True).pack(
			padx=32, anchor='w', pady=(0, 2)
		)
		entry_pin = ctk.CTkEntry(
			container,
			placeholder_text='Tu PIN secreto',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		entry_pin.pack(padx=32, fill='x', pady=(0, 8))

		make_form_label(container, 'NUEVA CONTRASEÑA', required=True).pack(
			padx=32, anchor='w', pady=(0, 2)
		)
		entry_new_pass = ctk.CTkEntry(
			container,
			placeholder_text='Mínimo 6 caracteres',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		entry_new_pass.pack(padx=32, fill='x', pady=(0, 8))

		make_form_label(container, 'CONFIRMAR NUEVA CONTRASEÑA', required=True).pack(
			padx=32, anchor='w', pady=(0, 2)
		)
		entry_confirm = ctk.CTkEntry(
			container,
			placeholder_text='Repetir contraseña',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		entry_confirm.pack(padx=32, fill='x', pady=(0, 16))

		lbl_err = ctk.CTkLabel(
			container, text='', font=FONT_SMALL_BOLD, text_color=RED_TEXT
		)
		lbl_err.pack(pady=(0, 4))

		def _do_recovery():
			username = entry_username.get().strip()
			pin = entry_pin.get().strip()
			new_pass = entry_new_pass.get().strip()
			confirmed = entry_confirm.get().strip()

			if not all([username, pin, new_pass, confirmed]):
				lbl_err.configure(text='Todos los campos son obligatorios.')
				return
			if new_pass != confirmed:
				lbl_err.configure(text='Las contraseñas no coinciden.')
				return

			btn_recover.configure(state='disabled', text='Verificando...')
			tenant_id = self.auth_ctrl.get_first_tenant_id()
			dialog.after(
				50, lambda: _execute_recovery(tenant_id, username, pin, new_pass)
			)

		def _execute_recovery(tenant_id, username, pin, new_pass):
			success, msg = self.user_ctrl.reset_password_with_pin(
				tenant_id, username, pin, new_pass
			)
			if success:
				dialog.destroy()
				CTkMessagebox(
					title='Contraseña restablecida',
					message=f'{msg}\n\nYa podés iniciar sesión.',
					icon='check',
				)
				self.entry_username.delete(0, 'end')
				self.entry_username.insert(0, username)
				self.entry_password.delete(0, 'end')
				self.entry_password.focus()
			else:
				lbl_err.configure(text=msg)
				btn_recover.configure(state='normal', text='Restablecer Contraseña')

		btn_recover = ctk.CTkButton(
			container,
			text='Restablecer Contraseña',
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			height=40,
			corner_radius=8,
			command=_do_recovery,
		)
		btn_recover.pack(padx=32, fill='x', pady=(0, 6))
