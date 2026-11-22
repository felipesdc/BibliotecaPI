import logging
import sqlite3
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction, DatabaseError
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST
from django.core.paginator import Paginator

from .backups import criar_copia_sqlite, abrir_backup
from .forms import ConfiguracaoBibliotecaForm, EtiquetasForm, ReservaForm, FiltroReservasForm
from .models import BackupRegistro, ConfiguracaoBiblioteca, Leitor, Livro, LivroCopia, Reserva
from .reservas import reservar, cancelar

logger = logging.getLogger(__name__)


@never_cache
@login_required
@permission_required('acervo.manage_backups', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def backups(request):
    if request.method == 'POST':
        arquivo = None
        try:
            arquivo = criar_copia_sqlite()
            registro = BackupRegistro.objects.create(nome=arquivo.name, tamanho=arquivo.stat().st_size, criado_por=request.user)
        except (OSError, ValueError, sqlite3.Error, DatabaseError):
            if arquivo:
                arquivo.unlink(missing_ok=True)
            logger.exception('Não foi possível gerar o backup da biblioteca.')
            messages.error(request, 'Não foi possível gerar a cópia. Tente novamente ou solicite suporte.')
        else:
            messages.success(request, 'Backup completo gerado. Guarde a cópia em um local protegido fora deste computador.')
            return redirect('backups')
    registros = list(BackupRegistro.objects.select_related('criado_por')[:25])
    for item in registros:
        caminho = Path(settings.BACKUP_DIR) / item.nome
        item.disponivel = caminho.is_file() and not caminho.is_symlink()
    return render(request, 'acervo/backups.html', {'registros': registros, 'ultimo': registros[0] if registros else None})


@never_cache
@login_required
@permission_required('acervo.manage_backups', raise_exception=True)
@require_http_methods(['GET'])
def baixar_backup(request, pk):
    registro = get_object_or_404(BackupRegistro, pk=pk)
    try:
        arquivo = abrir_backup(registro.nome)
    except OSError:
        raise Http404('Cópia não disponível no armazenamento.')
    resposta = FileResponse(arquivo, as_attachment=True, filename=registro.nome, content_type='application/octet-stream')
    resposta['X-Content-Type-Options'] = 'nosniff'
    return resposta


@login_required
@permission_required('acervo.change_configuracaobiblioteca', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def configuracao(request):
    atual = ConfiguracaoBiblioteca.atual()
    form = ConfiguracaoBibliotecaForm(request.POST if request.method == 'POST' else None, instance=atual)
    if request.method == 'POST' and form.is_valid():
        dados = form.cleaned_data
        with transaction.atomic():
            # A criação inicial não sobrescreve uma configuração salva em outra aba.
            ConfiguracaoBiblioteca.objects.get_or_create(pk=1)
            alteradas = ConfiguracaoBiblioteca.objects.filter(pk=1, versao=dados['versao']).update(
                **{k: dados[k] for k in ['nome', 'email', 'telefone', 'orientacoes']}, versao=dados['versao'] + 1)
        if alteradas:
            messages.success(request, 'Identidade e orientações da biblioteca atualizadas.')
            return redirect('configuracao')
        form.add_error(None, 'A configuração mudou em outra operação. Atualize a página antes de salvar novamente.')
    return render(request, 'acervo/configuracao.html', {'form': form})


@login_required
@permission_required('acervo.print_etiquetas', raise_exception=True)
@require_http_methods(['GET', 'POST'])
def etiquetas(request):
    busca = request.GET.get('q', '').strip()[:100]
    itens = LivroCopia.objects.select_related('livro').order_by('livro__titulo', 'codigo', 'pk')
    if busca:
        itens = itens.filter(Q(codigo__icontains=busca) | Q(livro__titulo__icontains=busca) | Q(livro__isbn__icontains=busca))
    livro = request.GET.get('livro', '')
    if livro:
        if not livro.isdecimal() or len(livro) > 18:
            raise Http404
        itens = itens.filter(livro_id=livro)
    form = EtiquetasForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        return render(request, 'acervo/etiquetas_impressao.html', {'itens': form.cleaned_data['exemplares']})
    # Campo de seleção contém só os 60 resultados visíveis; validação POST aceita IDs reais.
    visiveis = list(itens[:61])
    form.fields['exemplares'].queryset = LivroCopia.objects.filter(pk__in=[i.pk for i in visiveis[:60]]).select_related('livro').order_by('livro__titulo', 'codigo', 'pk')
    return render(request, 'acervo/etiquetas.html', {'form': form, 'busca': busca, 'mais_resultados': len(visiveis) > 60, 'livro_id': livro, 'tem_exemplares': bool(visiveis)})


@login_required
@permission_required(('acervo.manage_reservas', 'acervo.view_leitor', 'acervo.marca_devolucao'), raise_exception=True)
@require_http_methods(['GET'])
def reservas(request):
    form = FiltroReservasForm(request.GET)
    livro_id = request.GET.get('livro', '')
    livro_filtrado = None
    if livro_id:
        if not livro_id.isdecimal() or len(livro_id) > 18:
            raise Http404
        livro_filtrado = get_object_or_404(Livro, pk=livro_id)
    itens = Reserva.objects.select_related('livro', 'leitor', 'criado_por', 'encerrado_por').order_by('-criado_em', '-pk')
    if form.is_valid():
        dados = form.cleaned_data
        estado = dados.get('situacao')
        if estado != 'todas':
            itens = itens.filter(estado=estado or 'a')
        if not estado:
            itens = itens.order_by('livro__titulo', 'criado_em', 'pk')
        busca = dados.get('q', '')
        if busca:
            filtro = Q(livro__titulo__icontains=busca) | Q(leitor__nome__icontains=busca)
            if busca.isdecimal() and len(busca) <= 18:
                filtro |= Q(leitor_id=int(busca))
            itens = itens.filter(filtro)
    else:
        itens = itens.none()
    if livro_filtrado:
        itens = itens.filter(livro=livro_filtrado)
    pagina = Paginator(itens, 20).get_page(request.GET.get('page'))
    livros = {r.livro_id for r in pagina}
    filas = Reserva.objects.filter(livro_id__in=livros, estado='a', leitor__ativo=True).order_by('livro_id', 'criado_em', 'pk')
    posicoes, totais = {}, {}
    for item in filas:
        totais[item.livro_id] = totais.get(item.livro_id, 0) + 1
        posicoes[item.pk] = totais[item.livro_id]
    livres = dict(LivroCopia.objects.filter(livro_id__in=livros, estado='d').values('livro_id').annotate(total=Count('pk')).values_list('livro_id', 'total'))
    for item in pagina:
        item.posicao = posicoes.get(item.pk)
        item.pode_retirar = bool(item.posicao and item.posicao <= livres.get(item.livro_id, 0))
    return render(request, 'acervo/reservas.html', {'form': form, 'page_obj': pagina, 'object_list': pagina.object_list,
                  'is_paginated': pagina.has_other_pages(), 'paginator': pagina.paginator, 'livro_filtrado': livro_filtrado})


@login_required
@permission_required(('acervo.manage_reservas', 'acervo.view_leitor', 'acervo.marca_devolucao'), raise_exception=True)
@require_http_methods(['GET', 'POST'])
def criar_reserva(request, pk):
    livro = get_object_or_404(Livro, pk=pk)
    form = ReservaForm(request.POST if request.method == 'POST' else None, initial={'leitor': request.GET.get('leitor', '')})
    leitor_id = request.POST.get('leitor', '') if request.method == 'POST' else request.GET.get('leitor', '')
    leitor = Leitor.objects.filter(pk=leitor_id).first() if leitor_id.isdecimal() and len(leitor_id) <= 18 else None
    busca = request.GET.get('q', '').strip()[:100]
    leitores = Leitor.objects.filter(ativo=True, nome__icontains=busca)[:21] if busca else []
    if request.method == 'POST' and form.is_valid():
        try:
            reservar(livro=livro, leitor=form.cleaned_data['leitor'], operador=request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Reserva registrada. A posição é definida pela ordem de entrada dos leitores ativos.')
            return redirect('reservas')
    return render(request, 'acervo/reserva_form.html', {'form': form, 'livro': livro, 'leitor': leitor, 'busca': busca, 'leitores': list(leitores)})


@login_required
@permission_required(('acervo.manage_reservas', 'acervo.view_leitor', 'acervo.marca_devolucao'), raise_exception=True)
@require_POST
def cancelar_reserva(request, pk):
    get_object_or_404(Reserva, pk=pk)
    try:
        cancelar(reserva_id=pk, operador=request.user)
    except ValidationError as exc:
        messages.info(request, ' '.join(exc.messages))
    else:
        messages.success(request, 'Reserva cancelada. Os demais leitores avançam na fila.')
    return redirect('reservas')
