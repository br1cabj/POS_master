import logging
import os
import platform
import subprocess
import tempfile

from fpdf import FPDF

logger = logging.getLogger(__name__)


class ReceiptController:
	def __init__(self):
		# Usamos el directorio temporal del sistema operativo en lugar de una carpeta local.
		# Esto evita problemas de permisos en Windows ("Archivos de Programa")
		self.receipts_dir = os.path.join(tempfile.gettempdir(), 'MiERP_Recibos')

		if not os.path.exists(self.receipts_dir):
			try:
				os.makedirs(self.receipts_dir)
			except Exception as e:
				logger.error(f'Error creando directorio de recibos: {e}')

	def generate_pdf(self, sale_id, date_str, items_list, total, customer_name):
		"""Genera un archivo PDF con formato de ticketera térmica dinámico (80mm)"""
		try:
			# 1. Calculamos el alto dinámico del ticket
			alto_encabezado = 45
			alto_pie = 30
			alto_items = len(items_list) * 5

			alto_total = alto_encabezado + alto_items + alto_pie + 15

			# Formato (ancho, alto)
			pdf = FPDF(format=(80, alto_total))

			pdf.set_auto_page_break(auto=False, margin=0)

			pdf.add_page()

			# --- Configuración de márgenes ---
			pdf.set_margins(left=5, top=5, right=5)
			ancho_usable = 70

			# --- ENCABEZADO ---
			pdf.set_font('Arial', 'B', 14)
			pdf.cell(ancho_usable, 8, 'MI NEGOCIO POS', ln=True, align='C')

			pdf.set_font('Arial', '', 9)
			pdf.cell(ancho_usable, 5, f'Ticket Nro: {sale_id}', ln=True, align='C')
			pdf.cell(ancho_usable, 5, f'Fecha: {date_str}', ln=True, align='C')
			pdf.cell(
				ancho_usable, 5, f'Cliente: {customer_name[:20]}', ln=True, align='C'
			)  # Recortamos el nombre si es muy largo
			pdf.cell(ancho_usable, 5, '-' * 40, ln=True, align='C')

			# --- CABECERA DE LA TABLA ---
			pdf.set_font('Arial', 'B', 8)
			pdf.cell(35, 5, 'Articulo', align='L')
			pdf.cell(10, 5, 'Cant', align='C')
			pdf.cell(25, 5, 'Subtotal', ln=True, align='R')

			# --- LISTA DE PRODUCTOS ---
			pdf.set_font('Arial', '', 8)
			for item in items_list:
				desc_corta = str(item.get('desc', ''))[:18]

				# Manejo seguro de las variables numéricas para el ticket
				qty = float(item.get('qty', 1))
				qty_str = f'{int(qty)}' if qty.is_integer() else f'{qty:.2f}'
				subtotal = float(item.get('subtotal', 0.0))

				pdf.cell(35, 5, desc_corta, align='L')
				pdf.cell(10, 5, qty_str, align='C')
				pdf.cell(25, 5, f'${subtotal:.2f}', ln=True, align='R')

			# --- TOTAL ---
			pdf.cell(ancho_usable, 5, '-' * 40, ln=True, align='C')
			pdf.set_font('Arial', 'B', 12)
			pdf.cell(ancho_usable, 8, f'TOTAL: ${total:.2f}', ln=True, align='R')

			pdf.set_font('Arial', 'I', 8)
			pdf.cell(ancho_usable, 10, '¡Gracias por su compra!', ln=True, align='C')

			# --- GUARDAR ARCHIVO ---
			filename = os.path.join(self.receipts_dir, f'ticket_{sale_id}.pdf')
			pdf.output(filename)

			# --- DISPARADOR AUTOMÁTICO ---
			self.print_receipt(filename)

			return True, filename

		except Exception as e:
			logger.error(
				f'Error generando PDF del ticket {sale_id}: {e}', exc_info=True
			)
			return False, 'Error interno al generar el recibo.'

	def print_receipt(self, filepath):
		"""Abre o imprime el archivo automáticamente dependiendo del sistema operativo."""
		try:
			abs_path = os.path.abspath(filepath)
			os_name = platform.system()

			if os_name == 'Windows':
				# Recuerda: 'print' usará el visor de PDF predeterminado.
				os.startfile(abs_path, 'open')
			elif os_name == 'Darwin':
				subprocess.run(['open', abs_path])
			else:
				subprocess.run(['xdg-open', abs_path])

		except Exception as e:
			logger.error(
				f'Error al intentar ejecutar el archivo PDF: {e}', exc_info=True
			)
