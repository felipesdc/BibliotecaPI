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
