from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Emprestimo, Leitor, Livro, LivroCopia


class HistoricoPesquisavelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipe = get_user_model().objects.create_user(username='equipe_historico')
        cls.equipe.user_permissions.add(Permission.objects.get(content_type__app_label='acervo', codename='marca_devolucao'))
        cls.legado = get_user_model().objects.create_user(username='legado_ficticio', first_name='Nomelegado')
        cls.leitor = Leitor.objects.create(nome='Ana fictícia')
        cls.outro = Leitor.objects.create(nome='Bruno fictício')
        cls.livro = Livro.objects.create(titulo='Jardim de teste', isbn='9780000000002')
        cls.hoje = timezone.localdate()
        cls.url = reverse('historico')

    def setUp(self):
        self.client.force_login(self.equipe)

    def registro(self, *, leitor=None, codigo='HIST-001', devolvido=False, dia=None, horario=time(12), tomador=None):
        copia = LivroCopia.objects.create(livro=self.livro, codigo=codigo)
        evento = Emprestimo.objects.create(copia=copia, leitor=leitor, tomador=tomador, prazo=self.hoje,
                                         devolvido_em=timezone.now() if devolvido else None)
        instante = timezone.make_aware(datetime.combine(dia or self.hoje, horario))
        Emprestimo.objects.filter(pk=evento.pk).update(criado_em=instante)
        return evento

    def test_buscas_combinacao_e_contas_legadas(self):
        ana = self.registro(leitor=self.leitor, devolvido=True)
        bruno = self.registro(leitor=self.outro, codigo='HIST-002')
        legado = self.registro(tomador=self.legado, codigo='HIST-003')
        for busca, ids in [('Ana fictícia', [ana.pk]), (str(self.leitor.pk), [ana.pk]),
                           ('HIST-002', [bruno.pk]), ('Jardim', [legado.pk, bruno.pk, ana.pk]),
                           (self.livro.isbn, [legado.pk, bruno.pk, ana.pk]), ('Nomelegado', [legado.pk])]:
            r = self.client.get(self.url, {'q': busca})
            self.assertEqual(list(r.context['object_list'].values_list('pk', flat=True)), ids)
        r = self.client.get(self.url, {'q': 'HIST', 'situacao': 'devolvidos'})
        self.assertEqual(list(r.context['object_list']), [ana])
        r = self.client.get(self.url, {'situacao': 'abertos'})
        self.assertEqual(list(r.context['object_list']), [legado, bruno])

    def test_periodo_por_registro_inclusivo_na_data_local(self):
        self.registro(codigo='ANTES', dia=self.hoje - timedelta(days=1))
        primeiro = self.registro(codigo='INICIO', horario=time.min)
        ultimo = self.registro(codigo='FIM', horario=time(23, 59, 59), devolvido=True)
        self.registro(codigo='DEPOIS', dia=self.hoje + timedelta(days=1))
        r = self.client.get(self.url, {'inicio': self.hoje, 'fim': self.hoje})
        self.assertEqual(list(r.context['object_list']), [ultimo, primeiro])
        self.assertEqual(r.context['paginator'].count, 2)
        self.assertEqual(len(self.client.get(self.url, {'fim': self.hoje}).context['object_list']), 3)

    def test_validacao_e_estados_vazios(self):
        self.registro(leitor=self.leitor)
        for dados in [{'inicio': 'invalido'}, {'inicio': self.hoje, 'fim': self.hoje - timedelta(days=1)},
                      {'situacao': 'invalida'}, {'q': 'x' * 101}]:
            r = self.client.get(self.url, dados)
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.context['filtros'].errors)
            self.assertEqual(list(r.context['object_list']), [])
            self.assertContains(r, 'Corrija os filtros')
        self.assertContains(self.client.get(self.url, {'q': 'nao-existe'}), 'Nenhum registro encontrado')

    def test_paginacao_preserva_filtros_e_ordem_estavel(self):
        ids = [self.registro(leitor=self.leitor, codigo=f'PAG-{i}', devolvido=True).pk for i in range(27)]
        filtros = {'q': 'PAG-', 'situacao': 'devolvidos', 'inicio': self.hoje.isoformat()}
        r = self.client.get(self.url, filtros)
        self.assertEqual(list(r.context['object_list'].values_list('pk', flat=True)), list(reversed(ids))[0:25])
        self.assertContains(r, '27</strong> registros encontrados')
        for parametro in ['q=PAG-', 'situacao=devolvidos', 'inicio=', 'page=2']:
            self.assertContains(r, parametro)
        r = self.client.get(self.url, {**filtros, 'page': 2})
        self.assertEqual(len(r.context['object_list']), 2)

    def test_acesso_e_buscas_nao_alteram_registros(self):
        evento = self.registro(leitor=self.leitor)
        antes = list(Emprestimo.objects.values())
        self.client.get(self.url, {'q': 'Ana', 'situacao': 'abertos'})
        self.assertEqual(list(Emprestimo.objects.values()), antes)
        self.assertEqual(Emprestimo.objects.get().pk, evento.pk)
        self.client.logout()
        self.assertEqual(self.client.get(self.url, {'q': 'Ana'}).status_code, 302)
        self.client.force_login(self.legado)
        self.assertEqual(self.client.get(self.url, {'q': 'Ana'}).status_code, 403)
