from django.db import models

import uuid  # Required for unique book instances
from datetime import date

from django.conf import settings  # Required to assign User as a borrower
from django.urls import reverse  # To generate URLS by reversing URL patterns


class Genero(models.Model):
    """Modelo que representa o gênero do Livro (Ficção, Acadêmico etc.)."""
    nome = models.CharField(
        max_length=200,
        unique=True,
        help_text="Gênero do Livro (por exemplo Literatura Nacional, Estrangeira, Não Ficção etc.)"
    )

    def get_absolute_url(self):
        """Retorna a URL para um determinado gênero."""
        return reverse('detalhe-genero', args=[str(self.id)])

    def __str__(self):
        """Retorna nome do gênero como representação String para o modelo Genero """
        return self.nome


class Lingua(models.Model):
    """Modelo que representa a línngua em que o livro está escrito"""
    nome = models.CharField(max_length=200,
                            unique=True,
                            help_text="Língua em que o livro está escrito")

    def get_absolute_url(self):
        """Retorna a URL para detalhar uma língua em particular."""
        return reverse('detalhe-lingua', args=[str(self.id)])

    def __str__(self):
        """Retorna o nome da língua como representação String para o modelo Lingua"""
        return self.nome


class Livro(models.Model):
    """Modelo para representar um Livro (mas não uma cópia)"""
    titulo = models.CharField(max_length=200)
    autor = models.ForeignKey('Autor', on_delete=models.RESTRICT, null=True)
    # Chave estrangeira para Autor, um livro pode ter um autor, um autor pode ter muitos livros.
    descricao = models.TextField(
        max_length=1000, help_text="Breve descrição do livro")
    isbn = models.CharField('ISBN', max_length=13,
                            unique=True,
                            help_text='13 Caracteres <a href="https://www.isbn-international.org/content/what-isbn'
                                      '">ISBN number</a>')
    genero = models.ManyToManyField(
        Genero, help_text="Selecione o gênero do livro")
    # Campo ManyToManyField por livro poder ter vários gêneros e gêneros englobarem vários livros

    lingua = models.ForeignKey(
        'Lingua', on_delete=models.SET_NULL, null=True)

    class Meta:
        ordering = ['titulo', 'autor']

    def mostra_genero(self):
        """Representação String para o gênero do livro."""
        return ', '.join([self.genero.nome for genre in self.genero.all()[:3]])

    mostra_genero.short_description = 'Genero'

    def get_absolute_url(self):
        """Retorna a URL para um livro em particular."""
        return reverse('detalhe-livro', args=[str(self.id)])

    def __str__(self):
        """Representação String do titulo para o modelo Livro"""
        return self.titulo




class LivroCopia(models.Model):
    """Modelo representando a cópia do livro"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4,
                          help_text="ID único para uma cópia do livro disponível na biblioteca")
    livro = models.ForeignKey('Livro', on_delete=models.RESTRICT, null=True)
    editora = models.CharField(max_length=200)
    data_devolucao = models.DateField(null=True, blank=True)
    tomador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    @property
    def em_atraso(self):
        """Determina se o empréstimo está em atraso com base na data_devolucao e data atual."""
        return bool(self.data_devolucao and date.today() > self.data_devolucao)

    ESTADOS_EMPRESTIMO = (
        ('m', 'Manutenção'),
        ('e', 'Emprestado'),
        ('d', 'Disponível'),
        ('r', 'Reservado'),
    )

    estado = models.CharField(
        max_length=1,
        choices=ESTADOS_EMPRESTIMO,
        blank=True,
        default='m',
        help_text='Disponibilidade do Livro')

    class Meta:
        ordering = ['data_devolucao']
        permissions = (("marca_devolucao", "Marca o livro como devolvido"),)

    def get_absolute_url(self):
        """Retorna a URL para uma cópia de livro em particular."""
        return reverse('detalhe-copia', args=[str(self.id)])

    def __str__(self):
        """Representacao String para a cópia do livro."""
        return f'{self.id} ({self.livro.titulo})'


class Autor(models.Model):
    """Modelo de representação de autor."""
    primeiro_nome = models.CharField(max_length=100)
    sobrenome = models.CharField(max_length=100)
    data_nascimento = models.DateField(null=True, blank=True)
    data_falecimento = models.DateField('morte', null=True, blank=True)

    class Meta:
        ordering = ['sobrenome', 'primeiro_nome']

    def get_absolute_url(self):
        """Retorna a URL para um autor em particular."""
        return reverse('detalhe-autor', args=[str(self.id)])

    def __str__(self):
        """Representação String do modelo Autor."""
        return f'{self.sobrenome}, {self.primeiro_nome}'