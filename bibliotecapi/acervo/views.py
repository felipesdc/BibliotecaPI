from django.shortcuts import render

# Create your views here.
from .models import Livro, Autor, LivroCopia, Genero

def index(request):
    """View function for home page of site."""

    # Generate counts of some of the main objects
    numero_de_livros = Livro.objects.all().count()
    numero_de_copias = LivroCopia.objects.all().count()

    # Available books (status = 'a')
    numero_de_copias_disponiveis = LivroCopia.objects.filter(estado__exact='d').count()

    # The 'all()' is implied by default.
    numero_de_autores = Autor.objects.count()

    context = {
        'numero_de_livros': numero_de_livros,
        'numero_de_copias': numero_de_copias,
        'numero_de_copias_disponiveis': numero_de_copias_disponiveis,
        'numero_de_autores': numero_de_autores,
    }

    # Render the HTML template index.html with the data in the context variable
    return render(request, 'index.html', context=context)
