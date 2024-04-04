from django.urls import path
from . import views


urlpatterns = [
    path('', views.index, name='index'),
    path('livros/', views.ListaLivrosView.as_view(), name='livros'),
    path('livro/<int:pk>', views.DetalheLivroView.as_view(), name='detalhe-livro'),

]

urlpatterns += [
    path('autores/', views.AutorListView.as_view(), name='autores'),
    path('autor/<int:pk>',
         views.AutorDetailView.as_view(), name='detalhe-autor'),
]

urlpatterns += [
    path('linguas/', views.LinguaListView.as_view(), name='linguas'),
    path('lingua/<int:pk>',
         views.LinguaDetailView.as_view(), name='detalhe-lingua'),
]

urlpatterns += [
    path('generos/', views.GeneroListView.as_view(), name='generos'),
    path('genero/<int:pk>',
         views.GeneroDetailView.as_view(), name='detalhe-genero'),
]

urlpatterns += [
    path('copias/', views.LivroCopiaListView.as_view(), name='copias'),
    path('copia/<uuid:pk>', views.LivroCopiaDetailView.as_view(),
         name='detalhe-copia'),
]

urlpatterns += [
    path('meus-emprestimos/', views.CopiasEmprestadasPorUsuarioListView.as_view(), name='meus-emprestimos'),
    path(r'emprestimos/', views.TodosEmprestimosListView.as_view(), name='todos-emprestimos')
]

urlpatterns += [
    path('copia/<uuid:pk>/renew/', views.renovacao_emprestimo_bibliotecario, name='renovacao-emprestimo-bibliotecario'),
]

urlpatterns += [
    path('autor/adicionar/', views.AdicionarAutor.as_view(), name='adicionar-autor'),
    path('autor/<int:pk>/alterar/', views.AlterarAutor.as_view(), name='alterar-autor'),
    path('autor/<int:pk>/excluir/', views.ExcluirAutor.as_view(), name='excluir-autor'),
]

urlpatterns += [
    path('livro/adicionar/', views.AdicionarLivro.as_view(), name='adicionar-livro'),
    path('livro/<int:pk>/alterar/', views.AlterarLivro.as_view(), name='alterar-livro'),
    path('livro/<int:pk>/excluir/', views.ExcluirLivro.as_view(), name='excluir-livro'),
]


urlpatterns += [
    path('genero/adicionar/', views.AdicionarGenero.as_view(), name='adicionar-genero'),
    path('genero/<int:pk>/alterar/', views.AlterarGenero.as_view(), name='alterar-genero'),
    path('genero/<int:pk>/excluir/', views.ExcluirGenero.as_view(), name='excluir-genero'),
]

urlpatterns += [
    path('lingua/adicionar/', views.AdicionarLingua.as_view(), name='adicionar-lingua'),
    path('lingua/<int:pk>/alterar/',
         views.AlterarLingua.as_view(), name='alterar-lingua'),
    path('lingua/<int:pk>/excluir/',
         views.ExcluirLingua.as_view(), name='excluir-lingua'),
]

urlpatterns += [
    path('copia/create/', views.AdicionarLivroCopia.as_view(),
         name='adicionar-copia'),
    path('copia/<uuid:pk>/alterar/',
         views.AlterarLivroCopia.as_view(), name='alterar-copia'),
    path('copia/<uuid:pk>/excluir/',
         views.ExcluirLivroCopia.as_view(), name='excluir-copia'),
]