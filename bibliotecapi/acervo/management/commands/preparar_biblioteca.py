from getpass import getpass

from django.contrib.auth import get_user_model
from acervo.acessos import configurar_grupos, criar_usuario
from acervo.models import PerfilAcesso
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Cria o acesso inicial da equipe com senha informada de forma interativa.'

    def add_arguments(self, parser):
        parser.add_argument('--se-vazio', action='store_true', help='Só solicita usuário se ainda não houver equipe.')

    def handle(self, *args, **options):
        configurar_grupos()
        usuarios = get_user_model()
        if options['se_vazio'] and PerfilAcesso.objects.filter(papel='gestor', usuario__is_active=True).exists():
            return
        nome = input('Nome de acesso da equipe: ').strip()
        if not nome or usuarios.objects.filter(username=nome).exists():
            raise CommandError('Informe um nome de acesso novo e não vazio.')
        senha = getpass('Senha: ')
        if senha != getpass('Repita a senha: '):
            raise CommandError('As senhas não coincidem.')
        try:
            criar_usuario(None, username=nome, papel='gestor', senha=senha, exigir_troca=False)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc
        self.stdout.write(self.style.SUCCESS('Gestor criado. Os próximos usuários podem ser cadastrados pela interface.'))
