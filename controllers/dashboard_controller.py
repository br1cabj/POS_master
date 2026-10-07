import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from controllers.base import BaseController
from database.models import Sale, SaleDetail

logger = logging.getLogger(__name__)


class DashboardDataError(RuntimeError):
	"""Indica que no fue posible calcular datos confiables del panel."""


class DashboardController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	@staticmethod
	def _local_today() -> date:
		"""Usa la fecha local del equipo de forma explícita para las métricas diarias."""
		return datetime.now().astimezone().date()

	def get_today_stats(self, tenant_id):
		"""Retorna (total_ventas, total_ganancia, cantidad_tickets) de ventas completadas del día."""
		with self._Session() as session:
			try:
				today = self._local_today()
				net_total = Sale.total_amount - func.coalesce(Sale.total_returned, 0)
				result = (
					session.query(
						func.coalesce(func.sum(net_total), 0.0),
						func.coalesce(func.sum(Sale.profit), 0.0),
						func.count(Sale.id),
					)
					.filter(
						Sale.tenant_id == tenant_id,
						Sale.date >= datetime.combine(today, datetime.min.time()),
						Sale.date <= datetime.combine(today, datetime.max.time()),
						Sale.status.in_(['completada', 'parcial']),
					)
					.first()
				)
				return (
					(float(result[0]), float(result[1]), int(result[2]))
					if result
					else (0.0, 0.0, 0)
				)
			except (SQLAlchemyError, TypeError, ValueError) as exc:
				logger.error('Error al cargar estadísticas de hoy: %s', exc, exc_info=True)
				raise DashboardDataError('No se pudieron calcular las estadísticas de hoy.') from exc

	def get_weekly_sales(self, tenant_id):
		"""Retorna (etiquetas, valores) con el total de ventas completadas de los últimos 7 días."""
		with self._Session() as session:
			try:
				today = self._local_today()
				daily_totals: dict[str, Decimal] = {
					(today - timedelta(days=i)).strftime('%d/%m'): Decimal('0')
					for i in range(6, -1, -1)
				}

				for sale in (
					session.query(
						Sale.date,
						(Sale.total_amount - func.coalesce(Sale.total_returned, 0)).label(
							'net_total'
						),
					)
					.filter(
						Sale.tenant_id == tenant_id,
						Sale.date
						>= datetime.combine(
							today - timedelta(days=6), datetime.min.time()
						),
						Sale.date < datetime.combine(today + timedelta(days=1), datetime.min.time()),
						Sale.status.in_(['completada', 'parcial']),
					)
					.all()
				):
					if not sale.date:
						continue
					day_str = (
						sale.date.date()
						if isinstance(sale.date, datetime)
						else sale.date
					).strftime('%d/%m')
					if day_str in daily_totals:
						daily_totals[day_str] += Decimal(str(sale.net_total or 0))

				return list(daily_totals.keys()), [
					float(v) for v in daily_totals.values()
				]
			except (SQLAlchemyError, TypeError, ValueError) as exc:
				logger.error('Error al generar gráfico semanal: %s', exc, exc_info=True)
				raise DashboardDataError('No se pudieron calcular las ventas semanales.') from exc

	def get_top_products(self, tenant_id, limit=5):
		"""Retorna los N productos más vendidos netos de devoluciones en el historial."""
		try:
			limit = max(1, min(int(limit), 50))
		except (TypeError, ValueError) as exc:
			raise DashboardDataError('El límite del ranking es inválido.') from exc
		with self._Session() as session:
			try:
				net_qty = SaleDetail.quantity - func.coalesce(
					SaleDetail.returned_quantity, 0
				)
				# Las ventas libres no tienen variant_id: se agrupan por descripción para
				# no mezclarlas bajo una única fila NULL con un nombre arbitrario.
				product_key = func.coalesce(SaleDetail.variant_id, SaleDetail.description)
				return [
					{'description': item[0], 'quantity': float(item[1])}
					for item in (
						session.query(
							func.max(SaleDetail.description).label('description'),
							func.sum(net_qty).label('total_qty'),
						)
						.join(Sale)
						.filter(
							Sale.tenant_id == tenant_id,
							Sale.status.in_(['completada', 'parcial']),
						)
						.group_by(product_key)
						.having(func.sum(net_qty) > 0)
						.order_by(func.sum(net_qty).desc(), func.max(SaleDetail.description).asc())
						.limit(limit)
						.all()
					)
				]
			except (SQLAlchemyError, TypeError, ValueError) as exc:
				logger.error('Error al obtener top productos: %s', exc, exc_info=True)
				raise DashboardDataError('No se pudo calcular el ranking de productos.') from exc
