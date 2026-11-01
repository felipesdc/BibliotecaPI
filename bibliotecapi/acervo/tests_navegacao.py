from html.parser import HTMLParser

from django.test import TestCase
from django.urls import reverse

from . import acessos
from .models import Leitor, Livro, LivroCopia


class Elementos(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.itens = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.itens.append((tag, dict(attrs)))


class NavegacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        acessos.configurar_grupos()
        cls.gestor = acessos.criar_usuario(None, username='gestor_navegacao', papel='gestor', senha='NavegacaoFicticia2026!', exigir_troca=False)
        cls.consulta = acessos.criar_usuario(cls.gestor, username='consulta_navegacao', papel='consulta', senha='NavegacaoFicticia2026!', exigir_troca=False)
        cls.leitor = Leitor.objects.create(nome='Leitora fictícia')
        cls.livro = Livro.objects.create(titulo='Livro fictício')
        cls.copia = LivroCopia.objects.create(livro=cls.livro)

    def setUp(self):
        self.client.force_login(self.gestor)

    def ativos(self, resposta):
        return [attrs for tag, attrs in Elementos(resposta.content.decode()).itens if tag == 'a' and 'aria-current' in attrs]

    def test_secao_atual_na_lista_e_nas_telas_filhas(self):
        for rota, argumentos, secao, estado in [
            ('livros', [], 'livros', 'page'), ('detalhe-livro', [self.livro.pk], 'livros', 'location'),
            ('alterar-livro', [self.livro.pk], 'livros', 'location'),
            ('detalhe-copia', [self.copia.pk], 'copias', 'location'),
            ('detalhe-leitor', [self.leitor.pk], 'leitores', 'location'),
            ('alterar-leitor', [self.leitor.pk], 'leitores', 'location'),
            ('criar-usuario', [], 'usuarios', 'location'),
            ('emprestar', [self.copia.pk], 'todos-emprestimos', 'location'),
            ('historico', [], 'historico', 'page'), ('importar-acervo', [], 'importar-acervo', 'page'),
        ]:
            with self.subTest(rota=rota):
                r = self.client.get(reverse(rota, args=argumentos))
                self.assertEqual(r.status_code, 200)
                ativos = self.ativos(r)
                self.assertEqual(len(ativos), 1)
                self.assertEqual(ativos[0]['href'], reverse(secao))
                self.assertEqual(ativos[0]['aria-current'], estado)

    def test_estrutura_do_menu_e_link_para_conteudo(self):
        r = self.client.get(reverse('index'))
        elementos = Elementos(r.content.decode()).itens
        botao = next(attrs for tag, attrs in elementos if attrs.get('id') == 'alternar-menu')
        self.assertEqual(botao['type'], 'button')
        self.assertIn('hidden', botao)
        self.assertEqual(botao['aria-controls'], 'menu-biblioteca')
        menu = next(attrs for tag, attrs in elementos if attrs.get('id') == 'menu-biblioteca')
        self.assertNotIn('hidden', menu)  # Sem JS, todos os links permanecem disponíveis.
        self.assertTrue(any(tag == 'a' and attrs.get('href') == '#conteudo' for tag, attrs in elementos))
        self.assertTrue(any(attrs.get('id') == 'conteudo' and attrs.get('tabindex') == '-1' for _, attrs in elementos))
        self.assertTrue(any(tag == 'script' and attrs.get('src', '').endswith('/js/interface.js') and 'defer' in attrs for tag, attrs in elementos))

    def test_resumo_de_erros_liga_ao_campo_e_preserva_dados(self):
        r = self.client.post(reverse('adicionar-leitor'), {'nome': '', 'email': 'email-invalido', 'telefone': '000-testes'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Revise os dados para continuar')
        self.assertContains(r, 'href="#id_nome"')
        self.assertContains(r, 'href="#id_email"')
        self.assertContains(r, '000-testes')
        self.assertContains(r, 'aria-invalid="true"')
        elementos = Elementos(r.content.decode()).itens
        resumo = [attrs for _, attrs in elementos if 'data-foco-erros' in attrs]
        self.assertEqual(len(resumo), 1)
        self.assertEqual(resumo[0]['tabindex'], '-1')
        self.assertNotContains(self.client.get(reverse('adicionar-leitor')), 'Revise os dados para continuar')

    def test_filtros_e_central_tem_um_alvo_de_foco_de_erros(self):
        for r in [self.client.get(reverse('todos-emprestimos'), {'vencimento_de': 'invalido'}),
                  self.client.post(reverse('atendimento'), {'leitor': self.leitor.pk, 'acao': 'emprestar', 'copia': 'invalido', 'prazo': ''})]:
            self.assertEqual(r.status_code, 200)
            resumo = [attrs for _, attrs in Elementos(r.content.decode()).itens if 'data-foco-erros' in attrs]
            self.assertEqual(len(resumo), 1)

    def test_titulo_da_aba_e_permissoes_do_menu(self):
        r = self.client.get(reverse('leitores'))
        self.assertContains(r, '<title>Leitores · BibliotecaPI</title>', html=True)
        self.client.force_login(self.consulta)
        r = self.client.get(reverse('livros'))
        self.assertContains(r, 'Catálogo de livros · BibliotecaPI')
        self.assertNotContains(r, 'href="' + reverse('usuarios') + '"')
        self.assertNotContains(r, 'href="' + reverse('atendimento') + '"')
        self.client.logout()
        r = self.client.get(reverse('login'))
        self.assertContains(r, 'Acesso à biblioteca · BibliotecaPI')
        self.assertEqual(self.ativos(r), [])
