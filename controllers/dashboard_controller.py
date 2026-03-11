from datetime import date

from sqlalchemy.orm import sessionmaker

from database.models import Sale


class DashboardController:
	def __init__(self, db_engine):
		self.Session = sessionmaker(bind=db_engine)

	def get_today_stats(self, tenant_id):
		"""
		Calcula las estadísticas del día actual:
		Ingresos totales, Ganancia neta y Cantidad de ventas.
		"""
		session = self.Session()
		try:
			today = date.today()
			all_sales = session.query(Sale).filter_by(tenant_id=tenant_id).all()

			# Filtramos solo las ventas cuya fecha coincida con hoy
			today_sales = [sale for sale in all_sales if sale.date.date() == today]

			total_revenue = sum(sale.total_amount for sale in today_sales)
			total_profit = sum(sale.profit for sale in today_sales)
			ticket_count = len(today_sales)

			return total_revenue, total_profit, ticket_count

		except Exception as e:
			print(f'Error al obtener estadísticas: {e}')
			return 0.0, 0.0, 0
		finally:
			session.close()
