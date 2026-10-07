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
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import ClassVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from controllers.base import BaseController
from controllers.sales_controller import SalesController
from database.models import (
	Article,
	ArticleVariant,
	CashMovement,
	CashSession,
	ComboItem,
	Customer,
	Quotation,
	QuotationItem,
	Sale,
	SaleDetail,
	Stock,
	StockMovement,
	User,
	Warehouse,
)
from utils.shared import get_or_create_default_warehouse
from utils.quotation_pdf import QuotationPDF
from utils.styles import (
	ACCENT,
	GREEN,
	ORANGE,
	RED,
)

logger = logging.getLogger(__name__)


def _to_dec(value) -> Decimal:
	"""Convierte un valor finito a Decimal; el caller decide cómo informar el error."""
	try:
		if value is None:
			raise ValueError('Valor vacío.')
		str_val = str(value).strip().replace(',', '.')
		parsed = Decimal(str_val)
		if not parsed.is_finite():
			raise ValueError('El valor debe ser finito.')
		return parsed
	except (InvalidOperation, ValueError, TypeError) as exc:
		raise ValueError(f'Número inválido: {value!r}.') from exc


class QuotationController(BaseController):
	STATUS_LABELS: ClassVar[dict[str, str]] = {
		'borrador': 'Borrador',
		'enviada': 'Enviada',
		'aceptada': 'Aceptada',
		'rechazada': 'Rechazada',
		'vencida': 'Vencida',
	}

	STATUS_COLORS: ClassVar[dict[str, str]] = {
		'borrador': '#6b7280',
		'enviada': ACCENT,
		'aceptada': GREEN,
		'rechazada': RED,
		'vencida': ORANGE,
	}
	_ALLOWED_PAYMENTS: ClassVar[set[str]] = {'efectivo', 'transferencia', 'tarjeta', 'fiado'}
	_ALLOWED_STATUS_TRANSITIONS: ClassVar[dict[str, set[str]]] = {
		'borrador': {'enviada', 'rechazada', 'vencida'},
		'enviada': {'rechazada', 'vencida'},
		'rechazada': set(),
		'vencida': set(),
		'aceptada': set(),
	}

	def __init__(self, db_engine):
		super().__init__(db_engine)
		self._pdf_dir = os.path.join(tempfile.gettempdir(), 'CloudPOS_Cotizaciones')
		os.makedirs(self._pdf_dir, exist_ok=True)

	def _next_number(self, session: Session, tenant_id: int) -> str:
		"""Genera el próximo número correlativo de cotización para un tenant específico."""
		all_numbers = [
			row[0]
			for row in session.query(Quotation.number)
			.filter_by(tenant_id=tenant_id)
			.with_for_update()
			.all()
		]
		max_n = 0
		for num in all_numbers:
			suffix = str(num).rpartition('-')[2]
			if suffix.isdigit():
				max_n = max(max_n, int(suffix))
		return f'COT-{max_n + 1:04d}'

	@staticmethod
	def _get_owned(s: Session, quotation_id: str, tenant_id: str) -> Quotation | None:
		return (
			s.query(Quotation)
			.filter(Quotation.id == quotation_id, Quotation.tenant_id == tenant_id)
			.first()
		)

	@staticmethod
	def _is_expired(q: Quotation) -> bool:
		return bool(q.valid_until and q.valid_until < date.today())

	def _expire_if_needed(self, q: Quotation) -> bool:
		if q.status in {'borrador', 'enviada'} and self._is_expired(q):
			q.status = 'vencida'
			return True
		return False

	@staticmethod
	def _validate_user(s: Session, tenant_id: str, user_id: str) -> bool:
		return bool(
			s.query(User.id)
			.filter(
				User.id == user_id,
				User.tenant_id == tenant_id,
				User.is_active.is_(True),
				User.deleted_at.is_(None),
			)
			.first()
		)

	@staticmethod
	def _validate_customer(s: Session, tenant_id: str, customer_id: str | None) -> bool:
		if not customer_id:
			return True
		return bool(
			s.query(Customer.id)
			.filter(
				Customer.id == customer_id,
				Customer.tenant_id == tenant_id,
				Customer.is_active.is_(True),
				Customer.deleted_at.is_(None),
			)
			.first()
		)

	def _normalize_items(self, s: Session, tenant_id: str, items: list[dict]) -> tuple[list[dict], Decimal]:
		if not items:
			raise ValueError('Agregá al menos un ítem a la cotización.')
		if len(items) > 500:
			raise ValueError('Una cotización admite hasta 500 ítems.')
		normalized = []
		for index, item in enumerate(items, start=1):
			description = str(item.get('description') or '').strip()
			if not description:
				raise ValueError(f'El ítem #{index} no tiene descripción.')
			if len(description) > 500:
				raise ValueError(f'La descripción del ítem #{index} es demasiado larga.')
			quantity = _to_dec(item.get('quantity', item.get('qty')))
			unit_price = _to_dec(item.get('unit_price'))
			if quantity <= 0:
				raise ValueError(f'La cantidad del ítem #{index} debe ser mayor a cero.')
			if unit_price <= 0:
				raise ValueError(f'El precio del ítem #{index} debe ser mayor a cero.')
			variant_id = item.get('variant_id') or None
			if variant_id:
				variant = (
					s.query(ArticleVariant.id)
					.join(Article)
					.filter(
						ArticleVariant.id == variant_id,
						Article.tenant_id == tenant_id,
						Article.is_active.is_(True),
						Article.deleted_at.is_(None),
						ArticleVariant.is_active.is_(True),
						ArticleVariant.deleted_at.is_(None),
					)
					.first()
				)
				if not variant:
					raise ValueError(f'El producto del ítem #{index} no está disponible.')
			subtotal = (quantity * unit_price).quantize(Decimal('0.01'), ROUND_HALF_UP)
			normalized.append({
				'description': description,
				'quantity': quantity,
				'unit_price': unit_price,
				'subtotal': subtotal,
				'variant_id': variant_id,
			})
		return normalized, sum((item['subtotal'] for item in normalized), Decimal('0'))

	@staticmethod
	def _validated_discount(value, subtotal: Decimal) -> Decimal:
		discount = _to_dec(value if value not in (None, '') else 0)
		if discount < 0:
			raise ValueError('El descuento no puede ser negativo.')
		if discount > subtotal:
			raise ValueError('El descuento no puede superar el subtotal.')
		return discount.quantize(Decimal('0.01'), ROUND_HALF_UP)

	@staticmethod
	def _load_full(s: Session, quotation_id) -> 'Quotation | None':
		"""Carga una cotización con todas sus relaciones usando joinedload."""
		return (
			s.query(Quotation)
			.options(
				joinedload(Quotation.customer),
				joinedload(Quotation.user),
				joinedload(Quotation.items)
				.joinedload(QuotationItem.variant)
				.joinedload(ArticleVariant.stocks),
			)
			.filter_by(id=quotation_id)
			.first()
		)

	def _row_to_dict(self, q: Quotation) -> dict:
		"""Serializa un objeto Quotation de SQLAlchemy a un diccionario de Python."""
		cname = q.customer.name if q.customer else ''
		uname = q.user.username if q.user else ''
		items = [
			{
				'id': it.id,
				'description': it.description,
				'quantity': float(it.quantity),
				'qty': float(it.quantity),
				'unit_price': float(it.unit_price),
				'subtotal': float(it.subtotal),
				'variant_id': it.variant_id,
				'stock': float(sum(s.quantity for s in it.variant.stocks))
				if it.variant and it.variant.stocks
				else None,
			}
			for it in q.items
		]
		return {
			'id': q.id,
			'number': q.number,
			'date': q.date.strftime('%d/%m/%Y %H:%M') if q.date else '',
			'valid_until': q.valid_until.strftime('%d/%m/%Y') if q.valid_until else '',
			'valid_until_iso': q.valid_until.isoformat() if q.valid_until else '',
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
		self, tenant_id: str, status: str | None = None, limit: int = 100
	) -> list[dict]:
		"""Obtiene un listado paginado/limitado de cotizaciones asociadas a un tenant."""
		with self._Session() as s:
			q = (
				s.query(Quotation)
				.options(
					joinedload(Quotation.customer),
					joinedload(Quotation.user),
					joinedload(Quotation.items)
					.joinedload(QuotationItem.variant)
					.joinedload(ArticleVariant.stocks),
				)
				.filter_by(tenant_id=tenant_id)
			)
			if status and status != 'todas':
				q = q.filter_by(status=status)
			rows = q.order_by(Quotation.date.desc()).limit(min(max(limit, 1), 500)).all()
			if any(self._expire_if_needed(row) for row in rows):
				s.commit()
			return [self._row_to_dict(r) for r in rows]

	def get_quotation(self, quotation_id: str, tenant_id: str) -> dict | None:
		"""Recupera los datos completos de una cotización específica por su ID."""
		with self._Session() as s:
			q = self._load_full(s, quotation_id)
			if not q or q.tenant_id != tenant_id:
				return None
			if self._expire_if_needed(q):
				s.commit()
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
		try:
			valid_days = int(valid_days)
			if not 0 <= valid_days <= 3650:
				return False, 'Los días de validez deben estar entre 0 y 3650.'
		except (TypeError, ValueError):
			return False, 'Los días de validez son inválidos.'
		notes = str(notes or '').strip()
		if len(notes) > 1_000:
			return False, 'Las notas no pueden superar los 1000 caracteres.'
		with self._Session() as s:
			for attempt in range(3):
				try:
					if not self._validate_user(s, tenant_id, user_id):
						return False, 'Usuario no válido para esta empresa.'
					if not self._validate_customer(s, tenant_id, customer_id):
						return False, 'Cliente no válido para esta empresa.'
					normalized_items, subtotal = self._normalize_items(s, tenant_id, items)
					discount = self._validated_discount(discount_amount, subtotal)
					number = self._next_number(s, tenant_id)
					total = (subtotal - discount).quantize(Decimal('0.01'), ROUND_HALF_UP)

					valid_until = None
					if valid_days and valid_days > 0:
						valid_until = (
							datetime.now() + timedelta(days=valid_days)
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

					for it in normalized_items:
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
					return True, self._row_to_dict(self._load_full(s, q.id))
				except ValueError as exc:
					s.rollback()
					return False, str(exc)
				except IntegrityError:
					s.rollback()
					if attempt == 2:
						return (
							False,
							'Error al generar número de cotización. Intente nuevamente.',
						)
					continue
				except Exception as e:
					s.rollback()
					logger.error('Error creando cotización: %s', e, exc_info=True)
					return False, 'Error interno al procesar la cotización.'

	def update_quotation(
		self,
		quotation_id: str,
		tenant_id: str,
		items: list[dict],
		customer_id: str | None = None,
		valid_until: date | None = None,
		notes: str = '',
		discount_amount: float = 0,
		status: str | None = None,
	) -> tuple[bool, str | dict]:
		"""Modifica una cotización existente y actualiza sus ítems."""
		with self._Session() as s:
			try:
				q = self._get_owned(s, quotation_id, tenant_id)
				if not q:
					return False, 'Cotización no encontrada.'
				if self._expire_if_needed(q):
					s.commit()
					return False, 'La cotización venció y ya no puede modificarse.'
				if q.status != 'borrador':
					return False, 'Solo se pueden editar cotizaciones en borrador.'
				if status and status != q.status:
					return False, 'El estado se cambia mediante la acción de estado correspondiente.'
				if valid_until is not None and not isinstance(valid_until, date):
					return False, 'La fecha de validez es inválida.'
				if valid_until and valid_until < date.today():
					return False, 'La fecha de validez no puede estar en el pasado.'
				notes = str(notes or '').strip()
				if len(notes) > 1_000:
					return False, 'Las notas no pueden superar los 1000 caracteres.'
				if not self._validate_customer(s, tenant_id, customer_id):
					return False, 'Cliente no válido para esta empresa.'
				normalized_items, subtotal = self._normalize_items(s, tenant_id, items)
				discount = self._validated_discount(discount_amount, subtotal)
				total = (subtotal - discount).quantize(Decimal('0.01'), ROUND_HALF_UP)

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

				for it in normalized_items:
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
				return True, self._row_to_dict(self._load_full(s, q.id))
			except ValueError as exc:
				s.rollback()
				return False, str(exc)
			except Exception as e:
				s.rollback()
				logger.error(
					'Error actualizando cotización %s: %s',
					quotation_id,
					e,
					exc_info=True,
				)
				return False, 'Error interno al actualizar la cotización.'

	def set_status(
		self, quotation_id: str, new_status: str, tenant_id: str
	) -> tuple[bool, str]:
		"""Actualiza el estado (borrador, aceptada, etc.) de una cotización."""
		valid = set(self.STATUS_LABELS.keys())
		if new_status not in valid:
			return False, f'Estado inválido: {new_status}'

		with self._Session() as s:
			try:
				q = self._get_owned(s, quotation_id, tenant_id)
				if not q:
					return False, 'Cotización no encontrada.'
				if self._expire_if_needed(q):
					s.commit()
					return False, 'La cotización venció y no puede cambiar de estado.'
				if new_status == 'aceptada':
					return False, 'Una cotización se acepta únicamente al convertirla en venta.'
				if new_status not in self._ALLOWED_STATUS_TRANSITIONS.get(q.status, set()):
					return False, 'Transición de estado no permitida.'
				q.status = new_status
				s.commit()
				return True, new_status
			except Exception as e:
				s.rollback()
				logger.error('Error cambiando estado: %s', e, exc_info=True)
				return False, 'Error interno al modificar estado.'

	def delete_quotation(
		self, quotation_id: str, tenant_id: str
	) -> tuple[bool, str]:
		"""Elimina físicamente una cotización y todos sus ítems asociados."""
		with self._Session() as s:
			try:
				q = self._get_owned(s, quotation_id, tenant_id)
				if not q:
					return False, 'Cotización no encontrada.'
				if q.status != 'borrador':
					return False, 'Solo se pueden eliminar cotizaciones en borrador.'
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
		self, quotation_id: str, user_id: str, tenant_id: str
	) -> tuple[bool, str | dict]:
		"""Crea una copia idéntica de una cotización existente y la asigna como borrador."""
		with self._Session() as s:
			try:
				orig = self._get_owned(s, quotation_id, tenant_id)
				if not orig:
					return False, 'Cotización original no encontrada.'
				if not self._validate_user(s, tenant_id, user_id):
					return False, 'Usuario no válido para esta empresa.'

				number = self._next_number(s, orig.tenant_id)

				days_valid = 15
				if orig.valid_until:
					# Protección ante diferencias horarias
					diff = (orig.valid_until - datetime.now().date()).days
					days_valid = diff if diff > 0 else 15

				customer_id = orig.customer_id
				if not self._validate_customer(s, tenant_id, customer_id):
					customer_id = None

				new_q = Quotation(
					number=number,
					tenant_id=orig.tenant_id,
					user_id=user_id,
					customer_id=customer_id,
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
				return True, self._row_to_dict(self._load_full(s, new_q.id))
			except Exception as e:
				s.rollback()
				logger.error(
					'Error duplicando cotización %s: %s', quotation_id, e, exc_info=True
				)
				return False, 'Error interno al duplicar el documento.'

	def convert_to_sale(
		self,
		quotation_id: str,
		user_id: str,
		payment_method: str = 'efectivo',
		warehouse_id: str | None = None,
		tenant_id: str | None = None,
	) -> tuple[bool, str]:
		"""
		Transforma una cotización en una venta firme.
		Descuenta stock, registra la ganancia real basada en el costo,
		e ingresa el movimiento en la caja del usuario especificado.
		Pasar tenant_id activa la verificación de propiedad del documento.
		"""
		with self._Session() as s:
			try:
				if not tenant_id:
					return False, 'Se requiere la empresa para convertir una cotización.'
				q = (
					s.query(Quotation)
					.filter(Quotation.id == quotation_id)
					.with_for_update()
					.first()
				)
				if not q:
					return False, 'Cotización no encontrada.'
				# Verificar que la cotización pertenece al tenant que ejecuta la acción
				if tenant_id is not None and q.tenant_id != tenant_id:
					logger.warning(
						'Intento de convertir cotización %s de tenant ajeno (esperado %s, real %s).',
						quotation_id,
						tenant_id,
						q.tenant_id,
					)
					return False, 'Cotización no encontrada.'
				if self._expire_if_needed(q):
					s.commit()
					return False, 'La cotización está vencida y no puede convertirse.'
				if q.status != 'enviada':
					return (
						False,
						f'No se puede convertir una cotización en estado "{self.STATUS_LABELS.get(q.status, q.status)}". '
						'Solo se pueden convertir cotizaciones enviadas.',
					)
				if q.total_amount is None or Decimal(str(q.total_amount)) <= 0:
					return False, 'El total de la cotización debe ser mayor a cero.'
				if not q.items:
					return False, 'La cotización no tiene ítems para convertir.'
				for item in q.items:
					if (
						not item.description
						or Decimal(str(item.quantity)) <= 0
						or Decimal(str(item.unit_price)) <= 0
						or Decimal(str(item.subtotal)) <= 0
					):
						return False, 'La cotización contiene ítems inválidos y no puede convertirse.'
				expected_total = (
					sum((Decimal(str(item.subtotal)) for item in q.items), Decimal('0'))
					- Decimal(str(q.discount_amount or 0))
				).quantize(Decimal('0.01'), ROUND_HALF_UP)
				quoted_total = Decimal(str(q.total_amount)).quantize(
					Decimal('0.01'), ROUND_HALF_UP
				)
				if expected_total != quoted_total:
					return False, 'La cotización tiene totales inconsistentes y no puede convertirse.'
				if not self._validate_user(s, q.tenant_id, user_id):
					return False, 'Usuario no válido para esta empresa.'
				payment_method = (payment_method or '').lower()
				if payment_method not in self._ALLOWED_PAYMENTS:
					return False, 'Método de pago inválido.'
				if not self._validate_customer(s, q.tenant_id, q.customer_id):
					return False, 'El cliente de la cotización ya no está disponible.'

				# Resolver el inventario como una venta normal: las filas Stock son
				# por lote, por lo que ``first()`` podía descontar un lote arbitrario.
				# La cotización usa el depósito elegido (o el general), pero distribuye
				# el descuento FEFO entre sus lotes.
				stock_items = [it for it in q.items if it.variant_id]
				source_warehouse_id = warehouse_id
				if stock_items and not source_warehouse_id:
					source_warehouse_id = get_or_create_default_warehouse(s, q.tenant_id)
				if stock_items and not (
					s.query(Warehouse.id)
					.filter(
						Warehouse.id == source_warehouse_id,
						Warehouse.tenant_id == q.tenant_id,
						Warehouse.is_active.is_(True),
					)
					.first()
				):
					return False, 'El depósito seleccionado no es válido para esta empresa.'

				variant_ids = [it.variant_id for it in stock_items]
				variants = {
					v.id: v
					for v in s.query(ArticleVariant)
					.join(Article)
					.options(
						joinedload(ArticleVariant.article),
						joinedload(ArticleVariant.ingredients).joinedload(
							ComboItem.ingredient
						),
					)
					.filter(
						ArticleVariant.id.in_(variant_ids),
						Article.tenant_id == q.tenant_id,
						Article.is_active.is_(True),
						Article.deleted_at.is_(None),
						ArticleVariant.is_active.is_(True),
						ArticleVariant.deleted_at.is_(None),
					)
					.all()
				}
				stock_variant_ids = set()
				for it in stock_items:
					variant = variants.get(it.variant_id)
					if not variant:
						raise ValueError(f'Producto no encontrado o no autorizado: {it.description}')
					if variant.is_combo:
						stock_variant_ids.update(ci.ingredient_id for ci in variant.ingredients)
					else:
						stock_variant_ids.add(variant.base_variant_id or variant.id)

				stocks_by_variant = {}
				if stock_variant_ids:
					for row in (
						s.query(Stock)
						.filter(
							Stock.variant_id.in_(stock_variant_ids),
							Stock.warehouse_id == source_warehouse_id,
						)
						.with_for_update()
						.all()
					):
						stocks_by_variant.setdefault(row.variant_id, []).append(row)

				total_cost = Decimal('0')
				items_data = []
				stock_allocations = []
				for it in q.items:
					unit_cost = Decimal('0')
					if it.variant_id:
						variant = variants[it.variant_id]
						if variant.is_combo:
							for component in variant.ingredients:
								if component.ingredient is None:
									raise ValueError(
										f'El combo "{it.description}" contiene un ingrediente eliminado.'
									)
								required = Decimal(str(component.quantity_required)) * Decimal(str(it.quantity))
								allocations = SalesController._take_from_stock_rows(
									stocks_by_variant.get(component.ingredient_id, []), required
								)
								stock_allocations.extend(
									(stock, qty, component.ingredient_id) for stock, qty in allocations
								)
								unit_cost += Decimal(str(component.ingredient.cost_price or 0)) * Decimal(
									str(component.quantity_required)
								)
						else:
							deduct_variant_id = variant.base_variant_id or variant.id
							units = Decimal(str(variant.units_per_pack or 1))
							deduct_qty = Decimal(str(it.quantity)) * units if variant.base_variant_id else Decimal(str(it.quantity))
							allocations = SalesController._take_from_stock_rows(
								stocks_by_variant.get(deduct_variant_id, []), deduct_qty
							)
							stock_allocations.extend(
								(stock, qty, deduct_variant_id) for stock, qty in allocations
							)
							unit_cost = Decimal(str(variant.cost_price or 0))

					total_cost += unit_cost * Decimal(str(it.quantity))
					items_data.append({'ref': it, 'unit_cost': unit_cost})

				real_profit = (q.total_amount - total_cost).quantize(
					Decimal('0.01'), ROUND_HALF_UP
				)
				is_fiado = (payment_method or '').lower() == 'fiado'
				if is_fiado and not q.customer_id:
					raise ValueError('Debes seleccionar un cliente válido para fiar.')
				sale = Sale(
					tenant_id=q.tenant_id,
					user_id=user_id,
					customer_id=q.customer_id,
					total_amount=q.total_amount,
					discount_amount=q.discount_amount,
					profit=real_profit,
					payment_method=(payment_method or 'efectivo').lower(),
					status='pendiente' if is_fiado else 'completada',
					quotation_number=q.number,
				)
				s.add(sale)
				s.flush()

				for data in items_data:
					it = data['ref']
					s.add(
						SaleDetail(
							sale_id=sale.id,
							description=it.description,
							quantity=it.quantity,
							unit_cost=data['unit_cost'],
							unit_price=it.unit_price,
							subtotal=it.subtotal,
							variant_id=it.variant_id,
						)
					)
				for stock, quantity, variant_id in stock_allocations:
					s.add(
						StockMovement(
							movement_type='out',
							quantity=quantity,
							reference=f'Venta Ticket #{sale.id} (desde COT-{q.number.split("-")[-1]})',
							source_warehouse_id=stock.warehouse_id,
							variant_id=variant_id,
							user_id=user_id,
							tenant_id=q.tenant_id,
						)
					)

				# Registro del ingreso en caja o actualización de deuda de cliente
				cash_session = None
				if not is_fiado:
					cash_session = (
						s.query(CashSession)
						.filter_by(tenant_id=q.tenant_id, user_id=user_id, is_open=True)
						.first()
					)
					if not cash_session:
						raise ValueError(
							'Debes abrir la caja antes de convertir una cotización en venta.'
						)

				if is_fiado and q.customer_id:
					customer = (
						s.query(Customer)
						.filter_by(id=q.customer_id)
						.with_for_update()
						.first()
					)
					if customer:
						customer.current_balance = (
							customer.current_balance or Decimal('0')
						) + q.total_amount

				if cash_session and q.total_amount > Decimal('0'):
					s.add(
						CashMovement(
							session_id=cash_session.id,
							movement_type=(
								'venta'
								if (payment_method or '').lower() == 'efectivo'
								else 'venta_digital'
							),
							amount=q.total_amount,
							description=f'Ticket #{sale.id} - Pago: {(payment_method or "efectivo").capitalize()} (desde COT-{q.number.split("-")[-1]})',
						)
					)

				q.status = 'aceptada'
				s.commit()
				return True, str(sale.id)
			except ValueError as ve:
				s.rollback()
				return False, str(ve)
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
						Article.is_active.is_(True),
						Article.deleted_at.is_(None),
						ArticleVariant.is_active.is_(True),
						ArticleVariant.deleted_at.is_(None),
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
					if v.pack_label:
						label += f' — {v.pack_label}'
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

	def get_active_warehouses(self, tenant_id: str) -> list[dict]:
		"""Returns eligible warehouses for quote conversion without leaking tenants."""
		with self._Session() as s:
			return [
				{'id': row.id, 'name': row.name}
				for row in (
					s.query(Warehouse)
					.filter(Warehouse.tenant_id == tenant_id, Warehouse.is_active.is_(True))
					.order_by(Warehouse.name)
					.all()
				)
			]

	def generate_pdf(self, quotation_id: str, tenant_id: str) -> tuple[bool, str]:
		"""Delega la creación del archivo PDF al servicio de renderizado."""
		try:
			data = self.get_quotation(quotation_id, tenant_id)
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
