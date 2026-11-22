from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from acervo.backups import criar_copia_sqlite


class Command(BaseCommand):
    help = 'Cria cópia consistente do SQLite local, incluindo acervo, leitores, contas e histórico.'

    def add_arguments(self, parser):
        parser.add_argument('--destino', default=str(settings.BACKUP_DIR))

    def handle(self, *args, **options):
        try:
            arquivo = criar_copia_sqlite(options['destino'])
        except (OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f'Backup criado: {arquivo}'))
