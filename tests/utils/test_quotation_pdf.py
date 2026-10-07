import pypdfium2 as pdfium

from utils.quotation_pdf import QuotationPDF


def test_quote_pdf_preserves_long_items_across_pages(monkeypatch, tmp_path):
	monkeypatch.setattr(
		'utils.quotation_pdf.settings_manager.load',
		lambda: {
			'company_name': 'Empresa de prueba',
			'currency_symbol': '$',
			'currency_decimals': 2,
		},
	)
	monkeypatch.setattr(QuotationPDF, '_open_file', lambda _self, _path: None)
	items = [
		{
			'description': f'Artículo {number}: ' + 'descripción extensa ' * 10,
			'quantity': 1,
			'unit_price': 10,
			'subtotal': 10,
		}
		for number in range(40)
	]
	service = QuotationPDF(
		{
			'number': 'COT-0099',
			'date': '07/10/2026 10:00',
			'valid_until': '22/10/2026',
			'status_label': 'Enviada',
			'customer_name': 'Cliente de prueba',
			'items': items,
			'total_amount': 400,
			'discount_amount': 0,
			'notes': 'Condiciones comerciales aplicables.',
		},
		str(tmp_path),
	)

	ok, filepath = service.generate()

	assert ok, filepath
	pdf = (tmp_path / 'cotizacion_COT_0099.pdf').read_bytes()
	assert pdf.startswith(b'%PDF')
	assert len(pdf) > 5_000
	assert len(pdfium.PdfDocument(filepath)) > 1
