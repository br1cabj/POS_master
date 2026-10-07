from database.models import Article, CashSession, Supplier, Tenant, User
from views.onboarding_view import get_onboarding_progress


def test_onboarding_progress_reflects_only_active_tenant_data(test_db_session):
	tenant = Tenant(id='tenant-onboarding', name='Negocio de prueba')
	other_tenant = Tenant(id='tenant-other', name='Otro negocio')
	admin = User(
		id='admin-id',
		username='admin',
		password_hash='hash-de-prueba',
		tenant_id=tenant.id,
	)
	test_db_session.add_all(
		[
			tenant,
			other_tenant,
			admin,
			Supplier(name='Inactivo', tenant_id=tenant.id, is_active=False),
			Supplier(name='Ajeno', tenant_id=other_tenant.id, is_active=True),
			Article(name='Producto', tenant_id=tenant.id, is_active=True),
			CashSession(user_id='admin-id', tenant_id=tenant.id, is_open=False),
		]
	)
	test_db_session.commit()

	progress = get_onboarding_progress(test_db_session.get_bind(), tenant.id)

	assert progress == {
		'system': True,
		'suppliers': False,
		'articles': True,
		'cash': True,
	}


def test_onboarding_progress_is_safe_without_a_database_connection():
	assert get_onboarding_progress(None, 'tenant-onboarding') == {
		'system': True,
		'suppliers': False,
		'articles': False,
		'cash': False,
	}
