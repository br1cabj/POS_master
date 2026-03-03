from tkinter import ttk

import customtkinter as ctk


class HistoryView(ctk.CTkFrame):
	def __init__(self, master, current_user, db_engine):
		super().__init__(master)
		self.current_user = current_user

		from controllers.sales_controller import SalesController

		self.controller = SalesController(db_engine)

		ctk.CTkLabel(
			self, text='Historial de Ventas y Ganancias', font=('Arial', 24, 'bold')
		).pack(pady=20)
		ctk.CTkButton(
			self, text='🔄 Actualizar', command=self.load_history, width=100
		).pack(pady=5, padx=20, anchor='e')

		# --- TABLA DE VENTAS ---
		columns = ('ID', 'Fecha', 'Cliente', 'Vendedor', 'Total', 'Ganancia')
		self.tree = ttk.Treeview(self, columns=columns, show='headings')

		for col in columns:
			self.tree.heading(col, text=col)
			self.tree.column(col, width=100, anchor='center')
		self.tree.column('Cliente', width=150)

		self.tree.pack(fill='both', expand=True, padx=20, pady=10)
		self.tree.bind('<Double-1>', self.open_details_popup)

		self.load_history()

	def load_history(self):
		for item in self.tree.get_children():
			self.tree.delete(item)

		sales = self.controller.get_history(self.current_user.tenant_id)

		for sale in sales:
			date_str = sale.date.strftime('%Y-%m-%d %H:%M')
			# Extraemos los nombres verificando que existan
			customer_name = sale.customer.name if sale.customer else 'Sin Cliente'
			seller_name = sale.user.username if sale.user else 'Desconocido'

			self.tree.insert(
				'',
				'end',
				values=(
					sale.id,
					date_str,
					customer_name,
					seller_name,
					f'${sale.total_amount:.2f}',
					f'${sale.profit:.2f}',
				),
			)

	def open_details_popup(self, event):
		selected_item = self.tree.selection()
		if not selected_item:
			return

		item_data = self.tree.item(selected_item)
		sale_id = item_data['values'][0]

		details = self.controller.get_sale_details(sale_id)

		popup = ctk.CTkToplevel(self)
		popup.title(f'Detalle Venta #{sale_id}')
		popup.geometry('450x300')
		popup.attributes('-topmost', True)

		ctk.CTkLabel(
			popup, text=f'Artículos de la Venta #{sale_id}', font=('Arial', 16, 'bold')
		).pack(pady=10)

		textbox = ctk.CTkTextbox(popup, width=400, height=200)
		textbox.pack(pady=10)

		text_content = ''
		for d in details:
			# Ahora usamos d.description en lugar de d.product_name
			text_content += f'• {d.description} | Cant: {d.quantity} | P.Unit: ${d.unit_price} | Sub: ${d.subtotal}\n'

		textbox.insert('0.0', text_content)
		textbox.configure(state='disabled')
