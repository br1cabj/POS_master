"""
controllers/quotation_controller.py
====================================
Gestión de cotizaciones / presupuestos.
Incluye operaciones CRUD, generación de archivos PDF, conversión directa a venta
(impactando caja, stock y costos) y duplicación rápida de documentos.
"""

import logging
import os
import tempfile
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from controllers.base import BaseController
from database.models import (
	Article,
	ArticleVariant,
	CashMovement,
	CashSession,
	Quotation,
	QuotationItem,
	Sale,
	SaleDetail,
	Stock,
)
from utils.quotation_pdf import QuotationPDF
from utils.styles import (
	ACCENT,
	GREEN,
	ORANGE,
	RED,
)

logger = logging.getLogger(__name__)


def _to_dec(value, default=Decimal('0')) -> Decimal:
	"""Convierte de forma segura cualquier valor a un objeto Decimal."""
	try:
		if value is None:
			return default
		str_val = str(value).strip().replace(',', '.')
		return Decimal(str_val)
	except Exception:
		return default


class QuotationController(BaseController):
	STATUS_LABELS = {
		'borrador': 'Borrador',
		'enviada': 'Enviada',
		'aceptada': 'Aceptada',
		'rechazada': 'Rechazada',
		'vencida': 'Vencida',
	}

	STATUS_COLORS = {
		'borrador': '#6b7280',
		'enviada': ACCENT,
		'aceptada': GREEN,
		'rechazada': RED,
		'vencida': ORANGE,
	}

	def __init__(self, db_engine):
		super().__init__(db_engine)
		self._pdf_dir = os.path.join(tempfile.gettempdir(), 'MiERP_Cotizaciones')
		os.makedirs(self._pdf_dir, exist_ok=True)

	def _next_number(self, session: Session, tenant_id: int) -> str:
		"""Genera el próximo número correlativo de cotización para un tenant específico."""
		last = (
			session.query(Quotation)
			.filter_by(tenant_id=tenant_id)
			.order_by(Quotation.number.desc())
			.first()
		)
		n = 1
		if last:
			try:
				n = int(last.number.split('-')[-1]) + 1
			except Exception:
				# Fallback: recorrer todos los números y tomar el máximo sufijo numérico
				all_numbers = [
					row[0]
					for row in session.query(Quotation.number)
					.filter_by(tenant_id=tenant_id)
					.all()
				]
				max_n = 0
				for num in all_numbers:
					try:
						max_n = max(max_n, int(num.split('-')[-1]))
					except Exception:
						pass
				n = max_n + 1
		return f'COT-{n:04d}'

	def _row_to_dict(self, q: Quotation) -> dict:
		"""Serializa un objeto Quotation de SQLAlchemy a un diccionario de Python."""
		cname = q.customer.name if q.customer else ''
		uname = q.user.username if q.user else ''
		items = [
			{
				'id': it.id,
				'description': it.description,
				'quantity': float(it.quantity),
				'unit_price': float(it.unit_price),
				'subtotal': float(it.subtotal),
				'variant_id': it.variant_id,
			}
			for it in q.items
		]
		return {
			'id': q.id,
			'number': q.number,
			'date': q.date.strftime('%d/%m/%Y %H:%M') if q.date else '',
			'valid_until': q.valid_until.strftime('%d/%m/%Y') if q.valid_until else '',
			'valid_until_raw': q.valid_until,
			'status': q.status,
			'status_label': self.STATUS_LABELS.get(q.status, q.status),
			'total_amount': float(q.total_amount),
			'discount_amount': float(q.discount_amount or 0),
			'notes': q.notes or '',
			'customer_id': q.customer_id,
			'customer_name': cname,
			'user_name': uname,
			'items': items,
		}

	def list_quotations(
		self, tenant_id: int, status: str = None, limit: int = 100
	) -> list[dict]:
		"""Obtiene un listado paginado/limitado de cotizaciones asociadas a un tenant."""
		with self._Session() as s:
			q = s.query(Quotation).filter_by(tenant_id=tenant_id)
			if status and status != 'todas':
				q = q.filter_by(status=status)
			rows = q.order_by(Quotation.date.desc()).limit(limit).all()
			return [self._row_to_dict(r) for r in rows]

	def get_quotation(self, quotation_id: int) -> dict | None:
		"""Recupera los datos completos de una cotización específica por su ID."""
		with self._Session() as s:
			q = s.get(Quotation, quotation_id)
			return self._row_to_dict(q) if q else None

	def create_quotation(
		self,
		tenant_id: int,
		user_id: int,
		items: list[dict],
		customer_id: int = None,
		valid_days: int = 15,
		notes: str = '',
		discount_amount: float = 0,
	) -> tuple[bool, str | dict]:
		"""Registra una nueva cotización en la base de datos."""
		with self._Session() as s:
			try:
				number = self._next_number(s, tenant_id)
				discount = _to_dec(discount_amount)

				subtotal = sum(_to_dec(it.get('subtotal', 0)) for it in items)
				total = (subtotal - discount).quantize(Decimal('0.01'), ROUND_HALF_UP)
				if total < Decimal('0'):
					total = Decimal('0')

				valid_until = None
				if valid_days and valid_days > 0:
					valid_until = (datetime.now() + timedelta(days=valid_days)).date()

				q = Quotation(
					number=number,
					tenant_id=tenant_id,
					user_id=user_id,
					customer_id=customer_id or None,
					valid_until=valid_until,
					total_amount=total,
					discount_amount=discount,
					notes=notes,
					status='borrador',
				)
				s.add(q)
				s.flush()

				for it in items:
					qi = QuotationItem(
						quotation_id=q.id,
						description=it.get('description', ''),
						quantity=_to_dec(it.get('quantity', 1)),
						unit_price=_to_dec(it.get('unit_price', 0)),
						subtotal=_to_dec(it.get('subtotal', 0)),
						variant_id=it.get('variant_id') or None,
					)
					s.add(qi)

				s.commit()
				return True, self._row_to_dict(s.get(Quotation, q.id))
			except Exception as e:
				s.rollback()
				logger.error('Error creando cotización: %s', e, exc_info=True)
				return False, 'Error interno al procesar la cotización.'

	def update_quotation(
		self,
		quotation_id: int,
		items: list[dict],
		customer_id: int = None,
		valid_until: date = None,
		notes: str = '',
		discount_amount: float = 0,
		status: str = None,
	) -> tuple[bool, str | dict]:
		"""Modifica una cotización existente y actualiza sus ítems."""
		with self._Session() as s:
			try:
				q = s.get(Quotation, quotation_id)
				if not q:
					return False, 'Cotización no encontrada.'

				discount = _to_dec(discount_amount)
				subtotal = sum(_to_dec(it.get('subtotal', 0)) for it in items)
				total = (subtotal - discount).quantize(Decimal('0.01'), ROUND_HALF_UP)
				if total < Decimal('0'):
					total = Decimal('0')

				q.customer_id = customer_id or None
				q.valid_until = valid_until
				q.notes = notes
				q.discount_amount = discount
				q.total_amount = total
				if status:
					q.status = status

				for old in list(q.items):
					s.delete(old)
				s.flush()

				for it in items:
					qi = QuotationItem(
						quotation_id=q.id,
						description=it.get('description', ''),
						quantity=_to_dec(it.get('quantity', 1)),
						unit_price=_to_dec(it.get('unit_price', 0)),
						subtotal=_to_dec(it.get('subtotal', 0)),
						variant_id=it.get('variant_id') or None,
					)
					s.add(qi)

				s.commit()
				return True, self._row_to_dict(s.get(Quotation, q.id))
			except Exception as e:
				s.rollback()
				logger.error(
					'Error actualizando cotización %s: %s',
					quotation_id,
					e,
					exc_info=True,
				)
				return False, 'Error interno al actualizar la cotización.'

	def set_status(self, quotation_id: int, new_status: str, tenant_id: int = None) -> tuple[bool, str]:
		"""Actualiza el estado (borrador, aceptada, etc.) de una cotización."""
		valid = set(self.STATUS_LABELS.keys())
		if new_status not in valid:
			return False, f'Estado inválido: {new_status}'

		with self._Session() as s:
			try:
				q = s.get(Quotation, quotation_id)
				if not q:
					return False, 'Cotización no encontrada.'
				if tenant_id is not None and q.tenant_id != tenant_id:
					return False, 'Cotización no encontrada.'
				q.status = new_status
				s.commit()
				return True, new_status
			except Exception as e:
				s.rollback()
				logger.error('Error cambiando estado: %s', e, exc_info=True)
				return False, 'Error interno al modificar estado.'

	def delete_quotation(self, quotation_id: int, tenant_id: int = None) -> tuple[bool, str]:
		"""Elimina físicamente una cotización y todos sus ítems asociados."""
		with self._Session() as s:
			try:
				q = s.get(Quotation, quotation_id)
				if not q:
					return False, 'Cotización no encontrada.'
				if tenant_id is not None and q.tenant_id != tenant_id:
					return False, 'Cotización no encontrada.'
				s.delete(q)
				s.commit()
				return True, 'Eliminada correctamente.'
			except Exception as e:
				s.rollback()
				logger.error(
					'Error eliminando cotización %s: %s', quotation_id, e, exc_info=True
				)
				return False, 'Error interno al eliminar la cotización.'

	def duplicate_quotation(
		self, quotation_id: int, user_id: int
	) -> tuple[bool, str | dict]:
		"""Crea una copia idéntica de una cotización existente y la asigna como borrador."""
		with self._Session() as s:
			try:
				orig = s.get(Quotation, quotation_id)
				if not orig:
					return False, 'Cotización original no encontrada.'

				number = self._next_number(s, orig.tenant_id)

				days_valid = 15
				if orig.valid_until:
					# Protección ante diferencias horarias
					diff = (orig.valid_until - datetime.now().date()).days
					days_valid = max(diff, 1)

				new_q = Quotation(
					number=number,
					tenant_id=orig.tenant_id,
					user_id=user_id,
					customer_id=orig.customer_id,
					valid_until=(datetime.now() + timedelta(days=days_valid)).date(),
					total_amount=orig.total_amount,
					discount_amount=orig.discount_amount,
					notes=orig.notes,
					status='borrador',
				)
				s.add(new_q)
				s.flush()

				for it in orig.items:
					s.add(
						QuotationItem(
							quotation_id=new_q.id,
							description=it.description,
							quantity=it.quantity,
							unit_price=it.unit_price,
							subtotal=it.subtotal,
							variant_id=it.variant_id,
						)
					)

				s.commit()
				return True, self._row_to_dict(s.get(Quotation, new_q.id))
			except Exception as e:
				s.rollback()
				logger.error(
					'Error duplicando cotización %s: %s', quotation_id, e, exc_info=True
				)
				return False, 'Error interno al duplicar el documento.'

	def convert_to_sale(
		self,
		quotation_id: int,
		user_id: int,
		payment_method: str = 'efectivo',
		warehouse_id: int = None,
		tenant_id: int = None,
	) -> tuple[bool, str]:
		"""
		Transforma una cotización en una venta firme.
		Descuenta stock, registra la ganancia real basada en el costo,
		e ingresa el movimiento en la caja del usuario especificado.
		Pasar tenant_id activa la verificación de propiedad del documento.
		"""
		with self._Session() as s:
			try:
				q = s.get(Quotation, quotation_id)
				if not q:
					return False, 'Cotización no encontrada.'
				# Verificar que la cotización pertenece al tenant que ejecuta la acción
				if tenant_id is not None and q.tenant_id != tenant_id:
					logger.warning(
						'Intento de convertir cotización %s de tenant ajeno (esperado %s, real %s).',
						quotation_id, tenant_id, q.tenant_id,
					)
					return False, 'Cotización no encontrada.'
				if q.status in ('rechazada', 'aceptada', 'vencida'):
					return (
						False,
						f'No se puede convertir una cotización en estado "{self.STATUS_LABELS.get(q.status, q.status)}".',
					)

				# Calcular el costo real para la rentabilidad de la venta
				total_cost = Decimal('0')
				items_data = []

				for it in q.items:
					unit_cost = Decimal('0')
					if it.variant_id:
						variant = s.get(ArticleVariant, it.variant_id)
						if variant and variant.cost_price:
							unit_cost = variant.cost_price

					line_cost = unit_cost * it.quantity
					total_cost += line_cost

					items_data.append({'ref': it, 'unit_cost': unit_cost})

				real_profit = (q.total_amount - total_cost).quantize(
					Decimal('0.01'), ROUND_HALF_UP
				)

				sale = Sale(
					tenant_id=q.tenant_id,
					user_id=user_id,
					customer_id=q.customer_id,
					total_amount=q.total_amount,
					discount_amount=q.discount_amount,
					profit=real_profit,
					payment_method=payment_method,
					status='completada',
					quotation_number=q.number,
				)
				s.add(sale)
				s.flush()

				for data in items_data:
					it = data['ref']
					sd = SaleDetail(
						sale_id=sale.id,
						description=it.description,
						quantity=it.quantity,
						unit_cost=data['unit_cost'],
						unit_price=it.unit_price,
						subtotal=it.subtotal,
						variant_id=it.variant_id,
					)
					s.add(sd)

					if it.variant_id:
						if not warehouse_id:
							raise ValueError(
								f'Se requiere un depósito para descontar el stock de "{it.description}".'
							)
						stock_row = (
							s.query(Stock)
							.filter_by(
								variant_id=it.variant_id, warehouse_id=warehouse_id
							)
							.with_for_update()
							.first()
						)
						if not stock_row:
							raise ValueError(
								f'No hay stock registrado para "{it.description}" en el depósito seleccionado. '
								'Registra el producto en inventario antes de convertir la cotización.'
							)
						if stock_row.quantity < it.quantity:
							raise ValueError(
								f'Stock insuficiente para "{it.description}": '
								f'disponible {float(stock_row.quantity):.2f}, requerido {float(it.quantity):.2f}.'
							)
						stock_row.quantity -= it.quantity

				# Registro del ingreso en caja, asegurando que sea la del usuario que ejecuta
				cash_session = (
					s.query(CashSession)
					.filter_by(tenant_id=q.tenant_id, user_id=user_id, is_open=True)
					.first()
				)
				if cash_session and q.total_amount > Decimal('0'):
					s.add(
						CashMovement(
							session_id=cash_session.id,
							movement_type='venta',
							amount=q.total_amount,
							description=f'Ticket #{sale.id} (desde COT-{q.number.split("-")[-1]})',
						)
					)

				q.status = 'aceptada'
				s.commit()
				return True, str(sale.id)
			except Exception as e:
				s.rollback()
				logger.error(
					'Error convirtiendo cotización %s a venta: %s',
					quotation_id,
					e,
					exc_info=True,
				)
				return False, 'Error interno durante la conversión.'

	def search_variants(self, tenant_id: int, query: str) -> list[dict]:
		"""Busca variantes de artículos activos por nombre o código de barras."""
		with self._Session() as s:
			try:
				q_str = f'%{query}%'
				rows = (
					s.query(ArticleVariant)
					.join(Article)
					.filter(
						Article.tenant_id == tenant_id,
						Article.is_active,
						ArticleVariant.is_active,
					)
					.filter(
						(Article.name.ilike(q_str))
						| (ArticleVariant.barcode.ilike(q_str))
					)
					.limit(30)
					.all()
				)
				result = []
				for v in rows:
					label = v.article.name
					if v.attribute_1:
						label += f' – {v.attribute_1}'
					if v.attribute_2:
						label += f' / {v.attribute_2}'
					result.append(
						{
							'variant_id': v.id,
							'label': label,
							'selling_price': float(v.selling_price),
							'barcode': v.barcode or '',
						}
					)
				return result
			except Exception as e:
				logger.error(
					'Error buscando variantes en catálogo: %s', e, exc_info=True
				)
				return []

	def generate_pdf(self, quotation_id: int) -> tuple[bool, str]:
		"""Delega la creación del archivo PDF al servicio de renderizado."""
		try:
			data = self.get_quotation(quotation_id)
			if not data:
				return False, 'Cotización no encontrada.'

			pdf_service = QuotationPDF(data=data, output_dir=self._pdf_dir)
			return pdf_service.generate()

		except Exception as e:
			logger.error(
				'Error preparando PDF de cotización %s: %s',
				quotation_id,
				e,
				exc_info=True,
			)
			return False, 'Error interno al generar el documento PDF.'
