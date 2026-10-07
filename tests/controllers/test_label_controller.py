from decimal import Decimal
from types import SimpleNamespace
import sys

import pytest

from controllers.label_controller import TEMPLATES, LabelController, _fmt_price, _sanitize
from database.models import Article, ArticleVariant, Tenant


def _seed_variant(session, barcode=None, variant_id='variant-label'):
	tenant = Tenant(id='tenant-label', name='Etiquetas SA')
	article = Article(id='article-label', tenant_id=tenant.id, name='Producto de prueba')
	variant = ArticleVariant(
		id=variant_id,
		tenant_id=tenant.id,
		article_id=article.id,
		barcode=barcode,
		cost_price=Decimal('10'),
		selling_price=Decimal('25'),
	)
	session.add_all([tenant, article, variant])
	session.commit()
	return tenant, article, variant


def test_label_barcode_validation_and_local_price_format():
	controller = LabelController()
	assert controller.barcode_spec('7791234567003') == ('ean13', '779123456700')
	assert controller.barcode_spec('036000291452') == ('upc', '03600029145')
	assert controller.barcode_spec('INT00001') == ('code128', 'INT00001')
	assert 'dígito verificador' in controller.validate_barcode('7791234567004')
	assert _fmt_price(1234.5, '$', 2) == '$1.234,50'
	assert _sanitize('Pack — molienda fina') == 'Pack - molienda fina'


def test_missing_variant_barcode_is_persisted(test_db_session):
	tenant, _, variant = _seed_variant(test_db_session)
	controller = LabelController()

	barcode = controller.ensure_variant_barcode(
		test_db_session.bind, tenant.id, variant.id
	)

	test_db_session.refresh(variant)
	assert barcode.startswith('INT')
	assert variant.barcode == barcode


def test_manual_article_rejects_barcode_owned_by_another_product(test_db_session):
	tenant, _, _ = _seed_variant(test_db_session, barcode='INTOWNED0001')
	controller = LabelController()

	with pytest.raises(ValueError, match='ya pertenece'):
		controller.save_manual_article(
			test_db_session.bind, tenant.id, 'Manual', 10, 'INTOWNED0001'
		)


def test_pdf_preflight_rejects_invalid_barcode():
	controller = LabelController()
	ok, message = controller.generate_pdf(
		[{'name': 'Producto', 'barcode': '7791234567004', 'price': 10, 'copies': 1}]
	)
	assert not ok
	assert 'dígito verificador' in message


@pytest.mark.parametrize('template_key', TEMPLATES)
def test_preview_renders_each_print_template(template_key):
	controller = LabelController()
	image = controller.render_preview_image(
		{
			'name': 'Producto de preview',
			'barcode': '7791234567003',
			'price': 1234,
			'copies': 1,
		},
		template_key,
	)
	assert image.width > image.height > 0


def test_label_delivery_uses_selected_windows_driver(monkeypatch):
	controller = LabelController()
	shell_execute_calls = []
	monkeypatch.setattr(
		'controllers.label_controller.platform.system', lambda: 'Windows'
	)
	monkeypatch.setitem(
		sys.modules,
		'win32api',
		SimpleNamespace(
			ShellExecute=lambda *args: shell_execute_calls.append(args) or 33
		),
	)

	controller._deliver_pdf(
		'C:/temp/etiqueta.pdf',
		{'printer_label_name': 'Impresora de etiquetas', 'label_output_mode': 'printer'},
	)

	assert shell_execute_calls
	assert 'Impresora de etiquetas' in shell_execute_calls[0][3]
	assert controller.last_delivery_message == 'PDF enviado a «Impresora de etiquetas».'
