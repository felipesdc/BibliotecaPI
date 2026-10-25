from datetime import datetime
from pathlib import Path
import sqlite3

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Cria cópia consistente do SQLite local, incluindo acervo, leitores, contas e histórico.'

    def add_arguments(self, parser):
        parser.add_argument('--destino', default=str(settings.BACKUP_DIR))

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        if db['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('Este comando exige SQLite.')
        origem = Path(db['NAME'])
        if not origem.exists():
            raise CommandError('Banco não encontrado. Execute migrate antes.')
        destino = Path(options['destino'])
        destino.mkdir(parents=True, exist_ok=True)
        arquivo = destino / f'biblioteca-{datetime.now():%Y%m%d-%H%M%S-%f}.sqlite3'
        arquivo.touch(mode=0o600, exist_ok=False)
        with sqlite3.connect(origem) as fonte, sqlite3.connect(arquivo) as copia:
            fonte.backup(copia)
        self.stdout.write(self.style.SUCCESS(f'Backup criado: {arquivo}'))
