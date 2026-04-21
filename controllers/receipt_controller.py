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
		os.makedirs(self.receipts_dir, exist_ok=True)

	def _sanitize(self, text):
		if not text:
			return ''
		return (
			unicodedata.normalize('NFKD', str(text))
			.encode('latin-1', 'ignore')
			.decode('latin-1')
		)

	def generate_pdf(
		self, tenant_id, sale_id, date_str, items_list, total, customer_name
	):
		"""
		Genera un ticket térmico en PDF de 80mm con alto dinámico según cantidad de ítems.
		Productos con cantidad entera se imprimen en 1 línea; productos pesables en 2.
		Retorna (True, filepath) o (False, mensaje_error).
		"""
		try:
			try:
				safe_sale_id = int(sale_id)
				safe_tenant_id = int(tenant_id)
			except (ValueError, TypeError):
				logger.error(f'ID de venta inválido: {sale_id}')
				return False, 'ID de venta inválido.'

			lines = sum(
				1 if Decimal(str(i.get('qty', 1))) % 1 == 0 else 2 for i in items_list
			)
			page_height = 45 + (lines * 5) + 30 + 15

			pdf = FPDF(format=(80, page_height))
			pdf.set_auto_page_break(auto=False, margin=0)
			pdf.add_page()
			pdf.set_margins(left=5, top=5, right=5)
			W = 70

			pdf.set_font('Arial', 'B', 14)
			pdf.cell(W, 8, 'MI NEGOCIO POS', ln=True, align='C')
			pdf.set_font('Arial', '', 9)
			pdf.cell(W, 5, f'Ticket Nro: {safe_sale_id}', ln=True, align='C')
			pdf.cell(W, 5, f'Fecha: {date_str}', ln=True, align='C')
			pdf.cell(
				W,
				5,
				f'Cliente: {self._sanitize(customer_name[:20])}',
				ln=True,
				align='C',
			)
			pdf.cell(W, 5, '-' * 40, ln=True, align='C')

			pdf.set_font('Arial', '', 8)
			for item in items_list:
				desc = self._sanitize(item.get('desc', ''))[:22]
				qty = Decimal(str(item.get('qty', 1)))
				price = Decimal(str(item.get('price', 0)))
				subtotal = Decimal(str(item.get('subtotal', '0.0')))

				if qty % 1 == 0:
					pdf.cell(10, 5, f'{int(qty)} x', align='L')
					pdf.cell(38, 5, desc, align='L')
					pdf.cell(22, 5, f'${subtotal:.2f}', ln=True, align='R')
				else:
					pdf.cell(W, 5, desc, ln=True, align='L')
					pdf.cell(5, 5, '', align='L')
					pdf.cell(43, 5, f'{qty:.3f} Kg x ${price:.2f}', align='L')
					pdf.cell(22, 5, f'${subtotal:.2f}', ln=True, align='R')

			pdf.cell(W, 5, '-' * 40, ln=True, align='C')
			pdf.set_font('Arial', 'B', 12)
			pdf.cell(W, 8, f'TOTAL: ${Decimal(str(total)):.2f}', ln=True, align='R')
			pdf.set_font('Arial', 'I', 8)
			pdf.cell(W, 10, '¡Gracias por su compra!', ln=True, align='C')

			filepath = os.path.join(
				self.receipts_dir, f'tenant_{safe_tenant_id}_ticket_{safe_sale_id}.pdf'
			)
			pdf.output(filepath)
			self.print_receipt(filepath)
			return True, filepath

		except Exception as e:
			logger.error(
				f'Error generando PDF del ticket {sale_id}: {e}', exc_info=True
			)
			return False, 'Error interno al generar el recibo.'

	def print_receipt(self, filepath):
		"""Abre el PDF con el visor del sistema operativo para su impresión."""
		try:
			if not os.path.exists(filepath):
				logger.error(f'Archivo no encontrado para imprimir: {filepath}')
				return False

			abs_path = os.path.abspath(filepath)

			# Seguridad: verificar que el archivo esté dentro del directorio permitido
			allowed_dir = os.path.abspath(self.receipts_dir)
			if not abs_path.startswith(allowed_dir + os.sep) and abs_path != allowed_dir:
				logger.error(
					f'Intento de acceso a archivo fuera del directorio de recibos: {filepath}'
				)
				return False

			os_name = platform.system()

			if os_name == 'Windows':
				os.startfile(abs_path, 'open')
			elif os_name == 'Darwin':
				subprocess.run(['open', abs_path], check=True, capture_output=True)
			else:
				subprocess.run(['xdg-open', abs_path], check=True, capture_output=True)

			return True
		except Exception as e:
			logger.error(f'Error al abrir el archivo PDF: {e}', exc_info=True)
			return False
