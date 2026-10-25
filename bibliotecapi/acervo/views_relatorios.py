import csv
from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required, permission_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .forms import PeriodoRelatorioForm
from .relatorios import gerar_relatorio
from .views import celula_csv

TIPOS_EXPORTACAO = {'resumo', 'mensal', 'atrasos', 'titulos', 'leitores', 'acervo', 'emprestimos', 'devolucoes'}


def nome_leitor(item):
    return item.leitor.nome if item.leitor else str(item.tomador or 'Não informado')


def linhas_csv(tipo, r):
    if tipo == 'resumo':
        yield ['Escopo', 'Inicio', 'Fim', 'Indicador', 'Valor']
        for chave, valor in r['estoque'].items():
            yield ['Situação atual', r['hoje'], r['hoje'], chave, valor]
        for chave, valor in r['periodo'].items():
            yield ['Movimentação no período', r['inicio'], r['fim'], chave, valor if valor is not None else 'Sem dados']
    elif tipo == 'mensal':
        yield ['Mes', 'Emprestimos iniciados', 'Devolucoes realizadas', 'Inicio do filtro', 'Fim do filtro']
        for linha in r['mensal']:
            yield [linha['mes'].strftime('%Y-%m'), linha['emprestimos'], linha['devolucoes'], r['inicio'], r['fim']]
    elif tipo == 'atrasos':
        yield ['Data de referencia', 'Codigo', 'Titulo', 'Leitor', 'Prazo', 'Dias em atraso']
        for copia in r['atrasos']:
            yield [r['hoje'], copia.codigo, copia.livro.titulo if copia.livro else 'Não informado', nome_leitor(copia), copia.data_devolucao, (r['hoje'] - copia.data_devolucao).days]
    elif tipo == 'titulos':
        yield ['Titulo', 'Autor', 'Emprestimos no periodo', 'Inicio', 'Fim']
        for livro in r['livros_ranking']:
            yield [livro.titulo, livro.autor or '', livro.total_emprestimos, r['inicio'], r['fim']]
    elif tipo == 'leitores':
        yield ['Id', 'Leitor', 'Cadastro ativo hoje', 'Emprestimos no periodo', 'Inicio', 'Fim']
        for leitor in r['leitores_atividade']:
            yield [leitor.pk, leitor.nome, 'Sim' if leitor.ativo else 'Não', leitor.total_emprestimos, r['inicio'], r['fim']]
    elif tipo == 'acervo':
        yield ['Data de referencia', 'Genero', 'Titulos', 'Exemplares']
        for genero in r['generos_acervo']:
            yield [r['hoje'], genero.nome, genero.titulos, genero.exemplares]
        yield [r['hoje'], 'Titulos sem genero', r['estoque']['sem_genero'], '']
    elif tipo in {'emprestimos', 'devolucoes'}:
        yield ['Id', 'Codigo', 'Titulo', 'Leitor', 'Emprestado em', 'Prazo', 'Devolvido em', 'Inicio', 'Fim']
        eventos = r['emprestimos_periodo'] if tipo == 'emprestimos' else r['devolucoes_periodo']
        for evento in eventos:
            yield [evento.pk, evento.copia.codigo, evento.copia.livro.titulo if evento.copia.livro else 'Não informado', nome_leitor(evento), timezone.localtime(evento.criado_em).isoformat(), evento.prazo, timezone.localtime(evento.devolvido_em).isoformat() if evento.devolvido_em else '', r['inicio'], r['fim']]


@login_required
@permission_required('acervo.view_relatorios', raise_exception=True)
@require_GET
def relatorios(request):
    hoje = timezone.localdate()
    dados = {'inicio': request.GET.get('inicio', (hoje - timedelta(days=179)).isoformat()), 'fim': request.GET.get('fim', hoje.isoformat())}
    form = PeriodoRelatorioForm(dados)
    if not form.is_valid():
        return render(request, 'acervo/relatorios.html', {'form': form}, status=400)
    tipo = request.GET.get('tipo', 'resumo')
    if request.GET.get('formato') == 'csv' and tipo not in TIPOS_EXPORTACAO:
        return HttpResponse('Tipo de relatório inválido.', status=400)
    relatorio = gerar_relatorio(**form.cleaned_data)
    if request.GET.get('formato') == 'csv':
        resposta = HttpResponse(content_type='text/csv; charset=utf-8')
        resposta['Content-Disposition'] = f'attachment; filename="relatorio-{tipo}-{hoje:%Y%m%d}.csv"'
        resposta.write('\ufeff')
        writer = csv.writer(resposta, delimiter=';')
        for linha in linhas_csv(tipo, relatorio):
            writer.writerow([celula_csv(valor) if valor is not None else '' for valor in linha])
        return resposta
    relatorio.update({'form': form, 'parametros': urlencode(dados), 'top_livros': relatorio['livros_ranking'][:10], 'top_leitores': relatorio['leitores_atividade'].filter(total_emprestimos__gt=0)[:10], 'atrasos_amostra': relatorio['atrasos'][:10], 'vencimentos_amostra': relatorio['vencimentos'][:10], 'ultimas_importacoes': relatorio['importacoes_periodo'][:5]})
    return render(request, 'acervo/relatorios.html', relatorio)
