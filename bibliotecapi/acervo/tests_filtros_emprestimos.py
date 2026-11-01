from datetime import timedelta
from urllib.parse import urlencode

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Leitor, Livro, LivroCopia


class FiltrosEmprestimosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipe = get_user_model().objects.create_user(username='balcao_filtros')
        cls.equipe.user_permissions.set(Permission.objects.filter(content_type__app_label='acervo', codename__in=['marca_devolucao', 'view_leitor']))
        cls.legado = get_user_model().objects.create_user(username='conta_legada', first_name='Nomelegado', last_name='Sobrenomelegado')
        cls.ana = Leitor.objects.create(nome='Ana fictícia')
        cls.bruno = Leitor.objects.create(nome='Bruno fictício')
        cls.livro = Livro.objects.create(titulo='Jardim fictício', isbn='9780000000002')
        cls.outro_livro = Livro.objects.create(titulo='Aventura fictícia')
        cls.hoje = timezone.localdate()
        cls.url = reverse('todos-emprestimos')
        cls.atrasado = LivroCopia.objects.create(livro=cls.livro, codigo='FILTRO-ATRASO', estado='e', leitor=cls.ana, data_devolucao=cls.hoje - timedelta(days=1))
        cls.vence = LivroCopia.objects.create(livro=cls.outro_livro, codigo='FILTRO-HOJE', estado='e', leitor=cls.bruno, data_devolucao=cls.hoje)
        cls.amanha = LivroCopia.objects.create(livro=cls.livro, codigo='FILTRO-AMANHA', estado='e', leitor=cls.ana, data_devolucao=cls.hoje + timedelta(days=1))
        cls.semana = LivroCopia.objects.create(livro=cls.livro, codigo='FILTRO-SEMANA', estado='e', tomador=cls.legado, data_devolucao=cls.hoje + timedelta(days=7))
        cls.futuro = LivroCopia.objects.create(livro=cls.livro, codigo='FILTRO-FUTURO', estado='e', leitor=cls.bruno, data_devolucao=cls.hoje + timedelta(days=8))
        cls.sem_prazo = LivroCopia.objects.create(livro=cls.livro, codigo='FILTRO-SEM-PRAZO', estado='e', leitor=cls.ana)
        cls.disponivel = LivroCopia.objects.create(livro=cls.livro, codigo='DISPONIVEL', estado='d')

    def setUp(self):
        self.client.force_login(self.equipe)

    def registros(self, **filtros):
        r = self.client.get(self.url, filtros)
        self.assertEqual(r.status_code, 200)
        return list(r.context['object_list'])

    def test_busca_por_leitor_titulo_codigo_isbn_e_conta_legada(self):
        self.assertEqual(set(self.registros(q='Ana fictícia')), {self.atrasado, self.amanha, self.sem_prazo})
        self.assertEqual(set(self.registros(q=str(self.ana.pk))), {self.atrasado, self.amanha, self.sem_prazo})
        self.assertEqual(self.registros(q='Aventura'), [self.vence])
        self.assertEqual(self.registros(q='FILTRO-HOJE'), [self.vence])
        self.assertEqual(len(self.registros(q=self.livro.isbn)), 5)
        for nome in ['conta_legada', 'Nomelegado', 'Sobrenomelegado']:
            self.assertEqual(self.registros(q=nome), [self.semana])
        self.assertEqual(self.registros(q='DISPONIVEL'), [])

    def test_situacoes_e_limites_inclusivos_de_periodo(self):
        for filtro, esperado in [('atrasados', [self.atrasado]), ('hoje', [self.vence]), ('semana', [self.amanha, self.semana]), ('sem_prazo', [self.sem_prazo])]:
            self.assertEqual(self.registros(situacao=filtro), esperado)
        self.assertEqual(self.registros(vencimento_de=self.hoje, vencimento_ate=self.hoje + timedelta(days=1)), [self.vence, self.amanha])
        self.assertEqual(self.registros(q='Ana fictícia', situacao='semana', vencimento_ate=self.hoje + timedelta(days=1)), [self.amanha])
        self.assertEqual(self.registros(vencimento_ate=self.hoje), [self.atrasado, self.vence])

    def test_filtros_invalidos_e_situacao_desconhecida(self):
        for dados in [{'vencimento_de': 'invalida'}, {'vencimento_de': self.hoje, 'vencimento_ate': self.hoje - timedelta(days=1)}, {'situacao': 'sem_prazo', 'vencimento_de': self.hoje}, {'q': 'x' * 101}, {'ordem': 'password'}]:
            r = self.client.get(self.url, dados)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.context['filtros'].errors)
            self.assertEqual(list(r.context['object_list']), [])
            self.assertContains(r, 'Corrija os filtros')
        self.assertEqual(len(self.registros(situacao='invalida')), 6)

    def test_ordenacao_e_sem_prazo_no_fim(self):
        self.assertEqual(self.registros()[-1], self.sem_prazo)
        descendente = self.registros(ordem='prazo_desc')
        self.assertEqual(descendente[0], self.futuro)
        self.assertEqual(descendente[-1], self.sem_prazo)
        self.assertEqual(self.registros(ordem='titulo')[0], self.vence)
        nomes = [c.leitor.nome if c.leitor else c.tomador.username for c in self.registros(ordem='leitor')]
        self.assertEqual(nomes, sorted(nomes))

    def test_paginacao_preserva_busca_ordenacao_e_periodo(self):
        for i in range(15):
            LivroCopia.objects.create(livro=self.livro, codigo=f'PAGINA-{i:02}', estado='e', leitor=self.ana, data_devolucao=self.hoje)
        filtros = {'q': 'PAGINA', 'situacao': 'hoje', 'ordem': 'titulo', 'vencimento_de': self.hoje.isoformat()}
        r = self.client.get(self.url, filtros)
        self.assertEqual(len(r.context['object_list']), 10)
        self.assertContains(r, '15</strong> empréstimos encontrados')
        for parametro in ['q=PAGINA', 'situacao=hoje', 'ordem=titulo', 'page=2']:
            self.assertContains(r, parametro)
        self.assertEqual(len(self.client.get(self.url, {**filtros, 'page': 2}).context['object_list']), 5)
        LivroCopia.objects.filter(codigo__startswith='PAGINA-').exclude(codigo='PAGINA-00').delete()
        r = self.client.get(self.url, {**filtros, 'page': 2})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['page_obj'].number, 1)
        self.assertEqual(self.registros(q='nao-encontrado'), [])
        self.assertContains(self.client.get(self.url, {'q': 'nao-encontrado'}), 'amplie o período')

    def test_renovacao_devolucao_preservam_retorno_e_rejeitam_url_externa(self):
        retorno = self.url + '?' + urlencode({'q': 'Ana fictícia', 'situacao': 'atrasados', 'page': 1})
        renovar = reverse('renovacao-emprestimo-bibliotecario', args=[self.atrasado.pk])
        r = self.client.get(renovar, {'retorno': retorno})
        self.assertEqual(r.context['retorno'], retorno)
        r = self.client.post(renovar, {'data_renovacao': self.hoje, 'retorno': retorno})
        self.assertRedirects(r, retorno, fetch_redirect_response=False)
        r = self.client.post(reverse('devolver', args=[self.atrasado.pk]), {'retorno': retorno})
        self.assertRedirects(r, retorno, fetch_redirect_response=False)
        for destino in ['https://example.test/', '//example.test/', '/acervo/usuarios/', 'http://[malformado', self.url + '\\evil', self.url + '\n']:
            r = self.client.get(renovar.replace(str(self.atrasado.pk), str(self.vence.pk)), {'retorno': destino})
            self.assertEqual(r.context['retorno'], self.url)

    def test_permissoes_e_ausencia_de_gravacao_na_busca(self):
        antes = list(LivroCopia.objects.values_list('pk', 'estado', 'data_devolucao'))
        self.client.get(self.url, {'q': 'Ana', 'situacao': 'semana'})
        self.assertEqual(list(LivroCopia.objects.values_list('pk', 'estado', 'data_devolucao')), antes)
        self.client.logout()
        self.assertEqual(self.client.get(self.url, {'q': 'Ana'}).status_code, 302)
        consulta = get_user_model().objects.create_user(username='consulta_filtros')
        self.client.force_login(consulta)
        self.assertEqual(self.client.get(self.url, {'q': 'Ana'}).status_code, 403)
