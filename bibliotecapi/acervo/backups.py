"""Cópias consistentes em arquivos privados; caminhos nunca vêm da requisição."""
from contextlib import closing
from datetime import datetime
import os
from pathlib import Path
import sqlite3
import stat
from uuid import uuid4

from django.conf import settings


def criar_copia_sqlite(destino=None):
    banco = settings.DATABASES['default']
    origem = Path(banco['NAME'])
    if banco['ENGINE'] != 'django.db.backends.sqlite3' or not origem.is_file():
        raise ValueError('O banco SQLite em arquivo não foi encontrado.')
    pasta = Path(destino or settings.BACKUP_DIR)
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / f'biblioteca-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex}.sqlite3'
    arquivo.touch(mode=0o600, exist_ok=False)
    try:
        with closing(sqlite3.connect(origem.resolve().as_uri() + '?mode=ro', uri=True, timeout=30)) as fonte:
            with closing(sqlite3.connect(arquivo)) as copia:
                fonte.backup(copia, pages=256)
                if copia.execute('PRAGMA quick_check').fetchone() != ('ok',):
                    raise ValueError('A verificação do backup não foi aprovada.')
    except Exception:
        arquivo.unlink(missing_ok=True)
        raise
    return arquivo


def abrir_backup(nome):
    if Path(nome).name != nome or not nome.startswith('biblioteca-') or not nome.endswith('.sqlite3'):
        raise FileNotFoundError
    arquivo = Path(settings.BACKUP_DIR).resolve() / nome
    descritor = os.open(arquivo, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    if not stat.S_ISREG(os.fstat(descritor).st_mode):
        os.close(descritor)
        raise FileNotFoundError
    return os.fdopen(descritor, 'rb')
