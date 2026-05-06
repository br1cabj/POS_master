"""
utils/date_picker.py
====================
Widget reutilizable de selección de fecha con calendario popup.

Interfaz pública (compatible con CTkEntry):
    picker.get()              → 'DD/MM/AAAA' o ''
    picker.get_date()         → date | None
    picker.set_date(d)        → pre-llena con un objeto date
    picker.set_text(s)        → pre-llena con un string ya formateado
    picker.clear()            → limpia el campo
    picker.configure(state=)  → habilita / deshabilita
    picker.bind(seq, cb)      → delega al entry interno
"""

import calendar
from datetime import date, datetime
from typing import Callable, Optional

import customtkinter as ctk

from utils.styles import (
	ACCENT,
	ACCENT_DIM,
	ACCENT_HOVER,
	ACCENT_TEXT,
	BORDER,
	BORDER_ACTIVE,
	FONT_BODY,
	FONT_BODY_BOLD,
	FONT_LABEL_BOLD,
	FONT_SMALL,
	ORANGE_TEXT,
	PAD_MD,
	PAD_SM,
	PAD_XS,
	RED_TEXT,
	SURFACE2,
	SURFACE3,
	SURFACE4,
	TEXT_MUTED,
	TEXT_PRIMARY,
	TEXT_SECONDARY,
)

_FMT = '%d/%m/%Y'
_MONTHS = [
	'Enero',
	'Febrero',
	'Marzo',
	'Abril',
	'Mayo',
	'Junio',
	'Julio',
	'Agosto',
	'Septiembre',
	'Octubre',
	'Noviembre',
	'Diciembre',
]
_DAYS = ['Lu', 'Ma', 'Mi', 'Ju', 'Vi', 'Sá', 'Do']

# Keys that should not trigger auto-format
_SKIP_KEYS = {
	'BackSpace',
	'Delete',
	'Left',
	'Right',
	'Home',
	'End',
	'Tab',
	'Return',
	'KP_Enter',
	'Escape',
	'shift_l',
	'shift_r',
	'control_l',
	'control_r',
	'alt_l',
	'alt_r',
	'caps_lock',
	'num_lock',
	'f1',
	'f2',
	'f3',
	'f4',
	'f5',
}


class CTkDatePicker(ctk.CTkFrame):
	"""
	Campo de fecha con calendario popup. Drop-in replacement de CTkEntry
	para campos de fecha en formato DD/MM/AAAA.
	"""

	def __init__(
		self,
		parent,
		width: int = 160,
		height: int = 38,
		placeholder: str = 'DD/MM/AAAA',
		initial_date: Optional[date] = None,
		on_date_selected: Optional[Callable[[date], None]] = None,
		state: str = 'normal',
		**kwargs,
	):
		super().__init__(parent, fg_color='transparent', **kwargs)

		self._selected: Optional[date] = None
		self._popup: Optional['_CalendarPopup'] = None
		self._on_date_selected = on_date_selected
		self._click_bind_id: Optional[str] = None

		btn_size = max(height, 28)
		entry_w = max(width - btn_size - 2, 80)

		self._entry = ctk.CTkEntry(
			self,
			width=entry_w,
			height=btn_size,
			placeholder_text=placeholder,
			font=FONT_BODY,
			fg_color=SURFACE3,
			border_color=BORDER_ACTIVE,
			text_color=TEXT_PRIMARY,
			placeholder_text_color=TEXT_MUTED,
			corner_radius=6,
			border_width=1,
			state=state,
		)
		self._entry.pack(side='left')
		self._entry.bind('<KeyRelease>', self._on_key)
		self._entry.bind('<FocusOut>', lambda e: self._validate_visual())

		self._btn = ctk.CTkButton(
			self,
			text='📅',
			width=btn_size,
			height=btn_size,
			font=FONT_BODY,
			fg_color=SURFACE3,
			hover_color=SURFACE4,
			text_color=TEXT_SECONDARY,
			border_width=1,
			border_color=BORDER_ACTIVE,
			corner_radius=6,
			state=state,
			command=self._toggle_popup,
		)
		self._btn.pack(side='left', padx=(2, 0))

		if initial_date:
			self.set_date(initial_date)

	# ── Public API ───────────────────────────────────────────────────────────

	def get(self) -> str:
		return self._entry.get().strip()

	def get_date(self) -> Optional[date]:
		return self._selected

	def set_date(self, d: date):
		self._selected = d
		self._entry.configure(state='normal')
		self._entry.delete(0, 'end')
		self._entry.insert(0, d.strftime(_FMT))
		self._entry.configure(border_color=ACCENT_TEXT)

	def set_text(self, text: str):
		"""Pre-llena con un string ya formateado (ej: pre-fill desde base de datos)."""
		self._entry.configure(state='normal')
		self._entry.delete(0, 'end')
		self._entry.insert(0, text)
		self._validate_visual()

	def clear(self):
		self._selected = None
		self._entry.delete(0, 'end')
		self._entry.configure(border_color=BORDER_ACTIVE)

	def configure(self, **kwargs):
		state = kwargs.pop('state', None)
		if state is not None:
			self._entry.configure(state=state)
			self._btn.configure(state=state)
		if kwargs:
			super().configure(**kwargs)

	def bind(self, sequence, callback, add=None):
		if add:
			self._entry.bind(sequence, callback, add)
		else:
			self._entry.bind(sequence, callback)

	# ── Input handling ───────────────────────────────────────────────────────

	def _on_key(self, event):
		if event.keysym.lower() in _SKIP_KEYS:
			self._validate_visual()
			return

		val = self._entry.get()
		digits = ''.join(c for c in val if c.isdigit())[:8]

		formatted = ''
		for i, ch in enumerate(digits):
			if i in (2, 4):
				formatted += '/'
			formatted += ch

		if formatted != val:
			self._entry.delete(0, 'end')
			self._entry.insert(0, formatted)
			self._entry.icursor(len(formatted))

		self._validate_visual()

	def _validate_visual(self):
		val = self.get()
		if not val:
			self._entry.configure(border_color=BORDER_ACTIVE)
			self._selected = None
			return
		if len(val) < 10:
			self._entry.configure(border_color=BORDER_ACTIVE)
			self._selected = None
			return
		try:
			self._selected = datetime.strptime(val, _FMT).date()
			self._entry.configure(border_color=ACCENT_TEXT)
		except ValueError:
			self._selected = None
			self._entry.configure(border_color=RED_TEXT)

	# ── Popup ────────────────────────────────────────────────────────────────

	def _toggle_popup(self):
		if self._popup and self._popup.winfo_exists():
			self._close_popup()
		else:
			self._open_popup()

	def _open_popup(self):
		viewing = (self._selected or date.today()).replace(day=1)
		self._popup = _CalendarPopup(
			viewing=viewing,
			selected=self._selected,
			on_pick=self._on_pick,
		)
		self._position_popup()
		self._click_bind_id = self.winfo_toplevel().bind(
			'<Button-1>', self._check_outside, '+'
		)

	def _position_popup(self):
		if not (self._popup and self._popup.winfo_exists()):
			return
		self.update_idletasks()
		self._popup.update_idletasks()

		x = self._entry.winfo_rootx()
		y = self._entry.winfo_rooty() + self._entry.winfo_height() + 6

		sw = self.winfo_screenwidth()
		sh = self.winfo_screenheight()
		pw = self._popup.winfo_reqwidth() or 290
		ph = self._popup.winfo_reqheight() or 320

		x = min(x, sw - pw - 10)
		y = min(y, sh - ph - 10)
		x = max(x, 10)
		y = max(y, 10)

		self._popup.geometry(f'+{x}+{y}')
		self._popup.lift()

	def _check_outside(self, event):
		if not (self._popup and self._popup.winfo_exists()):
			return
		px = self._popup.winfo_rootx()
		py = self._popup.winfo_rooty()
		pw = self._popup.winfo_width()
		ph = self._popup.winfo_height()
		inside_popup = px <= event.x_root <= px + pw and py <= event.y_root <= py + ph
		inside_btn = (
			self._btn.winfo_rootx()
			<= event.x_root
			<= self._btn.winfo_rootx() + self._btn.winfo_width()
			and self._btn.winfo_rooty()
			<= event.y_root
			<= self._btn.winfo_rooty() + self._btn.winfo_height()
		)
		if not inside_popup and not inside_btn:
			self._close_popup()

	def _close_popup(self):
		if self._popup and self._popup.winfo_exists():
			self._popup.destroy()
		self._popup = None
		if self._click_bind_id:
			try:
				self.winfo_toplevel().unbind('<Button-1>', self._click_bind_id)
			except Exception:
				pass
			self._click_bind_id = None

	def _on_pick(self, d: date):
		self.set_date(d)
		self._close_popup()
		if self._on_date_selected:
			self._on_date_selected(d)


# ── Popup calendar window ────────────────────────────────────────────────────


class _CalendarPopup(ctk.CTkToplevel):
	def __init__(self, viewing: date, selected: Optional[date], on_pick: Callable):
		super().__init__()
		self.overrideredirect(True)
		self.attributes('-topmost', True)

		self._viewing = viewing
		self._selected = selected
		self._on_pick = on_pick
		self._today = date.today()

		self._build()

	def _build(self):
		for w in self.winfo_children():
			w.destroy()

		card = ctk.CTkFrame(
			self,
			fg_color=SURFACE2,
			corner_radius=14,
			border_width=1,
			border_color=BORDER_ACTIVE,
		)
		card.pack(padx=0, pady=0)

		self._build_header(card)
		self._build_weekday_row(card)
		self._build_day_grid(card)
		self._build_footer(card)

	# ── Header ───────────────────────────────────────────────────────────────

	def _build_header(self, parent):
		header = ctk.CTkFrame(parent, fg_color='transparent')
		header.pack(fill='x', padx=PAD_MD, pady=(PAD_MD, PAD_XS))
		header.grid_columnconfigure(1, weight=1)

		ctk.CTkButton(
			header,
			text='‹',
			width=30,
			height=30,
			fg_color=SURFACE3,
			hover_color=ACCENT_DIM,
			text_color=TEXT_PRIMARY,
			font=('Arial', 16, 'bold'),
			corner_radius=8,
			command=self._prev_month,
		).grid(row=0, column=0, sticky='w')

		ctk.CTkLabel(
			header,
			text=f'{_MONTHS[self._viewing.month - 1]}  {self._viewing.year}',
			font=FONT_BODY_BOLD,
			text_color=TEXT_PRIMARY,
		).grid(row=0, column=1)

		ctk.CTkButton(
			header,
			text='›',
			width=30,
			height=30,
			fg_color=SURFACE3,
			hover_color=ACCENT_DIM,
			text_color=TEXT_PRIMARY,
			font=('Arial', 16, 'bold'),
			corner_radius=8,
			command=self._next_month,
		).grid(row=0, column=2, sticky='e')

	# ── Weekday labels ───────────────────────────────────────────────────────

	def _build_weekday_row(self, parent):
		row = ctk.CTkFrame(parent, fg_color='transparent')
		row.pack(fill='x', padx=PAD_MD, pady=(PAD_XS, 2))

		for i, name in enumerate(_DAYS):
			color = ORANGE_TEXT if i >= 5 else TEXT_MUTED
			ctk.CTkLabel(
				row,
				text=name,
				width=36,
				height=20,
				font=FONT_LABEL_BOLD,
				text_color=color,
				anchor='center',
			).pack(side='left', padx=1)

	# ── Day grid ─────────────────────────────────────────────────────────────

	def _build_day_grid(self, parent):
		grid_frame = ctk.CTkFrame(parent, fg_color='transparent')
		grid_frame.pack(fill='x', padx=PAD_MD, pady=(0, PAD_XS))

		for week in calendar.monthcalendar(self._viewing.year, self._viewing.month):
			week_row = ctk.CTkFrame(grid_frame, fg_color='transparent')
			week_row.pack(fill='x', pady=1)

			for col, day_num in enumerate(week):
				if day_num == 0:
					ctk.CTkFrame(
						week_row, width=36, height=32, fg_color='transparent'
					).pack(side='left', padx=1)
					continue

				d = date(self._viewing.year, self._viewing.month, day_num)
				is_selected = self._selected is not None and d == self._selected
				is_today = d == self._today
				is_weekend = col >= 5

				if is_selected:
					fg = ACCENT
					hover = ACCENT_HOVER
					txt = 'white'
					bw = 0
					bc = BORDER
				elif is_today:
					fg = ACCENT_DIM
					hover = ACCENT
					txt = ACCENT_TEXT
					bw = 1
					bc = ACCENT
				else:
					fg = 'transparent'
					hover = SURFACE3
					txt = ORANGE_TEXT if is_weekend else TEXT_PRIMARY
					bw = 0
					bc = BORDER

				ctk.CTkButton(
					week_row,
					text=str(day_num),
					width=36,
					height=32,
					fg_color=fg,
					hover_color=hover,
					text_color=txt,
					font=FONT_SMALL,
					corner_radius=8,
					border_width=bw,
					border_color=bc,
					command=lambda dd=d: self._on_pick(dd),
				).pack(side='left', padx=1)

	# ── Footer ───────────────────────────────────────────────────────────────

	def _build_footer(self, parent):
		ctk.CTkFrame(parent, height=1, fg_color=BORDER_ACTIVE, corner_radius=0).pack(
			fill='x', padx=PAD_MD, pady=(PAD_SM, 0)
		)

		ctk.CTkButton(
			parent,
			text='Hoy',
			height=30,
			fg_color='transparent',
			hover_color=SURFACE3,
			text_color=ACCENT_TEXT,
			font=FONT_LABEL_BOLD,
			corner_radius=6,
			command=lambda: self._on_pick(self._today),
		).pack(pady=(4, PAD_SM))

	# ── Navigation ───────────────────────────────────────────────────────────

	def _prev_month(self):
		y, m = self._viewing.year, self._viewing.month
		self._viewing = self._viewing.replace(
			year=y - 1 if m == 1 else y,
			month=12 if m == 1 else m - 1,
		)
		self._build()

	def _next_month(self):
		y, m = self._viewing.year, self._viewing.month
		self._viewing = self._viewing.replace(
			year=y + 1 if m == 12 else y,
			month=1 if m == 12 else m + 1,
		)
		self._build()
