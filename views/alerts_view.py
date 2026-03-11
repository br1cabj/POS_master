from tkinter import ttk

import customtkinter as ctk


class AlertsView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.article_controller import ArticleController

		self.controller = ArticleController(db_engine)

		# --- TÍTULO Y BOTÓN DE ACTUALIZAR ---
		ctk.CTkLabel(
			self,
			text='⚠️ Alertas de Stock Mínimo',
			font=('Arial', 24, 'bold'),
			text_color='orange',
		).pack(pady=20)

		self.btn_refresh = ctk.CTkButton(
			self, text='🔄 Refrescar Lista', command=self.load_alerts
		)
		self.btn_refresh.pack(pady=10)

		# --- TABLA DE ARTÍCULOS CRÍTICOS ---
		columns = ('Código', 'Descripción', 'Stock Actual', 'Stock Mínimo')
		self.tree = ttk.Treeview(self, columns=columns, show='headings', height=15)

		# Configuramos los encabezados de la tabla
		for col in columns:
			self.tree.heading(col, text=col)
			self.tree.column(col, anchor='center')

		# Le damos más espacio a la descripción
		self.tree.column('Descripción', width=300, anchor='w')

		self.tree.pack(fill='both', expand=True, padx=20, pady=20)

		# Cargamos los datos apenas se abre la pantalla
		self.load_alerts()

	def load_alerts(self):
		"""Limpia la tabla y la llena con los artículos que necesitan reabastecimiento"""
		# 1. Limpiar datos viejos
		for item in self.tree.get_children():
			self.tree.delete(item)

		# 2. Pedir datos nuevos al controlador
		low_stock_articles = self.controller.get_low_stock_articles(
			self.current_user.tenant_id
		)

		# 3. Insertar los datos en la tabla
		for a in low_stock_articles:
			self.tree.insert(
				'',
				'end',
				values=(
					a.barcode if a.barcode else 'N/A',
					a.description,
					a.stock,
					a.min_stock,
				),
			)
