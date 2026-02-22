import os


class PrintService:
	def generate_ticket(self, sale, details, tenant_name, user_name):
		"""
		Crea un archivo .txt con el diseño de un ticket de impresora térmica.
		"""
		# Definimos el ancho del papel (estándar térmico suele ser 32 o 48 caracteres)
		width = 40

		# Línea divisoria
		line = '-' * width

		# Construcción del contenido del ticket
		ticket_content = []
		ticket_content.append(line)
		ticket_content.append(f'{tenant_name.center(width)}')
		ticket_content.append(f'Ticket de Venta #{sale.id}'.center(width))
		ticket_content.append(line)
		ticket_content.append(f'Fecha: {sale.date.strftime("%d/%m/%Y %H:%M")}')
		ticket_content.append(f'Le atendio: {user_name}')
		ticket_content.append(line)
		ticket_content.append(f'{"PROD":<15} {"CANT":^6} {"TOTAL":>10}')  # Encabezados
		ticket_content.append(line)

		# Agregar cada producto
		for item in details:
			name = (
				(item.product_name[:15] + '..')
				if len(item.product_name) > 15
				else item.product_name
			)
			qty = str(item.quantity)
			sub = f'${item.subtotal:.2f}'

			row = f'{name:<15} {qty:^6} {sub:>10}'
			ticket_content.append(row)

		ticket_content.append(line)
		ticket_content.append(f'TOTAL: ${sale.total_amount:.2f}'.rjust(width))
		ticket_content.append(line)
		ticket_content.append('¡Gracias por su compra!'.center(width))
		ticket_content.append(line)
		ticket_content.append('\n\n')

		# Unir todo en un solo texto
		final_text = '\n'.join(ticket_content)

		try:
			filename = f'tickets/ticket_{sale.id}.txt'
			with open(filename, 'w', encoding='utf-8') as f:
				f.write(final_text)

			os.startfile(os.path.abspath(filename))
			return True
		except Exception as e:
			print(f'Error al imprimir: {e}')
			return False
