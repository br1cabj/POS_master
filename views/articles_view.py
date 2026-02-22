# views/articles_view.py
from tkinter import ttk

import customtkinter as ctk


class ArticlesView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.article_controller import ArticleController

		self.controller = ArticleController(db_engine)

		self.grid_columnconfigure(1, weight=1)
		self.grid_rowconfigure(0, weight=1)

		# === PANEL IZQUIERDO: FORMULARIO ===
		self.left_panel = ctk.CTkScrollableFrame(self, width=280)
		self.left_panel.grid(row=0, column=0, sticky='ns', padx=10, pady=10)

		ctk.CTkLabel(
			self.left_panel, text='Nuevo Artículo', font=('Arial', 20, 'bold')
		).pack(pady=10)

		# Campos del formulario
		self.entry_barcode = ctk.CTkEntry(
			self.left_panel, placeholder_text='Código de Barras'
		)
		self.entry_barcode.pack(pady=5, padx=10, fill='x')

		self.entry_desc = ctk.CTkEntry(
			self.left_panel, placeholder_text='Descripción *'
		)
		self.entry_desc.pack(pady=5, padx=10, fill='x')

		self.entry_cost = ctk.CTkEntry(
			self.left_panel, placeholder_text='Precio de Costo ($)'
		)
		self.entry_cost.pack(pady=5, padx=10, fill='x')

		self.entry_price1 = ctk.CTkEntry(
			self.left_panel, placeholder_text='Precio Venta 1 ($) *'
		)
		self.entry_price1.pack(pady=5, padx=10, fill='x')

		# Precios opcionales (Lista 2 y 3)
		self.entry_price2 = ctk.CTkEntry(
			self.left_panel, placeholder_text='Precio Venta 2 (Opcional)'
		)
		self.entry_price2.pack(pady=5, padx=10, fill='x')

		self.entry_price3 = ctk.CTkEntry(
			self.left_panel, placeholder_text='Precio Venta 3 (Opcional)'
		)
		self.entry_price3.pack(pady=5, padx=10, fill='x')

		self.entry_stock = ctk.CTkEntry(
			self.left_panel, placeholder_text='Stock Actual'
		)
		self.entry_stock.pack(pady=5, padx=10, fill='x')

		self.entry_min_stock = ctk.CTkEntry(
			self.left_panel, placeholder_text='Stock Mínimo (Alerta)'
		)
		self.entry_min_stock.pack(pady=5, padx=10, fill='x')

		self.btn_save = ctk.CTkButton(
			self.left_panel, text='Guardar Artículo', command=self.save_article
		)
		self.btn_save.pack(pady=20, padx=10, fill='x')

		self.lbl_msg = ctk.CTkLabel(self.left_panel, text='', text_color='green')
		self.lbl_msg.pack()

		# === PANEL DERECHO: LISTA ===
		self.right_panel = ctk.CTkFrame(self)
		self.right_panel.grid(row=0, column=1, sticky='nsew', padx=10, pady=10)

		ctk.CTkLabel(
			self.right_panel, text='Catálogo de Artículos', font=('Arial', 20, 'bold')
		).pack(pady=10)

		columns = ('Cod', 'Descripción', 'Costo', 'P1', 'P2', 'P3', 'Stock', 'Min')
		self.tree = ttk.Treeview(self.right_panel, columns=columns, show='headings')

		for col in columns:
			self.tree.heading(col, text=col)
			self.tree.column(col, width=80, anchor='center')
		self.tree.column('Descripción', width=200, anchor='w')

		self.tree.pack(fill='both', expand=True, padx=10, pady=10)
		self.refresh_list()

	def save_article(self):
		desc = self.entry_desc.get().strip()
		p1 = self.entry_price1.get().strip()

		if not desc or not p1:
			self.lbl_msg.configure(
				text='Descripción y Precio 1 son obligatorios', text_color='red'
			)
			return

		success, msg = self.controller.add_article(
			barcode=self.entry_barcode.get(),
			description=desc,
			cost_price=self.entry_cost.get(),
			price_1=p1,
			price_2=self.entry_price2.get(),
			price_3=self.entry_price3.get(),
			stock=self.entry_stock.get(),
			min_stock=self.entry_min_stock.get(),
			tenant_id=self.current_user.tenant_id,
		)

		if success:
			self.lbl_msg.configure(text=msg, text_color='green')
			self.refresh_list()
			# Limpiar entradas (simplificado)
			for widget in self.left_panel.winfo_children():
				if isinstance(widget, ctk.CTkEntry):
					widget.delete(0, 'end')
		else:
			self.lbl_msg.configure(text=msg, text_color='red')

	def refresh_list(self):
		for item in self.tree.get_children():
			self.tree.delete(item)

		articles = self.controller.get_articles(self.current_user.tenant_id)
		for a in articles:
			self.tree.insert(
				'',
				'end',
				values=(
					a.barcode,
					a.description,
					f'${a.cost_price}',
					f'${a.price_1}',
					f'${a.price_2}',
					f'${a.price_3}',
					a.stock,
					a.min_stock,
				),
			)
