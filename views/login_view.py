import customtkinter as ctk

class LoginView(ctk.CTkFrame):
  def __init__(self, master, login_command):
    super().__init__(master)
    self.login_command = login_command

    self.pack(pady=20, padx=60, fill='both', expand=True)

    # Título
    self.label = ctk.CTkLabel(self, text="Iniciar Sesión", font=("Roboto", 24))
    self.label.pack(pady=12, padx=10)

    # Campo Usuario
    self.entry_user = ctk.CTkEntry(self, placeholder_text="Usuario")
    self.entry_user.pack(pady=12, padx=10)

    # Campo Contraseña
    self.entry_pass = ctk.CTkEntry(self, placeholder_text="Contraseña", show="*")
    self.entry_pass.pack(pady=12, padx=10)

    # Botón
    self.button = ctk.CTkButton(self, text="Entrar", command=self.handle_login)
    self.button.pack(pady=12, padx=10)
        
    # Etiqueta para errores
    self.error_label = ctk.CTkLabel(self, text="", text_color="red")
    self.error_label.pack(pady=5)

  def handle_login(self):
    # Obtenemos el texto de las cajas
    username = self.entry_user.get()
    password = self.entry_pass.get()
        
    # Llamamos a la función que nos pasó el sistema principal
    self.login_command(username, password)
    
  def show_error(self, message):
    self.error_label.configure(text=message)