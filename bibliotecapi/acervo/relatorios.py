"""Indicadores gerenciais: estoque atual separado de eventos no período."""
from datetime import datetime, time, timedelta

from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import TruncDate, TruncMonth
from django.utils import timezone

from .models import Autor, Emprestimo, Genero, Importacao, Leitor, Lingua, Livro, LivroCopia

MESES = ['', 'jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez']


def limites_periodo(inicio, fim):
    zona = timezone.get_current_timezone()
    return (
        timezone.make_aware(datetime.combine(inicio, time.min), zona),
        timezone.make_aware(datetime.combine(fim + timedelta(days=1), time.min), zona),
    )


def gerar_relatorio(inicio, fim):
    hoje = timezone.localdate()
    limite_inicial, limite_final = limites_periodo(inicio, fim)
    filtro = {'criado_em__gte': limite_inicial, 'criado_em__lt': limite_final}
    emprestimos = Emprestimo.objects.filter(**filtro)
    devolucoes = Emprestimo.objects.filter(devolvido_em__gte=limite_inicial, devolvido_em__lt=limite_final)
    pontuais = devolucoes.annotate(dia=TruncDate('devolvido_em')).filter(dia__lte=F('prazo')).count()
    n_devolucoes = devolucoes.count()
    duracao = devolucoes.aggregate(media=Avg(ExpressionWrapper(F('devolvido_em') - F('criado_em'), output_field=DurationField())))['media']

    copias = LivroCopia.objects.all()
    totais_estado = dict(copias.order_by().values('estado').annotate(total=Count('pk')).values_list('estado', 'total'))
    estados = [{'codigo': codigo, 'nome': rotulo, 'total': totais_estado.get(codigo, 0)} for codigo, rotulo in LivroCopia.ESTADOS_EMPRESTIMO]
    outros = sum(n for estado, n in totais_estado.items() if estado not in dict(LivroCopia.ESTADOS_EMPRESTIMO))
    if outros:
        estados.append({'codigo': '', 'nome': 'Sem classificação', 'total': outros})
    total_copias = sum(totais_estado.values())
    for estado in estados:
        estado['percentual'] = round(100 * estado['total'] / total_copias) if total_copias else 0

    atrasos = copias.filter(estado='e', data_devolucao__lt=hoje).select_related('livro', 'leitor', 'tomador').order_by('data_devolucao', 'codigo', 'pk')
    vencimentos = copias.filter(estado='e', data_devolucao__gte=hoje, data_devolucao__lte=hoje + timedelta(days=7)).select_related('livro', 'leitor', 'tomador').order_by('data_devolucao', 'pk')
    livros = Livro.objects.select_related('autor').annotate(total_emprestimos=Count('livrocopia__emprestimo', filter=Q(livrocopia__emprestimo__criado_em__gte=limite_inicial, livrocopia__emprestimo__criado_em__lt=limite_final), distinct=True)).filter(total_emprestimos__gt=0).order_by('-total_emprestimos', 'titulo', 'pk')
    leitores = Leitor.objects.annotate(total_emprestimos=Count('emprestimo', filter=Q(emprestimo__criado_em__gte=limite_inicial, emprestimo__criado_em__lt=limite_final), distinct=True)).order_by('-total_emprestimos', 'nome', 'pk')
    generos = Genero.objects.annotate(titulos=Count('livro', distinct=True), exemplares=Count('livro__livrocopia', distinct=True)).order_by('-exemplares', 'nome')

    iniciados_mes = {r['mes'].date().replace(day=1): r['total'] for r in emprestimos.order_by().annotate(mes=TruncMonth('criado_em')).values('mes').annotate(total=Count('pk'))}
    devolvidos_mes = {r['mes'].date().replace(day=1): r['total'] for r in devolucoes.order_by().annotate(mes=TruncMonth('devolvido_em')).values('mes').annotate(total=Count('pk'))}
    mensal, mes = [], inicio.replace(day=1)
    while mes <= fim:
        mensal.append({'mes': mes, 'rotulo': f'{MESES[mes.month]}/{mes.year}', 'emprestimos': iniciados_mes.get(mes, 0), 'devolucoes': devolvidos_mes.get(mes, 0)})
        mes = mes.replace(year=mes.year + 1, month=1) if mes.month == 12 else mes.replace(month=mes.month + 1)
    pico = max([max(m['emprestimos'], m['devolucoes']) for m in mensal] + [1])
    for linha in mensal:
        linha['barra_emprestimos'] = round(100 * linha['emprestimos'] / pico)
        linha['barra_devolucoes'] = round(100 * linha['devolucoes'] / pico)

    importacoes = Importacao.objects.filter(**filtro).select_related('criado_por').order_by('-criado_em', '-pk')
    return {
        'hoje': hoje, 'inicio': inicio, 'fim': fim,
        'estoque': {'titulos': Livro.objects.count(), 'exemplares': total_copias, 'disponiveis': totais_estado.get('d', 0), 'emprestados': totais_estado.get('e', 0), 'atrasados': atrasos.count(), 'manutencao': totais_estado.get('m', 0), 'reservados': totais_estado.get('r', 0), 'leitores_ativos': Leitor.objects.filter(ativo=True).count(), 'leitores_inativos': Leitor.objects.filter(ativo=False).count(), 'autores': Autor.objects.count(), 'generos': Genero.objects.count(), 'idiomas': Lingua.objects.count(), 'sem_genero': Livro.objects.filter(genero__isnull=True).count()},
        'periodo': {'emprestimos': emprestimos.count(), 'devolucoes': n_devolucoes, 'pontuais': pontuais, 'pontualidade': round(100 * pontuais / n_devolucoes, 1) if n_devolucoes else None, 'duracao_media': round(duracao.total_seconds() / 86400, 1) if duracao is not None else None, 'leitores_com_emprestimos': emprestimos.filter(leitor__isnull=False).values('leitor').distinct().count(), 'leitores_ativos_sem_movimento': leitores.filter(ativo=True, total_emprestimos=0).count(), 'importacoes_concluidas': importacoes.filter(concluida=True).count(), 'importacoes_pendentes': importacoes.filter(concluida=False).count()},
        'estados': estados, 'mensal': mensal, 'livros_ranking': livros, 'leitores_atividade': leitores,
        'generos_acervo': generos, 'atrasos': atrasos, 'vencimentos': vencimentos,
        'emprestimos_periodo': emprestimos.select_related('copia__livro', 'leitor', 'tomador', 'realizado_por').order_by('criado_em', 'pk'),
        'devolucoes_periodo': devolucoes.select_related('copia__livro', 'leitor', 'tomador').order_by('devolvido_em', 'pk'),
        'importacoes_periodo': importacoes,
    }
