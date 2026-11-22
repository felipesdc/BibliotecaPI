from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import acessos
from .circulacao import registrar_emprestimo, registrar_devolucao, registrar_renovacao
from .models import Leitor, Livro, LivroCopia, Reserva
from .reservas import reservar, cancelar


class ReservasTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        acessos.configurar_grupos()
        cls.gestor = acessos.criar_usuario(None, username='gestor_fila', papel='gestor', senha='FilaFicticia2026!', exigir_troca=False)
        cls.atendente = acessos.criar_usuario(cls.gestor, username='balcao_fila', papel='atendente', senha='FilaFicticia2026!', exigir_troca=False)
        cls.consulta = acessos.criar_usuario(cls.gestor, username='consulta_fila', papel='consulta', senha='FilaFicticia2026!', exigir_troca=False)
        cls.livro = Livro.objects.create(titulo='Livro fictício da fila')
        cls.ana = Leitor.objects.create(nome='Ana fictícia')
        cls.bruno = Leitor.objects.create(nome='Bruno fictício')
        cls.clara = Leitor.objects.create(nome='Clara fictícia')
        cls.hoje = timezone.localdate()

    def setUp(self):
        self.client.force_login(self.atendente)
        self.copia = LivroCopia.objects.create(livro=self.livro)

    def reserva(self, leitor):
        return reservar(livro=self.livro, leitor=leitor, operador=self.atendente)

    def emprestar(self, leitor, copia=None):
        return registrar_emprestimo(copia=copia or self.copia, leitor=leitor, prazo=self.hoje + timedelta(days=14), operador=self.atendente)

    def test_fifo_atendimento_automatico_e_promocao_apos_devolucao(self):
        primeira, segunda = self.reserva(self.ana), self.reserva(self.bruno)
        with self.assertRaisesMessage(ValidationError, 'prioridade'):
            self.emprestar(self.bruno)
        evento = self.emprestar(self.ana)
        primeira.refresh_from_db()
        self.assertEqual(primeira.estado, 'u')
        self.assertEqual(primeira.emprestimo, evento)
        self.assertEqual(primeira.encerrado_por, self.atendente)
        r = self.client.get(reverse('reservas'))
        self.assertFalse(r.context['object_list'][0].pode_retirar)
        registrar_devolucao(copia_id=self.copia.pk, operador=self.atendente)
        r = self.client.get(reverse('reservas'))
        self.assertEqual(r.context['object_list'][0].pk, segunda.pk)
        self.assertTrue(r.context['object_list'][0].pode_retirar)
        self.emprestar(self.bruno)
        segunda.refresh_from_db()
        self.assertEqual(segunda.estado, 'u')

    def test_cancelamento_promove_proximo_e_preserva_auditoria(self):
        primeira, segunda = self.reserva(self.ana), self.reserva(self.bruno)
        cancelar(reserva_id=primeira.pk, operador=self.gestor)
        primeira.refresh_from_db()
        self.assertEqual(primeira.estado, 'c')
        self.assertEqual(primeira.encerrado_por, self.gestor)
        with self.assertRaises(ValidationError):
            cancelar(reserva_id=primeira.pk, operador=self.atendente)
        self.emprestar(self.bruno)
        self.assertEqual(Reserva.objects.count(), 2)

    def test_leitor_inativo_fica_suspenso_e_nao_bloqueia_fila(self):
        primeira = self.reserva(self.ana)
        self.reserva(self.bruno)
        self.ana.ativo = False
        self.ana.save()
        self.assertContains(self.client.get(reverse('reservas')), 'Suspensa')
        self.emprestar(self.bruno)
        primeira.refresh_from_db()
        self.assertEqual(primeira.estado, 'a')
        with self.assertRaisesMessage(ValidationError, 'ativo'):
            self.reserva(self.ana)

    def test_exemplares_excedentes_livres_e_prioridade_por_quantidade(self):
        self.reserva(self.ana)
        extra = LivroCopia.objects.create(livro=self.livro)
        self.emprestar(self.clara, extra)  # Uma cópia excedente à fila.
        with self.assertRaisesMessage(ValidationError, 'prioridade'):
            self.emprestar(self.bruno)
        self.emprestar(self.ana)

    def test_segundo_da_fila_pode_retirar_se_ha_duas_copias(self):
        self.reserva(self.ana)
        self.reserva(self.bruno)
        self.reserva(self.clara)
        LivroCopia.objects.create(livro=self.livro)
        with self.assertRaisesMessage(ValidationError, 'prioridade'):
            self.emprestar(self.clara)
        self.emprestar(self.bruno)
        self.assertEqual(Reserva.objects.get(leitor=self.ana).estado, 'a')

    def test_reserva_impede_renovacao_e_cancelamento_libera(self):
        self.emprestar(self.ana)
        espera = self.reserva(self.bruno)
        with self.assertRaisesMessage(ValidationError, 'outro leitor'):
            registrar_renovacao(copia_id=self.copia.pk, prazo=self.hoje)
        cancelar(reserva_id=espera.pk, operador=self.atendente)
        registrar_renovacao(copia_id=self.copia.pk, prazo=self.hoje)
        self.copia.refresh_from_db()
        self.assertEqual(self.copia.data_devolucao, self.hoje)

    def test_nao_duplica_reserva_nem_reserva_titulo_ja_emprestado(self):
        self.reserva(self.ana)
        with self.assertRaisesMessage(ValidationError, 'já está na fila'):
            self.reserva(self.ana)
        self.emprestar(self.ana)
        with self.assertRaisesMessage(ValidationError, 'já tem um exemplar'):
            self.reserva(self.ana)

    def test_rotas_permissoes_csrf_e_post(self):
        reserva = self.reserva(self.ana)
        urls = [reverse('reservas'), reverse('criar-reserva', args=[self.livro.pk]), reverse('cancelar-reserva', args=[reserva.pk])]
        self.client.force_login(self.consulta)
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(urls[0]).status_code, 302)
        self.client.force_login(self.atendente)
        self.assertEqual(self.client.get(urls[2]).status_code, 405)
        self.assertEqual(Reserva.objects.get(pk=reserva.pk).estado, 'a')
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.atendente)
        self.assertEqual(c.post(urls[2]).status_code, 403)

    def test_cadastro_e_filtros_pela_interface(self):
        url = reverse('criar-reserva', args=[self.livro.pk])
        self.assertContains(self.client.get(url, {'q': 'Ana'}), 'Ana fictícia')
        self.assertFalse(Reserva.objects.exists())
        self.assertEqual(self.client.post(url, {'leitor': self.ana.pk}).status_code, 302)
        self.assertEqual(Reserva.objects.count(), 1)
        r = self.client.get(reverse('reservas'), {'q': str(self.ana.pk)})
        self.assertContains(r, 'Exemplar disponível')
        self.assertContains(r, 'posição 1')
        reserva = Reserva.objects.get()
        self.client.post(reverse('cancelar-reserva', args=[reserva.pk]))
        self.assertEqual(self.client.get(reverse('reservas')).context['paginator'].count, 0)
        self.assertEqual(self.client.get(reverse('reservas'), {'situacao': 'c'}).context['paginator'].count, 1)
        self.assertTrue(self.client.get(reverse('reservas'), {'situacao': 'invalida'}).context['form'].errors)

    def test_central_e_tela_antiga_respeitam_a_mesma_fila(self):
        self.reserva(self.ana)
        for rota in [reverse('emprestar', args=[self.copia.pk]), reverse('atendimento')]:
            r = self.client.post(rota, {'acao': 'emprestar', 'leitor': self.bruno.pk, 'copia': self.copia.pk, 'prazo': self.hoje})
            self.assertContains(r, 'prioridade')
        self.copia.refresh_from_db()
        self.assertEqual(self.copia.estado, 'd')
