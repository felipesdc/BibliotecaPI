from django.contrib import admin

# Register your models here.

from .models import Autor, Genero, Livro, LivroCopia, Lingua

"""Minimal registration of Models.
admin.site.register(Book)
admin.site.register(Author)
admin.site.register(BookInstance)
admin.site.register(Genre)
admin.site.register(Language)
"""

admin.site.register(Genero)
admin.site.register(Lingua)


class LivrosInline(admin.TabularInline):
    """Defines format of inline book insertion (used in AuthorAdmin)"""
    model = Livro


@admin.register(Autor)
class AutorAdmin(admin.ModelAdmin):
    """Administration object for Author models.
    Defines:
     - fields to be displayed in list view (list_display)
     - orders fields in detail view (fields),
       grouping the date fields horizontally
     - adds inline addition of books in author view (inlines)
    """
    list_display = ('sobrenome',
                    'primeiro_nome', 'data_nascimento', 'data_falecimento')
    fields = ['primeiro_nome', 'sobrenome', ('data_nascimento', 'data_falecimento')]
    inlines = [LivrosInline]


class LivroCopiaInline(admin.TabularInline):
    """Defines format of inline book instance insertion (used in BookAdmin)"""
    model = LivroCopia


class LivroAdmin(admin.ModelAdmin):
    """Administration object for Book models.
    Defines:
     - fields to be displayed in list view (list_display)
     - adds inline addition of book instances in book view (inlines)
    """
    list_display = ('titulo', 'autor', 'mostra_genero')
    inlines = [LivroCopiaInline]


admin.site.register(Livro)


@admin.register(LivroCopia)
class LivroCopiaAdmin(admin.ModelAdmin):
    """Administration object for BookInstance models.
    Defines:
     - fields to be displayed in list view (list_display)
     - filters that will be displayed in sidebar (list_filter)
     - grouping of fields into sections (fieldsets)
    """
    list_display = ('livro', 'estado', 'tomador', 'data_devolucao', 'id')
    list_filter = ('estado', 'data_devolucao')

    fieldsets = (
        (None, {
            'fields': ('livro', 'editora', 'id')
        }),
        ('Availability', {
            'fields': ('estado', 'data_devolucao', 'tomador')
        }),
    )

