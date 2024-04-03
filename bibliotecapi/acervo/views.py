from django.shortcuts import render, get_object_or_404
from django.views import generic

from .models import Livro, Autor, LivroCopia, Genero, Lingua


def index(request):
    """Função para criação de visualização inicial da página."""

    # Gerando contagens para alguns itens do acervo
    numero_de_livros = Livro.objects.all().count()
    numero_de_copias = LivroCopia.objects.all().count()
    numero_de_generos = Genero.objects.all().count()

    # Livros Disponíveis para Empréstimo (estado = 'd')
    numero_de_copias_disponiveis = LivroCopia.objects.filter(estado__exact='d').count()

    # O 'all()' é implícito por padrão
    numero_de_autores = Autor.objects.count()

    context = {
        'numero_de_livros': numero_de_livros,
        'numero_de_copias': numero_de_copias,
        'numero_de_copias_disponiveis': numero_de_copias_disponiveis,
        'numero_de_autores': numero_de_autores,
        'numero_de_generos': numero_de_generos
    }

    # Render the HTML template index.html with the data in the context variable
    return render(request, 'index.html', context=context)



class ListaLivrosView(generic.ListView):
    model = Livro
    context_object_name = 'lista_livros'
    template_name = 'acervo/lista_livros.html'
    paginate_by = 10

class DetalheLivroView(generic.DetailView):
    model = Livro
    context_object_name = 'livro'
    template_name = 'acervo/detalhe_livro.html'

class AutorListView(generic.ListView):
    """Classe genérica para visão lista de Autores."""
    model = Autor
    context_object_name = 'lista_autores'
    template_name = 'acervo/lista_autores.html'
    paginate_by = 10

class AutorDetailView(generic.DetailView):
    """Classe genérica para visão detalhe do Autor."""
    model = Autor
    context_object_name = 'autor'
    template_name = 'acervo/detalhe_autor.html'

class GeneroListView(generic.ListView):
    """Classe genérica para visão detalhe do Gênero."""
    model = Genero
    context_object_name = 'lista_generos'
    template_name = 'acervo/lista_generos.html'
    paginate_by = 10


class GeneroDetailView(generic.DetailView):
    """Classe genérica para visão lista de Gêneros."""
    model = Genero
    context_object_name = 'genero'
    template_name = 'acervo/detalhe_genero.html'

class LinguaListView(generic.ListView):
    """Classe genérica para visão detalhe da língua."""
    model = Lingua
    context_object_name = 'lista_linguas'
    template_name = 'acervo/lista_linguas.html'
    paginate_by = 10

class LinguaDetailView(generic.DetailView):
    """Classe genérica para visão lista das Línguas."""
    model = Lingua
    context_object_name = 'lingua'
    template_name = 'acervo/detalhe_lingua.html'

class LivroCopiaListView(generic.ListView):
    """Classe genérica para visão lista das Cópias de Livros."""
    model = LivroCopia
    context_object_name = 'lista_copias'
    template_name = 'acervo/lista_copias.html'
    paginate_by = 10


class LivroCopiaDetailView(generic.DetailView):
    """Classe genérica para visão detalhe da Cópia de Livro."""
    model = LivroCopia
    context_object_name = 'copia'
    template_name = 'acervo/detalhe_copia.html'
