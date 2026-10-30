from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import acessos
from .circulacao import registrar_emprestimo
from .models import Emprestimo, Leitor, Livro, LivroCopia, PoliticaCirculacao


class RegrasCirculacaoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        acessos.configurar_grupos()
        cls.gestor = acessos.criar_usuario(None, username='gestor_regras', papel='gestor', senha='Ficticia2026!Regras', exigir_troca=False)
        cls.atendente = acessos.criar_usuario(cls.gestor, username='atendente_regras', papel='atendente', senha='Ficticia2026!Regras', exigir_troca=False)
        cls.consulta = acessos.criar_usuario(cls.gestor, username='consulta_regras', papel='consulta', senha='Ficticia2026!Regras', exigir_troca=False)
        cls.leitor = Leitor.objects.create(nome='Leitora fictícia')
        cls.livro = Livro.objects.create(titulo='Livro fictício de circulação')
        cls.hoje = timezone.localdate()

    def setUp(self):
        self.client.force_login(self.gestor)
        self.copia = LivroCopia.objects.create(livro=self.livro)

    def registrar(self, copia=None, dias=14):
        return registrar_emprestimo(copia=copia or self.copia, leitor=self.leitor,
                                   prazo=self.hoje + timedelta(days=dias), operador=self.atendente)

    def test_padrao_preserva_comportamento_e_sugere_prazo(self):
        politica = PoliticaCirculacao.atual()
        self.assertEqual((politica.prazo_padrao, politica.limite_emprestimos, politica.bloquear_atrasados), (14, 0, False))
        self.registrar()
        self.registrar(LivroCopia.objects.create(livro=self.livro))
        self.assertEqual(Emprestimo.objects.count(), 2)
        PoliticaCirculacao.objects.create(pk=1, prazo_padrao=7)
        resposta = self.client.get(reverse('emprestar', args=[self.copia.pk]))
        self.assertEqual(resposta.context['form'].initial['prazo'], self.hoje + timedelta(days=7))

    def test_limite_bloqueia_sem_gravar_e_devolucao_libera(self):
        PoliticaCirculacao.objects.create(pk=1, limite_emprestimos=1)
        primeiro = self.registrar()
        outra = LivroCopia.objects.create(livro=self.livro)
        resposta = self.client.post(reverse('emprestar', args=[outra.pk]), {'leitor': self.leitor.pk, 'prazo': self.hoje})
        self.assertContains(resposta, 'atingiu o limite')
        outra.refresh_from_db()
        self.assertEqual(outra.estado, 'd')
        self.assertEqual(Emprestimo.objects.count(), 1)
        self.client.post(reverse('devolver', args=[self.copia.pk]))
        self.registrar(outra)
        primeiro.refresh_from_db()
        self.assertIsNotNone(primeiro.devolvido_em)

    def test_atraso_inclui_exemplar_legado_e_nao_vencimento_hoje(self):
        PoliticaCirculacao.objects.create(pk=1, bloquear_atrasados=True)
        legado = LivroCopia.objects.create(livro=self.livro, estado='e', leitor=self.leitor, data_devolucao=self.hoje - timedelta(days=1))
        with self.assertRaisesMessage(ValidationError, 'devoluções em atraso'):
            self.registrar()
        legado.data_devolucao = self.hoje
        legado.save()
        self.registrar()
        self.assertEqual(Emprestimo.objects.count(), 1)

    def test_leitor_inativo_e_exemplar_indisponivel(self):
        self.leitor.ativo = False
        self.leitor.save()
        with self.assertRaisesMessage(ValidationError, 'inativo'):
            self.registrar()
        self.leitor.ativo = True
        self.leitor.save()
        self.copia.estado = 'm'
        self.copia.save()
        with self.assertRaisesMessage(ValidationError, 'não está disponível'):
            self.registrar()
        self.assertFalse(Emprestimo.objects.exists())

    def test_limite_nao_conta_outro_leitor_ou_devolvidos(self):
        PoliticaCirculacao.objects.create(pk=1, limite_emprestimos=1, bloquear_atrasados=True)
        outro = Leitor.objects.create(nome='Outro fictício')
        copia = LivroCopia.objects.create(livro=self.livro, estado='e', leitor=outro, data_devolucao=self.hoje - timedelta(days=1))
        Emprestimo.objects.create(copia=self.copia, leitor=self.leitor, prazo=self.hoje - timedelta(days=2), devolvido_em=timezone.now())
        self.registrar()
        self.assertEqual(LivroCopia.objects.get(pk=copia.pk).leitor, outro)

    def test_configuracao_permissoes_validacao_e_persistencia(self):
        url = reverse('politica-circulacao')
        for usuario in [self.atendente, self.consulta]:
            self.client.force_login(usuario)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {'prazo_padrao': 7}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.gestor)
        for prazo, limite in [(0, 1), (366, 1), (7, -1), (7, 1001)]:
            self.assertEqual(self.client.post(url, {'prazo_padrao': prazo, 'limite_emprestimos': limite}).status_code, 200)
            self.assertFalse(PoliticaCirculacao.objects.exists())
        emprestimo = self.registrar()
        self.assertEqual(self.client.post(url, {'prazo_padrao': 7, 'limite_emprestimos': 3, 'bloquear_atrasados': 'on'}).status_code, 302)
        politica = PoliticaCirculacao.atual()
        self.assertEqual((politica.prazo_padrao, politica.limite_emprestimos, politica.bloquear_atrasados), (7, 3, True))
        emprestimo.refresh_from_db()
        self.assertEqual(emprestimo.prazo, self.hoje + timedelta(days=14))
        self.client.post(url, {'prazo_padrao': 10, 'limite_emprestimos': 0})
        self.assertEqual(PoliticaCirculacao.objects.count(), 1)
        self.assertFalse(PoliticaCirculacao.atual().bloquear_atrasados)
