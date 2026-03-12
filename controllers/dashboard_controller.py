import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from database.models import Sale, SaleDetail

logger = logging.getLogger(__name__)


class DashboardController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_today_stats(self, tenant_id):
		"""Calcula las ventas del día actual pidiéndole el trabajo directamente a la BD."""
		with self.Session() as session:
			try:
				today = date.today()

				# Dependiendo de tu BD, Sale.date puede ser DateTime o Date.
				# Esta es una forma segura de buscar "todo lo de hoy" si es DateTime
				start_of_day = datetime.combine(today, datetime.min.time())
				end_of_day = datetime.combine(today, datetime.max.time())

				result = (
					session.query(
						func.coalesce(func.sum(Sale.total_amount), 0.0),
						func.coalesce(func.sum(Sale.profit), 0.0),
						func.count(Sale.id),
					)
					.filter(
						Sale.tenant_id == tenant_id,
						Sale.date >= start_of_day,
						Sale.date <= end_of_day,
					)
					.first()
				)

				# Desempaquetamos la tupla (revenue, profit, count)
				if result:
					# func.sum devuelve Decimal o Float, nos aseguramos que sean float nativos
					return float(result[0]), float(result[1]), int(result[2])

				return 0.0, 0.0, 0

			except Exception as e:
				logger.error(f'Error al cargar estadísticas de hoy: {e}', exc_info=True)
				return 0.0, 0.0, 0

	def get_weekly_sales(self, tenant_id):
		"""Prepara los datos del gráfico de la última semana (7 días)."""
		with self.Session() as session:
			try:
				today = date.today()
				# Hace 6 días + el día de hoy = 7 días
				start_date = datetime.combine(
					today - timedelta(days=6), datetime.min.time()
				)

				daily_totals = {}
				for i in range(6, -1, -1):
					day = today - timedelta(days=i)
					daily_totals[day.strftime('%d/%m')] = 0.0

				# Solo pedimos a la BD las ventas de la última semana
				recent_sales = (
					session.query(Sale.date, Sale.total_amount)
					.filter(Sale.tenant_id == tenant_id, Sale.date >= start_date)
					.all()
				)

				# Mapeamos los resultados a nuestro diccionario base
				for sale in recent_sales:
					# Asumimos que sale.date puede ser datetime, sacamos la fecha plana
					sale_date = (
						sale.date.date()
						if isinstance(sale.date, datetime)
						else sale.date
					)
					day_str = sale_date.strftime('%d/%m')

					if day_str in daily_totals:
						# Sumamos el float para asegurar compatibilidad
						daily_totals[day_str] += float(sale.total_amount or 0.0)

				return list(daily_totals.keys()), list(daily_totals.values())

			except Exception as e:
				logger.error(f'Error al generar gráfico semanal: {e}', exc_info=True)
				return [], []

	def get_top_products(self, tenant_id, limit=5):
		"""Obtiene los productos más vendidos. La lógica SQL aquí ya era excelente."""
		with self.Session() as session:
			try:
				top_items = (
					session.query(
						SaleDetail.description,
						func.sum(SaleDetail.quantity).label('total_qty'),
					)
					.join(Sale)
					.filter(Sale.tenant_id == tenant_id)
					.group_by(SaleDetail.description)
					.order_by(func.sum(SaleDetail.quantity).desc())
					.limit(limit)
					.all()
				)

				return [
					{'description': item[0], 'quantity': float(item[1])}
					for item in top_items
				]
			except Exception as e:
				logger.error(f'Error al obtener top productos: {e}', exc_info=True)
				return []
