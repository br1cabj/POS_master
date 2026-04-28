import logging
import os
import platform
import subprocess
import tempfile
import unicodedata
from decimal import Decimal, ROUND_HALF_UP

from fpdf import FPDF

from utils import settings_manager

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

	def _space(self, pdf, W, h=3):
		pdf.cell(W, h, '', ln=True)

	def generate_pdf(
		self, tenant_id, sale_id, date_str, items_list, total, customer_name,
		discount_amount=0,
	):
		try:
			try:
				safe_sale_id   = int(sale_id)
				safe_tenant_id = int(tenant_id)
			except (ValueError, TypeError):
				logger.error(f'ID de venta invalido: {sale_id}')
				return False, 'ID de venta invalido.'

			discount_dec = Decimal(str(discount_amount or 0))
			has_discount = discount_dec > 0

			# Subtotal bruto
			subtotal_sum = sum(
				Decimal(str(i.get('subtotal', '0.0'))) for i in items_list
			)

			# Descuento proporcional por item
			item_discounts = {}
			if has_discount and subtotal_sum > 0:
				distributed = Decimal('0')
				items_indexed = list(enumerate(items_list))
				for idx, item in items_indexed[:-1]:
					sub = Decimal(str(item.get('subtotal', '0.0')))
					d = (discount_dec * sub / subtotal_sum).quantize(
						Decimal('0.01'), rounding=ROUND_HALF_UP
					)
					item_discounts[idx] = d
					distributed += d
				last_idx = items_indexed[-1][0]
				item_discounts[last_idx] = discount_dec - distributed

			# Altura dinamica
			item_lines = sum(
				1 if Decimal(str(i.get('qty', 1))) % 1 == 0 else 2
				for i in items_list
			)
			disc_section = (len(items_list) + 2) if has_discount else 0
			page_height = 60 + (item_lines * 5) + 12 + (disc_section * 5) + 20

			pdf = FPDF(format=(80, page_height))
			pdf.set_auto_page_break(auto=False, margin=0)
			pdf.add_page()
			pdf.set_margins(left=5, top=6, right=5)
			W = 70

			# ── CABECERA ──────────────────────────────────────────────────────
			business_name = self._sanitize(
				settings_manager.get('company_name', 'Mi Negocio')
			)
			address = self._sanitize(settings_manager.get('company_address', ''))
			phone   = self._sanitize(settings_manager.get('company_phone', ''))

			pdf.set_font('Arial', 'B', 15)
			pdf.cell(W, 9, business_name, ln=True, align='C')

			pdf.set_font('Arial', '', 8)
			if address:
				pdf.cell(W, 4, address, ln=True, align='C')
			if phone:
				pdf.cell(W, 4, f'Tel: {phone}', ln=True, align='C')

			self._space(pdf, W, 2)
			pdf.cell(W, 4, f'Ticket N {safe_sale_id}   {date_str}', ln=True, align='C')
			pdf.cell(W, 4, f'Cliente: {self._sanitize(customer_name[:28])}', ln=True, align='C')
			self._space(pdf, W, 5)

			# ── PRODUCTOS ─────────────────────────────────────────────────────
			for item in items_list:
				desc  = self._sanitize(item.get('desc', ''))[:24]
				qty   = Decimal(str(item.get('qty', 1)))
				price = Decimal(str(item.get('price', 0)))
				sub   = Decimal(str(item.get('subtotal', '0.0')))

				pdf.set_font('Arial', '', 9)
				if qty % 1 == 0:
					pdf.cell(10, 5, f'{int(qty)} x', align='L')
					pdf.cell(36, 5, desc, align='L')
					pdf.cell(24, 5, f'${sub:.2f}', ln=True, align='R')
				else:
					pdf.cell(W, 5, desc, ln=True, align='L')
					pdf.cell(5,  5, '', align='L')
					pdf.cell(41, 5, f'{qty:.3f} kg x ${price:.2f}', align='L')
					pdf.cell(24, 5, f'${sub:.2f}', ln=True, align='R')

			# ── SUBTOTAL ──────────────────────────────────────────────────────
			self._space(pdf, W, 3)
			pdf.set_font('Arial', '', 9)
			pdf.cell(46, 5, 'Subtotal', align='R')
			pdf.cell(24, 5, f'${subtotal_sum:.2f}', ln=True, align='R')

			# ── SECCIÓN DESCUENTOS ────────────────────────────────────────────
			if has_discount:
				self._space(pdf, W, 4)

				# Título "Descuentos" subrayado
				pdf.set_font('Arial', 'BU', 10)
				pdf.set_text_color(180, 100, 0)
				pdf.cell(W, 6, 'Descuentos', ln=True, align='L')
				pdf.set_text_color(0, 0, 0)
				self._space(pdf, W, 1)

				for idx, item in enumerate(items_list):
					d = item_discounts.get(idx, Decimal('0'))
					if d > 0:
						desc = self._sanitize(item.get('desc', ''))[:24]
						qty  = Decimal(str(item.get('qty', 1)))
						pdf.set_font('Arial', '', 9)
						pdf.set_text_color(180, 100, 0)
						if qty % 1 == 0:
							pdf.cell(10, 5, f'{int(qty)} x', align='L')
							pdf.cell(36, 5, desc, align='L')
							pdf.cell(24, 5, f'-${d:.2f}', ln=True, align='R')
						else:
							pdf.cell(10, 5, f'{qty:.3f}', align='L')
							pdf.cell(36, 5, desc, align='L')
							pdf.cell(24, 5, f'-${d:.2f}', ln=True, align='R')
						pdf.set_text_color(0, 0, 0)

			# ── TOTAL ─────────────────────────────────────────────────────────
			self._space(pdf, W, 4)
			pdf.set_font('Arial', 'B', 13)
			total_dec = Decimal(str(total))
			pdf.cell(46, 8, 'Total', align='R')
			pdf.cell(24, 8, f'${total_dec:.2f}', ln=True, align='R')

			# ── PIE ───────────────────────────────────────────────────────────
			self._space(pdf, W, 6)
			pdf.set_font('Arial', 'I', 8)
			pdf.cell(W, 6, 'Gracias por su compra!', ln=True, align='C')

			filepath = os.path.join(
				self.receipts_dir,
				f'tenant_{safe_tenant_id}_ticket_{safe_sale_id}.pdf',
			)
			pdf.output(filepath)
			self.print_receipt(filepath)
			return True, filepath

		except Exception as e:
			logger.error(f'Error generando PDF del ticket {sale_id}: {e}', exc_info=True)
			return False, 'Error interno al generar el recibo.'

	def print_receipt(self, filepath):
		try:
			if not os.path.exists(filepath):
				logger.error(f'Archivo no encontrado para imprimir: {filepath}')
				return False

			abs_path = os.path.abspath(filepath)
			allowed_dir = os.path.abspath(self.receipts_dir)
			if not abs_path.startswith(allowed_dir + os.sep) and abs_path != allowed_dir:
				logger.error(f'Acceso denegado fuera del directorio de recibos: {filepath}')
				return False

			os_name = platform.system()
			if os_name == 'Windows':
				os.startfile(abs_path, 'open')
			elif os_name == 'Darwin':
				result = subprocess.run(['open', abs_path], capture_output=True)
				if result.returncode != 0:
					logger.warning(f'open retorno codigo {result.returncode}')
					return False
			else:
				result = subprocess.run(['xdg-open', abs_path], capture_output=True)
				if result.returncode != 0:
					logger.warning(f'xdg-open retorno codigo {result.returncode}')
					return False
			return True
		except Exception as e:
			logger.error(f'Error al abrir el archivo PDF: {e}', exc_info=True)
			return False
