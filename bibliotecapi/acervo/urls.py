from django.urls import path
from . import views, views_relatorios


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

urlpatterns += [
    path('importar/', views.importar_acervo, name='importar-acervo'),
    path('importar/<int:pk>/', views.mapear_importacao, name='mapear-importacao'),
    path('modelo/', views.modelo_importacao, name='modelo-importacao'),
    path('exportar/', views.exportar_acervo, name='exportar-acervo'),
    path('leitores/', views.LeitoresView.as_view(), name='leitores'),
    path('leitores/<int:pk>/', views.DetalheLeitorView.as_view(), name='detalhe-leitor'),
    path('leitores/adicionar/', views.AdicionarLeitor.as_view(), name='adicionar-leitor'),
    path('leitores/<int:pk>/alterar/', views.AlterarLeitor.as_view(), name='alterar-leitor'),
    path('copia/<uuid:pk>/emprestar/', views.emprestar, name='emprestar'),
    path('copia/<uuid:pk>/devolver/', views.devolver, name='devolver'),
    path('historico/', views.HistoricoView.as_view(), name='historico'),
]

urlpatterns += [path('relatorios/', views_relatorios.relatorios, name='relatorios')]

from . import views_acessos
urlpatterns += [
    path('usuarios/', views_acessos.usuarios, name='usuarios'),
    path('usuarios/criar/', views_acessos.criar_usuario, name='criar-usuario'),
    path('usuarios/<int:pk>/', views_acessos.editar_usuario, name='editar-usuario'),
    path('usuarios/<int:pk>/desativar/', views_acessos.situacao_usuario, {'ativo': False}, name='desativar-usuario'),
    path('usuarios/<int:pk>/reativar/', views_acessos.situacao_usuario, {'ativo': True}, name='reativar-usuario'),
    path('usuarios/<int:pk>/senha/', views_acessos.redefinir_senha, name='redefinir-senha-usuario'),
]

urlpatterns += [path('regras-circulacao/', views.politica_circulacao, name='politica-circulacao')]
