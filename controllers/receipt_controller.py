import logging
import os
import platform
import subprocess
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Dict, List, Optional, Tuple

from fpdf import FPDF

from utils import settings_manager

logger = logging.getLogger(__name__)


class ReceiptController:
	def __init__(self):
		"""Inicializa el controlador usando un directorio persistente en el sistema."""
		user_home = os.path.expanduser('~')
		self.receipts_dir = os.path.join(user_home, 'cloudPOS')
		os.makedirs(self.receipts_dir, exist_ok=True)

	def _space(self, pdf: FPDF, w: int, h: int = 3) -> None:
		pdf.cell(w, h, '', new_x='LMARGIN', new_y='NEXT')

	def _get_column_widths(self, paper_width: int) -> Tuple[int, int, int, int]:
		"""Calcula los anchos de columna dinámicos según el tamaño del papel."""
		if paper_width == 58:
			return 48, 8, 22, 18  # Total_W, Qty_W, Desc_W, Total_W
		return 70, 10, 36, 24  # Default 80mm

	def generate_pdf(
		self,
		tenant_id: int,
		sale_id: int,
		date_str: str,
		items_list: List[Dict[str, Any]],
		total: float | Decimal,
		customer_name: str,
		cashier_name: str = 'Caja Principal',
		discount_amount: float | Decimal = 0,
		payment_method: Optional[str] = None,
		payment_method_2: Optional[str] = None,
		amount_method_2: Optional[float | Decimal] = None,
		paid_amount: Optional[float | Decimal] = None,
		change_amount: Optional[float | Decimal] = None,
		paper_width: int = 80,
	) -> Tuple[bool, str]:
		"""Genera el PDF del ticket con soporte para 80mm/58mm y codificación UTF-8 nativa."""
		try:
			try:
				safe_sale_id = str(sale_id)
				safe_tenant_id = str(tenant_id)
			except (ValueError, TypeError):
				logger.error('ID de venta inválido: %s', sale_id)
				return False, 'ID de venta inválido.'

			discount_dec = Decimal(str(discount_amount or 0))
			has_discount = discount_dec > 0

			subtotal_sum = sum(
				Decimal(str(i.get('subtotal', '0.0'))) for i in items_list
			)

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

			item_lines = sum(
				1 if Decimal(str(i.get('qty', 1))) % 1 == 0 else 2 for i in items_list
			)
			disc_section = (len(items_list) + 2) if has_discount else 0

			pay_lines = 0
			if payment_method:
				pay_lines += 1
				if payment_method_2 and amount_method_2:
					pay_lines += 1
				if (
					paid_amount is not None
					and change_amount is not None
					and change_amount >= 0
				):
					pay_lines += 2

			page_height = (
				70 + (item_lines * 5) + (disc_section * 5) + (pay_lines * 5) + 24
			)

			pdf = FPDF(format=(paper_width, page_height))
			pdf.set_auto_page_break(auto=False, margin=0)
			pdf.add_page()
			pdf.set_margins(left=5, top=6, right=5)

			W, COL_QTY, COL_DESC, COL_TOT = self._get_column_widths(paper_width)
			MAX_DESC_LEN = 24 if paper_width == 80 else 14

			business_name = settings_manager.get('company_name', 'Mi Negocio')
			address = settings_manager.get('company_address', '')
			phone = settings_manager.get('company_phone', '')

			pdf.set_font('helvetica', 'B', 14)
			pdf.cell(W, 8, business_name, new_x='LMARGIN', new_y='NEXT', align='C')

			pdf.set_font('helvetica', '', 8)
			if address:
				pdf.cell(W, 4, address, new_x='LMARGIN', new_y='NEXT', align='C')
			if phone:
				pdf.cell(
					W, 4, f'Tel: {phone}', new_x='LMARGIN', new_y='NEXT', align='C'
				)

			self._space(pdf, W, 2)
			pdf.cell(
				W,
				4,
				f'Ticket N° {safe_sale_id}   {date_str}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='C',
			)
			pdf.cell(
				W,
				4,
				f'Cajero: {cashier_name[:20]}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='C',
			)
			pdf.cell(
				W,
				4,
				f'Cliente: {customer_name[: MAX_DESC_LEN + 4]}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='C',
			)
			self._space(pdf, W, 5)

			for item in items_list:
				desc = str(item.get('desc', ''))[:MAX_DESC_LEN]
				qty = Decimal(str(item.get('qty', 1)))
				price = Decimal(str(item.get('price', 0)))
				sub = Decimal(str(item.get('subtotal', '0.0')))

				pdf.set_font('helvetica', '', 9)
				if qty % 1 == 0:
					pdf.cell(COL_QTY, 5, f'{int(qty)} x', align='L')
					pdf.cell(COL_DESC, 5, desc, align='L')
					pdf.cell(
						COL_TOT,
						5,
						f'${sub:.2f}',
						new_x='LMARGIN',
						new_y='NEXT',
						align='R',
					)
				else:
					pdf.cell(W, 5, desc, new_x='LMARGIN', new_y='NEXT', align='L')
					pdf.cell(COL_QTY / 2, 5, '', align='L')
					pdf.cell(
						COL_DESC + (COL_QTY / 2),
						5,
						f'{qty:.3f} kg x ${price:.2f}',
						align='L',
					)
					pdf.cell(
						COL_TOT,
						5,
						f'${sub:.2f}',
						new_x='LMARGIN',
						new_y='NEXT',
						align='R',
					)

			self._space(pdf, W, 3)
			pdf.set_font('helvetica', '', 9)
			pdf.cell(COL_QTY + COL_DESC, 5, 'Subtotal', align='R')
			pdf.cell(
				COL_TOT,
				5,
				f'${subtotal_sum:.2f}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='R',
			)

			if has_discount:
				self._space(pdf, W, 4)
				pdf.set_font('helvetica', 'BU', 10)
				pdf.set_text_color(180, 100, 0)
				pdf.cell(W, 6, 'Descuentos', new_x='LMARGIN', new_y='NEXT', align='L')
				pdf.set_text_color(0, 0, 0)
				self._space(pdf, W, 1)

				for idx, item in enumerate(items_list):
					d = item_discounts.get(idx, Decimal('0'))
					if d > 0:
						desc = str(item.get('desc', ''))[:MAX_DESC_LEN]
						qty = Decimal(str(item.get('qty', 1)))
						pdf.set_font('helvetica', '', 9)
						pdf.set_text_color(180, 100, 0)

						qty_str = f'{int(qty)} x' if qty % 1 == 0 else f'{qty:.3f}'
						pdf.cell(COL_QTY, 5, qty_str, align='L')
						pdf.cell(COL_DESC, 5, desc, align='L')
						pdf.cell(
							COL_TOT,
							5,
							f'-${d:.2f}',
							new_x='LMARGIN',
							new_y='NEXT',
							align='R',
						)
						pdf.set_text_color(0, 0, 0)

			self._space(pdf, W, 4)
			pdf.set_font('helvetica', 'B', 13)
			total_dec = Decimal(str(total))
			pdf.cell(COL_QTY + COL_DESC, 8, 'Total', align='R')
			pdf.cell(
				COL_TOT,
				8,
				f'${total_dec:.2f}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='R',
			)

			if payment_method:
				self._space(pdf, W, 3)
				pdf.set_font('helvetica', '', 9)
				pm_display = payment_method.capitalize()

				if payment_method_2 and amount_method_2:
					amt_m2 = Decimal(str(amount_method_2))
					amt_m1 = total_dec - amt_m2
					pm2_display = payment_method_2.capitalize()

					pdf.cell(COL_QTY + COL_DESC, 5, f'Pago ({pm_display})', align='R')
					pdf.cell(
						COL_TOT,
						5,
						f'${amt_m1:.2f}',
						new_x='LMARGIN',
						new_y='NEXT',
						align='R',
					)
					pdf.cell(COL_QTY + COL_DESC, 5, f'Pago ({pm2_display})', align='R')
					pdf.cell(
						COL_TOT,
						5,
						f'${amt_m2:.2f}',
						new_x='LMARGIN',
						new_y='NEXT',
						align='R',
					)
				else:
					pdf.cell(COL_QTY + COL_DESC, 5, 'Forma de pago', align='R')
					pdf.cell(
						COL_TOT, 5, pm_display, new_x='LMARGIN', new_y='NEXT', align='R'
					)

				paid_dec = (
					Decimal(str(paid_amount)) if paid_amount is not None else None
				)
				change_dec = (
					Decimal(str(change_amount)) if change_amount is not None else None
				)

				if paid_dec is not None and change_dec is not None and change_dec >= 0:
					pdf.cell(COL_QTY + COL_DESC, 5, 'Entregado', align='R')
					pdf.cell(
						COL_TOT,
						5,
						f'${paid_dec:.2f}',
						new_x='LMARGIN',
						new_y='NEXT',
						align='R',
					)
					pdf.set_font('helvetica', 'B', 9)
					pdf.cell(COL_QTY + COL_DESC, 5, 'Vuelto', align='R')
					pdf.cell(
						COL_TOT,
						5,
						f'${change_dec:.2f}',
						new_x='LMARGIN',
						new_y='NEXT',
						align='R',
					)

			self._space(pdf, W, 6)
			pdf.set_font('helvetica', 'I', 8)
			pdf.cell(
				W,
				6,
				'¡Gracias por su compra!',
				new_x='LMARGIN',
				new_y='NEXT',
				align='C',
			)

			filepath = os.path.join(
				self.receipts_dir, f'tenant_{safe_tenant_id}_ticket_{safe_sale_id}.pdf'
			)
			pdf.output(filepath)
			self.print_receipt(filepath)
			return True, filepath

		except Exception as e:
			logger.error(
				'Error generando PDF del ticket %s: %s', sale_id, e, exc_info=True
			)
			return False, 'Error interno al generar el recibo.'

	def print_receipt(self, filepath: str) -> bool:
		"""Abre el visor de sistema para impresión genérica."""
		try:
			if not os.path.exists(filepath):
				logger.error('Archivo no encontrado para imprimir: %s', filepath)
				return False

			abs_path = os.path.abspath(filepath)
			allowed_dir = os.path.abspath(self.receipts_dir)
			if (
				not abs_path.startswith(allowed_dir + os.sep)
				and abs_path != allowed_dir
			):
				logger.error(
					'Acceso denegado fuera del directorio de recibos: %s', filepath
				)
				return False

			os_name = platform.system()
			if os_name == 'Windows':
				os.startfile(abs_path, 'open')
			elif os_name == 'Darwin':
				result = subprocess.run(['open', abs_path], capture_output=True)
				if result.returncode != 0:
					logger.warning('open retornó código %s', result.returncode)
					return False
			else:
				result = subprocess.run(['xdg-open', abs_path], capture_output=True)
				if result.returncode != 0:
					logger.warning('xdg-open retornó código %s', result.returncode)
					return False
			return True
		except Exception as e:
			logger.error('Error al abrir el archivo PDF: %s', e, exc_info=True)
			return False

	def reprint_receipt(self, tenant_id: int, sale_id: int) -> Tuple[bool, str]:
		"""Reabre el PDF de un ticket ya generado."""
		try:
			safe_sale_id = str(sale_id)
			safe_tenant_id = str(tenant_id)
		except (ValueError, TypeError):
			return False, 'ID de venta inválido.'

		filepath = os.path.join(
			self.receipts_dir, f'tenant_{safe_tenant_id}_ticket_{safe_sale_id}.pdf'
		)

		if not os.path.exists(filepath):
			return (
				False,
				f'No se encontró el ticket #{safe_sale_id} en disco.\nQuizás fue generado en otra sesión o equipo.',
			)

		ok = self.print_receipt(filepath)
		return (
			(True, filepath) if ok else (False, 'No se pudo abrir el PDF del ticket.')
		)

	def generate_credit_note(
		self,
		tenant_id: int,
		sale_id: int,
		date_str: str,
		items_returned: List[Dict[str, Any]],
		refund_total: float | Decimal,
		customer_name: str,
		cashier_name: str = 'Caja Principal',
		note_type: str = 'Devolución',
		paper_width: int = 80,
	) -> Tuple[bool, str]:
		"""Genera e imprime una nota de crédito en PDF."""
		try:
			try:
				safe_sale_id = str(sale_id)
				safe_tenant_id = str(tenant_id)
			except (ValueError, TypeError):
				logger.error('ID inválido para nota de crédito: %s', sale_id)
				return False, 'ID de venta inválido.'

			item_lines = len(items_returned) if items_returned else 1
			page_height = 70 + (item_lines * 5) + 40

			pdf = FPDF(format=(paper_width, page_height))
			pdf.set_auto_page_break(auto=False, margin=0)
			pdf.add_page()
			pdf.set_margins(left=5, top=6, right=5)

			W, COL_QTY, COL_DESC, COL_TOT = self._get_column_widths(paper_width)
			MAX_DESC_LEN = 24 if paper_width == 80 else 14

			business_name = settings_manager.get('company_name', 'Mi Negocio')
			pdf.set_font('helvetica', 'B', 14)
			pdf.cell(W, 8, business_name, new_x='LMARGIN', new_y='NEXT', align='C')

			pdf.set_font('helvetica', 'B', 10)
			pdf.set_text_color(180, 40, 40)
			pdf.cell(
				W,
				6,
				f'NOTA DE CRÉDITO - {note_type.upper()}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='C',
			)
			pdf.set_text_color(0, 0, 0)

			pdf.set_font('helvetica', '', 8)
			pdf.cell(
				W,
				4,
				f'Ref. Ticket N° {safe_sale_id}   {date_str}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='C',
			)
			pdf.cell(
				W,
				4,
				f'Cajero: {cashier_name[:20]}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='C',
			)

			cust_display = (customer_name or 'Consumidor Final')[: MAX_DESC_LEN + 4]
			pdf.cell(
				W,
				4,
				f'Cliente: {cust_display}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='C',
			)
			self._space(pdf, W, 4)

			pdf.set_font('helvetica', 'B', 8)
			pdf.set_text_color(100, 100, 100)
			pdf.cell(W, 4, 'ÍTEMS DEVUELTOS', new_x='LMARGIN', new_y='NEXT', align='L')
			pdf.set_text_color(0, 0, 0)
			self._space(pdf, W, 1)

			if items_returned:
				for item in items_returned:
					desc = str(item.get('desc', ''))[:MAX_DESC_LEN]
					qty = Decimal(str(item.get('qty', 1)))
					sub = Decimal(str(item.get('subtotal', '0.0')))

					pdf.set_font('helvetica', '', 9)
					if qty % 1 == 0:
						pdf.cell(COL_QTY, 5, f'{int(qty)} x', align='L')
						pdf.cell(COL_DESC, 5, desc, align='L')
						pdf.cell(
							COL_TOT,
							5,
							f'${sub:.2f}',
							new_x='LMARGIN',
							new_y='NEXT',
							align='R',
						)
					else:
						pdf.cell(W, 5, desc, new_x='LMARGIN', new_y='NEXT', align='L')
						price = Decimal(str(item.get('price', 0)))
						pdf.cell(COL_QTY / 2, 5, '', align='L')
						pdf.cell(
							COL_DESC + (COL_QTY / 2),
							5,
							f'{qty:.3f} kg x ${price:.2f}',
							align='L',
						)
						pdf.cell(
							COL_TOT,
							5,
							f'${sub:.2f}',
							new_x='LMARGIN',
							new_y='NEXT',
							align='R',
						)
			else:
				pdf.set_font('helvetica', 'I', 9)
				pdf.cell(
					W,
					5,
					'Ticket completo anulado',
					new_x='LMARGIN',
					new_y='NEXT',
					align='C',
				)

			self._space(pdf, W, 4)
			pdf.set_font('helvetica', 'B', 13)
			refund_dec = Decimal(str(refund_total))
			pdf.cell(COL_QTY + COL_DESC, 8, 'Reembolso', align='R')
			pdf.cell(
				COL_TOT,
				8,
				f'${refund_dec:.2f}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='R',
			)

			self._space(pdf, W, 5)
			pdf.set_font('helvetica', 'I', 8)
			pdf.cell(
				W,
				5,
				'Documento no fiscal - Nota de Crédito',
				new_x='LMARGIN',
				new_y='NEXT',
				align='C',
			)

			note_suffix = note_type[:3].lower()
			filepath = os.path.join(
				self.receipts_dir,
				f'tenant_{safe_tenant_id}_NC_{safe_sale_id}_{note_suffix}.pdf',
			)
			pdf.output(filepath)
			self.print_receipt(filepath)
			return True, filepath

		except Exception as e:
			logger.error(
				'Error generando nota de crédito para ticket %s: %s',
				sale_id,
				e,
				exc_info=True,
			)
			return False, 'Error interno al generar la nota de crédito.'
