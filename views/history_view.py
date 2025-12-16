from tkinter import ttk

import customtkinter as ctk


class HistoryView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.sales_controller import SalesController

		self.controller = SalesController(db_engine)

		# Título
		ctk.CTkLabel(self, text='Historial de Ventas', font=('Arial', 24, 'bold')).pack(
			pady=20
		)

		# Botón actualizar
		ctk.CTkButton(
			self, text='🔄 Actualizar', command=self.load_history, width=100
		).pack(pady=5, padx=20, anchor='e')

		# --- TABLA DE VENTAS ---
		# Definimos columnas
		columns = ('ID', 'Fecha', 'Vendedor', 'Total')
		self.tree = ttk.Treeview(self, columns=columns, show='headings')

		# Configurar encabezados
		self.tree.heading('ID', text='ID Venta')
		self.tree.heading('Fecha', text='Fecha / Hora')
		self.tree.heading('Vendedor', text='Vendedor')
		self.tree.heading('Total', text='Total ($)')

		# Configurar ancho de columnas
		self.tree.column('ID', width=50, anchor='center')
		self.tree.column('Fecha', width=150, anchor='center')
		self.tree.column('Vendedor', width=100, anchor='center')
		self.tree.column('Total', width=100, anchor='e')  # 'e' es derecha (east)

		self.tree.pack(fill='both', expand=True, padx=20, pady=10)

		# Evento: Doble click para ver detalles
		self.tree.bind('<Double-1>', self.open_details_popup)

		self.load_history()

	def load_history(self):
		# Limpiar tabla
		for item in self.tree.get_children():
			self.tree.delete(item)

		sales = self.controller.get_history(self.current_user.tenant_id)

		for sale in sales:
			# Formatear fecha bonita
			date_str = sale.date.strftime('%Y-%m-%d %H:%M')
			# Obtenemos el nombre del vendedor (gracias a la relación en models.py)
			seller_name = sale.user.username

			self.tree.insert(
				'',
				'end',
				values=(sale.id, date_str, seller_name, f'${sale.total_amount:.2f}'),
			)

	def open_details_popup(self, event):
		# 1. Identificar qué fila se seleccionó
		selected_item = self.tree.selection()
		if not selected_item:
			return

		item_data = self.tree.item(selected_item)
		sale_id = item_data['values'][0]  # El ID es la primera columna

		# 2. Buscar los detalles en la BD
		details = self.controller.get_sale_details(sale_id)

		# 3. Crear ventana emergente (Toplevel)
		popup = ctk.CTkToplevel(self)
		popup.title(f'Detalle Venta #{sale_id}')
		popup.geometry('400x300')
		# Hacer que la ventana esté siempre al frente
		popup.attributes('-topmost', True)

		ctk.CTkLabel(
			popup, text=f'Productos de la Venta #{sale_id}', font=('Arial', 16, 'bold')
		).pack(pady=10)

		# Texto simple para mostrar lista
		textbox = ctk.CTkTextbox(popup, width=350, height=200)
		textbox.pack(pady=10)

		text_content = ''
		for d in details:
			text_content += f'• {d.product_name} x {d.quantity} = ${d.subtotal}\n'

		textbox.insert('0.0', text_content)
		textbox.configure(state='disabled')  # Para que sea solo lectura
