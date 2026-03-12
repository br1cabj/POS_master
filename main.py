import sys
from tkinter import messagebox

import customtkinter as ctk

from controllers.auth_controller import AuthController
from database.models import init_db
from views.login_view import LoginView
from views.main_dashboard import MainDashboard

# Configuración visual
ctk.set_appearance_mode('System')
ctk.set_default_color_theme('blue')


class App(ctk.CTk):
	def __init__(self):
		super().__init__()

		# 1. Configuración básica y profesional de la ventana
		self.title('Punto de Venta')

		# Calculamos el centro de la pantalla
		window_width = 1000
		window_height = 650
		screen_width = self.winfo_screenwidth()
		screen_height = self.winfo_screenheight()
		x_cordinate = int((screen_width / 2) - (window_width / 2))
		y_cordinate = int((screen_height / 2) - (window_height / 2))

		# Aplicamos geometría y tamaño mínimo
		self.geometry(f'{window_width}x{window_height}+{x_cordinate}+{y_cordinate}')
		self.minsize(
			900, 600
		)  # Evita que la interfaz se rompa si se achica mucho la ventana

		try:
			self.db_engine = init_db()
			self.auth_controller = AuthController(self.db_engine)
		except Exception as e:
			# Si la base de datos falla, mostramos una alerta y cerramos el programa limpiamente
			messagebox.showerror(
				'Error Crítico', f'No se pudo conectar a la base de datos:\n{str(e)}'
			)
			sys.exit(1)

		# Variable para guardar quién está logueado actualmente
		self.current_user = None

		# 3. Mostrar la primera pantalla
		self.show_login()

	def show_login(self):
		"""Limpia la ventana y muestra el Login"""
		self.clear_window()
		self.view = LoginView(self, login_command=self.attempt_login)

	def show_dashboard(self):
		"""Limpia la ventana y muestra el Dashboard"""
		self.clear_window()
		self.view = MainDashboard(
			master=self,
			current_user=self.current_user,
			db_engine=self.db_engine,
			logout_command=self.logout,
		)

	def attempt_login(self, username, password):
		"""Esta función conecta la VISTA (LoginView) con el CONTROLADOR (AuthController)"""
		user = self.auth_controller.login(username, password)

		if user:
			print(f'Acceso concedido a {user.username}')
			self.current_user = user
			self.show_dashboard()
		else:
			self.view.show_error('Usuario o contraseña incorrectos')

	def logout(self):
		"""Cierra sesión y vuelve al login de forma segura"""
		self.current_user = None
		self.show_login()

	def clear_window(self):
		"""Elimina cualquier vista que esté actualmente en pantalla para evitar superposiciones"""
		if hasattr(self, 'view') and self.view is not None:
			self.view.destroy()


if __name__ == '__main__':
	app = App()
	app.mainloop()
