from tkinter import ttk

import customtkinter as ctk

from controllers.user_controller import UserController
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
	ORANGE,
	ORANGE_DIM,
	ORANGE_TEXT,
	PAD_LG,
	PAD_MD,
	PAD_SM,
	PAD_XS,
	RED,
	RED_DIM,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	make_form_label,
)


class UsersView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = UserController(ctx.db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		# ── Panel izquierdo: Nuevo empleado ──────────────────────────────────
		self.left_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.left_panel.grid(
			row=0, column=0, sticky='nsew', padx=(PAD_LG, PAD_SM), pady=PAD_LG
		)

		ctk.CTkLabel(
			self.left_panel,
			text='🛠  Nuevo Empleado',
			font=FONT_TITLE,
			text_color=TEXT_PRIMARY,
		).pack(pady=(PAD_LG, PAD_SM))

		# Usuario
		make_form_label(self.left_panel, 'NOMBRE DE USUARIO', required=True).pack(
			padx=PAD_LG, anchor='w', pady=(PAD_SM, PAD_XS)
		)
		self.entry_user = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Nombre de usuario',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		self.entry_user.pack(pady=(0, PAD_SM), padx=PAD_LG, fill='x')

		# Contraseña
		make_form_label(self.left_panel, 'CONTRASEÑA', required=True).pack(
			padx=PAD_LG, anchor='w', pady=(PAD_XS, PAD_XS)
		)
		self.entry_pass = ctk.CTkEntry(
			self.left_panel,
			placeholder_text='Mínimo 6 caracteres',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		self.entry_pass.pack(pady=(0, PAD_SM), padx=PAD_LG, fill='x')

		# PIN de recuperación
		pin_frame = ctk.CTkFrame(
			self.left_panel,
			fg_color=ORANGE_DIM,
			corner_radius=8,
			border_width=1,
			border_color=ORANGE,
		)
		pin_frame.pack(padx=PAD_LG, fill='x', pady=(PAD_SM, PAD_MD))

		ctk.CTkLabel(
			pin_frame,
			text='🔑  PIN DE RECUPERACIÓN  (opcional)',
			font=FONT_LABEL_BOLD,
			text_color=ORANGE_TEXT,
			anchor='w',
		).pack(padx=PAD_MD, anchor='w', pady=(PAD_SM, PAD_XS))

		self.entry_pin = ctk.CTkEntry(
			pin_frame,
			placeholder_text='Ej: 1234  (mín. 4 dígitos)',
			show='*',
			fg_color=SURFACE3,
			border_color=ORANGE,
			text_color=TEXT_PRIMARY,
			height=34,
			font=FONT_BODY,
		)
		self.entry_pin.pack(padx=PAD_MD, fill='x', pady=(0, PAD_XS))

		ctk.CTkLabel(
			pin_frame,
			text='Si el empleado olvida su contraseña, usará este PIN para recuperarla.',
			font=FONT_LABEL,
			text_color=ORANGE_TEXT,
			wraplength=230,
			justify='left',
		).pack(padx=PAD_MD, anchor='w', pady=(0, PAD_SM))

		# Rol
		make_form_label(self.left_panel, 'ROL DE ACCESO', required=True).pack(
			padx=PAD_LG, anchor='w', pady=(PAD_XS, PAD_XS)
		)
		self.combo_role = ctk.CTkComboBox(
			self.left_panel,
			values=['Cajero', 'Administrador'],
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			button_color=SURFACE3,
			button_hover_color=SURFACE4,
			dropdown_fg_color=SURFACE2,
			dropdown_text_color=TEXT_PRIMARY,
			font=FONT_BODY,
		)
		self.combo_role.pack(pady=(0, PAD_LG), padx=PAD_LG, fill='x')

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
			font=FONT_BODY_BOLD,
			command=self.add_user,
		)
		self.btn_add.pack(pady=(0, PAD_LG), padx=PAD_LG, fill='x')

		# ── Panel derecho: Lista de usuarios ─────────────────────────────────
		self.right_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.right_panel.grid(
			row=0, column=1, sticky='nsew', padx=(PAD_SM, PAD_LG), pady=PAD_LG
		)

		hdr = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		hdr.pack(fill='x', padx=PAD_MD, pady=(PAD_MD, PAD_XS))

		ctk.CTkLabel(
			hdr,
			text='Directorio de Empleados',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		ctk.CTkLabel(
			self.right_panel,
			text='Seleccioná un empleado para gestionar su cuenta',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=PAD_MD, pady=(0, PAD_SM))

		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(
			fill='both', expand=True, padx=PAD_SM, pady=(0, PAD_SM)
		)

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

		# CORRECCIÓN: Inicialización con el Design System
		self.init_treeview(self.tree)

		col_widths = {'ID': 50, 'Usuario': 200, 'Rol': 120, 'PIN': 100}
		for col in columns:
			self.tree.heading(col, text=col)
			self.tree.column(col, anchor='center', width=col_widths.get(col, 100))

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		# Botones de acción
		btns = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		btns.pack(fill='x', padx=PAD_SM, pady=(0, PAD_MD))

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
			font=FONT_BODY_BOLD,
			command=self._open_reset_popup,
		)
		self.btn_reset_pass.pack(side='left', expand=True, fill='x', padx=(0, PAD_SM))

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
			font=FONT_BODY_BOLD,
			command=self._open_pin_popup,
		)
		self.btn_update_pin.pack(side='left', expand=True, fill='x', padx=(0, PAD_SM))

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
			font=FONT_BODY_BOLD,
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

		for idx, u in enumerate(users):
			role_display = '👑 Admin' if u.get('role') == 'admin' else '👤 Cajero'
			pin_display = '✅ Configurado' if u.get('has_recovery_pin') else '⚠ Sin PIN'

			# CORRECCIÓN: Usando la base_view para zebra striping
			self.insert_tree_row(
				tree=self.tree,
				index=idx,
				values=(u.get('id'), u.get('username'), role_display, pin_display),
			)

	# =========================================================
	# CREAR USUARIO
	# =========================================================
	def add_user(self):
		username = self.entry_user.get().strip()
		password = self.entry_pass.get().strip()

		# Mapeo de UI a valores internos de base de datos
		role_ui = self.combo_role.get()
		role = 'admin' if role_ui == 'Administrador' else 'cajero'

		pin = self.entry_pin.get().strip() or None

		if not username or not password:
			self.show_warning('Usuario y contraseña son obligatorios.')
			return

		if len(password) < 6:
			self.show_warning('La contraseña debe tener al menos 6 caracteres.')
			return

		# CORRECCIÓN: Validación firme de longitud y formato de PIN
		if pin and (not pin.isdigit() or len(pin) < 4):
			self.show_warning('El PIN debe tener al menos 4 dígitos numéricos.')
			return

		tenant_id = self.ctx.tenant_id
		success, msg = self.controller.add_user(
			tenant_id, username, password, role, recovery_pin=pin
		)

		if success:
			if pin:
				self.show_success(
					f'{msg}\n\nPIN de recuperación guardado correctamente.\nAsegurate de que el empleado lo recuerde.',
					'Empleado creado',
				)
			else:
				self.show_success(msg)

			self.entry_user.delete(0, 'end')
			self.entry_pass.delete(0, 'end')
			self.entry_pin.delete(0, 'end')
			self.load_data()
		else:
			self.show_error(msg)

	# =========================================================
	# POPUP: RESTABLECER CONTRASEÑA (admin → usuario)
	# =========================================================
	def _open_reset_popup(self):
		selected = self.tree.selection()
		if not selected:
			self.show_warning('Seleccioná un empleado de la tabla primero.')
			return

		values = self.tree.item(selected[0], 'values')
		target_id = values[0]
		target_name = values[1]

		popup = ctk.CTkToplevel(self)
		popup.title('Restablecer Contraseña')
		popup.minsize(380, 360)
		popup.resizable(False, False)
		popup.grab_set()
		popup.focus()

		ctk.CTkLabel(
			popup,
			text='🔑  Restablecer Contraseña',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
		).pack(pady=(PAD_LG, PAD_XS))

		ctk.CTkLabel(
			popup,
			text=f'Empleado:  {target_name}',
			font=FONT_BODY,
			text_color=ORANGE_TEXT,
		).pack(pady=(0, PAD_MD))

		make_form_label(popup, 'NUEVA CONTRASEÑA', required=True).pack(
			padx=PAD_LG, anchor='w', pady=(0, PAD_XS)
		)
		entry_new = ctk.CTkEntry(
			popup,
			placeholder_text='Mínimo 6 caracteres',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		entry_new.pack(padx=PAD_LG, fill='x', pady=(0, PAD_SM))
		entry_new.focus()

		make_form_label(popup, 'CONFIRMAR CONTRASEÑA', required=True).pack(
			padx=PAD_LG, anchor='w', pady=(0, PAD_XS)
		)
		entry_confirm = ctk.CTkEntry(
			popup,
			placeholder_text='Repetir contraseña',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		entry_confirm.pack(padx=PAD_LG, fill='x', pady=(0, PAD_SM))

		lbl_err = ctk.CTkLabel(
			popup, text='', font=FONT_LABEL_BOLD, text_color=RED_TEXT
		)
		lbl_err.pack()

		def _do_reset():
			new_pass = entry_new.get().strip()
			confirmed = entry_confirm.get().strip()

			if not new_pass:
				lbl_err.configure(text='Ingresá la nueva contraseña.')
				return
			if len(new_pass) < 6:
				lbl_err.configure(
					text='La contraseña debe tener al menos 6 caracteres.'
				)
				return
			if new_pass != confirmed:
				lbl_err.configure(text='Las contraseñas no coinciden.')
				return

			success, msg = self.controller.reset_password_by_admin(
				self.ctx.tenant_id, target_id, new_pass
			)
			if success:
				popup.destroy()
				self.show_success(msg, 'Listo')
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
			font=FONT_BODY_BOLD,
			command=_do_reset,
		).pack(padx=PAD_LG, fill='x', pady=(PAD_XS, PAD_MD))

		entry_confirm.bind('<Return>', lambda e: _do_reset())

	# =========================================================
	# POPUP: ACTUALIZAR PIN
	# =========================================================
	def _open_pin_popup(self):
		selected = self.tree.selection()
		if not selected:
			self.show_warning('Seleccioná un empleado de la tabla primero.')
			return

		values = self.tree.item(selected[0], 'values')
		target_id = values[0]
		target_name = values[1]

		popup = ctk.CTkToplevel(self)
		popup.title('Actualizar PIN de Recuperación')
		popup.minsize(380, 320)
		popup.resizable(False, False)
		popup.grab_set()
		popup.focus()

		ctk.CTkLabel(
			popup,
			text='🔐  Actualizar PIN de Recuperación',
			font=FONT_HEADING,
			text_color=TEXT_PRIMARY,
		).pack(pady=(PAD_LG, PAD_XS))

		ctk.CTkLabel(
			popup,
			text=f'Empleado:  {target_name}',
			font=FONT_BODY,
			text_color=ACCENT_TEXT,
		).pack(pady=(0, PAD_MD))

		make_form_label(popup, 'NUEVO PIN  (mínimo 4 dígitos)', required=True).pack(
			padx=PAD_LG, anchor='w', pady=(0, PAD_XS)
		)
		entry_pin = ctk.CTkEntry(
			popup,
			placeholder_text='Ej: 1234',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		entry_pin.pack(padx=PAD_LG, fill='x', pady=(0, PAD_SM))
		entry_pin.focus()

		make_form_label(popup, 'CONFIRMAR PIN', required=True).pack(
			padx=PAD_LG, anchor='w', pady=(0, PAD_XS)
		)
		entry_confirm = ctk.CTkEntry(
			popup,
			placeholder_text='Repetir PIN',
			show='*',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=36,
			font=FONT_BODY,
		)
		entry_confirm.pack(padx=PAD_LG, fill='x', pady=(0, PAD_SM))

		lbl_err = ctk.CTkLabel(
			popup, text='', font=FONT_LABEL_BOLD, text_color=RED_TEXT
		)
		lbl_err.pack()

		def _do_update():
			pin = entry_pin.get().strip()
			confirmed = entry_confirm.get().strip()

			if not pin:
				lbl_err.configure(text='Ingresá el nuevo PIN.')
				return
			if not pin.isdigit() or len(pin) < 4:
				lbl_err.configure(text='El PIN debe tener al menos 4 números.')
				return
			if pin != confirmed:
				lbl_err.configure(text='Los PINs no coinciden.')
				return

			success, msg = self.controller.set_recovery_pin(
				self.ctx.tenant_id, target_id, pin
			)
			if success:
				popup.destroy()
				self.show_success(msg, 'Listo')
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
			font=FONT_BODY_BOLD,
			command=_do_update,
		).pack(padx=PAD_LG, fill='x', pady=(PAD_XS, PAD_MD))

		entry_confirm.bind('<Return>', lambda e: _do_update())

	# =========================================================
	# ELIMINAR
	# =========================================================
	def delete_user(self):
		selected = self.tree.selection()
		if not selected:
			self.show_warning('Seleccioná un usuario de la tabla.', 'Atención')
			return

		values = self.tree.item(selected[0], 'values')
		user_id = values[0]
		selected_username = values[1]
		current_username = self.ctx.username

		if selected_username == current_username:
			self.show_error(
				'No podés borrar tu propia cuenta mientras estás en sesión.',
				'Acción Denegada',
			)
			return

		if self.confirm(
			f'¿Seguro que deseás eliminar al empleado {selected_username}?', 'Confirmar'
		):
			tenant_id = self.ctx.tenant_id
			current_id = self.ctx.user_id
			success, msg = self.controller.delete_user(
				tenant_id, user_id, current_user_id=current_id
			)
			if success:
				self.load_data()
				self.show_success(msg, 'Eliminado')
			else:
				self.show_error(msg)
