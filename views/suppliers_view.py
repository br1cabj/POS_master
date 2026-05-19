from tkinter import ttk

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from controllers.supplier_controller import SupplierController
from core.base_view import BaseView
from core.context import AppContext
from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_LABEL,
	RED,
	RED_DIM,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
	apply_treeview_style,
)


class SuppliersView(BaseView):
	def __init__(self, master, ctx: AppContext):
		super().__init__(master, ctx)
		self.controller = SupplierController(ctx.db_engine)

		self.editing_id = None
		self.suppliers_list = []
		self._search_timer = None

		self.grid_columnconfigure(0, weight=1)
		self.grid_columnconfigure(1, weight=2)
		self.grid_rowconfigure(0, weight=1)

		apply_treeview_style()

		# ── Panel izquierdo: Formulario ──────────────────────────────────
		self.left_panel = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=12,
			border_width=1,
			border_color=BORDER,
		)
		self.left_panel.grid(row=0, column=0, sticky='nsew', padx=(16, 8), pady=16)

		self.lbl_form_title = ctk.CTkLabel(
			self.left_panel,
			text='🚚  Nuevo Proveedor',
			font=('Arial', 17, 'bold'),
			text_color=TEXT_PRIMARY,
		)
		self.lbl_form_title.pack(pady=(22, 16))

		for placeholder in [
			('Razón Social / Nombre', 'entry_name'),
			('Teléfono o WhatsApp', 'entry_phone'),
			('Correo Electrónico', 'entry_email'),
			('Dirección del depósito', 'entry_address'),
		]:
			entry = ctk.CTkEntry(
				self.left_panel,
				placeholder_text=placeholder[0],
				fg_color=SURFACE3,
				border_color=BORDER_ACTIVE,
				text_color=TEXT_PRIMARY,
				height=36,
			)
			entry.pack(pady=(0, 8), padx=20, fill='x')
			setattr(self, placeholder[1], entry)

		self.btn_save = ctk.CTkButton(
			self.left_panel,
			text='💾  Guardar Proveedor',
			fg_color=ACCENT_DIM,
			hover_color=ACCENT,
			text_color=ACCENT_TEXT,
			border_width=1,
			border_color=ACCENT,
			height=38,
			corner_radius=8,
			command=self.save_supplier,
		)
		self.btn_save.pack(pady=(8, 6), padx=20, fill='x')

		self.btn_cancel = ctk.CTkButton(
			self.left_panel,
			text='↺  Limpiar / Cancelar',
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER,
			height=36,
			corner_radius=8,
			command=self.reset_form,
		)
		self.btn_cancel.pack(pady=(0, 20), padx=20, fill='x')

		# ── Panel derecho: Directorio ────────────────────────────────────
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
			text='Directorio de Proveedores',
			font=('Arial', 15, 'bold'),
			text_color=TEXT_PRIMARY,
			anchor='w',
		).pack(side='left')

		ctk.CTkLabel(
			self.right_panel,
			text='Doble clic para editar',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
		).pack(anchor='w', padx=16, pady=(0, 6))

		# ── Buscador ──
		search_row = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		search_row.pack(fill='x', padx=14, pady=(0, 6))

		self._search_var = ctk.StringVar()
		self._search_var.trace_add('write', self._on_search_change)

		ctk.CTkEntry(
			search_row,
			textvariable=self._search_var,
			placeholder_text='🔍 Buscar por nombre, teléfono o email...',
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			height=34,
		).pack(side='left', fill='x', expand=True)

		self.lbl_count = ctk.CTkLabel(
			search_row,
			text='',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			width=100,
			anchor='e',
		)
		self.lbl_count.pack(side='right', padx=(8, 0))

		# ── Tabla ──
		self.table_container = ctk.CTkFrame(self.right_panel, fg_color='transparent')
		self.table_container.pack(fill='both', expand=True, padx=14, pady=(0, 8))

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		columns = ('ID', 'Nombre', 'Teléfono', 'Email', 'Dirección')
		self.tree = ttk.Treeview(
			self.table_container,
			columns=columns,
			show='headings',
			height=15,
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		for col in columns:
			self.tree.heading(col, text=col)
			width = 150 if col in ['Nombre', 'Email'] else 100
			self.tree.column(col, anchor='w' if col != 'ID' else 'center', width=width)

		self.tree.bind('<Double-1>', self.on_tree_double_click)
		self.tree.bind('<<TreeviewSelect>>', self._on_tree_select)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self._lbl_empty_suppliers = ctk.CTkLabel(
			self.table_container,
			text='No hay proveedores registrados.\nUsá el formulario para agregar uno.',
			font=FONT_LABEL,
			text_color=TEXT_MUTED,
			justify='center',
		)

		self.btn_delete = ctk.CTkButton(
			self.right_panel,
			text='🗑  Eliminar Seleccionado',
			fg_color=RED_DIM,
			hover_color=RED,
			text_color=RED_TEXT,
			border_width=1,
			border_color=RED,
			height=36,
			corner_radius=8,
			state='disabled',
			command=self.delete_supplier,
		)
		self.btn_delete.pack(pady=(4, 14), padx=14, fill='x')

		self.after(100, self.load_data)

	# =========================================================
	# LÓGICA Y EVENTOS
	# =========================================================
	def _on_search_change(self, *args):
		if self._search_timer:
			self.after_cancel(self._search_timer)
		self._search_timer = self.after(300, self._filter_tree)

	def _filter_tree(self, *args):
		q = self._search_var.get().lower().strip()
		matches = [
			s
			for s in self.suppliers_list
			if q in (s.get('name') or '').lower()
			or q in (s.get('phone') or '').lower()
			or q in (s.get('email') or '').lower()
		]

		for item in self.tree.get_children():
			self.tree.delete(item)

		for s in matches:
			self.tree.insert(
				'',
				'end',
				values=(s['id'], s['name'], s['phone'], s['email'], s['address']),
			)

		total = len(self.suppliers_list)
		shown = len(matches)
		if hasattr(self, 'lbl_count'):
			self.lbl_count.configure(
				text=f'{shown} de {total}' if q else f'{total} prov.'
			)

		if hasattr(self, '_lbl_empty_suppliers'):
			if not matches:
				self._lbl_empty_suppliers.place(relx=0.5, rely=0.5, anchor='center')
			else:
				self._lbl_empty_suppliers.place_forget()

		self._on_tree_select()

	def _on_tree_select(self, event=None):
		if self.tree.selection():
			self.btn_delete.configure(state='normal')
		else:
			self.btn_delete.configure(state='disabled')

	def load_data(self):
		tenant_id = self.ctx.tenant_id
		self.suppliers_list = self.controller.get_all_suppliers(tenant_id)
		self._filter_tree()

	def on_tree_double_click(self, event):
		selected = self.tree.selection()
		if not selected:
			return
		sup_id = self.tree.item(selected[0], 'values')[0]
		found = next(
			(s for s in self.suppliers_list if str(s['id']) == str(sup_id)), None
		)
		if found:
			self.reset_form()
			self.editing_id = found['id']
			self.entry_name.insert(0, found['name'])
			self.entry_phone.insert(0, found['phone'])
			self.entry_email.insert(0, found['email'])
			self.entry_address.insert(0, found['address'])
			self.lbl_form_title.configure(
				text='✏️  Editando Proveedor', text_color=ACCENT_TEXT
			)
			self.btn_save.configure(text='💾  Actualizar Datos')

	def reset_form(self):
		self.editing_id = None
		self.entry_name.delete(0, 'end')
		self.entry_phone.delete(0, 'end')
		self.entry_email.delete(0, 'end')
		self.entry_address.delete(0, 'end')
		self.lbl_form_title.configure(
			text='🚚  Nuevo Proveedor', text_color=TEXT_PRIMARY
		)
		self.btn_save.configure(text='💾  Guardar Proveedor')
		self.entry_name.focus()

	def save_supplier(self):
		self.clear_field_errors(self.entry_name)

		name = self.entry_name.get().strip()
		phone = self.entry_phone.get().strip()
		email = self.entry_email.get().strip()
		address = self.entry_address.get().strip()

		if not name:
			self.mark_field_error(self.entry_name)
			return

		tenant_id = self.ctx.tenant_id

		original = self.btn_save.cget('text')
		self.set_loading(self.btn_save, True)
		self.update_idletasks()
		try:
			success, msg = self.controller.save_supplier(
				tenant_id, self.editing_id, name, phone, email, address
			)
		finally:
			self.set_loading(self.btn_save, False, original)

		if success:
			self.show_success(msg)
			self.reset_form()
			self.load_data()
		else:
			self.show_error(msg)

	def delete_supplier(self):
		selected = self.tree.selection()
		if not selected:
			return

		msg = CTkMessagebox(
			title='Confirmar',
			message='¿Seguro que deseás eliminar a este proveedor?\n(No se borrarán las compras históricas.)',
			icon='question',
			option_1='No',
			option_2='Sí',
		)
		if msg.get() == 'Sí':
			sup_id = self.tree.item(selected[0], 'values')[0]
			tenant_id = self.ctx.tenant_id
			success, msg_response = self.controller.delete_supplier(tenant_id, sup_id)
			if success:
				self.load_data()
				self.reset_form()
				self.show_toast(msg_response, 'success')
			else:
				self.show_toast(msg_response, 'error')
