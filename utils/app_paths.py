"""Writable desktop data paths and non-destructive adoption of older installations."""

import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


def installation_dir() -> Path:
	if getattr(sys, 'frozen', False):
		return Path(sys.executable).resolve().parent
	return Path(__file__).resolve().parent.parent


def app_data_dir(*, create: bool = True) -> Path:
	if sys.platform == 'win32':
		base = Path(os.environ.get('LOCALAPPDATA') or Path.home())
	else:
		base = Path.home() / '.config'
	path = base / 'CloudPOS'
	if create:
		path.mkdir(parents=True, exist_ok=True)
	return path


def adopt_legacy_file(filename: str, *, database: bool = False) -> Path:
	"""Copy a legacy file once, preserving originals and existing destinations.

	SQLite's backup API includes committed WAL contents. Publishing a hard link
	from a completed temporary file is atomic and refuses to replace another
	process's destination. Both files live on the same filesystem.
	"""
	destination = app_data_dir() / filename
	source = installation_dir() / filename
	if destination.exists() or not source.is_file() or source == destination:
		return destination
	fd, temporary = tempfile.mkstemp(prefix=f'.{filename}-', dir=destination.parent)
	os.close(fd)
	try:
		if database:
			original = sqlite3.connect(source.as_uri() + '?mode=ro', uri=True)
			try:
				copy = sqlite3.connect(temporary)
				try:
					original.backup(copy)
					if copy.execute('PRAGMA quick_check').fetchone() != ('ok',):
						raise RuntimeError(
							'La base anterior no superó la comprobación de integridad.'
						)
				finally:
					copy.close()
			finally:
				original.close()
		else:
			shutil.copyfile(source, temporary)
		try:
			os.link(temporary, destination)
		except FileExistsError:
			pass
	finally:
		os.unlink(temporary)
	return destination
