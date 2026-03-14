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
		Esto elimina emojis y caracteres no imprimibles en Latin-1.
		"""
		if not text:
			return ''
		text_str = str(text)
		return (
			unicodedata.normalize('NFKD', text_str)
			.encode('latin-1', 'ignore')
			.decode('latin-1')
		)

	def generate_pdf(
		self, tenant_id, sale_id, date_str, items_list, total, customer_name
	):
		"""Genera un archivo PDF con formato de ticketera térmica dinámico (80mm)."""
		try:
			try:
				safe_sale_id = int(sale_id)
				safe_tenant_id = int(tenant_id)
			except (ValueError, TypeError):
				logger.error(f'Intento de Path Traversal o ID inválido: {sale_id}')
				return False, 'ID de venta inválido.'

			# 1.  CÁLCULO DINÁMICO DEL LARGO
			# Sumamos 1 línea por producto normal, y 2 líneas por producto pesable
			lineas_items = sum(
				1 if Decimal(str(i.get('qty', 1))) % 1 == 0 else 2 for i in items_list
			)

			alto_encabezado = 45
			alto_pie = 30
			alto_items = lineas_items * 5
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

			# --- LISTA DE PRODUCTOS (Diseño Supermercado) ---
			pdf.set_font('Arial', '', 8)

			for item in items_list:
				desc_corta = self._sanitize_for_pdf(item.get('desc', ''))[:22]
				qty = Decimal(str(item.get('qty', 1)))
				price = Decimal(str(item.get('price', 0)))
				subtotal = Decimal(str(item.get('subtotal', '0.0')))

				#  LÓGICA DE IMPRESIÓN
				if qty % 1 == 0:
					# Producto Normal (1 línea) -> Ej: "2 x Alfajor Jorgito   $1000.00"
					pdf.cell(10, 5, f'{int(qty)} x', align='L')
					pdf.cell(38, 5, desc_corta, align='L')
					pdf.cell(22, 5, f'${subtotal:.2f}', ln=True, align='R')
				else:
					# Producto Pesable (2 líneas) -> Ej: "Queso Tybo"
					#                                    "  0.285 Kg x $7000   $1995.00"
					pdf.cell(ancho_usable, 5, desc_corta, ln=True, align='L')
					pdf.cell(5, 5, '', align='L')  # Pequeña sangría visual
					pdf.cell(43, 5, f'{qty:.3f} Kg x ${price:.2f}', align='L')
					pdf.cell(22, 5, f'${subtotal:.2f}', ln=True, align='R')

			# --- TOTAL Y PIE DE PÁGINA ---
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

			# Mandar a imprimir (Abre el PDF en el OS)
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
