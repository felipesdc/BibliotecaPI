from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .circulacao import registrar_emprestimo
from .models import Emprestimo, Leitor, Livro, LivroCopia, PoliticaCirculacao


class AtendimentoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipe = get_user_model().objects.create_user(username='balcao_ficticio')
        cls.equipe.user_permissions.set(Permission.objects.filter(content_type__app_label='acervo', codename__in=['view_leitor', 'marca_devolucao']))
        cls.leitor = Leitor.objects.create(nome='Ana fictícia')
        cls.outro = Leitor.objects.create(nome='Bruno fictício')
        cls.livro = Livro.objects.create(titulo='Livro de teste', isbn='9780000000002')
        cls.hoje = timezone.localdate()
        cls.url = reverse('atendimento')

    def setUp(self):
        self.client.force_login(self.equipe)
        self.copia = LivroCopia.objects.create(livro=self.livro, codigo='TESTE-001')

    def dados(self, acao='emprestar', **extras):
        return {'acao': acao, 'leitor': self.leitor.pk, 'copia': self.copia.pk,
                'prazo': self.hoje + timedelta(days=7), 'busca_exemplar': 'TESTE', **extras}

    def abrir(self, leitor=None):
        return self.client.get(self.url, {'leitor': (leitor or self.leitor).pk, 'busca_exemplar': 'TESTE'})

    def emprestar(self):
        return registrar_emprestimo(copia=self.copia, leitor=self.leitor, prazo=self.hoje, operador=self.equipe)

    def confirmacao(self):
        return self.abrir().context['abertos'][0].confirmacao

    def test_busca_e_selecao_sem_mutacoes(self):
        resposta = self.client.get(self.url, {'busca_leitor': 'Ana', 'busca_exemplar': 'TESTE-001'})
        self.assertContains(resposta, 'Ana fictícia')
        self.assertContains(resposta, 'TESTE-001')
        self.assertNotContains(resposta, 'Emprestar TESTE-001 para')
        for consulta in ['Livro de teste', self.livro.isbn]:
            self.assertContains(self.client.get(self.url, {'busca_exemplar': consulta}), 'TESTE-001')
        self.assertEqual(self.client.get(self.url, {'busca_leitor': str(self.leitor.pk)}).context['leitores'], [self.leitor])
        self.assertContains(self.abrir(), 'Emprestar TESTE-001 para Ana fictícia')
        self.copia.refresh_from_db()
        self.assertEqual(self.copia.estado, 'd')
        self.assertFalse(Emprestimo.objects.exists())

    def test_ciclo_completo_e_feedback(self):
        resposta = self.client.post(self.url, self.dados(), follow=True)
        self.assertContains(resposta, 'Empréstimo confirmado:')
        self.assertContains(resposta, 'TESTE-001 para Ana fictícia')
        self.assertEqual(resposta.context['leitor'], self.leitor)
        self.assertEqual(len(resposta.context['abertos']), 1)
        token = self.confirmacao()
        resposta = self.client.post(self.url, self.dados('renovar', confirmacao=token), follow=True)
        self.assertContains(resposta, 'Renovação confirmada:')
        self.assertEqual(Emprestimo.objects.get().prazo, self.hoje + timedelta(days=7))
        resposta = self.client.post(self.url, self.dados('devolver', confirmacao=self.confirmacao()), follow=True)
        self.assertContains(resposta, 'Devolução confirmada:')
        self.assertContains(resposta, 'não tem exemplares emprestados')
        self.copia.refresh_from_db()
        self.assertEqual(self.copia.estado, 'd')
        self.assertIsNotNone(Emprestimo.objects.get().devolvido_em)

    def test_regras_revalidadas_e_sem_gravacao_em_rejeicoes(self):
        self.emprestar()
        PoliticaCirculacao.objects.create(pk=1, limite_emprestimos=1)
        outra = LivroCopia.objects.create(livro=self.livro)
        self.assertContains(self.abrir(), 'Limite de empréstimos atingido')
        resposta = self.client.post(self.url, self.dados(copia=outra.pk))
        self.assertContains(resposta, 'atingiu o limite')
        self.assertEqual(Emprestimo.objects.count(), 1)
        self.assertContains(self.client.post(self.url, self.dados(prazo='invalido')), 'Informe uma data válida')
        self.assertEqual(self.client.post(self.url, self.dados(leitor='')).status_code, 200)
        self.assertEqual(Emprestimo.objects.count(), 1)

    def test_isolamento_e_tela_desatualizada(self):
        self.emprestar()
        token = self.confirmacao()
        self.assertContains(self.client.post(self.url, self.dados('devolver', leitor=self.outro.pk, confirmacao=token)), 'não pertence')
        self.assertContains(self.client.post(self.url, self.dados('devolver', confirmacao='falso')), 'inválida')
        self.copia.refresh_from_db()
        self.assertEqual(self.copia.estado, 'e')
        self.client.post(self.url, self.dados('devolver', confirmacao=token))
        self.emprestar()  # Mesmo leitor e prazo, mas outro registro de empréstimo.
        self.assertContains(self.client.post(self.url, self.dados('devolver', confirmacao=token)), 'foi alterado')
        self.assertEqual(Emprestimo.objects.filter(devolvido_em__isnull=True).count(), 1)

    def test_renovacao_invalida_inativo_e_legado(self):
        self.copia.estado = 'e'
        self.copia.leitor = self.leitor
        self.copia.data_devolucao = self.hoje - timedelta(days=1)
        self.copia.save()
        self.leitor.ativo = False
        self.leitor.save()
        resposta = self.abrir()
        self.assertEqual(resposta.context['atrasados'], 1)
        self.assertContains(resposta, 'Leitor inativo')
        token = self.confirmacao()
        self.assertContains(self.client.post(self.url, self.dados('renovar', prazo=self.hoje + timedelta(days=29), confirmacao=token)), '28 dias')
        self.assertEqual(self.client.post(self.url, self.dados('devolver', confirmacao=token)).status_code, 302)
        self.assertIsNotNone(Emprestimo.objects.get().devolvido_em)

    def test_permissoes_csrf_e_ids_invalidos(self):
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        for permissao in ['view_leitor', 'marca_devolucao', 'view_livro']:
            usuario = get_user_model().objects.create_user(username=permissao)
            usuario.user_permissions.add(Permission.objects.get(content_type__app_label='acervo', codename=permissao))
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.post(self.url, self.dados()).status_code, 403)
        self.client.force_login(self.equipe)
        for valor in ['abc', '-1', '9' * 30, '9999999']:
            self.assertEqual(self.client.get(self.url, {'leitor': valor}).status_code, 404)
        protegido = Client(enforce_csrf_checks=True)
        protegido.force_login(self.equipe)
        self.assertEqual(protegido.post(self.url, self.dados()).status_code, 403)
        self.assertContains(self.client.post(self.url, self.dados(copia='invalido')), 'UUID')
        self.assertEqual(self.client.put(self.url).status_code, 405)

    def test_limita_resultados_e_estado_vazio(self):
        for numero in range(22):
            Leitor.objects.create(nome=f'Pessoa fictícia {numero}')
        resposta = self.client.get(self.url, {'busca_leitor': 'Pessoa fictícia'})
        self.assertEqual(len(resposta.context['leitores']), 21)
        self.assertContains(resposta, 'primeiros 20 leitores')
        self.assertContains(self.client.get(self.url, {'busca_exemplar': 'nao-existe'}), 'Nenhum exemplar encontrado')
        self.assertContains(self.client.get(self.url, {'busca_leitor': 'nao-existe'}), 'Nenhum leitor encontrado')

    def test_confirmacao_expirada(self):
        self.emprestar()
        token = self.confirmacao()
        with patch('django.core.signing.time.time', return_value=timezone.now().timestamp() + 7200):
            self.assertContains(self.client.post(self.url, self.dados('devolver', confirmacao=token)), 'expirou')
        self.assertIsNone(Emprestimo.objects.get().devolvido_em)
