from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import resolve, Resolver404

from .acessos import perfil_de

CHAVE_VERSAO = 'biblioteca_versao_sessao'


class ControleAcessoMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            perfil = perfil_de(request.user)
            if perfil:
                if request.session.get(CHAVE_VERSAO) != perfil.versao_sessao:
                    logout(request)
                    messages.info(request, 'Seu acesso foi atualizado. Entre novamente.')
                    return redirect('login')
                try:
                    rota = resolve(request.path_info).url_name
                except Resolver404:
                    rota = None
                if perfil.exigir_troca_senha and rota not in {'password_change', 'password_change_done', 'logout', 'health'}:
                    return redirect('password_change')
        return self.get_response(request)
