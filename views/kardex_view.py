from tkinter import ttk

import customtkinter as ctk

from controllers.inventory_controller import InventoryController


class KardexView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = InventoryController(db_engine)

		self.current_page = 1

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		# --- ESTILO MODERNO PARA LA TABLA ---
		style = ttk.Style()
		style.theme_use('default')
		style.configure(
			'Treeview',
			background='#2b2b2b',
			foreground='white',
			rowheight=30,
			fieldbackground='#2b2b2b',
			borderwidth=0,
		)
		style.map('Treeview', background=[('selected', '#1f538d')])
		style.configure(
			'Treeview.Heading',
			background='#565b5e',
			foreground='white',
			relief='flat',
			font=('Arial', 10, 'bold'),
		)
		style.map('Treeview.Heading', background=[('active', '#343638')])

		# --- ENCABEZADO Y CONTROLES ---
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='ew')

		ctk.CTkLabel(
			header_frame,
			text='📊 Kardex: Auditoría de Inventario',
			font=('Arial', 24, 'bold'),
		).pack(side='left')

		# Controles a la derecha
		controls_frame = ctk.CTkFrame(header_frame, fg_color='transparent')
		controls_frame.pack(side='right')

		# 🛡️ ESCUDO: Controles de Paginación y Refresco
		self.btn_prev = ctk.CTkButton(
			controls_frame, text='◀ Anterior', width=80, command=self.prev_page
		)
		self.btn_prev.pack(side='left', padx=5)

		self.lbl_page = ctk.CTkLabel(
			controls_frame,
			text=f'Página {self.current_page}',
			font=('Arial', 14, 'bold'),
		)
		self.lbl_page.pack(side='left', padx=10)

		self.btn_next = ctk.CTkButton(
			controls_frame, text='Siguiente ▶', width=80, command=self.next_page
		)
		self.btn_next.pack(side='left', padx=5)

		self.btn_refresh = ctk.CTkButton(
			controls_frame,
			text='🔄 Actualizar',
			fg_color='#1f538d',
			width=100,
			command=self.refresh_data,
		)
		self.btn_refresh.pack(side='left', padx=(20, 0))

		# --- CONTENEDOR DE LA TABLA ---
		self.table_frame = ctk.CTkFrame(self, fg_color='transparent')
		self.table_frame.grid(row=1, column=0, sticky='nsew', padx=20, pady=(0, 20))

		self.tree_scroll = ttk.Scrollbar(self.table_frame, orient='vertical')

		columns = ('Fecha', 'Tipo', 'Producto', 'Cantidad', 'Referencia', 'Usuario')
		self.tree = ttk.Treeview(
			self.table_frame,
			columns=columns,
			show='headings',
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		for col in columns:
			self.tree.heading(col, text=col)
			if col in ['Producto', 'Referencia']:
				self.tree.column(col, anchor='center', width=200)
			else:
				self.tree.column(col, anchor='center', width=100)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		self.tree.tag_configure('entrada', foreground='#00cc66')
		self.tree.tag_configure('salida', foreground='#ff6666')
		self.tree.tag_configure('ajuste', foreground='#ffaa00')

		self.after(100, self.load_data)

	def _get_tenant_id(self):
		return (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)

	# --- Lógica de Paginación ---
	def prev_page(self):
		if self.current_page > 1:
			self.current_page -= 1
			self.load_data()

	def next_page(self):
		# Asumimos que si hay datos, podríamos tener una página siguiente.
		# Si la tabla se dibuja vacía, el usuario sabrá que llegó al final.
		self.current_page += 1
		self.load_data()

	def refresh_data(self):
		self.current_page = 1
		self.load_data()

	def load_data(self):
		"""Busca los movimientos paginados y los inserta en la tabla"""
		for item in self.tree.get_children():
			self.tree.delete(item)

		self.lbl_page.configure(text=f'Página {self.current_page}')
		tenant_id = self._get_tenant_id()

		movements = self.controller.get_kardex(
			tenant_id, page=self.current_page, limit=100
		)

		# Si no hay movimientos y estamos más allá de la pág 1, desactivar botón "Siguiente"
		if not movements and self.current_page > 1:
			self.btn_next.configure(state='disabled')
			return
		else:
			self.btn_next.configure(state='normal')

		if self.current_page == 1:
			self.btn_prev.configure(state='disabled')
		else:
			self.btn_prev.configure(state='normal')

		for mov in movements:
			raw_date = mov.get('date')
			date_str = (
				raw_date.strftime('%d/%m/%Y %H:%M')
				if hasattr(raw_date, 'strftime')
				else str(raw_date)
			)

			mov_type = mov.get('movement_type')
			if mov_type == 'in':
				tipo, tag = '🟢 ENTRADA', 'entrada'
			elif mov_type == 'out':
				tipo, tag = '🔴 SALIDA', 'salida'
			else:
				tipo, tag = '🟡 AJUSTE', 'ajuste'

			producto = mov.get('article_name', 'Desconocido')
			usuario = mov.get('user_name', 'Sistema').capitalize()
			referencia = mov.get('reference') or '-'

			raw_qty = float(mov.get('quantity', 0))
			cantidad = f'{int(raw_qty)}' if raw_qty.is_integer() else f'{raw_qty:.4f}'

			item_id = self.tree.insert(
				'',
				'end',
				values=(date_str, tipo, producto, cantidad, referencia, usuario),
			)
			# Aplicamos color a la fila completa según su tipo
			self.tree.item(item_id, tags=(tag,))
