import sqlite3
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base, Tenant, User
from utils.styles import GREEN, RED, RED_TEXT
from views.setup_wizard_view import SetupWizard, _currency_symbol, _parse_tax_rate


class _Field:
	def __init__(self, value):
		self.value = value
		self.focused = False
		self.options = {}

	def get(self):
		return self.value

	def configure(self, **kwargs):
		self.options.update(kwargs)

	def focus(self):
		self.focused = True


class _Label:
	def __init__(self):
		self.options = {}

	def configure(self, **kwargs):
		self.options.update(kwargs)


def _wizard_for_connection(path):
	return SimpleNamespace(
		_entry_cashier_path=_Field(str(path)),
		_lbl_terminal_status=_Label(),
		_cashier_connection_verified=False,
		_cashier_verified_path='',
		_cashier_db_path='',
	)


def test_cashier_connection_accepts_a_readable_cloudpos_database(tmp_path):
	database = tmp_path / 'pos_system.db'
	with sqlite3.connect(database) as connection:
		connection.execute('CREATE TABLE users (id INTEGER PRIMARY KEY)')
		connection.execute('CREATE TABLE tenants (id INTEGER PRIMARY KEY)')

	wizard = _wizard_for_connection(database)

	assert SetupWizard._test_cashier_connection(wizard) is True
	assert wizard._cashier_connection_verified is True
	assert wizard._cashier_db_path == str(database)
	assert wizard._entry_cashier_path.options['border_color'] == GREEN


def test_cashier_connection_rejects_a_database_that_is_not_cloudpos(tmp_path):
	database = tmp_path / 'other.db'
	with sqlite3.connect(database) as connection:
		connection.execute('CREATE TABLE unrelated (id INTEGER PRIMARY KEY)')

	wizard = _wizard_for_connection(database)

	assert SetupWizard._test_cashier_connection(wizard) is False
	assert wizard._cashier_connection_verified is False
	assert wizard._entry_cashier_path.options['border_color'] == RED
	assert wizard._lbl_terminal_status.options['text_color'] == RED_TEXT


def test_administrator_password_only_requires_the_configured_length():
	password = 'aaaaaaaaaa'  # No exige mayúsculas, números ni símbolos.
	wizard = SimpleNamespace(
		_e_username=_Field('admin'),
		_e_pass=_Field(password),
		_e_pass2=_Field(password),
		_e_pin=_Field('1234'),
		_e_pin2=_Field('1234'),
		_clear_field_errors=lambda: None,
		_show_field_error=lambda *args: None,
	)

	assert SetupWizard._validate_step3(wizard) is True
	assert wizard._d_password == password


def test_tax_rate_rejects_nan_infinity_and_out_of_range_values():
	assert _parse_tax_rate('21') == 21.0
	assert _parse_tax_rate('21,5') == 21.5
	assert _parse_tax_rate('NaN') is None
	assert _parse_tax_rate('inf') is None
	assert _parse_tax_rate('-1') is None
	assert _parse_tax_rate('101') is None


def test_custom_currency_symbol_is_preserved_when_the_step_is_reopened():
	assert _currency_symbol('R$') == 'R$'
	assert _currency_symbol('') == '$'


def test_setup_database_retries_do_not_duplicate_a_completed_initialization():
	engine = create_engine('sqlite:///:memory:')
	wizard = SimpleNamespace(
		_d_store='Kiosco de prueba',
		_d_username='admin',
		_d_password='aaaaaaaaaa',
		_d_pin='1234',
	)

	with patch('utils.config.get_engine', return_value=engine):
		SetupWizard._setup_database(wizard)
		SetupWizard._setup_database(wizard)

	with sessionmaker(bind=engine)() as session:
		assert session.query(Tenant).count() == 1
		assert session.query(User).count() == 1

	wizard._d_password = 'otra-clave'
	with patch('utils.config.get_engine', return_value=engine):
		with pytest.raises(RuntimeError, match='mismo administrador'):
			SetupWizard._setup_database(wizard)

	Base.metadata.drop_all(engine)
