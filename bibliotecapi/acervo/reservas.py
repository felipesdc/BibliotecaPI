"""Fila por título: prioridade para leitores ativos, sem prender exemplar físico."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Leitor, Livro, LivroCopia, Reserva


def fila(livro_id):
    return Reserva.objects.filter(livro_id=livro_id, estado='a', leitor__ativo=True).order_by('criado_em', 'pk')


@transaction.atomic
def reservar(*, livro, leitor, operador):
    # A escrita inicial serializa também os concorrentes no SQLite.
    Livro.objects.filter(pk=livro.pk).update(titulo=F('titulo'))
    if not Leitor.objects.filter(pk=leitor.pk, ativo=True).exists():
        raise ValidationError('Selecione um leitor ativo para reservar.')
    if Reserva.objects.filter(livro=livro, leitor=leitor, estado='a').exists():
        raise ValidationError('Este leitor já está na fila deste título.')
    if LivroCopia.objects.filter(livro=livro, leitor=leitor, estado='e').exists():
        raise ValidationError('O leitor já tem um exemplar deste título emprestado.')
    return Reserva.objects.create(livro=livro, leitor=leitor, criado_por=operador)


@transaction.atomic
def cancelar(*, reserva_id, operador):
    alteradas = Reserva.objects.filter(pk=reserva_id, estado='a').update(
        estado='c', encerrado_em=timezone.now(), encerrado_por=operador)
    if not alteradas:
        raise ValidationError('Esta reserva já foi encerrada. Atualize a lista.')
