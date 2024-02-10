import uuid
from django.db import models


# Create your models here.

class Usuario(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4(), editable=False)
    cpf = models.PositiveBigIntegerField(unique=True, null=False)
    nome = models.TextField()
    data_nascimento = models.DateField()

    def __str__(self):
        return self.nome

