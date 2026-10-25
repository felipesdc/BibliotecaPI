from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = 'Cria o acesso inicial da equipe com senha informada de forma interativa.'

    def add_arguments(self, parser):
        parser.add_argument('--se-vazio', action='store_true', help='Só solicita usuário se ainda não houver equipe.')

    def handle(self, *args, **options):
        with transaction.atomic():
            grupo, _ = Group.objects.get_or_create(name='Bibliotecários')
            grupo.permissions.set(Permission.objects.filter(content_type__app_label='acervo'))
        usuarios = get_user_model()
        if options['se_vazio'] and usuarios.objects.filter(groups=grupo, is_active=True).exists():
            return
        nome = input('Nome de acesso da equipe: ').strip()
        if not nome or usuarios.objects.filter(username=nome).exists():
            raise CommandError('Informe um nome de acesso novo e não vazio.')
        senha = getpass('Senha: ')
        if senha != getpass('Repita a senha: '):
            raise CommandError('As senhas não coincidem.')
        usuario = usuarios(username=nome)
        try:
            usuario.full_clean(exclude=['password'])
            validate_password(senha, usuario)
        except ValidationError as exc:
            raise CommandError('; '.join(exc.messages)) from exc
        with transaction.atomic():
            usuario.set_password(senha)
            usuario.save()
            usuario.groups.add(grupo)
        self.stdout.write(self.style.SUCCESS('Acesso da equipe criado. Entre com esse usuário na ferramenta.'))
