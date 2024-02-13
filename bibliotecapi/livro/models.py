import uuid
from django.db import models
from django.utils import timezone



# Create your models here.
class Livro(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titulo = models.TextField()
    autor = models.TextField()
    isbn = models.TextField(unique=True)
    editora = models.TextField()
    data_publicacao = models.DateField(default=timezone.now)
    genero = models.TextField()
    sinopse = models.TextField()
    numero_paginas = models.IntegerField()
    idioma = models.TextField()

    def __str__(self):
        return self.titulo
