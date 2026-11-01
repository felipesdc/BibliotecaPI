from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import acessos
from .models import Emprestimo, Leitor, Livro, LivroCopia


class PainelInicialTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        acessos.configurar_grupos()
        cls.gestor = acessos.criar_usuario(None, username='gestor_painel', papel='gestor', senha='PainelFicticio2026!', exigir_troca=False)
        cls.atendente = acessos.criar_usuario(cls.gestor, username='atendente_painel', papel='atendente', senha='PainelFicticio2026!', exigir_troca=False)
        cls.consulta = acessos.criar_usuario(cls.gestor, username='consulta_painel', papel='consulta', senha='PainelFicticio2026!', exigir_troca=False)
        cls.leitor = Leitor.objects.create(nome='Leitor privado fictício')
        cls.livro = Livro.objects.create(titulo='Título de teste do painel')
        cls.hoje = timezone.localdate()
        cls.atrasado = LivroCopia.objects.create(livro=cls.livro, codigo='ATRASO-01', estado='e', leitor=cls.leitor, data_devolucao=cls.hoje - timedelta(days=2))
        cls.vence = LivroCopia.objects.create(livro=cls.livro, codigo='HOJE-01', estado='e', leitor=cls.leitor, data_devolucao=cls.hoje)
        cls.futuro = LivroCopia.objects.create(livro=cls.livro, codigo='FUTURO-01', estado='e', leitor=cls.leitor, data_devolucao=cls.hoje + timedelta(days=1))
        cls.sem_prazo = LivroCopia.objects.create(livro=cls.livro, estado='e')
        LivroCopia.objects.create(livro=cls.livro, estado='d')
        LivroCopia.objects.create(livro=cls.livro, estado='m', data_devolucao=cls.hoje - timedelta(days=3))

    def inicio(self, usuario):
        self.client.force_login(usuario)
        return self.client.get(reverse('index'))

    def test_atendente_prioriza_operacao(self):
        r = self.inicio(self.atendente)
        self.assertContains(r, 'Vamos atender a próxima leitura?')
        self.assertContains(r, 'Abrir central de atendimento')
        self.assertNotContains(r, 'Empréstimos neste mês')
        self.assertNotContains(r, 'Acervo e comunidade')
        self.assertEqual(r.context['estoque']['atrasados'], 1)
        self.assertEqual(r.context['estoque']['vencem_hoje'], 1)
        self.assertEqual(r.context['estoque']['sem_prazo'], 1)
        self.assertEqual([x.pk for x in r.context['prioridades']], [self.atrasado.pk, self.vence.pk])
        self.assertContains(r, '?situacao=atrasados')
        self.assertContains(r, '?leitor=' + str(self.leitor.pk))

    def test_gestor_movimento_mensal_e_atalhos(self):
        antigo = timezone.make_aware(datetime.combine(self.hoje.replace(day=1) - timedelta(days=1), time(12)))
        evento = Emprestimo.objects.create(copia=self.atrasado, leitor=self.leitor, prazo=self.hoje, devolvido_em=timezone.now())
        Emprestimo.objects.filter(pk=evento.pk).update(criado_em=antigo)
        Emprestimo.objects.create(copia=self.vence, leitor=self.leitor, prazo=self.hoje)
        r = self.inicio(self.gestor)
        self.assertContains(r, 'Sua biblioteca, em perspectiva.')
        self.assertContains(r, 'Relatórios gerenciais')
        self.assertContains(r, 'Acervo e comunidade')
        self.assertEqual(r.context['movimento_mes'], {'emprestimos': 1, 'devolucoes': 1})
        self.assertEqual(r.context['leitores_ativos'], 1)

    def test_publico_e_consulta_sem_dados_operacionais(self):
        for usuario in [None, self.consulta]:
            self.client.logout()
            if usuario:
                self.client.force_login(usuario)
            r = self.client.get(reverse('index'))
            self.assertContains(r, 'O próximo encontro')
            self.assertNotContains(r, self.leitor.nome)
            self.assertNotContains(r, 'Devoluções em atraso')
            self.assertNotContains(r, 'Prioridades do atendimento')
            self.assertNotIn('prioridades', r.context)
            self.assertNotIn('movimento_mes', r.context)
            self.assertNotIn('estoque', r.context)

    def test_permissoes_efetivas_e_conta_tecnica(self):
        tecnico = get_user_model().objects.create_superuser(username='tecnico_painel', password='Ficticia!2026')
        self.assertTrue(self.inicio(tecnico).context['painel_gestao'])
        relator = get_user_model().objects.create_user(username='relator_personalizado')
        relator.user_permissions.add(Permission.objects.get(content_type__app_label='acervo', codename='view_relatorios'))
        r = self.inicio(relator)
        self.assertTrue(r.context['painel_gestao'])
        self.assertFalse(r.context['painel_atendimento'])
        self.assertNotIn('prioridades', r.context)
        self.assertNotContains(r, self.leitor.nome)
        self.assertNotContains(r, 'Abrir central de atendimento')

    def test_limite_prioridades_e_estado_vazio(self):
        for i in range(7):
            LivroCopia.objects.create(livro=self.livro, estado='e', data_devolucao=self.hoje - timedelta(days=10+i))
        r = self.inicio(self.atendente)
        self.assertEqual(len(r.context['prioridades']), 5)
        prazos = [c.data_devolucao for c in r.context['prioridades']]
        self.assertEqual(prazos, sorted(prazos))
        LivroCopia.objects.all().delete()
        r = self.inicio(self.atendente)
        self.assertContains(r, 'Nenhum atraso ou vencimento hoje')
        self.assertEqual(r.context['estoque']['abertos'], 0)

    def test_filtros_de_destino_e_controle_de_acesso(self):
        self.inicio(self.atendente)
        for filtro, esperados in [('atrasados', [self.atrasado.pk]), ('hoje', [self.vence.pk]), ('sem_prazo', [self.sem_prazo.pk])]:
            r = self.client.get(reverse('todos-emprestimos'), {'situacao': filtro})
            self.assertEqual([c.pk for c in r.context['object_list']], esperados)
        r = self.client.get(reverse('todos-emprestimos'), {'situacao': 'invalido'})
        self.assertEqual(len(r.context['object_list']), 4)
        self.inicio(self.consulta)
        self.assertEqual(self.client.get(reverse('todos-emprestimos'), {'situacao': 'atrasados'}).status_code, 403)
