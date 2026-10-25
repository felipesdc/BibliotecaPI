import datetime

from django.views import generic
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required, permission_required
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy

from .forms import RenovacaoEmprestimoForm, UploadAcervoForm, EmprestarForm, ExemplarForm
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.db.models import Q, Count
from django.db.models.deletion import RestrictedError, ProtectedError
from django.utils import timezone
from django.views.decorators.http import require_POST
from . import importacao
import csv

from .models import Livro, Autor, LivroCopia, Genero, Lingua, Leitor, Emprestimo, Importacao

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
        'numero_de_visitas': numero_de_visitas,
        'emprestados': LivroCopia.objects.filter(estado='e').count(),
        'atrasados': LivroCopia.objects.filter(estado='e', data_devolucao__lt=timezone.localdate()).count(),
        'recentes': Livro.objects.select_related('autor').order_by('-pk')[:6],
    }

    # Render the HTML template index.html with the data in the context variable
    return render(request, 'index.html', context=context)


class ListaLivrosView(generic.ListView):
    model = Livro
    context_object_name = 'lista_livros'
    template_name = 'acervo/lista_livros.html'
    paginate_by = 12

    def get_queryset(self):
        livros = Livro.objects.select_related('autor', 'lingua').prefetch_related('genero').annotate(disponiveis=Count('livrocopia', filter=Q(livrocopia__estado='d'), distinct=True))
        busca = self.request.GET.get('q', '').strip()
        if busca:
            livros = livros.filter(Q(titulo__icontains=busca) | Q(autor__primeiro_nome__icontains=busca) | Q(autor__sobrenome__icontains=busca) | Q(isbn__icontains=busca) | Q(livrocopia__codigo__icontains=busca)).distinct()
        genero = self.request.GET.get('genero', '')
        if genero.isdigit():
            livros = livros.filter(genero__pk=genero)
        if self.request.GET.get('disponivel') == '1':
            livros = livros.filter(disponiveis__gt=0)
        return livros.order_by('titulo', 'pk')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['generos'] = Genero.objects.order_by('nome')
        return context


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
    ordering = ['nome', 'pk']
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
    ordering = ['nome', 'pk']
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
    paginate_by = 20
    queryset = LivroCopia.objects.select_related('livro', 'leitor', 'tomador').order_by('livro__titulo', 'codigo', 'pk')


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
        return LivroCopia.objects.filter(estado__exact='e').select_related('livro', 'leitor', 'tomador').order_by('data_devolucao', 'pk')


@login_required
@permission_required('acervo.marca_devolucao', raise_exception=True)
def renovacao_emprestimo_bibliotecario(request, pk):
    copia = get_object_or_404(LivroCopia, pk=pk, estado='e')

    # If this is a POST request then process the Form data
    if request.method == 'POST':

        # Create a form instance and populate it with data from the request (binding):
        form = RenovacaoEmprestimoForm(request.POST)

        # Check if the form is valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required (here we just write it to the model due_back field)
            with transaction.atomic():
                copia = LivroCopia.objects.select_for_update().get(pk=pk)
                if copia.estado != 'e':
                    messages.error(request, 'Este exemplar já foi devolvido.')
                    return redirect('todos-emprestimos')
                copia.data_devolucao = form.cleaned_data['data_renovacao']
                copia.save(update_fields=['data_devolucao'])
                Emprestimo.objects.filter(copia=copia, devolvido_em__isnull=True).update(prazo=copia.data_devolucao)
            messages.success(request, 'Empréstimo renovado.')

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
    permission_required = 'acervo.add_autor'


class AlterarAutor(PermissionRequiredMixin, UpdateView):
    model = Autor
    # Not recommended (potential security issue if more fields added)
    fields = ['primeiro_nome', 'sobrenome', 'data_nascimento', 'data_falecimento']
    permission_required = 'acervo.change_autor'


class ExcluirAutor(PermissionRequiredMixin, DeleteView):
    model = Autor
    success_url = reverse_lazy('autores')
    permission_required = 'acervo.delete_autor'

    def form_valid(self, form):
        try:
            self.object.delete()
            return HttpResponseRedirect(self.success_url)
        except (RestrictedError, ProtectedError):
            return HttpResponseRedirect(
                reverse("excluir-autor", kwargs={"pk": self.object.pk})
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
        except (RestrictedError, ProtectedError):
            return HttpResponseRedirect(
                reverse("excluir-livro", kwargs={"pk": self.object.pk})
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
    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get('livro', '').isdigit():
            initial['livro'] = self.request.GET['livro']
        return initial


    model = LivroCopia
    form_class = ExemplarForm
    permission_required = 'acervo.add_livrocopia'


class AlterarLivroCopia(PermissionRequiredMixin, UpdateView):
    model = LivroCopia
    # fields = "__all__"
    form_class = ExemplarForm
    permission_required = 'acervo.change_livrocopia'


class ExcluirLivroCopia(PermissionRequiredMixin, DeleteView):
    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, 'Este exemplar tem histórico de empréstimos e deve ser preservado.')
            return redirect('detalhe-copia', pk=self.object.pk)

    model = LivroCopia
    success_url = reverse_lazy('copias')
    permission_required = 'acervo.delete_livrocopia'


class LeitoresView(PermissionRequiredMixin, generic.ListView):
    model = Leitor
    permission_required = 'acervo.view_leitor'
    template_name = 'acervo/leitores.html'
    paginate_by = 20

    def get_queryset(self):
        return Leitor.objects.filter(nome__icontains=self.request.GET.get('q', '').strip())


class AdicionarLeitor(PermissionRequiredMixin, CreateView):
    model = Leitor
    fields = ['nome', 'email', 'telefone']
    permission_required = 'acervo.add_leitor'
    template_name = 'acervo/leitor_form.html'


class AlterarLeitor(PermissionRequiredMixin, UpdateView):
    model = Leitor
    fields = ['nome', 'email', 'telefone', 'ativo']
    permission_required = 'acervo.change_leitor'
    template_name = 'acervo/leitor_form.html'


@login_required
@permission_required('acervo.marca_devolucao', raise_exception=True)
def emprestar(request, pk):
    copia = get_object_or_404(LivroCopia.objects.select_related('livro'), pk=pk)
    form = EmprestarForm(request.POST or None, initial={'prazo': timezone.localdate() + datetime.timedelta(days=14)})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # A atualização condicional também evita empréstimo duplicado em SQLite.
            alteradas = LivroCopia.objects.filter(pk=pk, estado='d').update(estado='e', leitor=form.cleaned_data['leitor'], tomador=None, data_devolucao=form.cleaned_data['prazo'])
            if alteradas:
                Emprestimo.objects.create(copia=copia, leitor=form.cleaned_data['leitor'], realizado_por=request.user, prazo=form.cleaned_data['prazo'])
                messages.success(request, 'Empréstimo registrado.')
                return redirect('todos-emprestimos')
            form.add_error(None, 'Este exemplar não está disponível para empréstimo.')
    return render(request, 'acervo/emprestar.html', {'form': form, 'copia': copia})


@login_required
@permission_required('acervo.marca_devolucao', raise_exception=True)
@require_POST
def devolver(request, pk):
    with transaction.atomic():
        copia = get_object_or_404(LivroCopia.objects.select_for_update(), pk=pk)
        if copia.estado == 'e':
            agora = timezone.now()
            abertos = Emprestimo.objects.filter(copia=copia, devolvido_em__isnull=True)
            if not abertos.exists() and copia.data_devolucao:
                Emprestimo.objects.create(copia=copia, leitor=copia.leitor, tomador=copia.tomador, realizado_por=request.user, prazo=copia.data_devolucao, devolvido_em=agora)
            else:
                abertos.update(devolvido_em=agora)
            copia.estado, copia.leitor, copia.tomador, copia.data_devolucao = 'd', None, None, None
            copia.save(update_fields=['estado', 'leitor', 'tomador', 'data_devolucao'])
            messages.success(request, 'Devolução registrada. Exemplar disponível novamente.')
        else:
            messages.info(request, 'Este exemplar não tem empréstimo em aberto.')
    return redirect('todos-emprestimos')


class HistoricoView(PermissionRequiredMixin, generic.ListView):
    model = Emprestimo
    permission_required = 'acervo.marca_devolucao'
    template_name = 'acervo/historico.html'
    paginate_by = 25
    queryset = Emprestimo.objects.select_related('copia__livro', 'leitor', 'tomador', 'realizado_por')


@login_required
@permission_required(('acervo.add_livro', 'acervo.add_livrocopia', 'acervo.add_autor', 'acervo.add_genero', 'acervo.add_lingua'), raise_exception=True)
def importar_acervo(request):
    form = UploadAcervoForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        try:
            tabelas = importacao.ler_planilha(form.cleaned_data['arquivo'])
        except Exception as exc:
            form.add_error('arquivo', str(exc) if isinstance(exc, ValueError) else 'Não foi possível ler o arquivo. Verifique se é um .xlsx ou .csv válido.')
        else:
            lote = Importacao.objects.create(criado_por=request.user, nome=form.cleaned_data['arquivo'].name[:255], dados={'tabelas': tabelas})
            return redirect('mapear-importacao', pk=lote.pk)
    return render(request, 'acervo/importar.html', {'form': form})


@login_required
@permission_required(('acervo.add_livro', 'acervo.add_livrocopia', 'acervo.add_autor', 'acervo.add_genero', 'acervo.add_lingua'), raise_exception=True)
def mapear_importacao(request, pk):
    lote = get_object_or_404(Importacao, pk=pk, criado_por=request.user)
    if lote.concluida:
        return render(request, 'acervo/importacao_resultado.html', {'lote': lote})
    tabelas = lote.dados['tabelas']
    aba = request.POST.get('aba', request.GET.get('aba', next(iter(tabelas))))
    if aba not in tabelas:
        aba = next(iter(tabelas))
    tabela = tabelas[aba]
    mapa = importacao.sugestoes(tabela['cabecalho'])
    erros, previa = [], None
    if request.method == 'POST':
        mapa = {campo: request.POST.get(campo, '') for campo in importacao.CAMPOS}
        previa, erros = importacao.preparar(tabela, mapa)
        if request.POST.get('acao') == 'confirmar' and not request.POST.get('confirmo'):
            erros.append('Confirme que esta planilha contém apenas acervo disponível ou em manutenção.')
        if request.POST.get('acao') == 'confirmar' and not erros:
            try:
                with transaction.atomic():
                    bloqueado = Importacao.objects.select_for_update().get(pk=pk, criado_por=request.user)
                    if not bloqueado.concluida:
                        bloqueado.resultado = importacao.importar(previa)
                        bloqueado.concluida = True
                        # Dados brutos deixam de ser necessários após confirmação.
                        bloqueado.dados = {}
                        bloqueado.save(update_fields=['resultado', 'concluida', 'dados'])
                    lote = bloqueado
                return render(request, 'acervo/importacao_resultado.html', {'lote': lote})
            except IntegrityError:
                erros = ['O acervo mudou durante a importação. Atualize a prévia e tente novamente. Nenhuma alteração deste lote foi gravada.']
    campos = [{'chave': k, 'rotulo': v, 'selecionado': mapa[k]} for k, v in importacao.CAMPOS.items()]
    return render(request, 'acervo/mapear_importacao.html', {'lote': lote, 'abas': tabelas.keys(), 'aba': aba, 'cabecalho': tabela['cabecalho'], 'amostra': tabela['linhas'][:5], 'campos': campos, 'mapa': mapa, 'previa': previa[:30] if previa is not None else None, 'total': len(previa or []), 'novas': sum(not i['existente'] for i in previa or []), 'erros': erros[:100], 'total_erros': len(erros)})


def celula_csv(valor):
    texto = str('' if valor is None else valor)
    return "'" + texto if texto.lstrip().startswith(('=', '+', '-', '@')) else texto


@login_required
@permission_required('acervo.view_livrocopia', raise_exception=True)
def exportar_acervo(request):
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = 'attachment; filename="acervo.csv"'
    resposta.write('\ufeff')
    writer = csv.writer(resposta, delimiter=';')
    writer.writerow(['Codigo', 'Titulo', 'Autor', 'ISBN', 'Editora', 'Genero', 'Idioma', 'Descricao', 'Situacao'])
    for copia in LivroCopia.objects.select_related('livro__autor', 'livro__lingua').prefetch_related('livro__genero').order_by('codigo', 'pk'):
        livro = copia.livro
        if livro:
            nome_autor = f'{livro.autor.primeiro_nome} {livro.autor.sobrenome}'.strip() if livro.autor else ''
            writer.writerow([celula_csv(v) for v in [copia.codigo or str(copia.pk), livro.titulo, nome_autor, livro.isbn, copia.editora, ', '.join(g.nome for g in livro.genero.all()), livro.lingua or '', livro.descricao, copia.get_estado_display()]])
    return resposta


def modelo_importacao(request):
    resposta = HttpResponse(content_type='text/csv; charset=utf-8')
    resposta['Content-Disposition'] = 'attachment; filename="modelo-acervo.csv"'
    resposta.write('\ufeff')
    writer = csv.writer(resposta, delimiter=';')
    writer.writerow(['Codigo', 'Titulo', 'Autor', 'ISBN', 'Editora', 'Genero', 'Idioma', 'Descricao', 'Situacao'])
    writer.writerow(['BIB-001', 'Dom Casmurro', 'Machado de Assis', '', '', 'Literatura brasileira', 'Português', '', 'Disponível'])
    return resposta
