"""Registro de empréstimos com validação das regras dentro da transação."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Emprestimo, Leitor, LivroCopia, PoliticaCirculacao


@transaction.atomic
def registrar_emprestimo(*, copia, leitor, prazo, operador):
    # A primeira escrita serializa concorrentes também no SQLite, antes das contagens.
    # Em bancos com bloqueio por linha, serializa os empréstimos do mesmo leitor.
    if not Leitor.objects.filter(pk=leitor.pk, ativo=True).update(ativo=True):
        raise ValidationError('Este leitor está inativo. Selecione um leitor ativo.')
    politica = PoliticaCirculacao.atual()
    hoje = timezone.localdate()
    if prazo < hoje:
        raise ValidationError('Escolha hoje ou uma data futura.')
    abertos = LivroCopia.objects.filter(leitor=leitor, estado='e')
    if politica.limite_emprestimos and abertos.count() >= politica.limite_emprestimos:
        raise ValidationError('O leitor atingiu o limite de empréstimos em aberto.')
    if politica.bloquear_atrasados and abertos.filter(data_devolucao__lt=hoje).exists():
        raise ValidationError('O leitor tem devoluções em atraso. Regularize antes de um novo empréstimo.')
    alteradas = LivroCopia.objects.filter(pk=copia.pk, estado='d').update(
        estado='e', leitor=leitor, tomador=None, data_devolucao=prazo)
    if not alteradas:
        raise ValidationError('Este exemplar não está disponível para empréstimo.')
    return Emprestimo.objects.create(copia=copia, leitor=leitor, realizado_por=operador, prazo=prazo)


_NAO_INFORMADO = object()


def retrato_emprestimo(copia, registro=_NAO_INFORMADO):
    return {
        'copia': str(copia.pk), 'leitor': copia.leitor_id,
        'prazo': copia.data_devolucao.isoformat() if copia.data_devolucao else None,
        'registro': registro if registro is not _NAO_INFORMADO else Emprestimo.objects.filter(copia=copia, devolvido_em__isnull=True).values_list('pk', flat=True).first(),
    }


def _emprestimo_atual(copia_id, esperado):
    if not LivroCopia.objects.filter(pk=copia_id, estado='e').update(estado='e'):
        raise ValidationError('Este exemplar não tem empréstimo em aberto. Atualize o atendimento.')
    copia = LivroCopia.objects.select_related('livro', 'leitor').get(pk=copia_id)
    if esperado is not None and retrato_emprestimo(copia) != esperado:
        raise ValidationError('O empréstimo foi alterado. Atualize o atendimento antes de continuar.')
    return copia


@transaction.atomic
def registrar_devolucao(*, copia_id, operador, esperado=None):
    copia = _emprestimo_atual(copia_id, esperado)
    agora = timezone.now()
    abertos = Emprestimo.objects.filter(copia=copia, devolvido_em__isnull=True)
    if not abertos.exists() and copia.data_devolucao:
        Emprestimo.objects.create(copia=copia, leitor=copia.leitor, tomador=copia.tomador,
                                 realizado_por=operador, prazo=copia.data_devolucao, devolvido_em=agora)
    else:
        abertos.update(devolvido_em=agora)
    copia.estado, copia.leitor, copia.tomador, copia.data_devolucao = 'd', None, None, None
    copia.save(update_fields=['estado', 'leitor', 'tomador', 'data_devolucao'])
    return copia


@transaction.atomic
def registrar_renovacao(*, copia_id, prazo, esperado=None):
    from datetime import timedelta
    hoje = timezone.localdate()
    if not hoje <= prazo <= hoje + timedelta(days=28):
        raise ValidationError('A renovação deve ficar entre hoje e daqui a 28 dias.')
    copia = _emprestimo_atual(copia_id, esperado)
    copia.data_devolucao = prazo
    copia.save(update_fields=['data_devolucao'])
    Emprestimo.objects.filter(copia=copia, devolvido_em__isnull=True).update(prazo=prazo)
    return copia
