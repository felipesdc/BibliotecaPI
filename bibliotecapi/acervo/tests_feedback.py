from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .feedback import CHAVE_RESULTADO
from .models import Emprestimo, Leitor, Livro, LivroCopia


class ResultadoCirculacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipe = get_user_model().objects.create_user(username='operador_ficticio')
        cls.equipe.user_permissions.set(Permission.objects.filter(content_type__app_label='acervo', codename__in=['marca_devolucao', 'view_leitor']))
        cls.leitor = Leitor.objects.create(nome='Leitora de teste')
        cls.livro = Livro.objects.create(titulo='Livro fictício de confirmação')
        cls.hoje = timezone.localdate()
        cls.lista = reverse('todos-emprestimos')

    def setUp(self):
        self.client.force_login(self.equipe)
        self.copia = LivroCopia.objects.create(livro=self.livro, codigo='RESUMO-001')

    def emprestar(self, seguir=False):
        return self.client.post(reverse('emprestar', args=[self.copia.pk]),
                                {'leitor': self.leitor.pk, 'prazo': self.hoje}, follow=seguir)

    def test_emprestimo_resumo_unico_e_atalhos(self):
        r = self.emprestar(seguir=True)
        for texto in ['Empréstimo confirmado:', self.livro.titulo, 'RESUMO-001', self.leitor.nome,
                      self.hoje.strftime('%d/%m/%Y'), 'operador_ficticio', 'Continuar com este leitor', 'Atender outro leitor']:
            self.assertContains(r, texto)
        self.assertEqual(Emprestimo.objects.count(), 1)
        self.assertNotIn(CHAVE_RESULTADO, self.client.session)
        self.assertNotContains(self.client.get(self.lista), 'Empréstimo confirmado:')

    def test_renovacao_exibe_novo_prazo(self):
        self.emprestar(seguir=True)
        novo = self.hoje + timedelta(days=7)
        r = self.client.post(reverse('renovacao-emprestimo-bibliotecario', args=[self.copia.pk]), {'data_renovacao': novo}, follow=True)
        self.assertContains(r, 'Renovação confirmada:')
        self.assertContains(r, 'Novo prazo')
        self.assertContains(r, novo.strftime('%d/%m/%Y'))
        self.assertEqual(Emprestimo.objects.get().prazo, novo)

    def test_devolucao_preserva_identificacao_antes_de_limpar_exemplar(self):
        self.emprestar(seguir=True)
        r = self.client.post(reverse('devolver', args=[self.copia.pk]), follow=True)
        self.assertContains(r, 'Devolução confirmada:')
        self.assertContains(r, self.leitor.nome)
        self.assertContains(r, 'Prazo anterior')
        self.assertContains(r, 'Exemplar disponível novamente.')
        self.copia.refresh_from_db()
        self.assertIsNone(self.copia.leitor_id)
        self.assertIsNotNone(Emprestimo.objects.get().devolvido_em)
        repetida = self.client.post(reverse('devolver', args=[self.copia.pk]), follow=True)
        self.assertNotContains(repetida, 'Devolução confirmada:')

    def test_erros_nao_exibem_resumo_de_sucesso(self):
        r = self.client.post(reverse('emprestar', args=[self.copia.pk]), {'leitor': self.leitor.pk, 'prazo': 'invalido'})
        self.assertNotContains(r, 'Empréstimo confirmado:')
        self.assertNotIn(CHAVE_RESULTADO, self.client.session)
        self.emprestar(seguir=True)
        r = self.client.post(reverse('emprestar', args=[self.copia.pk]), {'leitor': self.leitor.pk, 'prazo': self.hoje})
        self.assertNotContains(r, 'Empréstimo confirmado:')
        self.assertNotIn(CHAVE_RESULTADO, self.client.session)

    def test_resumo_so_no_destino_expira_e_nao_vaza_para_outro_usuario(self):
        self.emprestar()
        self.assertNotContains(self.client.get(reverse('index')), 'Empréstimo confirmado:')
        self.assertIn(CHAVE_RESULTADO, self.client.session)
        with patch('acervo.feedback.timezone.now', return_value=timezone.now() + timedelta(minutes=11)):
            self.assertNotContains(self.client.get(self.lista), 'Empréstimo confirmado:')
        self.assertNotIn(CHAVE_RESULTADO, self.client.session)
        self.client.post(reverse('renovacao-emprestimo-bibliotecario', args=[self.copia.pk]), {'data_renovacao': self.hoje})
        resumo = self.client.session[CHAVE_RESULTADO]
        outro = get_user_model().objects.create_user(username='outro_operador')
        outro.user_permissions.set(self.equipe.user_permissions.all())
        self.client.force_login(outro)
        sessao = self.client.session
        sessao[CHAVE_RESULTADO] = resumo
        sessao.save()
        self.assertNotContains(self.client.get(self.lista), 'Renovação confirmada:')
        self.assertNotIn(CHAVE_RESULTADO, self.client.session)

    def test_legado_e_texto_escapado(self):
        self.livro.titulo = '<script>alert("teste")</script>'
        self.livro.save()
        self.copia.estado = 'e'
        self.copia.tomador = self.equipe
        self.copia.data_devolucao = self.hoje
        self.copia.save()
        r = self.client.post(reverse('devolver', args=[self.copia.pk]), follow=True)
        self.assertContains(r, '&lt;script&gt;')
        self.assertNotContains(r, '<script>')
        self.assertContains(r, 'operador_ficticio')
        self.assertNotContains(r, 'Continuar com este leitor')

    def test_central_usa_mesmo_resumo_e_permissoes_dos_atalhos(self):
        r = self.client.post(reverse('atendimento'), {'acao': 'emprestar', 'copia': self.copia.pk,
                'leitor': self.leitor.pk, 'prazo': self.hoje, 'busca_exemplar': 'RESUMO'}, follow=True)
        self.assertContains(r, 'Empréstimo confirmado:')
        self.assertEqual(r.context['leitor'], self.leitor)
        self.assertEqual(r.context['resultado_circulacao']['codigo'], 'RESUMO-001')
        self.equipe.user_permissions.remove(Permission.objects.get(content_type__app_label='acervo', codename='view_leitor'))
        r = self.client.post(reverse('renovacao-emprestimo-bibliotecario', args=[self.copia.pk]), {'data_renovacao': self.hoje}, follow=True)
        self.assertContains(r, 'Renovação confirmada:')
        self.assertNotContains(r, 'Continuar com este leitor')
        self.assertNotContains(r, 'Atender outro leitor')
