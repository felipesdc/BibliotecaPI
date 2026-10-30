from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import PasswordChangeView
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.decorators.http import require_GET, require_http_methods

from . import acessos
from .forms_acessos import CriarUsuarioForm, EditarUsuarioForm, RedefinirSenhaForm, AlterarSituacaoForm
from .middleware import CHAVE_VERSAO
from .models import PerfilAcesso


def alvo_editavel(pk):
    usuario = get_object_or_404(get_user_model(), pk=pk)
    if acessos.conta_protegida(usuario):
        raise PermissionDenied('Esta conta técnica é protegida. Utilize a administração técnica.')
    return usuario


def dados_perfil(usuario):
    perfil = acessos.perfil_de(usuario)
    return {'papel': perfil.papel if perfil else 'consulta', 'versao': perfil.versao_sessao if perfil else 0}


@login_required
@permission_required('acervo.manage_usuarios', raise_exception=True)
@require_GET
def usuarios(request):
    lista = get_user_model().objects.select_related('perfil_biblioteca').prefetch_related('groups', 'user_permissions').order_by('username', 'pk')
    q = request.GET.get('q', '').strip()
    if q:
        lista = lista.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
    papel = request.GET.get('papel', '')
    if papel in acessos.GRUPOS:
        lista = lista.filter(perfil_biblioteca__papel=papel)
    situacao = request.GET.get('situacao', '')
    if situacao in {'ativo', 'inativo'}:
        lista = lista.filter(is_active=situacao == 'ativo')
    pagina = Paginator(lista, 20).get_page(request.GET.get('page'))
    for usuario in pagina:
        usuario.acesso_protegido = acessos.conta_protegida(usuario)
    return render(request, 'acervo/usuarios.html', {'page_obj': pagina, 'is_paginated': pagina.has_other_pages(), 'papeis': PerfilAcesso.Papel.choices})


@login_required
@permission_required('acervo.manage_usuarios', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def criar_usuario(request):
    form = CriarUsuarioForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        dados = {k: form.cleaned_data[k] for k in ['username', 'first_name', 'last_name', 'email', 'papel']}
        try:
            usuario = acessos.criar_usuario(request.user, **dados, senha=form.cleaned_data['password1'])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Conta criada. Entregue a senha temporária ao usuário por um canal reservado; ele deverá trocá-la ao entrar.')
            return redirect('editar-usuario', pk=usuario.pk)
    return render(request, 'acervo/usuario_form.html', {'form': form})


@login_required
@permission_required('acervo.manage_usuarios', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def editar_usuario(request, pk):
    usuario = alvo_editavel(pk)
    form = EditarUsuarioForm(request.POST if request.method == 'POST' else None, instance=usuario, initial=dados_perfil(usuario), proprio=pk == request.user.pk)
    if request.method == 'POST' and form.is_valid():
        try:
            atualizado = acessos.editar_usuario(request.user, pk, **{k: form.cleaned_data[k] for k in ['first_name', 'last_name', 'email', 'papel', 'versao']})
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if atualizado.pk == request.user.pk:
                request.session[CHAVE_VERSAO] = atualizado.perfil_biblioteca.versao_sessao
            messages.success(request, 'Cadastro atualizado. Os outros acessos dessa conta precisarão entrar novamente.')
            return redirect('editar-usuario', pk=pk)
    return render(request, 'acervo/usuario_form.html', {'form': form, 'conta': usuario, 'eventos': usuario.eventos_acesso.select_related('realizado_por')[:15]})


@login_required
@permission_required('acervo.manage_usuarios', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def situacao_usuario(request, pk, ativo):
    usuario = alvo_editavel(pk)
    form = AlterarSituacaoForm(request.POST if request.method == 'POST' else None, initial=dados_perfil(usuario))
    if request.method == 'POST' and form.is_valid():
        try:
            acessos.definir_ativo(request.user, pk, ativo=ativo, versao=form.cleaned_data['versao'])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Conta reativada.' if ativo else 'Conta desativada. Os registros anteriores foram preservados.')
            return redirect('usuarios')
    return render(request, 'acervo/usuario_situacao.html', {'form': form, 'conta': usuario, 'ativar': ativo})


@login_required
@permission_required('acervo.manage_usuarios', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def redefinir_senha(request, pk):
    usuario = alvo_editavel(pk)
    if pk == request.user.pk:
        return redirect('password_change')
    form = RedefinirSenhaForm(usuario, request.POST if request.method == 'POST' else None, initial=dados_perfil(usuario))
    if request.method == 'POST' and form.is_valid():
        try:
            acessos.redefinir_senha(request.user, pk, senha=form.cleaned_data['new_password1'], versao=form.cleaned_data['versao'])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Senha temporária definida. O usuário deverá trocá-la no próximo acesso.')
            return redirect('editar-usuario', pk=pk)
    return render(request, 'acervo/usuario_senha.html', {'form': form, 'conta': usuario})


class AlterarMinhaSenha(LoginRequiredMixin, PasswordChangeView):
    template_name = 'registration/password_change_form.html'
    success_url = reverse_lazy('password_change_done')

    def form_valid(self, form):
        with transaction.atomic():
            atual = get_user_model().objects.select_for_update().get(pk=self.request.user.pk)
            perfil = PerfilAcesso.objects.select_for_update().filter(usuario=atual).first()
            versao_alterada = perfil and self.request.session.get(CHAVE_VERSAO) != perfil.versao_sessao
            if atual.password != self.request.user.password or not atual.is_active or versao_alterada:
                form.add_error(None, 'Seu acesso mudou durante a operação. Entre novamente antes de continuar.')
                return self.form_invalid(form)
            form.user = atual
            usuario = form.save()
            if perfil:
                perfil.exigir_troca_senha = False
                perfil.versao_sessao += 1
                perfil.save()
            acessos.registrar(usuario, usuario, 'senha_alterada')
            update_session_auth_hash(self.request, usuario)
            if perfil:
                self.request.session[CHAVE_VERSAO] = perfil.versao_sessao
        return redirect(self.success_url)
