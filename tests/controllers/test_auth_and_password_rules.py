from controllers.auth_controller import AuthController
from controllers.user_controller import PASSWORD_MIN_LENGTH, UserController
from database.models import Tenant


def test_passwords_use_only_minimum_length_and_preserve_spaces(test_db_session):
	tenant = Tenant(name='Negocio de prueba')
	test_db_session.add(tenant)
	test_db_session.commit()

	engine = test_db_session.get_bind()
	users = UserController(engine)
	password_with_spaces = '  abcdefgh  '

	ok, message = users.add_user(
		tenant.id,
		'operador',
		password_with_spaces,
		'cajero',
		recovery_pin='1234',
	)
	assert ok, message

	auth = AuthController(engine)
	assert auth.login('operador', password_with_spaces, tenant_id=tenant.id)
	assert auth.login('operador', password_with_spaces.strip(), tenant_id=tenant.id) is None

	ok, message = users.reset_password_with_pin(
		tenant.id, 'operador', '1234', 'x' * (PASSWORD_MIN_LENGTH - 1)
	)
	assert not ok
	assert str(PASSWORD_MIN_LENGTH) in message

	ok, message = users.reset_password_with_pin(
		tenant.id, 'operador', '1234', 'n' * PASSWORD_MIN_LENGTH
	)
	assert ok, message
	assert auth.login('operador', 'n' * PASSWORD_MIN_LENGTH, tenant_id=tenant.id)
