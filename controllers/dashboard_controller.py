from datetime import date, timedelta

from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from database.models import Sale, SaleDetail


class DashboardController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_today_stats(self, tenant_id):
		session = self.Session()
		try:
			today = date.today()
			all_sales = session.query(Sale).filter_by(tenant_id=tenant_id).all()
			today_sales = [sale for sale in all_sales if sale.date.date() == today]

			total_revenue = sum(sale.total_amount for sale in today_sales)
			total_profit = sum(sale.profit for sale in today_sales)
			ticket_count = len(today_sales)

			return total_revenue, total_profit, ticket_count
		except Exception as e:
			print(f'Error estadísticas: {e}')
			return 0.0, 0.0, 0
		finally:
			session.close()

	def get_weekly_sales(self, tenant_id):
		session = self.Session()
		try:
			today = date.today()
			daily_totals = {}
			for i in range(6, -1, -1):
				day = today - timedelta(days=i)
				daily_totals[day.strftime('%d/%m')] = 0.0

			all_sales = session.query(Sale).filter_by(tenant_id=tenant_id).all()
			for sale in all_sales:
				sale_date = sale.date.date()
				if 0 <= (today - sale_date).days <= 6:
					day_str = sale_date.strftime('%d/%m')
					if day_str in daily_totals:
						daily_totals[day_str] += sale.total_amount

			return list(daily_totals.keys()), list(daily_totals.values())
		except Exception as e:
			print(f'Error gráfico: {e}')
			return [], []
		finally:
			session.close()

	def get_top_products(self, tenant_id, limit=5):
		"""Obtiene los productos más vendidos históricamente o del mes."""
		session = self.Session()
		try:
			# Sumamos las cantidades vendidas agrupando por el nombre del producto
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

			# Retorna una lista de tuplas, ej: [('Coca Cola', 25), ('Galletas', 10)]
			return top_items
		except Exception as e:
			print(f'Error al obtener top productos: {e}')
			return []
		finally:
			session.close()
