import customtkinter as ctk
from database.models import init_db

#Config
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
  def __init__(self):
    super().__init__()

    self.title('Sistema POS')
    self.geometry('800x600')

    print('Iniciando sistema...')
    self.engine = init_db()
    print('Base de datos lista')

    self.label= ctk.CTkLabel(self, text='Bienvenido al Sistema', font=('Arial', 24))

if __name__ == '__main__':
  app = App()
  app.mainloop()