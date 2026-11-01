"""Atendimento de balcão, renderizado no servidor e sem dependências externas."""
from datetime import timedelta
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core import signing
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .circulacao import registrar_emprestimo, registrar_devolucao, registrar_renovacao, retrato_emprestimo
from .models import Emprestimo, Leitor, LivroCopia, PoliticaCirculacao

SALT = 'acervo.atendimento.emprestimo'


class OperacaoForm(forms.Form):
    acao = forms.ChoiceField(choices=[('emprestar', 'Emprestar'), ('renovar', 'Renovar'), ('devolver', 'Devolver')])
    copia = forms.UUIDField()
    prazo = forms.DateField(required=False, widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}))
    confirmacao = forms.CharField(required=False)

    def clean(self):
        dados = super().clean()
        if dados.get('acao') in ('emprestar', 'renovar') and not dados.get('prazo'):
            self.add_error('prazo', 'Informe a data de devolução.')
        return dados


@login_required
@permission_required(('acervo.view_leitor', 'acervo.marca_devolucao'), raise_exception=True)
@require_http_methods(['GET', 'POST'])
def atendimento(request):
    origem = request.POST if request.method == 'POST' else request.GET
    leitor_id = origem.get('leitor', '')
    if leitor_id and (not leitor_id.isdecimal() or len(leitor_id) > 18):
        from django.http import Http404
        raise Http404
    leitor = get_object_or_404(Leitor, pk=leitor_id) if leitor_id else None
    busca_leitor = origem.get('busca_leitor', '').strip()[:100]
    busca_exemplar = origem.get('busca_exemplar', '').strip()[:100]
    politica = PoliticaCirculacao.atual()
    form = OperacaoForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        if not leitor:
            form.add_error(None, 'Selecione o leitor antes de confirmar uma operação.')
        elif form.is_valid():
            dados = form.cleaned_data
            copia = get_object_or_404(LivroCopia.objects.select_related('livro'), pk=dados['copia'])
            try:
                if dados['acao'] == 'emprestar':
                    registrar_emprestimo(copia=copia, leitor=leitor, prazo=dados['prazo'], operador=request.user)
                    mensagem = f'Empréstimo confirmado: {copia.livro or "Sem título"} · {copia.codigo} para {leitor.nome}. Devolver até {dados["prazo"]:%d/%m/%Y}.'
                else:
                    try:
                        esperado = signing.loads(dados['confirmacao'], salt=SALT, max_age=3600)
                    except signing.BadSignature:
                        raise ValidationError('A confirmação expirou ou é inválida. Atualize o atendimento.')
                    if esperado.get('copia') != str(copia.pk) or esperado.get('leitor') != leitor.pk:
                        raise ValidationError('O exemplar não pertence ao atendimento deste leitor.')
                    if dados['acao'] == 'devolver':
                        registrar_devolucao(copia_id=copia.pk, operador=request.user, esperado=esperado)
                        mensagem = f'Devolução confirmada: {copia.livro or "Sem título"} · {copia.codigo}, de {leitor.nome}. Exemplar disponível novamente.'
                    else:
                        registrar_renovacao(copia_id=copia.pk, prazo=dados['prazo'], esperado=esperado)
                        mensagem = f'Renovação confirmada: {copia.codigo}, de {leitor.nome}. Novo prazo: {dados["prazo"]:%d/%m/%Y}.'
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(request, mensagem)
                return redirect(reverse('atendimento') + '?' + urlencode({'leitor': leitor.pk, 'busca_exemplar': busca_exemplar}))
    leitores = Leitor.objects.none()
    if busca_leitor:
        filtro = Q(nome__icontains=busca_leitor)
        if busca_leitor.isdecimal() and len(busca_leitor) <= 18:
            filtro |= Q(pk=int(busca_leitor))
        leitores = Leitor.objects.filter(filtro).order_by('nome', 'pk')[:21]
    exemplares = LivroCopia.objects.none()
    if busca_exemplar:
        exemplares = LivroCopia.objects.select_related('livro__autor').filter(
            Q(codigo__icontains=busca_exemplar) | Q(livro__titulo__icontains=busca_exemplar) |
            Q(livro__isbn__icontains=busca_exemplar)).order_by('codigo', 'pk')[:21]
    abertos = list(LivroCopia.objects.filter(leitor=leitor, estado='e').select_related('livro').order_by('data_devolucao', 'pk')) if leitor else []
    registros = dict(Emprestimo.objects.filter(copia__in=abertos, devolvido_em__isnull=True).values_list('copia_id', 'pk')) if abertos else {}
    for copia in abertos:
        copia.confirmacao = signing.dumps(retrato_emprestimo(copia, registros.get(copia.pk)), salt=SALT)
    hoje = timezone.localdate()
    bloqueios = []
    atrasados = sum(bool(c.data_devolucao and c.data_devolucao < hoje) for c in abertos)
    if leitor:
        if not leitor.ativo:
            bloqueios.append('Leitor inativo: novos empréstimos indisponíveis.')
        if politica.limite_emprestimos and len(abertos) >= politica.limite_emprestimos:
            bloqueios.append('Limite de empréstimos atingido. Registre uma devolução para liberar novos empréstimos.')
        if politica.bloquear_atrasados and atrasados:
            bloqueios.append('Há devoluções em atraso. Regularize antes de um novo empréstimo.')
    return render(request, 'acervo/atendimento.html', {
        'leitor': leitor, 'busca_leitor': busca_leitor, 'busca_exemplar': busca_exemplar,
        'leitores': list(leitores), 'exemplares': list(exemplares), 'abertos': abertos,
        'atrasados': atrasados, 'bloqueios': bloqueios, 'politica': politica,
        'prazo_sugerido': hoje + timedelta(days=politica.prazo_padrao),
        'renovacao_sugerida': hoje + timedelta(days=21), 'hoje': hoje,
        'max_renovacao': hoje + timedelta(days=28), 'form': form,
        'prazo_informado': origem.get('prazo', ''), 'copia_operacao': origem.get('copia', ''),
        'acao_operacao': origem.get('acao', ''),
    })
