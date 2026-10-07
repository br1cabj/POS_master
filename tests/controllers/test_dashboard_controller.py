from datetime import datetime, timedelta, timezone
from decimal import Decimal

from controllers.dashboard_controller import DashboardController
from database.models import Sale, SaleDetail, Tenant, User


def _seed(session):
	tenant = Tenant(id='tenant-dashboard', name='Empresa dashboard')
	user = User(
		id='user-dashboard',
		tenant_id=tenant.id,
		username='dashboard',
		password_hash='not-used-in-test',
	)
	session.add_all([tenant, user])
	session.commit()
	return tenant, user


def test_dashboard_uses_net_sales_and_net_product_quantities(test_db_session):
	tenant, user = _seed(test_db_session)
	now = datetime.now(timezone.utc).astimezone().replace(tzinfo=None)
	partially_returned = Sale(
		id='sale-dashboard-returned',
		tenant_id=tenant.id,
		user_id=user.id,
		date=now,
		total_amount=Decimal('100'),
		total_returned=Decimal('20'),
		profit=Decimal('25'),
		payment_method='efectivo',
		status='parcial',
	)
	completed = Sale(
		id='sale-dashboard-completed',
		tenant_id=tenant.id,
		user_id=user.id,
		date=now,
		total_amount=Decimal('50'),
		total_returned=Decimal('0'),
		profit=Decimal('15'),
		payment_method='efectivo',
		status='completada',
	)
	test_db_session.add_all([
		partially_returned,
		completed,
		SaleDetail(
			sale_id=partially_returned.id,
			description='Servicio A',
			quantity=Decimal('5'),
			returned_quantity=Decimal('2'),
			unit_cost=Decimal('5'),
			unit_price=Decimal('20'),
			subtotal=Decimal('100'),
		),
		SaleDetail(
			sale_id=completed.id,
			description='Servicio B',
			quantity=Decimal('3'),
			returned_quantity=Decimal('0'),
			unit_cost=Decimal('5'),
			unit_price=Decimal('16.67'),
			subtotal=Decimal('50'),
		),
		SaleDetail(
			sale_id=completed.id,
			description='Devuelto por completo',
			quantity=Decimal('2'),
			returned_quantity=Decimal('2'),
			unit_cost=Decimal('5'),
			unit_price=Decimal('10'),
			subtotal=Decimal('20'),
		),
	])
	test_db_session.commit()

	controller = DashboardController(test_db_session.bind)
	revenue, profit, tickets = controller.get_today_stats(tenant.id)
	dates, totals = controller.get_weekly_sales(tenant.id)
	top_products = controller.get_top_products(tenant.id)

	assert (revenue, profit, tickets) == (130.0, 40.0, 2)
	assert totals[-1] == 130.0
	assert dates
	assert top_products == [
		{'description': 'Servicio A', 'quantity': 3.0},
		{'description': 'Servicio B', 'quantity': 3.0},
	]


def test_dashboard_excludes_future_sales_from_weekly_chart(test_db_session):
	tenant, user = _seed(test_db_session)
	test_db_session.add(
		Sale(
			tenant_id=tenant.id,
			user_id=user.id,
			date=datetime.now(timezone.utc).astimezone().replace(tzinfo=None)
			+ timedelta(days=1),
			total_amount=Decimal('99'),
			profit=Decimal('20'),
			payment_method='efectivo',
			status='completada',
		)
	)
	test_db_session.commit()

	_dates, totals = DashboardController(test_db_session.bind).get_weekly_sales(tenant.id)

	assert totals[-1] == 0.0
