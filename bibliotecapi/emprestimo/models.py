import uuid

from django.db import models
from django.utils import timezone

from livro.models import Livro
from usuario.models import Usuario


# Create your models here.
class Emprestimo(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    id_livro = models.ForeignKey(Livro, on_delete=models.CASCADE)
    id_usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    data_emprestimo = models.DateField(default=timezone.now)
    data_devolucao_prevista = models.DateField(default=timezone.now)
    data_devolucao = models.DateField(default=timezone.now)
    status_emprestimo = models.BooleanField()
    quantidade_renovacoes = models.IntegerField()
    valor_multa = models.DecimalField(max_digits=10, decimal_places=2)
    metodo_pagamento = models.TextField()
    comentarios = models.TextField()

