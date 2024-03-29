# Generated by Django 4.2.10 on 2024-03-08 01:21

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Autor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('primeiro_nome', models.CharField(max_length=100)),
                ('sobrenome', models.CharField(max_length=100)),
                ('data_nascimento', models.DateField(blank=True, null=True)),
                ('data_falecimento', models.DateField(blank=True, null=True, verbose_name='morte')),
            ],
            options={
                'ordering': ['sobrenome', 'primeiro_nome'],
            },
        ),
        migrations.CreateModel(
            name='Genero',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(help_text='Gênero do Livro (por exemplo Literatura Nacional, Estrangeira, Não Ficção etc.)', max_length=200, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='Lingua',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(help_text='Língua em que o livro está escrito', max_length=200, unique=True)),
            ],
        ),
        migrations.CreateModel(
            name='Livro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=200)),
                ('descricao', models.TextField(help_text='Breve descrição do livro', max_length=1000)),
                ('isbn', models.CharField(help_text='13 Caracteres <a href="https://www.isbn-international.org/content/what-isbn">ISBN number</a>', max_length=13, unique=True, verbose_name='ISBN')),
                ('autor', models.ForeignKey(null=True, on_delete=django.db.models.deletion.RESTRICT, to='acervo.autor')),
                ('genero', models.ManyToManyField(help_text='Selecione o gênero do livro', to='acervo.genero')),
                ('lingua', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='acervo.lingua')),
            ],
            options={
                'ordering': ['titulo', 'autor'],
            },
        ),
        migrations.CreateModel(
            name='LivroCopia',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, help_text='ID único para uma cópia do livro disponível na biblioteca', primary_key=True, serialize=False)),
                ('editora', models.CharField(max_length=200)),
                ('data_devolucao', models.DateField(blank=True, null=True)),
                ('estado', models.CharField(blank=True, choices=[('m', 'Manutenção'), ('e', 'Emprestado'), ('d', 'Disponível'), ('r', 'Reservado')], default='m', help_text='Disponibilidade do Livro', max_length=1)),
                ('livro', models.ForeignKey(null=True, on_delete=django.db.models.deletion.RESTRICT, to='acervo.livro')),
                ('tomador', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['data_devolucao'],
                'permissions': (('marca_devolucao', 'Marca o livro como devolvido'),),
            },
        ),
    ]
