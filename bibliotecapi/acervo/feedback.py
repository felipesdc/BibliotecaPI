"""Resumo transitório de circulação, exibido uma vez após a operação concluída."""
from django.utils import timezone

CHAVE_RESULTADO = 'biblioteca_resultado_circulacao'
VALIDADE_SEGUNDOS = 600
TITULOS = {'emprestar': 'Empréstimo confirmado:', 'renovar': 'Renovação confirmada:', 'devolver': 'Devolução confirmada:'}


def confirmar_operacao(request, *, acao, copia, destino, leitor=None, prazo=None):
    pessoa = leitor or copia.leitor or copia.tomador
    data = prazo if prazo is not None else copia.data_devolucao
    agora = timezone.now()
    request.session[CHAVE_RESULTADO] = {
        'usuario': request.user.pk, 'destino': destino, 'criado_em': agora.timestamp(),
        'acao': acao, 'titulo': TITULOS[acao],
        'livro': str(copia.livro) if copia.livro else 'Sem título informado',
        'codigo': copia.codigo or str(copia.pk),
        'leitor': str(pessoa.nome if hasattr(pessoa, 'nome') else pessoa) if pessoa else 'Não informado',
        'leitor_id': pessoa.pk if hasattr(pessoa, 'nome') else None,
        'prazo': data.strftime('%d/%m/%Y') if data else 'Não informado',
        'horario': timezone.localtime(agora).strftime('%d/%m/%Y às %H:%M'),
        'operador': request.user.get_username(),
    }


def resultado_circulacao(request):
    resultado = request.session.get(CHAVE_RESULTADO)
    if not resultado:
        return {}
    if (not request.user.is_authenticated or resultado['usuario'] != request.user.pk
            or timezone.now().timestamp() - resultado['criado_em'] > VALIDADE_SEGUNDOS
            or not request.user.has_perm('acervo.marca_devolucao')):
        request.session.pop(CHAVE_RESULTADO, None)
        return {}
    rota = getattr(request.resolver_match, 'url_name', None)
    if request.method != 'GET' or rota != resultado['destino']:
        return {}
    request.session.pop(CHAVE_RESULTADO, None)
    return {'resultado_circulacao': resultado}
