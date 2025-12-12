import customtkinter as ctk

class MainDashboard(ctk.CTkFrame):
  def __init__(self, master, current_user, logout_command):
    super().__init__(master)

    self.pack(fill='both', expand=True)

    # Barra lateral (Sidebar)
    self.sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
    self.sidebar.pack(side="left", fill="y")

    # Área principal
    self.main_area = ctk.CTkFrame(self)
    self.main_area.pack(side="right", fill="both", expand=True, padx=20, pady=20)

    # Información del usuario (Bienvenida)
    welcome_text = f"Hola, {current_user.username}\nEmpresa ID: {current_user.tenant_id}\nRol: {current_user.role}"
    self.label_info = ctk.CTkLabel(self.sidebar, text=welcome_text, font=("Arial", 16))
    self.label_info.pack(pady=40, padx=10)

    # Botón de Cerrar Sesión
    self.btn_logout = ctk.CTkButton(self.sidebar, text="Cerrar Sesión", fg_color="red", command=logout_command)
    self.btn_logout.pack(side="bottom", pady=20, padx=10)

    # Título en el área principal
    self.lbl_title = ctk.CTkLabel(self.main_area, text="Panel de Control", font=("Arial", 30, "bold"))
    self.lbl_title.pack(pady=20)