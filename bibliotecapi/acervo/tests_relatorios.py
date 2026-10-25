import csv
from datetime import datetime, time, timedelta
import io

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Autor, Emprestimo, Genero, Importacao, Leitor, Lingua, Livro, LivroCopia
from .relatorios import gerar_relatorio


def data_hora(dia, hora=time(10)):
    return timezone.make_aware(datetime.combine(dia, hora), timezone.get_current_timezone())


def evento(copia, leitor, inicio, prazo, retorno=None):
    item = Emprestimo.objects.create(copia=copia, leitor=leitor, prazo=prazo, devolvido_em=retorno)
    Emprestimo.objects.filter(pk=item.pk).update(criado_em=inicio)
    return item


class RelatoriosTests(TestCase):
    def setUp(self):
        self.hoje = timezone.localdate()
        self.usuario = get_user_model().objects.create_user('gestor')
        self.usuario.user_permissions.add(Permission.objects.get(codename='view_relatorios'))
        self.client.force_login(self.usuario)
        self.livro = Livro.objects.create(titulo='Livro para relatório')
        self.genero = Genero.objects.create(nome='Ficção')
        self.livro.genero.add(self.genero, Genero.objects.create(nome='Aventura'))
        self.copia = LivroCopia.objects.create(livro=self.livro, codigo='R-001')
        self.leitor = Leitor.objects.create(nome='Leitor exemplo')

    def test_acesso_e_exportacao_exigem_permissao_especifica(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('relatorios')).status_code,302)
        atendente=get_user_model().objects.create_user('atendente')
        atendente.user_permissions.add(Permission.objects.get(codename='view_leitor'))
        self.client.force_login(atendente)
        for dados in [{}, {'formato':'csv','tipo':'resumo'}]:
            self.assertEqual(self.client.get(reverse('relatorios'),dados).status_code,403)

    def test_pagina_renderiza_e_so_aceita_get(self):
        resposta=self.client.get(reverse('relatorios'))
        self.assertContains(resposta,'Relatórios gerenciais')
        self.assertContains(resposta,'Movimentação no período')
        self.assertEqual(self.client.post(reverse('relatorios')).status_code,405)

    def test_acervo_e_atrasos_atuais_independem_do_periodo(self):
        self.copia.estado='e';self.copia.leitor=self.leitor;self.copia.data_devolucao=self.hoje-timedelta(days=2);self.copia.save()
        evento(self.copia,self.leitor,data_hora(self.hoje-timedelta(days=60)),self.copia.data_devolucao)
        r=gerar_relatorio(self.hoje-timedelta(days=7),self.hoje)
        self.assertEqual(r['estoque']['exemplares'],1)
        self.assertEqual(r['estoque']['atrasados'],1)
        self.assertEqual(r['periodo']['emprestimos'],0)
        self.assertEqual(r['atrasos'].count(),1)

    def test_devolucao_de_emprestimo_anterior_conta_no_periodo(self):
        evento(self.copia,self.leitor,data_hora(self.hoje-timedelta(days=40)),self.hoje-timedelta(days=3),data_hora(self.hoje-timedelta(days=3)))
        r=gerar_relatorio(self.hoje-timedelta(days=7),self.hoje)
        self.assertEqual(r['periodo']['emprestimos'],0)
        self.assertEqual(r['periodo']['devolucoes'],1)
        self.assertEqual(r['periodo']['pontualidade'],100)
        self.assertEqual(r['periodo']['duracao_media'],37)

    def test_pontualidade_usa_data_local_inclusive_prazo(self):
        prazo=self.hoje-timedelta(days=1)
        evento(self.copia,self.leitor,data_hora(self.hoje-timedelta(days=8)),prazo,data_hora(prazo,time(23,59)))
        evento(self.copia,self.leitor,data_hora(self.hoje-timedelta(days=7)),prazo,data_hora(self.hoje,time(0,1)))
        r=gerar_relatorio(self.hoje-timedelta(days=10),self.hoje)
        self.assertEqual(r['periodo']['devolucoes'],2)
        self.assertEqual(r['periodo']['pontuais'],1)
        self.assertEqual(r['periodo']['pontualidade'],50)

    def test_datas_limite_e_agrupamento_mensal_em_sao_paulo(self):
        from datetime import date
        inicio,fim=date(2026,6,1),date(2026,6,30)
        for dia,hora in [(date(2026,5,31),time(23,59)),(inicio,time(0)),(fim,time(23,59)),(date(2026,7,1),time(0))]:
            instante=data_hora(dia,hora)
            evento(self.copia,self.leitor,instante,dia,instante)
        r=gerar_relatorio(inicio,fim)
        self.assertEqual(r['periodo']['emprestimos'],2)
        self.assertEqual(r['periodo']['devolucoes'],2)
        self.assertEqual(r['mensal'][0]['emprestimos'],2)
        self.assertEqual(len(r['mensal']),1)

    def test_generos_multiplos_nao_duplicam_ranking(self):
        evento(self.copia,self.leitor,data_hora(self.hoje-timedelta(days=3)),self.hoje,data_hora(self.hoje))
        r=gerar_relatorio(self.hoje-timedelta(days=10),self.hoje)
        self.assertEqual(r['livros_ranking'][0].total_emprestimos,1)
        self.assertEqual(r['estoque']['exemplares'],1)
        self.assertEqual(list(r['generos_acervo'].values_list('exemplares',flat=True)),[1,1])

    def test_mes_sem_movimento_exibido_com_zero(self):
        from datetime import date
        r=gerar_relatorio(date(2026,7,1),date(2026,9,30))
        self.assertEqual(len(r['mensal']),3)
        self.assertEqual(sum(m['emprestimos'] for m in r['mensal']),0)
        self.assertIsNone(r['periodo']['pontualidade'])
        self.assertIsNone(r['periodo']['duracao_media'])

    def test_filtro_invalido_nao_retorna_indicadores_nem_csv(self):
        for dados in [
            {'inicio':self.hoje.isoformat(),'fim':(self.hoje-timedelta(days=1)).isoformat()},
            {'inicio':'invalido','fim':self.hoje.isoformat()},
            {'inicio':self.hoje.isoformat(),'fim':(self.hoje+timedelta(days=1)).isoformat()},
            {'inicio':(self.hoje-timedelta(days=731)).isoformat(),'fim':self.hoje.isoformat()},
        ]:
            for formato in ['html','csv']:
                with self.subTest(dados=dados,formato=formato):
                    resposta=self.client.get(reverse('relatorios'),{**dados,'formato':formato})
                    self.assertEqual(resposta.status_code,400)
                    self.assertNotIn('estoque',resposta.context)

    def test_todos_os_csv_preservam_zero_e_protegem_formulas(self):
        self.livro.titulo='=HYPERLINK("teste")';self.livro.save()
        evento(self.copia,self.leitor,data_hora(self.hoje-timedelta(days=1)),self.hoje,data_hora(self.hoje))
        for tipo in ['resumo','mensal','atrasos','titulos','leitores','acervo','emprestimos','devolucoes']:
            resposta=self.client.get(reverse('relatorios'),{'formato':'csv','tipo':tipo})
            self.assertEqual(resposta.status_code,200)
            self.assertTrue(resposta.content.startswith(b'\xef\xbb\xbf'))
            linhas=list(csv.reader(io.StringIO(resposta.content.decode('utf-8-sig')),delimiter=';'))
            self.assertGreaterEqual(len(linhas),1)
            if tipo=='titulos': self.assertTrue(linhas[1][0].startswith("'="))
            if tipo=='resumo': self.assertTrue(any(l[-1]=='0' for l in linhas[1:]))
        self.assertEqual(self.client.get(reverse('relatorios'),{'formato':'csv','tipo':'inexistente'}).status_code,400)

    def test_exportacao_leitores_inclui_mais_de_dez_e_sem_emprestimos(self):
        for i in range(12): Leitor.objects.create(nome=f'Pessoa {i:02d}')
        resposta=self.client.get(reverse('relatorios'),{'formato':'csv','tipo':'leitores'})
        linhas=list(csv.reader(io.StringIO(resposta.content.decode('utf-8-sig')),delimiter=';'))
        self.assertEqual(len(linhas),Leitor.objects.count()+1)
        self.assertTrue(all(l[3]=='0' for l in linhas[1:]))

    def test_demo_banner_apenas_na_instalacao_de_demonstracao(self):
        with override_settings(DEMO_MODE=True): self.assertContains(self.client.get(reverse('relatorios')),'AMBIENTE DE DEMONSTRAÇÃO')
        with override_settings(DEMO_MODE=False): self.assertNotContains(self.client.get(reverse('relatorios')),'AMBIENTE DE DEMONSTRAÇÃO')


class CargaDemonstracaoTests(TestCase):
    def test_carga_recusada_fora_do_ambiente_demo(self):
        with override_settings(DEMO_MODE=False),self.assertRaises(CommandError): call_command('carregar_demonstracao',stdout=io.StringIO())
        self.assertEqual(Livro.objects.count(),0)

    @override_settings(DEMO_MODE=True)
    def test_carga_recusada_se_ja_existem_dados(self):
        Livro.objects.create(titulo='Acervo real')
        with self.assertRaises(CommandError): call_command('carregar_demonstracao',stdout=io.StringIO())
        self.assertEqual(Livro.objects.count(),1)
        self.assertEqual(get_user_model().objects.count(),0)

    @override_settings(DEMO_MODE=True)
    def test_carga_completa_consistente_idempotente_e_permissoes(self):
        call_command('carregar_demonstracao',stdout=io.StringIO())
        for modelo,total in [(Autor,8),(Genero,6),(Lingua,3),(Livro,24),(LivroCopia,72),(Leitor,30),(Emprestimo,210),(Importacao,2)]:
            self.assertEqual(modelo.objects.count(),total)
        self.assertEqual(LivroCopia.objects.filter(estado='e').count(),18)
        self.assertEqual(Emprestimo.objects.filter(devolvido_em__isnull=True).count(),18)
        for copia in LivroCopia.objects.all(): copia.full_clean()
        for livro in Livro.objects.all(): livro.full_clean()
        for copia in LivroCopia.objects.all():
            eventos=list(Emprestimo.objects.filter(copia=copia).order_by('criado_em'))
            for anterior,proximo in zip(eventos,eventos[1:]):
                self.assertLessEqual(anterior.devolvido_em,proximo.criado_em)
        gestor=get_user_model().objects.get(username='gestor_demo')
        atendente=get_user_model().objects.get(username='atendente_demo')
        self.assertTrue(gestor.has_perm('acervo.view_relatorios'))
        self.assertFalse(atendente.has_perm('acervo.view_relatorios'))
        referencia=timezone.localdate()
        r=gerar_relatorio(referencia-timedelta(days=365),referencia)
        self.assertEqual(r['periodo']['emprestimos'],210)
        self.assertEqual(r['estoque']['atrasados'],9)
        call_command('carregar_demonstracao',stdout=io.StringIO())
        self.assertEqual(Emprestimo.objects.count(),210)
        self.assertEqual(get_user_model().objects.count(),2)
        self.client.force_login(gestor)
        self.assertEqual(self.client.get(reverse('relatorios')).status_code,200)
