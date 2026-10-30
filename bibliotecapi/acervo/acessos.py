"""Perfis de biblioteca não concedem acesso ao Django Admin nem a permissões auth.*."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .models import EventoAcesso, PerfilAcesso

GRUPOS = {'gestor': 'Biblioteca · Gestor', 'atendente': 'Biblioteca · Atendente', 'consulta': 'Biblioteca · Consulta interna'}
CATALOGO = [f'view_{m}' for m in ['livro', 'livrocopia', 'autor', 'genero', 'lingua']]
PERMISSOES = {
    'gestor': [f'{a}_{m}' for m in ['livro', 'livrocopia', 'autor', 'genero', 'lingua', 'leitor'] for a in ['view', 'add', 'change', 'delete']] + ['marca_devolucao', 'view_relatorios', 'manage_usuarios', 'export_acervo'],
    'atendente': CATALOGO + ['view_leitor', 'add_leitor', 'change_leitor', 'marca_devolucao'],
    'consulta': CATALOGO,
}


def configurar_grupos():
    grupos = {}
    for papel, nome in GRUPOS.items():
        grupo, _ = Group.objects.get_or_create(name=nome)
        grupo.permissions.set(Permission.objects.filter(content_type__app_label='acervo', codename__in=PERMISSOES[papel]))
        grupos[papel] = grupo
    return grupos


def perfil_de(usuario):
    try:
        return usuario.perfil_biblioteca
    except PerfilAcesso.DoesNotExist:
        return None


def conta_protegida(usuario):
    return usuario.is_superuser or usuario.is_staff or usuario.user_permissions.exists() or usuario.groups.exclude(name__in=GRUPOS.values()).exists()


def conferir_gestor(ator):
    if ator is not None and not ator.has_perm('acervo.manage_usuarios'):
        raise PermissionDenied


def conferir_alvo(ator, usuario_id, versao):
    conferir_gestor(ator)
    usuario = get_user_model().objects.select_for_update().get(pk=usuario_id)
    if conta_protegida(usuario):
        raise PermissionDenied('Contas técnicas ou com permissões personalizadas são administradas separadamente.')
    perfil = PerfilAcesso.objects.select_for_update().filter(usuario=usuario).first()
    if versao != (perfil.versao_sessao if perfil else 0):
        raise ValidationError('Esta conta foi alterada por outra operação. Atualize a página antes de continuar.')
    return usuario, perfil


def aplicar_papel(usuario, papel, perfil=None):
    if papel not in GRUPOS:
        raise ValidationError('Perfil inválido.')
    grupo = Group.objects.get(name=GRUPOS[papel])
    usuario.groups.set([grupo])
    usuario.user_permissions.clear()
    if perfil is None:
        perfil = PerfilAcesso.objects.create(usuario=usuario, papel=papel)
    else:
        perfil.papel = papel
    return perfil


def registrar(ator, usuario, acao, **detalhes):
    EventoAcesso.objects.create(usuario=usuario, realizado_por=ator, acao=acao, detalhes=detalhes)


def conferir_ultimo_gestor(usuario, perfil):
    if usuario.is_active and perfil and perfil.papel == 'gestor' and not PerfilAcesso.objects.filter(papel='gestor', usuario__is_active=True).exclude(usuario=usuario).exists():
        raise ValidationError('Mantenha pelo menos um gestor ativo na biblioteca.')


@transaction.atomic
def criar_usuario(ator, *, username, first_name='', last_name='', email='', papel, senha, exigir_troca=True, ativo=True):
    conferir_gestor(ator)
    if get_user_model().objects.filter(username__iexact=username).exists():
        raise ValidationError('Esse nome de acesso já está em uso.')
    usuario = get_user_model()(username=username, first_name=first_name, last_name=last_name, email=email, is_active=ativo)
    usuario.full_clean(exclude=['password'])
    validate_password(senha, usuario)
    usuario.set_password(senha)
    usuario.save()
    perfil = aplicar_papel(usuario, papel)
    perfil.exigir_troca_senha = exigir_troca
    perfil.save()
    registrar(ator, usuario, 'criado', papel=papel, ativo=ativo)
    return usuario


@transaction.atomic
def editar_usuario(ator, usuario_id, *, first_name, last_name, email, papel, versao):
    usuario, perfil = conferir_alvo(ator, usuario_id, versao)
    anterior = perfil.papel if perfil else None
    if papel != anterior:
        if usuario.pk == ator.pk:
            raise ValidationError('Peça a outro gestor para alterar seu perfil.')
        if papel != 'gestor':
            conferir_ultimo_gestor(usuario, perfil)
    usuario.first_name, usuario.last_name, usuario.email = first_name, last_name, email
    usuario.full_clean(exclude=['password'])
    usuario.save(update_fields=['first_name', 'last_name', 'email'])
    perfil = aplicar_papel(usuario, papel, perfil)
    perfil.versao_sessao += 1
    perfil.save()
    registrar(ator, usuario, 'perfil_alterado' if anterior != papel else 'editado', papel_anterior=anterior, papel=papel)
    return usuario


@transaction.atomic
def definir_ativo(ator, usuario_id, *, ativo, versao):
    usuario, perfil = conferir_alvo(ator, usuario_id, versao)
    if usuario.pk == ator.pk:
        raise ValidationError('Você não pode desativar sua própria conta.')
    if not ativo:
        conferir_ultimo_gestor(usuario, perfil)
    if usuario.is_active != ativo:
        usuario.is_active = ativo
        usuario.save(update_fields=['is_active'])
        if perfil is None:
            perfil = aplicar_papel(usuario, 'consulta')
        perfil.versao_sessao += 1
        perfil.save()
        registrar(ator, usuario, 'reativado' if ativo else 'desativado')
    return usuario


@transaction.atomic
def redefinir_senha(ator, usuario_id, *, senha, versao):
    usuario, perfil = conferir_alvo(ator, usuario_id, versao)
    if usuario.pk == ator.pk:
        raise ValidationError('Use “Alterar minha senha” para sua própria conta.')
    validate_password(senha, usuario)
    usuario.set_password(senha)
    usuario.save(update_fields=['password'])
    perfil = perfil or aplicar_papel(usuario, 'consulta')
    perfil.exigir_troca_senha = True
    perfil.versao_sessao += 1
    perfil.save()
    registrar(ator, usuario, 'senha_redefinida')
