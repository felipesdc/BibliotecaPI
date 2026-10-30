from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Emprestimo, Leitor, Livro, LivroCopia


class FichaLeitorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipe = get_user_model().objects.create_user(username='equipe_ficticia')
        cls.equipe.user_permissions.set(Permission.objects.filter(
            content_type__app_label='acervo', codename__in=['view_leitor', 'marca_devolucao']))
        cls.leitor = Leitor.objects.create(nome='Leitora fictícia', email='leitora@example.test')
        cls.outro = Leitor.objects.create(nome='Outro leitor fictício')
        cls.livro = Livro.objects.create(titulo='História fictícia')
        cls.hoje = timezone.localdate()
        cls.url = reverse('detalhe-leitor', args=[cls.leitor.pk])

    def setUp(self):
        self.client.force_login(self.equipe)

    def emprestimo(self, leitor=None, dias=0, devolvido=False):
        copia = LivroCopia.objects.create(livro=self.livro)
        return Emprestimo.objects.create(
            copia=copia, leitor=leitor or self.leitor, prazo=self.hoje + timedelta(days=dias),
            devolvido_em=timezone.now() if devolvido else None, realizado_por=self.equipe)

    def test_totais_filtros_e_isolamento(self):
        atraso = self.emprestimo(dias=-1)
        vence_hoje = self.emprestimo()
        encerrado = self.emprestimo(dias=-5, devolvido=True)
        self.emprestimo(leitor=self.outro, dias=-1)
        for filtro, esperados in [('', [encerrado.pk, vence_hoje.pk, atraso.pk]),
                                 ('abertos', [vence_hoje.pk, atraso.pk]),
                                 ('atrasados', [atraso.pk]), ('devolvidos', [encerrado.pk]),
                                 ('invalido', [encerrado.pk, vence_hoje.pk, atraso.pk])]:
            with self.subTest(filtro=filtro):
                resposta = self.client.get(self.url, {'situacao': filtro})
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(list(resposta.context['object_list'].values_list('pk', flat=True)), esperados)
                self.assertEqual(resposta.context['resumo'], dict(total=3, abertos=2, atrasados=1, devolvidos=1))
        self.assertContains(self.client.get(self.url), 'leitora@example.test')

    def test_acesso_exige_as_duas_permissoes(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        for codenomes in [[], ['view_leitor'], ['marca_devolucao']]:
            usuario = get_user_model().objects.create_user(username='teste' + str(len(codenomes)) + ''.join(codenomes))
            usuario.user_permissions.set(Permission.objects.filter(content_type__app_label='acervo', codename__in=codenomes))
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_inativo_vazio_e_inexistente(self):
        self.leitor.ativo = False
        self.leitor.save()
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'Leitor inativo')
        self.assertContains(resposta, 'Nenhum empréstimo encontrado')
        self.assertEqual(self.client.get(reverse('detalhe-leitor', args=[999999])).status_code, 404)

    def test_paginacao_preserva_filtro(self):
        for _ in range(21):
            self.emprestimo(dias=-1)
        resposta = self.client.get(self.url, {'situacao': 'atrasados'})
        self.assertEqual(len(resposta.context['object_list']), 20)
        self.assertContains(resposta, 'situacao=atrasados&amp;page=2')
        self.assertEqual(len(self.client.get(self.url, {'situacao': 'atrasados', 'page': 2}).context['object_list']), 1)
