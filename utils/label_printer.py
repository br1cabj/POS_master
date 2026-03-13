# utils/label_printer.py
import os

import barcode
from barcode.writer import ImageWriter
from fpdf import FPDF


class LabelPrinter:
	def __init__(self):
		self.temp_dir = 'temp_barcodes'
		if not os.path.exists(self.temp_dir):
			os.makedirs(self.temp_dir)

	def generate_labels_pdf(self, products_list, filename='etiquetas_gondola.pdf'):
		"""
		products_list debe ser una lista de diccionarios:
		[{'name': 'Sandwich Miga', 'barcode': '990001', 'price': 1500.00}]
		"""
		pdf = FPDF(orientation='P', unit='mm', format='A4')
		pdf.add_page()
		pdf.set_font('Arial', size=10)

		labels_per_row = 3
		label_width = 65
		label_height = 40
		x_start = 10
		y_start = 10

		x_current = x_start
		y_current = y_start
		count = 0

		for prod in products_list:
			code_str = str(prod['barcode']).zfill(12)

			# Generamos la imagen del código de barras
			ean = barcode.get('ean13', code_str, writer=ImageWriter())
			img_path = os.path.join(self.temp_dir, f'temp_{count}')
			ean.save(img_path)

			# Dibujamos el recuadro de la etiqueta
			pdf.rect(x_current, y_current, label_width, label_height)

			# Texto: Nombre del producto
			pdf.set_font('Arial', 'B', 11)
			pdf.set_xy(x_current + 2, y_current + 2)
			pdf.cell(label_width - 4, 6, prod['name'][:25], ln=1, align='C')

			# Texto: Precio gigante
			pdf.set_font('Arial', 'B', 20)
			pdf.set_xy(x_current + 2, y_current + 10)
			pdf.cell(
				label_width - 4, 10, f'${float(prod["price"]):.2f}', ln=1, align='C'
			)

			# Insertamos la imagen del código de barras
			pdf.image(f'{img_path}.png', x=x_current + 12, y=y_current + 20, w=40, h=15)

			count += 1
			x_current += label_width + 2

			# Salto de línea si llegamos a 3 etiquetas
			if count % labels_per_row == 0:
				x_current = x_start
				y_current += label_height + 5

			# Salto de página si llenamos la hoja
			if y_current > 250:
				pdf.add_page()
				x_current = x_start
				y_current = y_start

		pdf.output(filename)
		self._cleanup_temp_files()
		return filename

	def _cleanup_temp_files(self):
		for file in os.listdir(self.temp_dir):
			if file.endswith('.png'):
				os.remove(os.path.join(self.temp_dir, file))
