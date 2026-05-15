import logging
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func

from controllers.base import BaseController
from database.models import Sale, SaleDetail

logger = logging.getLogger(__name__)


class DashboardController(BaseController):
	def __init__(self, db_engine=None):
		super().__init__(db_engine)

	def get_today_stats(self, tenant_id):
		"""Retorna (total_ventas, total_ganancia, cantidad_tickets) de ventas completadas del día."""
		with self._Session() as session:
			try:
				today = date.today()
				result = (
					session.query(
						func.coalesce(func.sum(Sale.total_amount), 0.0),
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
			except Exception as e:
				logger.error(f'Error al cargar estadísticas de hoy: {e}', exc_info=True)
				return 0.0, 0.0, 0

	def get_weekly_sales(self, tenant_id):
		"""Retorna (etiquetas, valores) con el total de ventas completadas de los últimos 7 días."""
		with self._Session() as session:
			try:
				today = date.today()
				daily_totals: dict[str, Decimal] = {
					(today - timedelta(days=i)).strftime('%d/%m'): Decimal('0')
					for i in range(6, -1, -1)
				}

				for sale in (
					session.query(Sale.date, Sale.total_amount)
					.filter(
						Sale.tenant_id == tenant_id,
						Sale.date
						>= datetime.combine(
							today - timedelta(days=6), datetime.min.time()
						),
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
						daily_totals[day_str] += Decimal(str(sale.total_amount or 0))

				return list(daily_totals.keys()), [float(v) for v in daily_totals.values()]
			except Exception as e:
				logger.error(f'Error al generar gráfico semanal: {e}', exc_info=True)
				return [], []

	def get_top_products(self, tenant_id, limit=5):
		"""Retorna los N productos más vendidos por cantidad en todo el historial."""
		with self._Session() as session:
			try:
				return [
					{'description': item[0], 'quantity': float(item[1])}
					for item in (
						session.query(
							SaleDetail.description,
							func.sum(SaleDetail.quantity).label('total_qty'),
						)
						.join(Sale)
						.filter(
							Sale.tenant_id == tenant_id,
							Sale.status.in_(['completada', 'parcial']),
						)
						.group_by(SaleDetail.variant_id, SaleDetail.description)
						.order_by(func.sum(SaleDetail.quantity).desc())
						.limit(limit)
						.all()
					)
				]
			except Exception as e:
				logger.error(f'Error al obtener top productos: {e}', exc_info=True)
				return []
