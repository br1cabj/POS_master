from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from core.base_view import BaseView
from core.context import AppContext
from controllers.user_controller import UserController
from utils.styles import (
    ACCENT, ACCENT_DIM, ACCENT_TEXT, BORDER, BORDER_ACTIVE,
    RED, RED_DIM, RED_TEXT, SURFACE1, SURFACE2, SURFACE3, SURFACE4,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
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

        # ── Panel izquierdo: Nuevo empleado ──────────────────────────────
        self.left_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)

        ctk.CTkLabel(
            self.left_panel, text='Nuevo Empleado',
            font=('Arial', 17, 'bold'), text_color=TEXT_PRIMARY,
        ).pack(pady=(22, 16))

        self.entry_user = ctk.CTkEntry(
            self.left_panel, placeholder_text='Nombre de usuario',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
        )
        self.entry_user.pack(pady=(0, 8), padx=20, fill='x')

        self.entry_pass = ctk.CTkEntry(
            self.left_panel, placeholder_text='Contraseña', show='*',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
        )
        self.entry_pass.pack(pady=(0, 12), padx=20, fill='x')

        ctk.CTkLabel(
            self.left_panel, text='ROL DE ACCESO',
            font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
        ).pack(padx=20, anchor='w')
        self.combo_role = ctk.CTkComboBox(
            self.left_panel, values=['cajero', 'admin'],
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
            button_color=SURFACE3, button_hover_color=SURFACE4,
            dropdown_fg_color=SURFACE2, dropdown_text_color=TEXT_PRIMARY,
        )
        self.combo_role.pack(pady=(2, 16), padx=20, fill='x')

        self.btn_add = ctk.CTkButton(
            self.left_panel, text='➕  Crear Cuenta',
            fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=ACCENT_TEXT,
            border_width=1, border_color=ACCENT, height=40, corner_radius=8,
            command=self.add_user,
        )
        self.btn_add.pack(pady=(0, 20), padx=20, fill='x')

        # ── Panel derecho: Lista de usuarios ─────────────────────────────
        self.right_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.right_panel.grid(row=0, column=1, sticky='nsew', padx=(8, 16), pady=16)

        hdr = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        hdr.pack(fill='x', padx=16, pady=(16, 10))
        ctk.CTkLabel(
            hdr, text='Directorio de Empleados',
            font=('Arial', 15, 'bold'), text_color=TEXT_PRIMARY, anchor='w',
        ).pack(side='left')

        self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        self.table_container.pack(fill='both', expand=True, padx=14, pady=(0, 8))

        self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

        columns = ('ID', 'Usuario', 'Rol')
        self.tree = ttk.Treeview(
            self.table_container,
            columns=columns, show='headings', height=15,
            yscrollcommand=self.tree_scroll.set,
        )
        self.tree_scroll.configure(command=self.tree.yview)

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, anchor='center')

        self.tree_scroll.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)

        self.btn_delete = ctk.CTkButton(
            self.right_panel, text='🗑  Eliminar Seleccionado',
            fg_color=RED_DIM, hover_color=RED, text_color=RED_TEXT,
            border_width=1, border_color=RED, height=36, corner_radius=8,
            command=self.delete_user,
        )
        self.btn_delete.pack(pady=(4, 14), padx=14, fill='x')

        self.after(50, self.load_data)

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        tenant_id = self.ctx.tenant_id
        users = self.controller.get_users(tenant_id)
        for u in users:
            role_display = '👑 Admin' if u.get('role') == 'admin' else '👤 Cajero'
            self.tree.insert('', 'end', values=(u.get('id'), u.get('username'), role_display))

    def add_user(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get().strip()
        role = self.combo_role.get()

        if not username or not password:
            CTkMessagebox(
                title='Error', message='Usuario y contraseña son obligatorios.', icon='warning'
            )
            return

        tenant_id = self.ctx.tenant_id
        success, msg = self.controller.add_user(tenant_id, username, password, role)

        if success:
            CTkMessagebox(title='Éxito', message=msg, icon='check')
            self.entry_user.delete(0, 'end')
            self.entry_pass.delete(0, 'end')
            self.load_data()
        else:
            CTkMessagebox(title='Error', message=msg, icon='cancel')

    def delete_user(self):
        selected = self.tree.selection()
        if not selected:
            CTkMessagebox(title='Atención', message='Seleccioná un usuario de la tabla.', icon='info')
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
            icon='question', option_1='No', option_2='Sí',
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
