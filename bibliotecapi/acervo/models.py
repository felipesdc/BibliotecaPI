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
    autor = models.ForeignKey('Autor', on_delete=models.RESTRICT, null=True, blank=True)
    # Chave estrangeira para Autor, um livro pode ter um autor, um autor pode ter muitos livros.
    descricao = models.TextField(
        max_length=1000, blank=True, help_text="Breve descrição do livro")
    isbn = models.CharField('ISBN', max_length=13, blank=True, null=True,
                            unique=True,
                            help_text='13 Caracteres <a href="https://www.isbn-international.org/content/what-isbn'
                                      '">ISBN number</a>')
    genero = models.ManyToManyField(
        Genero, blank=True, help_text="Selecione o gênero do livro")
    # Campo ManyToManyField por livro poder ter vários gêneros e gêneros englobarem vários livros

    lingua = models.ForeignKey(
        'Lingua', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['titulo', 'autor']

    def mostra_genero(self):
        """Representação String para o gênero do livro."""
        return ', '.join([genre.nome for genre in self.genero.all()[:3]])

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
    codigo = models.CharField('Código do exemplar', max_length=100, unique=True, null=True, blank=True)
    leitor = models.ForeignKey('Leitor', on_delete=models.PROTECT, null=True, blank=True)
    editora = models.CharField(max_length=200, blank=True)
    data_devolucao = models.DateField(null=True, blank=True)
    tomador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.codigo:
            self.codigo = 'BIB-' + self.id.hex
        return super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.estado == 'e' and (not self.data_devolucao or not (self.leitor_id or self.tomador_id)):
            raise ValidationError('Um exemplar emprestado precisa de leitor e prazo de devolução.')
        if self.estado != 'e' and (self.leitor_id or self.tomador_id or self.data_devolucao):
            raise ValidationError('Somente exemplares emprestados podem ter leitor e prazo de devolução.')

    @property
    def em_atraso(self):
        """Determina se o empréstimo está em atraso com base na data_devolucao e data atual."""
        return bool(self.estado == 'e' and self.data_devolucao and date.today() > self.data_devolucao)

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
        default='d',
        help_text='Disponibilidade do Livro')

    class Meta:
        ordering = ['data_devolucao']
        permissions = (("marca_devolucao", "Marca o livro como devolvido"), ("export_acervo", "Pode exportar o acervo"))

    def get_absolute_url(self):
        """Retorna a URL para uma cópia de livro em particular."""
        return reverse('detalhe-copia', args=[str(self.id)])

    def __str__(self):
        """Representacao String para a cópia do livro."""
        return f'{self.codigo or str(self.id)[:8]} ({self.livro.titulo if self.livro else "Sem livro"})'


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

class Leitor(models.Model):
    nome = models.CharField(max_length=200)
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=30, blank=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        ordering = ['nome', 'pk']

    def __str__(self):
        return f'{self.nome} (#{self.pk})'

    def get_absolute_url(self):
        return reverse('leitores')


class Emprestimo(models.Model):
    copia = models.ForeignKey(LivroCopia, on_delete=models.PROTECT)
    leitor = models.ForeignKey(Leitor, on_delete=models.PROTECT, null=True, blank=True)
    tomador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='historico_biblioteca')
    realizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='operacoes_biblioteca')
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    prazo = models.DateField()
    devolvido_em = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['-criado_em']
        permissions = [('view_relatorios', 'Pode consultar relatórios gerenciais')]
        constraints = [models.UniqueConstraint(fields=['copia'], condition=models.Q(devolvido_em__isnull=True), name='um_emprestimo_aberto_por_copia')]


class Importacao(models.Model):
    criado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    criado_em = models.DateTimeField(auto_now_add=True)
    nome = models.CharField(max_length=255)
    dados = models.JSONField(default=dict)
    resultado = models.JSONField(default=dict)
    concluida = models.BooleanField(default=False)


class PerfilAcesso(models.Model):
    class Papel(models.TextChoices):
        GESTOR = 'gestor', 'Gestor'
        ATENDENTE = 'atendente', 'Atendente'
        CONSULTA = 'consulta', 'Consulta interna'

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='perfil_biblioteca')
    papel = models.CharField(max_length=20, choices=Papel.choices)
    exigir_troca_senha = models.BooleanField(default=False)
    versao_sessao = models.PositiveIntegerField(default=1)

    class Meta:
        permissions = [('manage_usuarios', 'Pode gerenciar usuários da biblioteca')]


class EventoAcesso(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='eventos_acesso')
    realizado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='gestao_acessos')
    acao = models.CharField(max_length=40, choices=[('criado', 'Conta criada'), ('editado', 'Cadastro atualizado'), ('perfil_alterado', 'Perfil alterado'), ('desativado', 'Conta desativada'), ('reativado', 'Conta reativada'), ('senha_redefinida', 'Senha temporária definida'), ('senha_alterada', 'Senha alterada pelo usuário'), ('migrado', 'Perfil migrado')])
    criado_em = models.DateTimeField(auto_now_add=True)
    detalhes = models.JSONField(default=dict)

    class Meta:
        ordering = ['-criado_em', '-pk']
