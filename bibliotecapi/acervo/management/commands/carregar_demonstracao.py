from datetime import date, datetime, time, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from acervo.models import Autor, Emprestimo, Genero, Importacao, Leitor, Lingua, Livro, LivroCopia

MARCADOR = '[DEMO v1] acervo fictício'
SENHA_DEMO = 'BibliotecaDemo2026!'


class Command(BaseCommand):
    help = 'Preenche todas as estruturas de negócio com dados fictícios, apenas em ambiente DEMO vazio.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEMO_MODE:
            raise CommandError('Carga recusada: use o Compose de demonstração, com BIBLIOTECA_DEMO=True.')
        if Importacao.objects.filter(nome=MARCADOR, concluida=True).exists():
            self.stdout.write('Demonstração já carregada. Nenhum dado foi alterado.')
            return
        modelos = [Autor, Genero, Lingua, Livro, LivroCopia, Leitor, Emprestimo, Importacao, get_user_model()]
        if any(modelo.objects.exists() for modelo in modelos):
            raise CommandError('Carga recusada: o banco de demonstração precisa estar vazio. Nenhum registro foi alterado.')
        hoje = timezone.localdate()
        zona = timezone.get_current_timezone()

        def instante(dia):
            return timezone.make_aware(datetime.combine(dia, time(10)), zona)

        gestores, _ = Group.objects.get_or_create(name='Gestores da demonstração')
        gestores.permissions.set(Permission.objects.filter(content_type__app_label='acervo'))
        atendentes, _ = Group.objects.get_or_create(name='Atendentes da demonstração')
        atendentes.permissions.set(Permission.objects.filter(content_type__app_label='acervo', codename__in=['view_livro', 'view_livrocopia', 'view_autor', 'view_genero', 'view_lingua', 'view_leitor', 'add_leitor', 'change_leitor', 'marca_devolucao']))
        gestor = get_user_model().objects.create_user('gestor_demo', password=SENHA_DEMO, first_name='Gestão', last_name='Demonstração', email='gestor@example.invalid', is_staff=True)
        gestor.groups.add(gestores)
        atendente = get_user_model().objects.create_user('atendente_demo', password=SENHA_DEMO, first_name='Atendimento', last_name='Demonstração', email='atendente@example.invalid')
        atendente.groups.add(atendentes)
        generos = [Genero.objects.create(nome=nome) for nome in ['Ficção', 'Literatura brasileira', 'Infantojuvenil', 'Ciência e tecnologia', 'História', 'Artes']]
        linguas = [Lingua.objects.create(nome=nome) for nome in ['Português', 'Inglês', 'Espanhol']]
        nomes = [('Helena', 'Campos'), ('Miguel', 'Serra'), ('Lia', 'Vales'), ('Rafael', 'Pontes'), ('Sofia', 'Monte'), ('Caio', 'Ventura'), ('Clara', 'Luz'), ('Davi', 'Rios')]
        autores = [Autor.objects.create(primeiro_nome=nome, sobrenome=sobrenome, data_nascimento=date(1945 + i * 5, 3, 10), data_falecimento=date(2010, 6, 15) if i == 0 else None) for i, (nome, sobrenome) in enumerate(nomes)]
        titulos = ['O jardim das possibilidades', 'Memórias da praça', 'A menina e o farol', 'Ciência no cotidiano', 'Caminhos do nosso bairro', 'Cores em movimento', 'O mapa das estrelas', 'Conversas na varanda', 'O trem dos pequenos sonhos', 'Tecnologia para todos', 'Retratos de outra época', 'A música das ruas', 'O rio que contava histórias', 'Entre cartas e encontros', 'A aventura do quintal', 'Laboratório de ideias', 'Histórias da nossa gente', 'Desenhando o amanhã', 'A casa das perguntas', 'Páginas ao vento', 'O segredo da biblioteca', 'Primeiros passos na programação', 'Pontes entre gerações', 'Teatro na comunidade']
        copias = []
        for i, titulo in enumerate(titulos):
            base_isbn = f'978000{i:06d}'
            digito = (-sum(int(c) * (1 if j % 2 == 0 else 3) for j, c in enumerate(base_isbn))) % 10
            livro = Livro.objects.create(titulo=titulo, autor=autores[i % 8], descricao='Obra fictícia criada exclusivamente para demonstrar o sistema BibliotecaPI.', isbn=base_isbn + str(digito), lingua=linguas[0 if i < 20 else (i % 2) + 1])
            livro.genero.add(generos[i % 6])
            if i % 5 == 0:
                livro.genero.add(generos[(i + 1) % 6])
            for j in range(3):
                copias.append(LivroCopia.objects.create(livro=livro, codigo=f'DEMO-{i + 1:03d}-{j + 1}', editora=f'Editora Fictícia {i % 4 + 1}', estado='d'))
        nomes_leitores = ['Ana', 'Bruno', 'Carla', 'Daniel', 'Elisa', 'Felipe', 'Gabriela', 'Hugo', 'Isabela', 'João', 'Karen', 'Lucas', 'Marina', 'Nicolas', 'Olívia', 'Pedro', 'Quitéria', 'Renata', 'Samuel', 'Talita', 'Ulisses', 'Vitória', 'William', 'Xênia', 'Yara', 'Zeca', 'Alice', 'Bento', 'Cecília', 'Diego']
        leitores = [Leitor.objects.create(nome=f'{nome} — leitor fictício {i + 1:02d}', email=f'leitor{i + 1:02d}@example.invalid', telefone=f'(00) 00000-{i + 1:04d}', ativo=i < 27) for i, nome in enumerate(nomes_leitores)]
        abertos = 0
        for i, copia in enumerate(copias):
            # Até quatro ciclos anteriores, sempre fechados antes dos empréstimos atuais.
            for rodada in range(4):
                if (i + rodada) % 3 == 0:
                    continue
                dia = hoje - timedelta(days=180 - rodada * 30 - i % 18)
                prazo = dia + timedelta(days=14)
                retorno = dia + timedelta(days=7 + i % 8 + (5 if i % 4 == 0 else 0))
                evento = Emprestimo.objects.create(copia=copia, leitor=leitores[(i + rodada * 7) % 30], realizado_por=atendente if i % 2 else gestor, prazo=prazo, devolvido_em=instante(retorno))
                Emprestimo.objects.filter(pk=evento.pk).update(criado_em=instante(dia))
            estado = ['d', 'd', 'd', 'd', 'd', 'd', 'e', 'e', 'e', 'm', 'm', 'r'][i % 12]
            copia.estado = estado
            if estado == 'e':
                dias = [3, 7, 14, 16, 20, 30][abertos % 6]
                dia = hoje - timedelta(days=dias)
                copia.leitor = leitores[abertos % 24]
                copia.data_devolucao = dia + timedelta(days=14)
                if abertos == 17:
                    copia.leitor, copia.tomador = None, atendente
                evento = Emprestimo.objects.create(copia=copia, leitor=copia.leitor, tomador=copia.tomador, realizado_por=atendente, prazo=copia.data_devolucao)
                Emprestimo.objects.filter(pk=evento.pk).update(criado_em=instante(dia))
                abertos += 1
            copia.full_clean()
            copia.save()
        Importacao.objects.create(criado_por=gestor, nome=MARCADOR, dados={'versao': 1, 'data_referencia': hoje.isoformat(), 'ficticio': True}, resultado={'criadas': len(copias), 'ignoradas': 0}, concluida=True)
        Importacao.objects.create(criado_por=gestor, nome='[DEMO] exemplo-pendente.csv', dados={'tabelas': {'Acervo': {'cabecalho': ['Código', 'Título', 'Autor'], 'linhas': [{'numero': 2, 'valores': ['DEMO-EXTRA', 'Novo título fictício', 'Helena Campos']}]}}}, concluida=False)
        self.stdout.write(self.style.SUCCESS(f'Demonstração criada: {Livro.objects.count()} títulos, {len(copias)} exemplares, {len(leitores)} leitores e {Emprestimo.objects.count()} empréstimos.'))
        self.stdout.write('Acesso gestor: gestor_demo | Acesso atendente: atendente_demo | Senha fictícia de ambos: ' + SENHA_DEMO)
