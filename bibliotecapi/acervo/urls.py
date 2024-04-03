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