from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.user_controller import UserController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	RED,
	RED_DIM,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	apply_treeview_style,
)


class UsersView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = UserController(ctx.db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		apply_treeview_style()

		# ── Panel izquierdo: Nuevo empleado ──────────────────────────────────
		self.left_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)

		ctk.CTkLabel(
			self.left_panel,
			text='🛠  Nuevo Empleado',
			font=('Arial', 17, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(22, 6))

		# Usuario
		ctk.CTkLabel(
			self.left_panel,
			text='NOMBRE DE USUARIO',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(8, 2))
		self.entry_user = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Nombre de usuario',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_user.pack(pady=(0, 4), padx=20, fill='x')

		# Contraseña
		ctk.CTkLabel(
			self.left_panel,
			text='CONTRASEÑA',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(4, 2))
		self.entry_pass = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Mínimo 6 caracteres',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		self.entry_pass.pack(pady=(0, 4), padx=20, fill='x')

		# PIN de recuperación
		pin_frame = ctk.CTkFrame(
			self.left_panel,
			fg_color=ORANGE_DIM,
			corner_radius=8,
			border_width=1,
			border_color=ORANGE,
		)
		pin_frame.pack(padx=20, fill='x', pady=(6, 10))

		ctk.CTkLabel(
			pin_frame,
			text='🔑  PIN DE RECUPERACIÓN  (opcional)',
			font=('Arial', 9, 'bold'),
			text_color=ORANGE_TEXT,
			anchor='w',
		).pack(padx=12, anchor='w', pady=(10, 2))

		self.entry_pin = ctk.CTkEntry(
			pin_frame,
			placeholder_text='Ej: 1234  (mín. 4 dígitos)',
			show='*',
			fg_color=SURFACE3,
			border_color=ORANGE,
			text_color=TEXT_PRIMARY,
			height=34,
		)
		self.entry_pin.pack(padx=12, fill='x', pady=(0, 4))

		ctk.CTkLabel(
			pin_frame,
			text='Si el empleado olvida su contraseña, usará este PIN para recuperarla.',
			font=('Arial', 9),
			text_color=ORANGE_TEXT,
			wraplength=230,
			justify='left',
		).pack(padx=12, anchor='w', pady=(0, 10))

		# Rol
		ctk.CTkLabel(
			self.left_panel,
			text='ROL DE ACCESO',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=20, anchor='w', pady=(4, 2))
		self.combo_role = ctk.CTkComboBox(
			self.left_panel,
			values=['cajero', 'admin'],
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			button_color=SURFACE3,
			button_hover_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			dropdown_text_color=TEXT_PRIMARY,
		)
		self.combo_role.pack(pady=(0, 16), padx=20, fill='x')

		self.btn_add = ctk.CTkButton(
			self.left_panel,
			text='➕  Crear Cuenta',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=40,
			corner_radius=8,
			command=self.add_user,
		)
		self.btn_add.pack(pady=(0, 20), padx=20, fill='x')

		# ── Panel derecho: Lista de usuarios ─────────────────────────────────
		self.right_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=16)

		hdr = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		hdr.pack(fill='x', padx=16, pady=(16, 4))
		ctk.CTkLabel(
			hdr,
			text='Directorio de Empleados',
			font=('Arial', 15, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		ctk.CTkLabel(
			self.right_panel,
			text='Seleccioná un empleado para gestionar su cuenta',
			font=('Arial', 10),
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=16, pady=(0, 6))

		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=14, pady=(0, 8))

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		columns = ('ID', 'Usuario', 'Rol', 'PIN')
		self.tree = ttk.Treeview(
			self.table_container,
			columns=columns,
			show='headings',
			height=14,
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		col_widths = {'ID': 50, 'Usuario': 200, 'Rol': 120, 'PIN': 100}
		for col in columns:
			self.tree.heading(col, text=col)
			self.tree.column(col, anchor='center', width=col_widths.get(col, 100))

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		# Botones de acción
		btns = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		btns.pack(fill='x', padx=14, pady=(0, 14))

		self.btn_reset_pass = ctk.CTkButton(
			btns,
			text='🔑  Restablecer Contraseña',
			fg_color=ORANGE_DIM,
			hover_color=ORANGE,
			text_color=ORANGE_TEXT,
			border_width=1,
			border_color=ORANGE,
			height=36,
			corner_radius=8,
			command=self._open_reset_popup,
		)
		self.btn_reset_pass.pack(side='left', expand=True, fill='x', padx=(0, 6))

		self.btn_update_pin = ctk.CTkButton(
			btns,
			text='🔐  Actualizar PIN',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=36,
			corner_radius=8,
			command=self._open_pin_popup,
		)
		self.btn_update_pin.pack(side='left', expand=True, fill='x', padx=(0, 6))

		self.btn_delete = ctk.CTkButton(
			btns,
			text='🗑  Eliminar',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
			height=36,
			corner_radius=8,
			command=self.delete_user,
		)
		self.btn_delete.pack(side='left', expand=True, fill='x')

		self.after(50, self.load_data)

	# =========================================================
	# DATOS
	# =========================================================
	def load_data(self):
		for item in self.tree.get_children():
			self.tree.delete(item)
		tenant_id = self.ctx.tenant_id
		users = self.controller.get_users(tenant_id)
		for u in users:
			role_display = '👑 Admin' if u.get('role') == 'admin' else '👤 Cajero'
			pin_display = '✅ Configurado' if u.get('has_recovery_pin') else '⚠ Sin PIN'
			self.tree.insert(
				'',
				'end',
				values=(u.get('id'), u.get('username'), role_display, pin_display),
			)

	# =========================================================
	# CREAR USUARIO
	# =========================================================
	def add_user(self):
		username = self.entry_user.get().strip()
		password = self.entry_pass.get().strip()
		role = self.combo_role.get()
		pin = self.entry_pin.get().strip() or None

		if not username or not password:
			CTkMessagebox(
				title='Error',
				message='Usuario y contraseña son obligatorios.',
				icon='warning',
			)
			return

		tenant_id = self.ctx.tenant_id
		success, msg = self.controller.add_user(
			tenant_id, username, password, role, recovery_pin=pin
		)

		if success:
			if pin:
				CTkMessagebox(
					title='Empleado creado',
					message=f'✅ {msg}\n\nPIN de recuperación guardado correctamente.\nAsegurate de que el empleado lo recuerde.',
					icon='check',
				)
			else:
				CTkMessagebox(title='Éxito', message=msg, icon='check')
			self.entry_user.delete(0, 'end')
			self.entry_pass.delete(0, 'end')
			self.entry_pin.delete(0, 'end')
			self.load_data()
		else:
			CTkMessagebox(title='Error', message=msg, icon='cancel')

	# =========================================================
	# POPUP: RESTABLECER CONTRASEÑA (admin → usuario)
	# =========================================================
	def _open_reset_popup(self):
		selected = self.tree.selection()
		if not selected:
			CTkMessagebox(
				title='Atención',
				message='Seleccioná un empleado de la tabla primero.',
				icon='info',
			)
			return

		values = self.tree.item(selected[0], 'values')
		target_id = values[0]
		target_name = values[1]

		popup = ctk.CTkToplevel(self)
		popup.title('Restablecer Contraseña')
		popup.geometry('380x320')
		popup.resizable(False, False)
		popup.grab_set()
		popup.focus()

		ctk.CTkLabel(
			popup,
			text='🔑  Restablecer Contraseña',
			font=('Arial', 16, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(24, 4))

		ctk.CTkLabel(
			popup,
			text=f'Empleado:  {target_name}',
			font=('Arial', 12),
			text_color=ORANGE_TEXT,
		).pack(pady=(0, 16))

		ctk.CTkLabel(
			popup,
			text='NUEVA CONTRASEÑA',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=28, anchor='w', pady=(0, 2))
		entry_new = ctk.CTkEntry(
			popup,
			placeholder_text='Mínimo 6 caracteres',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		entry_new.pack(padx=28, fill='x', pady=(0, 8))
		entry_new.focus()

		ctk.CTkLabel(
			popup,
			text='CONFIRMAR CONTRASEÑA',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=28, anchor='w', pady=(0, 2))
		entry_confirm = ctk.CTkEntry(
			popup,
			placeholder_text='Repetir contraseña',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		entry_confirm.pack(padx=28, fill='x', pady=(0, 12))

		lbl_err = ctk.CTkLabel(
			popup,
			text='',
			font=('Arial', 11),
			text_color=RED_TEXT,
		)
		lbl_err.pack()

		def _do_reset():
			new_pass = entry_new.get().strip()
			confirmed = entry_confirm.get().strip()
			if not new_pass:
				lbl_err.configure(text='Ingresá la nueva contraseña.')
				return
			if new_pass != confirmed:
				lbl_err.configure(text='Las contraseñas no coinciden.')
				return
			success, msg = self.controller.reset_password_by_admin(
				self.ctx.tenant_id, target_id, new_pass
			)
			if success:
				popup.destroy()
				CTkMessagebox(title='Listo', message=f'✅ {msg}', icon='check')
				self.load_data()
			else:
				lbl_err.configure(text=msg)

		ctk.CTkButton(
			popup,
			text='Restablecer Contraseña',
			fg_color=ORANGE,
			hover_color='#b45309',
			text_color='white',
			height=38,
			corner_radius=8,
			command=_do_reset,
		).pack(padx=28, fill='x', pady=(4, 0))

		entry_confirm.bind('<Return>', lambda e: _do_reset())

	# =========================================================
	# POPUP: ACTUALIZAR PIN
	# =========================================================
	def _open_pin_popup(self):
		selected = self.tree.selection()
		if not selected:
			CTkMessagebox(
				title='Atención',
				message='Seleccioná un empleado de la tabla primero.',
				icon='info',
			)
			return

		values = self.tree.item(selected[0], 'values')
		target_id = values[0]
		target_name = values[1]

		popup = ctk.CTkToplevel(self)
		popup.title('Actualizar PIN de Recuperación')
		popup.geometry('380x280')
		popup.resizable(False, False)
		popup.grab_set()
		popup.focus()

		ctk.CTkLabel(
			popup,
			text='🔐  Actualizar PIN de Recuperación',
			font=('Arial', 15, 'bold'),
			text_color=TEXT_PRIMARY,
		).pack(pady=(24, 4))

		ctk.CTkLabel(
			popup,
			text=f'Empleado:  {target_name}',
			font=('Arial', 12),
			text_color=ACCENT_TEXT,
		).pack(pady=(0, 16))

		ctk.CTkLabel(
			popup,
			text='NUEVO PIN  (mínimo 4 dígitos)',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=28, anchor='w', pady=(0, 2))
		entry_pin = ctk.CTkEntry(
			popup,
			placeholder_text='Ej: 1234',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		entry_pin.pack(padx=28, fill='x', pady=(0, 8))
		entry_pin.focus()

		ctk.CTkLabel(
			popup,
			text='CONFIRMAR PIN',
			font=('Arial', 9, 'bold'),
			text_color=TEXT_MUTED,
			anchor='w',
		).pack(padx=28, anchor='w', pady=(0, 2))
		entry_confirm = ctk.CTkEntry(
			popup,
			placeholder_text='Repetir PIN',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
		)
		entry_confirm.pack(padx=28, fill='x', pady=(0, 12))

		lbl_err = ctk.CTkLabel(
			popup,
			text='',
			font=('Arial', 11),
			text_color=RED_TEXT,
		)
		lbl_err.pack()

		def _do_update():
			pin = entry_pin.get().strip()
			confirmed = entry_confirm.get().strip()
			if not pin:
				lbl_err.configure(text='Ingresá el nuevo PIN.')
				return
			if pin != confirmed:
				lbl_err.configure(text='Los PINs no coinciden.')
				return
			success, msg = self.controller.set_recovery_pin(
				self.ctx.tenant_id, target_id, pin
			)
			if success:
				popup.destroy()
				CTkMessagebox(title='Listo', message=f'✅ {msg}', icon='check')
				self.load_data()
			else:
				lbl_err.configure(text=msg)

		ctk.CTkButton(
			popup,
			text='Guardar PIN',
			fg_color=ACCENT,
			hover_color='#1d4ed8',
			text_color='white',
			height=38,
			corner_radius=8,
			command=_do_update,
		).pack(padx=28, fill='x', pady=(4, 0))

		entry_confirm.bind('<Return>', lambda e: _do_update())

	# =========================================================
	# ELIMINAR
	# =========================================================
	def delete_user(self):
		selected = self.tree.selection()
		if not selected:
			CTkMessagebox(
				title='Atención',
				message='Seleccioná un usuario de la tabla.',
				icon='info',
			)
			return

		values = self.tree.item(selected[0], 'values')
		user_id = values[0]
		selected_username = values[1]
		current_username = self.ctx.username

		if selected_username == current_username:
			CTkMessagebox(
				title='Acción Denegada',
				message='No podés borrar tu propia cuenta mientras estás en sesión.',
				icon='cancel',
			)
			return

		msg_box = CTkMessagebox(
			title='Confirmar',
			message=f'¿Seguro que deseás eliminar al empleado {selected_username}?',
			icon='question',
			option_1='No',
			option_2='Sí',
		)

		if msg_box.get() == 'Sí':
			tenant_id = self.ctx.tenant_id
			current_id = self.ctx.user_id
			success, msg = self.controller.delete_user(
				tenant_id, user_id, current_user_id=current_id
			)
			if success:
				self.load_data()
				CTkMessagebox(title='Eliminado', message=msg, icon='check')
			else:
				CTkMessagebox(title='Error', message=msg, icon='cancel')
