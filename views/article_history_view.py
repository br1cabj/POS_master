from tkinter import ttk

import customtkinter as ctk

from controllers.article_controller import ArticleController


class ArticleHistoryView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user
		self.controller = ArticleController(db_engine)

		self.grid_columnconfigure(0, weight=1)
		self.grid_rowconfigure(1, weight=1)

		# --- ESTILO ---
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

		# --- ENCABEZADO ---
		header_frame = ctk.CTkFrame(self, fg_color='transparent')
		header_frame.grid(row=0, column=0, pady=(20, 10), padx=20, sticky='ew')

		ctk.CTkLabel(
			header_frame,
			text='🕵️ Auditoría: Historial de Precios',
			font=('Arial', 24, 'bold'),
		).pack(side='left')

		self.btn_refresh = ctk.CTkButton(
			header_frame,
			text='🔄 Actualizar',
			fg_color='#1f538d',
			width=100,
			command=self.load_data,
		)
		self.btn_refresh.pack(side='right')

		# --- TABLA ---
		self.table_container = ctk.CTkFrame(self, fg_color='transparent')
		self.table_container.grid(row=1, column=0, sticky='nsew', padx=20, pady=(0, 20))

		self.tree_scroll = ttk.Scrollbar(self.table_container, orient='vertical')

		columns = (
			'Fecha',
			'Usuario',
			'Acción',
			'Producto',
			'Costo (Ant -> Nuevo)',
			'Venta (Ant -> Nuevo)',
		)
		self.tree = ttk.Treeview(
			self.table_container,
			columns=columns,
			show='headings',
			yscrollcommand=self.tree_scroll.set,
		)
		self.tree_scroll.configure(command=self.tree.yview)

		for col in columns:
			self.tree.heading(col, text=col)
			width = 180 if col == 'Producto' else 120
			self.tree.column(col, anchor='center', width=width)

		self.tree_scroll.pack(side='right', fill='y')
		self.tree.pack(side='left', fill='both', expand=True)

		# Colores para tipos de acción
		self.tree.tag_configure('masivo', foreground='#ffaa00')  # Naranja
		self.tree.tag_configure('manual', foreground='#00aaff')  # Azul

		self.after(100, self.load_data)

	def load_data(self):
		for item in self.tree.get_children():
			self.tree.delete(item)

		tenant_id = (
			self.current_user.get('tenant_id')
			if isinstance(self.current_user, dict)
			else self.current_user.tenant_id
		)
		history = self.controller.get_price_history(tenant_id)

		for h in history:
			raw_date = h.get('date')
			date_str = (
				raw_date.strftime('%d/%m/%Y %H:%M')
				if hasattr(raw_date, 'strftime')
				else str(raw_date)
			)

			# Formateo visual del antes y después
			old_c, new_c = h.get('old_cost'), h.get('new_cost')
			old_p, new_p = h.get('old_price'), h.get('new_price')

			cost_str = f'${old_c:.2f} ➔ ${new_c:.2f}' if old_c is not None else '-'
			price_str = f'${old_p:.2f} ➔ ${new_p:.2f}' if old_p is not None else '-'

			tag = 'masivo' if h.get('action') == 'AUMENTO MASIVO' else 'manual'

			self.tree.insert(
				'',
				'end',
				values=(
					date_str,
					h.get('user_name').capitalize(),
					h.get('action'),
					h.get('article_name'),
					cost_str,
					price_str,
				),
				tags=(tag,),
			)
