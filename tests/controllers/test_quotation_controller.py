from datetime import date, timedelta
from decimal import Decimal

from controllers.quotation_controller import QuotationController
from database.models import Quotation, Tenant, User


def _seed(session):
	tenant = Tenant(id='tenant-quote-flow', name='Empresa principal')
	other_tenant = Tenant(id='tenant-quote-other', name='Empresa ajena')
	user = User(
		id='user-quote-flow',
		tenant_id=tenant.id,
		username='operador',
		password_hash='not-used-in-test',
	)
	other_user = User(
		id='user-quote-other',
		tenant_id=other_tenant.id,
		username='ajeno',
		password_hash='not-used-in-test',
	)
	session.add_all([tenant, other_tenant, user, other_user])
	session.commit()
	return tenant, other_tenant, user, other_user


def _items():
	return [
		{
			'description': 'Servicio de instalación',
			'quantity': '2',
			'unit_price': '10',
			# El subtotal del cliente no se debe aceptar como fuente de verdad.
			'subtotal': '0.01',
		}
	]


def test_quote_totals_are_server_calculated_and_state_is_guarded(test_db_session):
	tenant, other_tenant, user, _ = _seed(test_db_session)
	controller = QuotationController(test_db_session.bind)

	ok, quote = controller.create_quotation(
		tenant.id, user.id, _items(), discount_amount='3'
	)

	assert ok
	assert quote['total_amount'] == 17.0
	assert quote['items'][0]['subtotal'] == 20.0
	assert controller.get_quotation(quote['id'], other_tenant.id) is None

	ok, _ = controller.update_quotation(
		quote['id'], other_tenant.id, _items(), discount_amount='0'
	)
	assert not ok
	ok, _ = controller.delete_quotation(quote['id'], other_tenant.id)
	assert not ok

	ok, _ = controller.set_status(quote['id'], 'enviada', tenant.id)
	assert ok
	ok, _ = controller.update_quotation(
		quote['id'], tenant.id, _items(), discount_amount='0'
	)
	assert not ok
	ok, _ = controller.delete_quotation(quote['id'], tenant.id)
	assert not ok
	ok, _ = controller.set_status(quote['id'], 'aceptada', tenant.id)
	assert not ok


def test_quote_expiry_and_invalid_amounts_cannot_reach_conversion(test_db_session):
	tenant, _, user, _ = _seed(test_db_session)
	controller = QuotationController(test_db_session.bind)

	ok, message = controller.create_quotation(
		tenant.id, user.id, _items(), discount_amount='20.01'
	)
	assert not ok
	assert 'descuento' in message.lower()

	ok, quote = controller.create_quotation(tenant.id, user.id, _items())
	assert ok
	stored = test_db_session.get(Quotation, quote['id'])
	stored.status = 'enviada'
	stored.valid_until = date.today() - timedelta(days=1)
	test_db_session.commit()

	ok, message = controller.convert_to_sale(
		quote['id'], user.id, tenant_id=tenant.id
	)
	assert not ok
	assert 'vencida' in message.lower()
	test_db_session.refresh(stored)
	assert stored.status == 'vencida'
	assert stored.total_amount == Decimal('20.00')
