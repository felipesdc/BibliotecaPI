from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver
from .acessos import perfil_de
from .middleware import CHAVE_VERSAO


@receiver(user_logged_in, dispatch_uid='biblioteca_versao_login')
def registrar_versao_sessao(sender, request, user, **kwargs):
    perfil = perfil_de(user)
    if request is not None and perfil:
        request.session[CHAVE_VERSAO] = perfil.versao_sessao
