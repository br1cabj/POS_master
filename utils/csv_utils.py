"""Helpers for safe CSV values intended to be opened in spreadsheet software."""


def safe_spreadsheet_text(value) -> str:
	"""Neutralize formula-like text cells to mitigate spreadsheet formula injection."""
	text = '' if value is None else str(value)
	if text.lstrip(' \t\r\n').startswith(('=', '+', '-', '@')):
		return "'" + text
	return text
