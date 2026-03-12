# controllers/receipt_controller.py
import os
import platform
import subprocess

from fpdf import FPDF


class ReceiptController:
	def __init__(self):
		# Creamos una carpeta para guardar los tickets si no existe
		if not os.path.exists('recibos'):
			os.makedirs('recibos')

	def generate_pdf(self, sale_id, date_str, items_list, total, customer_name):
		"""Genera un archivo PDF con formato de ticketera térmica (80mm)"""
		try:
			pdf = FPDF(format=(80, 150))
			pdf.add_page()

			# --- ENCABEZADO ---
			pdf.set_font('Arial', 'B', 14)
			pdf.cell(60, 8, 'MI NEGOCIO POS', ln=True, align='C')

			pdf.set_font('Arial', '', 9)
			pdf.cell(60, 5, f'Ticket Nro: {sale_id}', ln=True, align='C')
			pdf.cell(60, 5, f'Fecha: {date_str}', ln=True, align='C')
			pdf.cell(60, 5, f'Cliente: {customer_name}', ln=True, align='C')
			pdf.cell(60, 5, '-' * 35, ln=True, align='C')

			# --- CABECERA DE LA TABLA ---
			pdf.set_font('Arial', 'B', 8)
			pdf.cell(30, 5, 'Articulo', align='L')
			pdf.cell(10, 5, 'Cant', align='C')
			pdf.cell(20, 5, 'Subtotal', ln=True, align='R')

			# --- LISTA DE PRODUCTOS ---
			pdf.set_font('Arial', '', 8)
			for item in items_list:
				desc_corta = item['desc'][:15]
				pdf.cell(30, 5, desc_corta, align='L')
				pdf.cell(10, 5, str(item['qty']), align='C')
				pdf.cell(20, 5, f'${item["subtotal"]:.2f}', ln=True, align='R')

			# --- TOTAL ---
			pdf.cell(60, 5, '-' * 35, ln=True, align='C')
			pdf.set_font('Arial', 'B', 12)
			pdf.cell(60, 8, f'TOTAL: ${total:.2f}', ln=True, align='R')

			pdf.set_font('Arial', 'I', 8)
			pdf.cell(60, 10, '¡Gracias por su compra!', ln=True, align='C')

			# --- GUARDAR ARCHIVO ---
			filename = f'recibos/ticket_{sale_id}.pdf'
			pdf.output(filename)

			# --- DISPARADOR AUTOMÁTICO ---
			self.print_receipt(filename)

			return True, filename
		except Exception as e:
			print(f'Error generando PDF: {e}')
			return False, str(e)

	def print_receipt(self, filepath):
		"""
		Abre o imprime el archivo automáticamente dependiendo del sistema operativo.
		"""
		try:
			# Convierte la ruta relativa a una ruta absoluta completa (necesario para Windows)
			abs_path = os.path.abspath(filepath)

			os_name = platform.system()

			if os_name == 'Windows':
				# MODO PRUEBAS: "open" abre el PDF en la pantalla.
				# MODO PRODUCCIÓN: Cambia la palabra "open" por "print" para que vaya a la impresora térmica directamente.
				os.startfile(abs_path, 'open')

			elif os_name == 'Darwin':  # Para computadoras Mac
				# MODO PRUEBAS: "open" abre el PDF.
				# MODO PRODUCCIÓN: Cambia "open" por "lpr" para imprimir directo.
				subprocess.run(['open', abs_path])

			else:  # Para Linux
				# MODO PRUEBAS: "xdg-open". MODO PRODUCCIÓN: "lpr"
				subprocess.run(['xdg-open', abs_path])

		except Exception as e:
			print(f'Error al intentar ejecutar el archivo: {e}')
