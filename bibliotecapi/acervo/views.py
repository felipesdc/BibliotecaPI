import datetime

from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required, permission_required
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy

from .forms import RenovacaoEmprestimoForm

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

    numero_de_visitas = request.session.get('numero_de_visitas', 0)
    request.session['numero_de_visitas'] = numero_de_visitas + 1

    context = {
        'numero_de_livros': numero_de_livros,
        'numero_de_copias': numero_de_copias,
        'numero_de_copias_disponiveis': numero_de_copias_disponiveis,
        'numero_de_autores': numero_de_autores,
        'numero_de_generos': numero_de_generos,
        'numero_de_visitas': numero_de_visitas
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


class CopiasEmprestadasPorUsuarioListView(LoginRequiredMixin,generic.ListView):
    """Classe genérica para visão lista das Cópias emprestadas por usuários."""
    model = LivroCopia
    template_name = 'acervo/lista_copias_emprestadas_usuario.html'
    paginate_by = 10

    def get_queryset(self):
        return (
            LivroCopia.objects.filter(tomador=self.request.user)
            .filter(estado__exact='e')
            .order_by('data_devolucao')
        )


class TodosEmprestimosListView(PermissionRequiredMixin, generic.ListView):
    """Classe genérica para visão lista de todas as Cópias emprestadas. Somente para usuários com permissão marca_devolucao"""
    model = LivroCopia
    permission_required = 'acervo.marca_devolucao'
    template_name = 'acervo/lista_todas_copias_emprestadas.html'
    paginate_by = 10

    def get_queryset(self):
        return LivroCopia.objects.filter(estado__exact='e').order_by('data_devolucao')


@login_required
@permission_required('acervo.marca_devolucao', raise_exception=True)
def renovacao_emprestimo_bibliotecario(request, pk):
    copia = get_object_or_404(LivroCopia, pk=pk)

    # If this is a POST request then process the Form data
    if request.method == 'POST':

        # Create a form instance and populate it with data from the request (binding):
        form = RenovacaoEmprestimoForm(request.POST)

        # Check if the form is valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required (here we just write it to the model due_back field)
            copia.data_devolucao = form.cleaned_data['data_renovacao']
            copia.save()

            # redirect to a new URL:
            return HttpResponseRedirect(reverse('todos-emprestimos'))

    # If this is a GET (or any other method) create the default form.
    else:
        data_renovacao_proposta = datetime.date.today() + datetime.timedelta(weeks=3)
        form = RenovacaoEmprestimoForm(initial={'data_renovacao': data_renovacao_proposta})

    context = {
        'form': form,
        'copia': copia,
    }

    return render(request, 'acervo/renovacao_emprestimo_bibliotecario.html', context)


class AdicionarAutor(PermissionRequiredMixin, CreateView):
    model = Autor
    fields = ['primeiro_nome', 'sobrenome', 'data_nascimento', 'data_falecimento']
    initial = {'data_falecimento': datetime.date.today()}
    permission_required = 'acervo.add_autor'


class AlterarAutor(PermissionRequiredMixin, UpdateView):
    model = Autor
    # Not recommended (potential security issue if more fields added)
    fields = '__all__'
    permission_required = 'acervo.change_autor'


class ExcluirAutor(PermissionRequiredMixin, DeleteView):
    model = Autor
    success_url = reverse_lazy('autors')
    permission_required = 'acervo.delete_autor'

    def form_valid(self, form):
        try:
            self.object.delete()
            return HttpResponseRedirect(self.success_url)
        except Exception as e:
            return HttpResponseRedirect(
                reverse("autor-delete", kwargs={"pk": self.object.pk})
            )

# Classes created for the forms challenge


class AdicionarLivro(PermissionRequiredMixin, CreateView):
    model = Livro
    fields = ['titulo', 'autor', 'descricao', 'isbn', 'genero', 'lingua']
    permission_required = 'acervo.add_livro'


class AlterarLivro(PermissionRequiredMixin, UpdateView):
    model = Livro
    fields = ['titulo', 'autor', 'descricao', 'isbn', 'genero', 'lingua']
    permission_required = 'acervo.change_livro'


class ExcluirLivro(PermissionRequiredMixin, DeleteView):
    model = Livro
    success_url = reverse_lazy('livros')
    permission_required = 'acervo.delete_livro'

    def form_valid(self, form):
        try:
            self.object.delete()
            return HttpResponseRedirect(self.success_url)
        except Exception as e:
            return HttpResponseRedirect(
                reverse("livro-delete", kwargs={"pk": self.object.pk})
            )


class AdicionarGenero(PermissionRequiredMixin, CreateView):
    model = Genero
    fields = ['nome', ]
    permission_required = 'acervo.add_genero'


class AlterarGenero(PermissionRequiredMixin, UpdateView):
    model = Genero
    fields = ['nome', ]
    permission_required = 'acervo.change_genero'


class ExcluirGenero(PermissionRequiredMixin, DeleteView):
    model = Genero
    success_url = reverse_lazy('generos')
    permission_required = 'acervo.delete_genero'


class AdicionarLingua(PermissionRequiredMixin, CreateView):
    model = Lingua
    fields = ['nome', ]
    permission_required = 'acervo.add_lingua'


class AlterarLingua(PermissionRequiredMixin, UpdateView):
    model = Lingua
    fields = ['nome', ]
    permission_required = 'acervo.change_lingua'


class ExcluirLingua(PermissionRequiredMixin, DeleteView):
    model = Lingua
    success_url = reverse_lazy('linguas')
    permission_required = 'acervo.delete_lingua'


class AdicionarLivroCopia(PermissionRequiredMixin, CreateView):
    model = LivroCopia
    fields = ['livro', 'editora', 'data_devolucao', 'tomador', 'estado']
    permission_required = 'acervo.add_livrocopia'


class AlterarLivroCopia(PermissionRequiredMixin, UpdateView):
    model = LivroCopia
    # fields = "__all__"
    fields = ['editora', 'data_devolucao', 'tomador', 'estado']
    permission_required = 'acervo.change_livrocopia'


class ExcluirLivroCopia(PermissionRequiredMixin, DeleteView):
    model = LivroCopia
    success_url = reverse_lazy('copias')
    permission_required = 'acervo.delete_livrocopia'
