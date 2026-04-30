import logging
import os
import platform
import subprocess
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
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

	def _draw_separator(
		self, pdf: FPDF, paper_width: int, W: int, style: str = 'solid'
	) -> None:
		"""Dibuja una línea separadora horizontal."""
		self._space(pdf, W, 2)
		y = pdf.get_y()
		if style == 'dashed':
			pdf.set_font('helvetica', '', 8)
			pdf.set_text_color(150, 150, 150)
			pdf.cell(W, 2, '-' * int(W / 1.5), new_x='LMARGIN', new_y='NEXT', align='C')
			pdf.set_text_color(0, 0, 0)
		else:
			pdf.set_draw_color(180, 180, 180)
			pdf.line(5, y, paper_width - 5, y)
			self._space(pdf, W, 2)

	def _extract_item_data(
		self, item: Dict[str, Any]
	) -> Tuple[str, Decimal, Decimal, Decimal]:
		"""
		Extrae la información de un ítem de forma segura soportando múltiples
		posibles llaves en el diccionario (qty vs quantity vs qty_to_return).
		"""
		desc = str(item.get('desc', item.get('description', '')))

		try:
			qty_val = item.get(
				'qty', item.get('qty_to_return', item.get('quantity', 1))
			)
			qty = Decimal(str(qty_val))
		except (ValueError, InvalidOperation, TypeError):
			qty = Decimal('1')

		try:
			price_val = item.get('price', item.get('unit_price', 0))
			price = Decimal(str(price_val))
		except (ValueError, InvalidOperation, TypeError):
			price = Decimal('0')

		try:
			sub_val = item.get('subtotal', item.get('refund_subtotal', 0))
			sub = Decimal(str(sub_val))
		except (ValueError, InvalidOperation, TypeError):
			sub = Decimal('0')

		return desc, qty, price, sub

	def generate_pdf(
		self,
		tenant_id: int,
		sale_id: Any,
		date_str: str,
		items_list: List[Dict[str, Any]],
		total: float | Decimal,
		customer_name: Optional[str],
		cashier_name: str = 'Caja Principal',
		discount_amount: float | Decimal = 0,
		payment_method: Optional[str] = None,
		payment_method_2: Optional[str] = None,
		amount_method_2: Optional[float | Decimal] = None,
		paid_amount: Optional[float | Decimal] = None,
		change_amount: Optional[float | Decimal] = None,
		paper_width: int = 80,
	) -> Tuple[bool, str]:
		"""Genera el PDF del ticket estándar con soporte UUID y diseño profesional."""
		try:
			try:
				safe_sale_id = str(sale_id)
				safe_tenant_id = str(tenant_id)
			except (ValueError, TypeError):
				logger.error('ID de venta inválido: %s', sale_id)
				return False, 'ID de venta inválido.'

			display_sale_id = safe_sale_id
			is_uuid = len(safe_sale_id) > 15
			if is_uuid:
				display_sale_id = safe_sale_id.split('-')[0].upper()

			items_list = items_list or []
			discount_dec = Decimal(str(discount_amount or 0))
			has_discount = discount_dec > 0

			subtotal_sum = sum(self._extract_item_data(i)[3] for i in items_list)

			item_discounts = {}
			if has_discount and subtotal_sum > 0:
				distributed = Decimal('0')
				items_indexed = list(enumerate(items_list))
				for idx, item in items_indexed[:-1]:
					sub = self._extract_item_data(item)[3]
					d = (discount_dec * sub / subtotal_sum).quantize(
						Decimal('0.01'), rounding=ROUND_HALF_UP
					)
					item_discounts[idx] = d
					distributed += d
				if items_indexed:
					last_idx = items_indexed[-1][0]
					item_discounts[last_idx] = discount_dec - distributed

			item_lines = sum(
				1 if self._extract_item_data(i)[1] % 1 == 0 else 2 for i in items_list
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

			uuid_footer_height = 10 if is_uuid else 0
			page_height = (
				100
				+ (item_lines * 6)
				+ (disc_section * 5)
				+ (pay_lines * 6)
				+ uuid_footer_height
			)

			pdf = FPDF(format=(paper_width, page_height))
			pdf.set_auto_page_break(auto=False, margin=0)
			pdf.add_page()
			pdf.set_margins(left=5, top=6, right=5)

			W, COL_QTY, COL_DESC, COL_TOT = self._get_column_widths(paper_width)
			MAX_DESC_LEN = 24 if paper_width == 80 else 14

			# ==========================================
			# 1. ENCABEZADO COMERCIAL
			# ==========================================
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

			self._draw_separator(pdf, paper_width, W, 'solid')

			# ==========================================
			# 2. METADATOS (Diseño apilado anticolisiones)
			# ==========================================
			pdf.set_font('helvetica', '', 8)
			pdf.cell(
				W,
				4,
				f'Ticket N°: {display_sale_id}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='L',
			)
			pdf.cell(
				W, 4, f'Fecha: {date_str}', new_x='LMARGIN', new_y='NEXT', align='L'
			)

			safe_customer = (customer_name or 'Consumidor Final')[: MAX_DESC_LEN + 4]
			pdf.cell(
				W,
				4,
				f'Cliente: {safe_customer}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='L',
			)
			pdf.cell(
				W,
				4,
				f'Cajero: {cashier_name[:20]}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='L',
			)

			self._draw_separator(pdf, paper_width, W, 'solid')

			# ==========================================
			# 3. LISTA DE ÍTEMS
			# ==========================================
			pdf.set_font('helvetica', 'B', 7)
			pdf.set_text_color(100, 100, 100)
			pdf.cell(COL_QTY, 4, 'CANT', align='L')
			pdf.cell(COL_DESC, 4, 'DESCRIPCIÓN', align='L')
			pdf.cell(COL_TOT, 4, 'TOTAL', new_x='LMARGIN', new_y='NEXT', align='R')
			pdf.set_text_color(0, 0, 0)

			self._draw_separator(pdf, paper_width, W, 'dashed')

			for item in items_list:
				desc_raw, qty, price, sub = self._extract_item_data(item)
				desc = desc_raw[:MAX_DESC_LEN]

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
					pdf.set_font('helvetica', 'I', 8)
					pdf.set_text_color(100, 100, 100)
					pdf.cell(COL_QTY / 2, 5, '', align='L')
					pdf.cell(
						COL_DESC + (COL_QTY / 2),
						5,
						f'{qty:.3f} x ${price:.2f}',
						align='L',
					)
					pdf.set_font('helvetica', '', 9)
					pdf.set_text_color(0, 0, 0)
					pdf.cell(
						COL_TOT,
						5,
						f'${sub:.2f}',
						new_x='LMARGIN',
						new_y='NEXT',
						align='R',
					)

			self._draw_separator(pdf, paper_width, W, 'solid')

			# ==========================================
			# 4. TOTALES Y PAGOS
			# ==========================================
			pdf.set_font('helvetica', '', 9)
			pdf.cell(COL_QTY + COL_DESC, 5, 'Subtotal:', align='R')
			pdf.cell(
				COL_TOT,
				5,
				f'${subtotal_sum:.2f}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='R',
			)

			if has_discount:
				self._space(pdf, W, 2)
				pdf.set_font('helvetica', 'BU', 9)
				pdf.set_text_color(180, 100, 0)
				pdf.cell(
					W,
					6,
					'Descuentos Aplicados',
					new_x='LMARGIN',
					new_y='NEXT',
					align='L',
				)
				pdf.set_text_color(0, 0, 0)

				for idx, item in enumerate(items_list):
					d = item_discounts.get(idx, Decimal('0'))
					if d > 0:
						desc_raw, qty, _, _ = self._extract_item_data(item)
						desc = desc_raw[:MAX_DESC_LEN]

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
				self._space(pdf, W, 2)

			self._space(pdf, W, 2)
			pdf.set_font('helvetica', 'B', 14)
			total_dec = Decimal(str(total))
			pdf.cell(COL_QTY + COL_DESC, 8, 'TOTAL:', align='R')
			pdf.cell(
				COL_TOT,
				8,
				f'${total_dec:.2f}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='R',
			)

			if payment_method:
				self._draw_separator(pdf, paper_width, W, 'dashed')
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

			# ==========================================
			# 5. PIE DE PÁGINA Y AUDITORÍA UUID
			# ==========================================
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

			if is_uuid:
				self._space(pdf, W, 2)
				pdf.set_font('helvetica', '', 5)
				pdf.set_text_color(150, 150, 150)
				pdf.cell(
					W,
					3,
					f'UUID: {safe_sale_id}',
					new_x='LMARGIN',
					new_y='NEXT',
					align='C',
				)

			# OJO: Se guarda el archivo con el safe_sale_id (UUID completo)
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

	def reprint_receipt(self, tenant_id: int, sale_id: Any) -> Tuple[bool, str]:
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
			# Try falling back to truncated ID just in case an older version saved it like that
			display_sale_id = safe_sale_id.split('-')[0].upper()
			fallback_path = os.path.join(
				self.receipts_dir,
				f'tenant_{safe_tenant_id}_ticket_{display_sale_id}.pdf',
			)
			if os.path.exists(fallback_path):
				filepath = fallback_path
			else:
				return (
					False,
					'No se encontró el ticket.\nQuizás fue generado en otra sesión o equipo.',
				)

		ok = self.print_receipt(filepath)
		return (
			(True, filepath) if ok else (False, 'No se pudo abrir el PDF del ticket.')
		)

	def generate_credit_note(
		self,
		tenant_id: int,
		sale_id: Any,
		date_str: str,
		items_returned: Optional[List[Dict[str, Any]]],
		refund_total: float | Decimal,
		customer_name: Optional[str],
		cashier_name: str = 'Caja Principal',
		note_type: str = 'Devolución',
		paper_width: int = 80,
	) -> Tuple[bool, str]:
		"""Genera e imprime una nota de crédito en PDF con diseño profesional y soporte UUID."""
		try:
			try:
				safe_sale_id = str(sale_id)
				safe_tenant_id = str(tenant_id)
			except (ValueError, TypeError):
				logger.error('ID inválido para nota de crédito: %s', sale_id)
				return False, 'ID de venta inválido.'

			# TOLERANCIA UUID
			display_sale_id = safe_sale_id
			is_uuid = len(safe_sale_id) > 15
			if is_uuid:
				display_sale_id = safe_sale_id.split('-')[0].upper()

			items_returned = items_returned or []

			item_lines = 0
			if items_returned:
				item_lines = sum(
					1 if self._extract_item_data(i)[1] % 1 == 0 else 2
					for i in items_returned
				)
			else:
				item_lines = 1

			uuid_footer_height = 10 if is_uuid else 0
			page_height = 95 + (item_lines * 6) + 40 + uuid_footer_height

			pdf = FPDF(format=(paper_width, page_height))
			pdf.set_auto_page_break(auto=False, margin=0)
			pdf.add_page()
			pdf.set_margins(left=5, top=6, right=5)

			W, COL_QTY, COL_DESC, COL_TOT = self._get_column_widths(paper_width)
			MAX_DESC_LEN = 24 if paper_width == 80 else 14

			# ==========================================
			# 1. ENCABEZADO Y TÍTULO
			# ==========================================
			business_name = settings_manager.get('company_name', 'Mi Negocio')
			pdf.set_font('helvetica', 'B', 14)
			pdf.cell(W, 8, business_name, new_x='LMARGIN', new_y='NEXT', align='C')

			self._space(pdf, W, 2)

			pdf.set_font('helvetica', 'B', 10)
			pdf.set_text_color(255, 255, 255)
			pdf.set_fill_color(200, 60, 60)
			pdf.cell(
				W,
				7,
				f'NOTA DE CRÉDITO - {note_type.upper()}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='C',
				fill=True,
			)
			pdf.set_text_color(0, 0, 0)
			self._space(pdf, W, 3)

			# ==========================================
			# 2. METADATOS APILADOS
			# ==========================================
			pdf.set_font('helvetica', '', 8)
			pdf.cell(
				W,
				4,
				f'Ref. Ticket: #{display_sale_id}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='L',
			)
			pdf.cell(
				W, 4, f'Fecha: {date_str}', new_x='LMARGIN', new_y='NEXT', align='L'
			)

			cust_display = (customer_name or 'Consumidor Final')[: MAX_DESC_LEN + 4]
			pdf.cell(
				W,
				4,
				f'Cliente: {cust_display}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='L',
			)
			pdf.cell(
				W,
				4,
				f'Cajero: {cashier_name[:20]}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='L',
			)

			self._draw_separator(pdf, paper_width, W, 'solid')

			# ==========================================
			# 3. CUERPO DE ÍTEMS DEVUELTOS
			# ==========================================
			pdf.set_font('helvetica', 'B', 7)
			pdf.set_text_color(100, 100, 100)
			pdf.cell(COL_QTY, 4, 'CANT', align='L')
			pdf.cell(COL_DESC, 4, 'DESCRIPCIÓN', align='L')
			pdf.cell(COL_TOT, 4, 'TOTAL', new_x='LMARGIN', new_y='NEXT', align='R')
			pdf.set_text_color(0, 0, 0)

			self._draw_separator(pdf, paper_width, W, 'dashed')

			if items_returned:
				for item in items_returned:
					desc_raw, qty, price, sub = self._extract_item_data(item)
					desc = desc_raw[:MAX_DESC_LEN]

					pdf.set_font('helvetica', '', 9)
					if qty % 1 == 0:
						pdf.cell(COL_QTY, 5, f'{int(qty)}', align='L')
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

						pdf.set_font('helvetica', 'I', 8)
						pdf.set_text_color(100, 100, 100)
						pdf.cell(COL_QTY / 2, 5, '', align='L')
						pdf.cell(
							COL_DESC + (COL_QTY / 2),
							5,
							f'{qty:.3f} x ${price:.2f}',
							align='L',
						)

						pdf.set_font('helvetica', '', 9)
						pdf.set_text_color(0, 0, 0)
						pdf.cell(
							COL_TOT,
							5,
							f'${sub:.2f}',
							new_x='LMARGIN',
							new_y='NEXT',
							align='R',
						)
			else:
				self._space(pdf, W, 2)
				pdf.set_font('helvetica', 'I', 9)
				pdf.set_text_color(100, 100, 100)
				pdf.cell(
					W,
					5,
					'Ticket completo anulado',
					new_x='LMARGIN',
					new_y='NEXT',
					align='C',
				)
				pdf.set_text_color(0, 0, 0)

			self._draw_separator(pdf, paper_width, W, 'solid')

			# ==========================================
			# 4. ZONA DE TOTALES
			# ==========================================
			self._space(pdf, W, 1)
			pdf.set_font('helvetica', 'B', 10)
			refund_dec = Decimal(str(refund_total))

			pdf.cell(COL_QTY + COL_DESC, 8, 'REEMBOLSO:', align='R')
			pdf.set_font('helvetica', 'B', 14)
			pdf.cell(
				COL_TOT,
				8,
				f'${refund_dec:.2f}',
				new_x='LMARGIN',
				new_y='NEXT',
				align='R',
			)

			self._space(pdf, W, 5)

			# ==========================================
			# 5. PIE DE PÁGINA Y UUID
			# ==========================================
			pdf.set_font('helvetica', 'I', 7)
			pdf.set_text_color(120, 120, 120)
			pdf.cell(
				W,
				4,
				'Documento no fiscal - Uso interno',
				new_x='LMARGIN',
				new_y='NEXT',
				align='C',
			)

			if is_uuid:
				self._space(pdf, W, 2)
				pdf.set_font('helvetica', '', 5)
				pdf.set_text_color(150, 150, 150)
				pdf.cell(
					W,
					3,
					f'UUID: {safe_sale_id}',
					new_x='LMARGIN',
					new_y='NEXT',
					align='C',
				)

			note_suffix = note_type[:3].lower()
			# OJO: Guardamos con safe_sale_id (UUID entero) para que el reimpresor lo encuentre
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
