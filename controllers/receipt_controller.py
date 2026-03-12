import logging
import os
import platform
import subprocess
import tempfile
import unicodedata
from decimal import Decimal

from fpdf import FPDF

logger = logging.getLogger(__name__)


class ReceiptController:
	def __init__(self):
		self.receipts_dir = os.path.join(tempfile.gettempdir(), 'MiERP_Recibos')

		if not os.path.exists(self.receipts_dir):
			try:
				os.makedirs(self.receipts_dir)
			except Exception as e:
				logger.error(f'Error creando directorio de recibos: {e}')

	def _sanitize_for_pdf(self, text):
		"""
		🛡️ ESCUDO: FPDF no soporta todos los caracteres Unicode.
		Esto elimina emojis y caracteres no imprimibles en Latin-1 para evitar crashes.
		"""
		if not text:
			return ''
		# Normalizamos y codificamos a ascii/latin-1 ignorando los errores
		text_str = str(text)
		return (
			unicodedata.normalize('NFKD', text_str)
			.encode('latin-1', 'ignore')
			.decode('latin-1')
		)

	def generate_pdf(
		self, tenant_id, sale_id, date_str, items_list, total, customer_name
	):
		"""
		Genera un archivo PDF con formato de ticketera térmica dinámico (80mm).
		🛡️ ESCUDO: Requiere tenant_id para aislar los archivos.
		"""
		try:
			# 1. 🛡️ ESCUDO: Validación estricta del ID para evitar Path Traversal
			try:
				safe_sale_id = int(sale_id)
				safe_tenant_id = int(tenant_id)
			except (ValueError, TypeError):
				logger.error(f'Intento de Path Traversal o ID inválido: {sale_id}')
				return False, 'ID de venta inválido.'

			# 2. Calculamos el alto dinámico del ticket
			alto_encabezado = 45
			alto_pie = 30
			alto_items = len(items_list) * 5

			alto_total = alto_encabezado + alto_items + alto_pie + 15

			pdf = FPDF(format=(80, alto_total))
			pdf.set_auto_page_break(auto=False, margin=0)
			pdf.add_page()
			pdf.set_margins(left=5, top=5, right=5)
			ancho_usable = 70

			# --- ENCABEZADO ---
			pdf.set_font('Arial', 'B', 14)
			pdf.cell(ancho_usable, 8, 'MI NEGOCIO POS', ln=True, align='C')

			pdf.set_font('Arial', '', 9)
			pdf.cell(ancho_usable, 5, f'Ticket Nro: {safe_sale_id}', ln=True, align='C')
			pdf.cell(ancho_usable, 5, f'Fecha: {date_str}', ln=True, align='C')

			safe_customer = self._sanitize_for_pdf(customer_name[:20])
			pdf.cell(ancho_usable, 5, f'Cliente: {safe_customer}', ln=True, align='C')
			pdf.cell(ancho_usable, 5, '-' * 40, ln=True, align='C')

			# --- CABECERA DE LA TABLA ---
			pdf.set_font('Arial', 'B', 8)
			pdf.cell(35, 5, 'Articulo', align='L')
			pdf.cell(10, 5, 'Cant', align='C')
			pdf.cell(25, 5, 'Subtotal', ln=True, align='R')

			# --- LISTA DE PRODUCTOS ---
			pdf.set_font('Arial', '', 8)
			for item in items_list:
				desc_corta = self._sanitize_for_pdf(item.get('desc', ''))[:18]

				qty = Decimal(str(item.get('qty', 1)))
				qty_str = f'{int(qty)}' if qty % 1 == 0 else f'{qty:.2f}'

				subtotal = Decimal(str(item.get('subtotal', '0.0')))

				pdf.cell(35, 5, desc_corta, align='L')
				pdf.cell(10, 5, qty_str, align='C')
				pdf.cell(25, 5, f'${subtotal:.2f}', ln=True, align='R')

			# --- TOTAL ---
			pdf.cell(ancho_usable, 5, '-' * 40, ln=True, align='C')
			pdf.set_font('Arial', 'B', 12)

			safe_total = Decimal(str(total))
			pdf.cell(ancho_usable, 8, f'TOTAL: ${safe_total:.2f}', ln=True, align='R')

			pdf.set_font('Arial', 'I', 8)
			pdf.cell(ancho_usable, 10, '¡Gracias por su compra!', ln=True, align='C')

			# --- GUARDAR ARCHIVO ---
			safe_filename = f'tenant_{safe_tenant_id}_ticket_{safe_sale_id}.pdf'
			filepath = os.path.join(self.receipts_dir, safe_filename)

			pdf.output(filepath)

			# Opcional: Si esto corre en la nube, NO llames a self.print_receipt().
			# Devuelve el filepath o el contenido del PDF para que el Frontend lo imprima.
			self.print_receipt(filepath)

			return True, filepath

		except Exception as e:
			logger.error(
				f'Error generando PDF del ticket {sale_id}: {e}', exc_info=True
			)
			return False, 'Error interno al generar el recibo.'

	def print_receipt(self, filepath):
		"""Intenta abrir el archivo. Nota: Solo funciona si el backend corre en la PC local."""
		try:
			if not os.path.exists(filepath):
				logger.error(f'Archivo no encontrado para imprimir: {filepath}')
				return False

			abs_path = os.path.abspath(filepath)
			os_name = platform.system()

			if os_name == 'Windows':
				os.startfile(abs_path, 'open')
			elif os_name == 'Darwin':
				subprocess.run(['open', abs_path], check=True)
			else:
				subprocess.run(['xdg-open', abs_path], check=True)

			return True

		except Exception as e:
			logger.error(
				f'Error al intentar ejecutar el archivo PDF: {e}', exc_info=True
			)
			return False
