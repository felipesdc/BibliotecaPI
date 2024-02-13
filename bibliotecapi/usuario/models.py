import uuid
from django.db import models
from django.utils import timezone



# Create your models here.

class Usuario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    cpf = models.PositiveBigIntegerField(unique=True)
    nome = models.TextField()
    endereco = models.TextField()
    telefone = models.TextField()
    email = models.EmailField()
    data_nascimento = models.DateField(default=timezone.now)
    data_registro = models.DateField(default=timezone.now)
    tipo_membro = models.TextField()
    status_emprestimo = models.BooleanField()


    def __str__(self):
        return self.nome
