"""
controllers/quotation_controller.py
====================================
Gestión de cotizaciones / presupuestos.
Incluye CRUD, generación de PDF, conversión a venta y duplicado.
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

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────
def _to_dec(value, default=Decimal('0')) -> Decimal:
	try:
		if isinstance(value, str):
			value = value.replace(',', '.')
		return Decimal(str(value))
	except Exception:
		return default


# ─────────────────────────────────────────────────────────────────────────────
# Controller
# ─────────────────────────────────────────────────────────────────────────────


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
		'enviada': '#2563eb',
		'aceptada': '#16a34a',
		'rechazada': '#dc2626',
		'vencida': '#d97706',
	}

	def __init__(self, db_engine):
		super().__init__(db_engine)
		self._pdf_dir = os.path.join(tempfile.gettempdir(), 'MiERP_Cotizaciones')
		os.makedirs(self._pdf_dir, exist_ok=True)

	# ── Helpers internos ──────────────────────────────────────────────────────

	def _next_number(self, session: Session, tenant_id: int) -> str:
		last = (
			session.query(Quotation)
			.filter_by(tenant_id=tenant_id)
			.order_by(Quotation.id.desc())
			.first()
		)
		n = 1
		if last:
			try:
				n = int(last.number.split('-')[-1]) + 1
			except Exception:
				n = last.id + 1
		return f'COT-{n:04d}'

	def _row_to_dict(self, q: Quotation) -> dict:
		cname = q.customer.name if q.customer else ''
		uname = q.user.username if q.user else ''
		items = []
		for it in q.items:
			items.append(
				{
					'id': it.id,
					'description': it.description,
					'quantity': float(it.quantity),
					'unit_price': float(it.unit_price),
					'subtotal': float(it.subtotal),
					'variant_id': it.variant_id,
				}
			)
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

	# ── CRUD ──────────────────────────────────────────────────────────────────

	def list_quotations(
		self, tenant_id: int, status: str = None, limit: int = 100
	) -> list[dict]:
		"""MEJORA 1: Implementa límite para no sobrecargar memoria con el tiempo."""
		with self._Session() as s:
			q = s.query(Quotation).filter_by(tenant_id=tenant_id)
			if status and status != 'todas':
				q = q.filter_by(status=status)
			rows = q.order_by(Quotation.date.desc()).limit(limit).all()
			return [self._row_to_dict(r) for r in rows]

	def get_quotation(self, quotation_id: int) -> dict | None:
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
		with self._Session() as s:
			try:
				number = self._next_number(s, tenant_id)
				discount = _to_dec(discount_amount)

				subtotal = sum(_to_dec(it.get('subtotal', 0)) for it in items)
				total = (subtotal - discount).quantize(Decimal('0.01'), ROUND_HALF_UP)
				if total < 0:
					total = Decimal('0')

				valid_until = None
				if valid_days and valid_days > 0:
					valid_until = (
						datetime.utcnow() + timedelta(days=valid_days)
					).date()

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
				s.rollback()  # MEJORA 3: Rollback explícito
				logger.error(f'Error creando cotización: {e}', exc_info=True)
				return False, str(e)

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
		with self._Session() as s:
			try:
				q = s.get(Quotation, quotation_id)
				if not q:
					return False, 'Cotización no encontrada.'

				discount = _to_dec(discount_amount)
				subtotal = sum(_to_dec(it.get('subtotal', 0)) for it in items)
				total = (subtotal - discount).quantize(Decimal('0.01'), ROUND_HALF_UP)
				if total < 0:
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
					f'Error actualizando cotización {quotation_id}: {e}', exc_info=True
				)
				return False, str(e)

	def set_status(self, quotation_id: int, new_status: str) -> tuple[bool, str]:
		valid = set(self.STATUS_LABELS.keys())
		if new_status not in valid:
			return False, f'Estado inválido: {new_status}'

		with self._Session() as s:
			try:
				q = s.get(Quotation, quotation_id)
				if not q:
					return False, 'Cotización no encontrada.'
				q.status = new_status
				s.commit()
				return True, new_status
			except Exception as e:
				s.rollback()
				logger.error(f'Error cambiando estado: {e}', exc_info=True)
				return False, str(e)

	def delete_quotation(self, quotation_id: int) -> tuple[bool, str]:
		with self._Session() as s:
			try:
				q = s.get(Quotation, quotation_id)
				if not q:
					return False, 'Cotización no encontrada.'
				s.delete(q)
				s.commit()
				return True, 'Eliminada.'
			except Exception as e:
				s.rollback()
				logger.error(
					f'Error eliminando cotización {quotation_id}: {e}', exc_info=True
				)
				return False, str(e)

	def duplicate_quotation(
		self, quotation_id: int, user_id: int
	) -> tuple[bool, str | dict]:
		with self._Session() as s:
			try:
				orig = s.get(Quotation, quotation_id)
				if not orig:
					return False, 'Cotización no encontrada.'

				number = self._next_number(s, orig.tenant_id)
				days_valid = (
					(orig.valid_until - datetime.utcnow().date()).days
					if orig.valid_until
					else 15
				)

				new_q = Quotation(
					number=number,
					tenant_id=orig.tenant_id,
					user_id=user_id,
					customer_id=orig.customer_id,
					valid_until=(
						(datetime.utcnow() + timedelta(days=max(days_valid, 15))).date()
						if orig.valid_until
						else None
					),
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
					f'Error duplicando cotización {quotation_id}: {e}', exc_info=True
				)
				return False, str(e)

	def convert_to_sale(
		self,
		quotation_id: int,
		user_id: int,
		payment_method: str = 'efectivo',
		warehouse_id: int = None,
	) -> tuple[bool, str]:
		with self._Session() as s:
			try:
				q = s.get(Quotation, quotation_id)
				if not q:
					return False, 'Cotización no encontrada.'
				if q.status == 'rechazada':
					return False, 'No se puede convertir una cotización rechazada.'

				profit = q.total_amount

				sale = Sale(
					tenant_id=q.tenant_id,
					user_id=user_id,
					customer_id=q.customer_id,
					total_amount=q.total_amount,
					discount_amount=q.discount_amount,
					profit=profit,
					payment_method=payment_method,
					status='completada',
				)
				s.add(sale)
				s.flush()

				for it in q.items:
					sd = SaleDetail(
						sale_id=sale.id,
						description=it.description,
						quantity=it.quantity,
						unit_cost=Decimal('0'),
						unit_price=it.unit_price,
						subtotal=it.subtotal,
						variant_id=it.variant_id,
					)
					s.add(sd)

					# MEJORA 4: Permite que el stock quede en negativo si hay descuadre
					if it.variant_id and warehouse_id:
						stock_row = (
							s.query(Stock)
							.filter_by(
								variant_id=it.variant_id, warehouse_id=warehouse_id
							)
							.first()
						)
						if stock_row:
							stock_row.quantity -= it.quantity

				cash_session = (
					s.query(CashSession)
					.filter_by(tenant_id=q.tenant_id, is_open=True)
					.first()
				)
				if cash_session and q.total_amount > 0:
					s.add(
						CashMovement(
							session_id=cash_session.id,
							movement_type='venta',
							amount=q.total_amount,
							description=f'Ticket #{sale.id} (desde {q.number})',
						)
					)

				q.status = 'aceptada'
				s.commit()
				return True, str(sale.id)
			except Exception as e:
				s.rollback()
				logger.error(
					f'Error convirtiendo cotización {quotation_id}: {e}', exc_info=True
				)
				return False, str(e)

	# ── Catálogo de artículos para autocompletar ──────────────────────────────

	def search_variants(self, tenant_id: int, query: str) -> list[dict]:
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
				logger.error(f'Error buscando variantes: {e}', exc_info=True)
				return []

	def generate_pdf(self, quotation_id: int) -> tuple[bool, str]:
		try:
			data = self.get_quotation(quotation_id)
			if not data:
				return False, 'Cotización no encontrada.'

			pdf_service = QuotationPDF(data=data, output_dir=self._pdf_dir)
			return pdf_service.generate()

		except Exception as e:
			logger.error(
				f'Error preparando PDF cotización {quotation_id}: {e}', exc_info=True
			)
			return False, str(e)
