from decimal import Decimal, InvalidOperation

import customtkinter as ctk
from CTkMessagebox import CTkMessagebox

from core.base_view import BaseView
from core.context import AppContext
from controllers.cash_controller import CashController
from utils.styles import (
    ACCENT, ACCENT_DIM, ACCENT_TEXT, BORDER, BORDER_ACTIVE,
    GREEN, GREEN_DIM, GREEN_TEXT, ORANGE, ORANGE_TEXT,
    RED, RED_DIM, RED_TEXT, SURFACE1, SURFACE2, SURFACE3, SURFACE4,
    TEXT_MUTED, TEXT_PRIMARY, TEXT_SECONDARY,
)


class CashView(BaseView):
    def __init__(self, master, ctx: AppContext):
        super().__init__(master, ctx)
        self.controller = CashController(ctx.db_engine)

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ── Panel izquierdo: Estado de caja y arqueo ─────────────────────
        self.left_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.left_panel.grid(row=0, column=0, padx=(16, 8), pady=16, sticky='nsew')

        ctk.CTkLabel(
            self.left_panel, text='Control de Caja',
            font=('Arial', 20, 'bold'), text_color=TEXT_PRIMARY,
        ).pack(pady=(24, 8))

        self.lbl_status = ctk.CTkLabel(
            self.left_panel, text='', font=('Arial', 16, 'bold')
        )
        self.lbl_status.pack(pady=(0, 6))

        self.lbl_summary = ctk.CTkLabel(
            self.left_panel, text='', font=('Courier', 13), justify='center',
            text_color=TEXT_SECONDARY,
        )
        self.lbl_summary.pack(pady=10)

        self.entry_amount = ctk.CTkEntry(
            self.left_panel,
            placeholder_text='Monto de Apertura ($)',
            font=('Arial', 15),
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=40,
        )
        self.entry_amount.pack(pady=10, padx=24, fill='x')

        self.btn_action = ctk.CTkButton(
            self.left_panel,
            text='',
            font=('Arial', 14, 'bold'),
            height=44,
            corner_radius=8,
            cursor='hand2',
            command=self.handle_action,
        )
        self.btn_action.pack(pady=10, padx=24, fill='x')

        self.lbl_msg = ctk.CTkLabel(
            self.left_panel, text='', font=('Arial', 11), text_color=TEXT_MUTED
        )
        self.lbl_msg.pack(pady=(0, 20))

        # ── Panel derecho: Movimientos manuales ──────────────────────────
        self.right_panel = ctk.CTkFrame(
            self, fg_color=SURFACE2, corner_radius=12,
            border_width=1, border_color=BORDER
        )
        self.right_panel.grid(row=0, column=1, padx=(8, 16), pady=16, sticky='nsew')

        ctk.CTkLabel(
            self.right_panel,
            text='Registrar Gasto / Ingreso',
            font=('Arial', 20, 'bold'), text_color=TEXT_PRIMARY,
        ).pack(pady=(24, 4))

        ctk.CTkLabel(
            self.right_panel,
            text='Registra movimientos manuales de efectivo',
            font=('Arial', 10), text_color=TEXT_MUTED,
        ).pack(pady=(0, 16))

        ctk.CTkLabel(
            self.right_panel, text='TIPO DE MOVIMIENTO',
            font=('Arial', 9, 'bold'), text_color=TEXT_MUTED, anchor='w',
        ).pack(padx=24, anchor='w')

        self._mov_type = 'gasto'
        type_row = ctk.CTkFrame(self.right_panel, fg_color='transparent')
        type_row.pack(pady=(2, 10), padx=24, fill='x')

        self.btn_tipo_gasto = ctk.CTkButton(
            type_row, text='💸  Gasto',
            fg_color=RED_DIM, hover_color=RED, text_color=RED_TEXT,
            border_width=1, border_color=RED, height=36, corner_radius=8,
            font=('Arial', 12, 'bold'), cursor='hand2',
            command=lambda: self._select_mov_type('gasto'),
        )
        self.btn_tipo_gasto.pack(side='left', fill='x', expand=True, padx=(0, 4))

        self.btn_tipo_ingreso = ctk.CTkButton(
            type_row, text='💰  Ingreso',
            fg_color=SURFACE3, hover_color=SURFACE4, text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER, height=36, corner_radius=8,
            font=('Arial', 12, 'bold'), cursor='hand2',
            command=lambda: self._select_mov_type('ingreso'),
        )
        self.btn_tipo_ingreso.pack(side='left', fill='x', expand=True)

        self.entry_mov_desc = ctk.CTkEntry(
            self.right_panel,
            placeholder_text='Descripción  (Ej: Pago de agua)',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
        )
        self.entry_mov_desc.pack(pady=(0, 10), padx=24, fill='x')

        self.entry_mov_amount = ctk.CTkEntry(
            self.right_panel,
            placeholder_text='Monto ($)',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE,
            text_color=TEXT_PRIMARY, height=36,
        )
        self.entry_mov_amount.pack(pady=(0, 16), padx=24, fill='x')

        self.btn_mov = ctk.CTkButton(
            self.right_panel,
            text='💾  Guardar Movimiento',
            fg_color=ACCENT_DIM, hover_color=ACCENT, text_color=ACCENT_TEXT,
            border_width=1, border_color=ACCENT, height=40, corner_radius=8,
            cursor='hand2',
            command=self.save_movement,
        )
        self.btn_mov.pack(pady=(0, 10), padx=24, fill='x')

        self.lbl_mov_msg = ctk.CTkLabel(
            self.right_panel, text='', font=('Arial', 11), text_color=TEXT_MUTED
        )
        self.lbl_mov_msg.pack()

        self.active_session = None
        # Inicializar color de tipo de movimiento
        self.after(50, lambda: self._select_mov_type('gasto'))
        self.after(100, self.refresh_view)

    def refresh_view(self):
        tenant_id = self.ctx.tenant_id
        user_id = self.ctx.user_id
        self.active_session = self.controller.get_active_session(tenant_id, user_id)

        if self.active_session:
            fondo = float(self.active_session.get('opening_balance', 0.0))
            resumen_texto = (
                f'Fondo Inicial : ${fondo:.2f}\n\n'
                f'🔒 MODO ARQUEO CIEGO ACTIVO 🔒\n'
                f'El total de ventas es secreto.\n'
                f'Al cerrar turno, deberás contar tus\nbilletes y declarar lo que tenés.'
            )
            self.lbl_status.configure(text='🟢  CAJA ABIERTA', text_color=GREEN_TEXT)
            self.lbl_summary.configure(text=resumen_texto, text_color=ACCENT_TEXT)
            self.entry_amount.pack_forget()
            self.btn_action.configure(
                text='🔒  Cerrar Turno · Contar Caja',
                fg_color=RED_DIM, hover_color=RED, text_color=RED_TEXT,
                border_width=1, border_color=RED,
            )
            self._set_panel_state(self.right_panel, 'normal')
        else:
            self.lbl_status.configure(text='🔴  CAJA CERRADA', text_color=ORANGE_TEXT)
            self.lbl_summary.configure(
                text='\nDebés abrirla para poder\nvender o registrar movimientos.\n',
                text_color=TEXT_SECONDARY,
            )
            self.entry_amount.pack(pady=10, padx=24, fill='x', before=self.btn_action)
            self.entry_amount.configure(placeholder_text='Fondo inicial ($)')
            self.btn_action.configure(
                text='ABRIR CAJA',
                fg_color=GREEN_DIM, hover_color=GREEN, text_color=GREEN_TEXT,
                border_width=1, border_color=GREEN,
            )
            self._set_panel_state(self.right_panel, 'disabled')

    def _set_panel_state(self, panel, state):
        for widget in panel.winfo_children():
            if hasattr(widget, 'configure') and not isinstance(widget, ctk.CTkLabel):
                try:
                    widget.configure(state=state)
                except ValueError:
                    pass

    def handle_action(self):
        tenant_id = self.ctx.tenant_id
        user_id = self.ctx.user_id

        if self.active_session:
            self.show_blind_close_popup()
        else:
            amount_str = self.entry_amount.get().strip().replace(',', '.')
            if not amount_str:
                self.lbl_msg.configure(text='Ingresá un monto inicial.', text_color=RED_TEXT)
                return
            success, msg = self.controller.open_session(tenant_id, user_id, amount_str)
            if success:
                self.lbl_msg.configure(text=msg, text_color=GREEN_TEXT)
                self.entry_amount.delete(0, 'end')
                self.refresh_view()
            else:
                self.lbl_msg.configure(text=msg, text_color=RED_TEXT)

    def _select_mov_type(self, mov_type: str):
        """Alterna visualmente entre Gasto e Ingreso."""
        self._mov_type = mov_type
        if mov_type == 'gasto':
            self.btn_tipo_gasto.configure(
                fg_color=RED_DIM, hover_color=RED,
                text_color=RED_TEXT, border_color=RED,
            )
            self.btn_tipo_ingreso.configure(
                fg_color=SURFACE3, hover_color=SURFACE4,
                text_color=TEXT_SECONDARY, border_color=BORDER,
            )
            self.entry_mov_amount.configure(border_color=RED)
            self.entry_mov_desc.configure(border_color=RED)
        else:
            self.btn_tipo_ingreso.configure(
                fg_color=GREEN_DIM, hover_color=GREEN,
                text_color=GREEN_TEXT, border_color=GREEN,
            )
            self.btn_tipo_gasto.configure(
                fg_color=SURFACE3, hover_color=SURFACE4,
                text_color=TEXT_SECONDARY, border_color=BORDER,
            )
            self.entry_mov_amount.configure(border_color=GREEN)
            self.entry_mov_desc.configure(border_color=GREEN)

    def save_movement(self):
        desc = self.entry_mov_desc.get().strip()
        amount_str = self.entry_mov_amount.get().strip().replace(',', '.')
        mov_type = self._mov_type
        tenant_id = self.ctx.tenant_id

        if not desc or not amount_str:
            self.lbl_mov_msg.configure(
                text='Descripción y monto son obligatorios.', text_color=RED_TEXT
            )
            return

        if not self.active_session:
            self.lbl_mov_msg.configure(
                text='No hay caja abierta. Abrí la caja primero.', text_color=RED_TEXT
            )
            return

        session_id = self.active_session.get('id')
        success, msg = self.controller.add_manual_movement(
            tenant_id, session_id, mov_type, amount_str, desc
        )

        if success:
            CTkMessagebox(title='Éxito', message=msg, icon='check')
            self.lbl_mov_msg.configure(text='', text_color=GREEN_TEXT)
            self.entry_mov_desc.delete(0, 'end')
            self.entry_mov_amount.delete(0, 'end')
        else:
            self.lbl_mov_msg.configure(text=msg, text_color=RED_TEXT)

    # ── Calculadora de billetes (Blind Close) ──────────────────────────────
    def show_blind_close_popup(self):
        self.popup = ctk.CTkToplevel(self)
        self.popup.title('Arqueo de Caja')
        self.popup.geometry('370x680')
        self.popup.configure(fg_color=SURFACE1)
        self.popup.attributes('-topmost', True)
        self.popup.grab_set()

        ctk.CTkLabel(
            self.popup, text='Cuenta tus billetes',
            font=('Arial', 20, 'bold'), text_color=TEXT_PRIMARY,
        ).pack(pady=(22, 4))
        ctk.CTkLabel(
            self.popup,
            text='Ingresá la CANTIDAD de billetes que tenés:',
            font=('Arial', 11), text_color=TEXT_MUTED,
        ).pack(pady=(0, 16))

        denominations = [10000, 2000, 1000, 500, 200, 100, 50]
        self.bill_entries = {}

        grid_frame = ctk.CTkFrame(self.popup, fg_color='transparent')
        grid_frame.pack(fill='x', padx=30)

        for i, denom in enumerate(denominations):
            ctk.CTkLabel(
                grid_frame, text=f'Billetes de ${denom}:',
                font=('Arial', 13), text_color=TEXT_SECONDARY,
            ).grid(row=i, column=0, sticky='e', pady=5, padx=10)
            entry = ctk.CTkEntry(
                grid_frame, width=80, justify='center',
                fg_color=SURFACE3, border_color=BORDER_ACTIVE, text_color=TEXT_PRIMARY,
            )
            entry.grid(row=i, column=1, pady=5)
            entry.insert(0, '0')
            entry.bind('<KeyRelease>', self._calculate_realtime_total)
            self.bill_entries[denom] = entry

        ctk.CTkLabel(
            grid_frame, text='Monedas / Otros ($):',
            font=('Arial', 13), text_color=TEXT_SECONDARY,
        ).grid(row=len(denominations), column=0, sticky='e', pady=15, padx=10)
        self.entry_otros = ctk.CTkEntry(
            grid_frame, width=80, justify='center',
            fg_color=SURFACE3, border_color=BORDER_ACTIVE, text_color=TEXT_PRIMARY,
        )
        self.entry_otros.grid(row=len(denominations), column=1, pady=15)
        self.entry_otros.insert(0, '0')
        self.entry_otros.bind('<KeyRelease>', self._calculate_realtime_total)

        self.lbl_popup_total = ctk.CTkLabel(
            self.popup, text='Total Declarado: $0.00',
            font=('Arial', 22, 'bold'), text_color=ACCENT_TEXT,
        )
        self.lbl_popup_total.pack(pady=20)

        self.current_counted_total = '0.00'

        ctk.CTkButton(
            self.popup, text='💾  CONFIRMAR Y CERRAR TURNO',
            fg_color=RED_DIM, hover_color=RED, text_color=RED_TEXT,
            border_width=1, border_color=RED,
            height=46, font=('Arial', 14, 'bold'), corner_radius=8,
            command=self._confirm_blind_close,
        ).pack(pady=10, padx=30, fill='x')

        ctk.CTkButton(
            self.popup, text='Cancelar',
            fg_color=SURFACE3, hover_color=SURFACE4, text_color=TEXT_SECONDARY,
            border_width=1, border_color=BORDER, height=36, corner_radius=8,
            command=self.popup.destroy,
        ).pack(padx=30, fill='x')

    def _calculate_realtime_total(self, event=None):
        total = Decimal('0.0')
        for denom, entry in self.bill_entries.items():
            qty = entry.get().strip()
            if qty.isdigit():
                total += Decimal(str(denom)) * Decimal(qty)
        otros = self.entry_otros.get().strip().replace(',', '.')
        if otros:
            try:
                total += Decimal(otros)
            except (InvalidOperation, ValueError):
                pass
        self.lbl_popup_total.configure(text=f'Total Declarado: ${total:.2f}')
        self.current_counted_total = str(total)

    def _confirm_blind_close(self):
        msg_box = CTkMessagebox(
            title='Advertencia',
            message=f'Estás declarando que tenés exactamente ${self.current_counted_total} en tu caja.\n¿Estás seguro? Esta acción no se puede deshacer.',
            icon='warning', option_1='Revisar de nuevo', option_2='Sí, Cerrar Caja',
        )
        if msg_box.get() == 'Sí, Cerrar Caja':
            tenant_id = self.ctx.tenant_id
            session_id = self.active_session.get('id')
            success, msg = self.controller.close_session(
                tenant_id, session_id, self.current_counted_total
            )
            if success:
                self.popup.destroy()
                CTkMessagebox(title='Turno Finalizado', message=msg, icon='check', width=450)
                self.refresh_view()
            else:
                CTkMessagebox(title='Error', message=msg, icon='cancel')
