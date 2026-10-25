import datetime
import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from openpyxl import Workbook

from .forms import RenovacaoEmprestimoForm
from .importacao import ler_planilha, preparar, importar, CAMPOS
from .models import Autor, Genero, Livro, LivroCopia, Leitor, Emprestimo, Importacao


class BibliotecaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.equipe = get_user_model().objects.create_user('equipe', password='senha-somente-teste')
        cls.equipe.user_permissions.set(Permission.objects.filter(content_type__app_label='acervo'))
        cls.visitante = get_user_model().objects.create_user('visitante')
        cls.autor = Autor.objects.create(primeiro_nome='Machado', sobrenome='de Assis')
        cls.livro = Livro.objects.create(titulo='Dom Casmurro', autor=cls.autor)
        cls.copia = LivroCopia.objects.create(livro=cls.livro, codigo='B-001', estado='d')
        cls.leitor = Leitor.objects.create(nome='Maria')

    def setUp(self):
        self.client.force_login(self.equipe)

    def arquivo(self, conteudo=None):
        return SimpleUploadedFile('acervo.csv', (conteudo or 'Tombo;Obra;Autor\nB-002;Memórias póstumas;Machado de Assis\n').encode('utf-8'))

    def lote(self):
        tabelas = ler_planilha(self.arquivo())
        return Importacao.objects.create(criado_por=self.equipe, nome='acervo.csv', dados={'tabelas': tabelas})

    def mapa(self, acao='previa'):
        return {'aba': 'Acervo', 'titulo': '1', 'codigo': '0', 'autor': '2', 'acao': acao, 'confirmo': '1'}

    def test_paginas_principais_e_formularios_renderizam(self):
        for nome in ['index','livros','copias','autores','generos','linguas','leitores','todos-emprestimos','historico','importar-acervo','adicionar-livro','adicionar-copia','adicionar-leitor','adicionar-autor','adicionar-genero','adicionar-lingua']:
            with self.subTest(nome=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 200)
        for nome, pk in [('detalhe-livro', self.livro.pk), ('detalhe-copia', self.copia.pk), ('alterar-livro',self.livro.pk),('emprestar',self.copia.pk)]:
            self.assertEqual(self.client.get(reverse(nome,args=[pk])).status_code,200)

    def test_catalogo_publico_operacoes_protegidas(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('livros')).status_code, 200)
        self.assertEqual(self.client.get(reverse('importar-acervo')).status_code, 302)
        self.client.force_login(self.visitante)
        self.assertEqual(self.client.get(reverse('leitores')).status_code, 403)
        self.assertEqual(self.client.post(reverse('emprestar',args=[self.copia.pk]), {'leitor':self.leitor.pk,'prazo':timezone.localdate()}).status_code,403)
        self.assertEqual(self.client.get(reverse('exportar-acervo')).status_code,403)

    def test_upload_previa_sem_escrita_confirmacao_idempotente(self):
        resposta = self.client.post(reverse('importar-acervo'), {'arquivo': self.arquivo()})
        self.assertEqual(resposta.status_code, 302)
        lote = Importacao.objects.latest('pk')
        url = reverse('mapear-importacao', args=[lote.pk])
        resposta = self.client.post(url, self.mapa())
        self.assertContains(resposta, 'Memórias póstumas')
        self.assertEqual(LivroCopia.objects.count(), 1)
        self.client.post(url, self.mapa('confirmar'))
        self.assertEqual(LivroCopia.objects.count(), 2)
        self.client.post(url, self.mapa('confirmar'))
        self.assertEqual(LivroCopia.objects.count(), 2)
        lote.refresh_from_db()
        self.assertTrue(lote.concluida)
        self.assertEqual(lote.dados, {})
        autre = self.lote()
        self.client.post(reverse('mapear-importacao',args=[autre.pk]),self.mapa('confirmar'))
        self.assertEqual(LivroCopia.objects.count(), 2)

    def test_importacao_exige_confirmacao(self):
        lote=self.lote();dados=self.mapa('confirmar');dados.pop('confirmo')
        self.assertContains(self.client.post(reverse('mapear-importacao',args=[lote.pk]),dados),'Confirme que esta planilha')
        self.assertEqual(LivroCopia.objects.count(),1)

    def test_importacao_privada_por_usuario(self):
        lote = self.lote()
        outro=get_user_model().objects.create_superuser('outro',password='teste')
        self.client.force_login(outro)
        self.assertEqual(self.client.get(reverse('mapear-importacao',args=[lote.pk])).status_code,404)

    def test_importacao_rollback_integral(self):
        lote=self.lote()
        def falha(linhas):
            Livro.objects.create(titulo='Não persistir')
            from django.db import IntegrityError
            raise IntegrityError('teste')
        with patch('acervo.importacao.importar', side_effect=falha):
            self.assertContains(self.client.post(reverse('mapear-importacao',args=[lote.pk]),self.mapa('confirmar')),'Nenhuma alteração deste lote')
        self.assertFalse(Livro.objects.filter(titulo='Não persistir').exists())
        lote.refresh_from_db(); self.assertFalse(lote.concluida)

    def test_erros_de_linha_impedem_importacao(self):
        tabela={'cabecalho':['codigo','titulo'], 'linhas':[{'numero':2,'valores':['X','Certo']},{'numero':3,'valores':['X','']}]}
        linhas,erros=preparar(tabela,{'titulo':'1','codigo':'0'})
        self.assertTrue(any('título ausente' in e for e in erros))
        self.assertTrue(any('código repetido' in e for e in erros))

    def test_codigo_existente_outro_titulo_bloqueado(self):
        tabela={'cabecalho':['codigo','titulo'],'linhas':[{'numero':2,'valores':['B-001','Outro livro']}]}
        _,erros=preparar(tabela,{'titulo':'1','codigo':'0'})
        self.assertTrue(any('outro título' in e for e in erros))

    def test_formulas_e_emprestimos_na_planilha_bloqueados(self):
        tabela={'cabecalho':['titulo','situacao'],'linhas':[{'numero':2,'valores':['=SUM(1,2)','Emprestado']}]}
        _,erros=preparar(tabela,{'titulo':'0','estado':'1'})
        self.assertEqual(len(erros),2)

    def test_xlsx_multiplas_abas_e_colunas(self):
        wb=Workbook();wb.active.title='Acervo';wb.active.append(['Titulo','Tombo']);wb.active.append(['Livro','001'])
        wb.create_sheet('Outra').append(['Titulo'])
        buffer=io.BytesIO();wb.save(buffer)
        tabelas=ler_planilha(SimpleUploadedFile('teste.xlsx',buffer.getvalue()))
        self.assertEqual(list(tabelas),['Acervo','Outra'])
        self.assertEqual(tabelas['Acervo']['linhas'][0]['valores'][1],'001')

    def test_isbn_invalido_bloqueado_e_ausente_aceito(self):
        tabela={'cabecalho':['Titulo','ISBN'],'linhas':[{'numero':2,'valores':['Livro','123']}]}
        _,erros=preparar(tabela,{'titulo':'0','isbn':'1'})
        self.assertTrue(any('ISBN-13' in e for e in erros))
        tabela['linhas'][0]['valores'][1]=''
        self.assertFalse(preparar(tabela,{'titulo':'0','isbn':'1'})[1])

    def test_sem_codigo_mesmo_arquivo_nao_duplica_exemplares(self):
        tabela={'cabecalho':['Titulo'],'linhas':[{'numero':2,'valores':['Livro']},{'numero':3,'valores':['Livro']}]}
        linhas,erros=preparar(tabela,{'titulo':'0'})
        self.assertFalse(erros);importar(linhas);importar(linhas)
        self.assertEqual(LivroCopia.objects.count(),3)

    def test_fluxo_completo_leitor_emprestimo_renovacao_devolucao(self):
        resposta=self.client.post(reverse('adicionar-leitor'),{'nome':'Joana','email':'','telefone':''})
        self.assertEqual(resposta.status_code,302)
        leitor=Leitor.objects.get(nome='Joana')
        url=reverse('emprestar',args=[self.copia.pk])
        prazo=timezone.localdate()+datetime.timedelta(days=14)
        self.assertEqual(self.client.post(url,{'leitor':leitor.pk,'prazo':prazo}).status_code,302)
        self.copia.refresh_from_db();self.assertEqual(self.copia.estado,'e')
        self.assertEqual(Emprestimo.objects.count(),1)
        self.assertContains(self.client.get(reverse('todos-emprestimos')),'Joana')
        self.assertContains(self.client.post(url,{'leitor':leitor.pk,'prazo':prazo}),'não está disponível')
        novo=timezone.localdate()+datetime.timedelta(days=21)
        self.client.post(reverse('renovacao-emprestimo-bibliotecario',args=[self.copia.pk]),{'data_renovacao':novo})
        self.assertEqual(Emprestimo.objects.get().prazo,novo)
        self.assertEqual(self.client.get(reverse('devolver',args=[self.copia.pk])).status_code,405)
        self.client.post(reverse('devolver',args=[self.copia.pk]))
        self.copia.refresh_from_db();self.assertEqual(self.copia.estado,'d')
        self.assertIsNone(self.copia.leitor);self.assertIsNone(self.copia.data_devolucao)
        self.assertIsNotNone(Emprestimo.objects.get().devolvido_em)
        self.client.post(reverse('devolver',args=[self.copia.pk]))
        self.assertEqual(Emprestimo.objects.count(),1)
        self.assertContains(self.client.get(reverse('historico')),'Joana')

    def test_atraso_apenas_em_emprestados(self):
        self.copia.data_devolucao=timezone.localdate()-datetime.timedelta(days=1)
        self.assertFalse(self.copia.em_atraso)
        self.copia.estado='e';self.assertTrue(self.copia.em_atraso)

    def test_renovacao_rejeita_datas_fora_dos_limites(self):
        for delta in [-1,29]:
            self.assertFalse(RenovacaoEmprestimoForm({'data_renovacao':timezone.localdate()+datetime.timedelta(days=delta)}).is_valid())
        self.assertTrue(RenovacaoEmprestimoForm({'data_renovacao':timezone.localdate()+datetime.timedelta(days=28)}).is_valid())

    def test_busca_e_paginacao_preservam_filtros(self):
        for i in range(15): Livro.objects.create(titulo=f'Livro teste {i}')
        resposta=self.client.get(reverse('livros'),{'q':'Livro teste'})
        self.assertContains(resposta,'q=Livro%20teste&amp;page=2')
        self.assertNotContains(resposta,'Dom Casmurro')
        self.assertContains(self.client.get(reverse('livros'),{'q':'Dom','disponivel':'1'}),'Dom Casmurro')

    def test_exclusao_autor_sem_livros_e_livro_com_historico(self):
        autor=Autor.objects.create(primeiro_nome='Autor',sobrenome='Teste')
        self.assertRedirects(self.client.post(reverse('excluir-autor',args=[autor.pk])),reverse('autores'))
        Emprestimo.objects.create(copia=self.copia,leitor=self.leitor,prazo=timezone.localdate(),devolvido_em=timezone.now())
        resposta=self.client.post(reverse('excluir-copia',args=[self.copia.pk]))
        self.assertEqual(resposta.status_code,302)
        self.assertTrue(LivroCopia.objects.filter(pk=self.copia.pk).exists())

    def test_exportacao_e_modelo_abrem_em_excel_e_protegem_formulas(self):
        self.livro.titulo='=HYPERLINK("url")';self.livro.save()
        resposta=self.client.get(reverse('exportar-acervo'))
        self.assertEqual(resposta.status_code,200)
        self.assertTrue(resposta.content.startswith(b'\xef\xbb\xbf'))
        self.assertIn("'=HYPERLINK",resposta.content.decode())
        self.assertContains(self.client.get(reverse('modelo-importacao')),'Dom Casmurro')

    def test_csrf_obrigatorio_para_escrita(self):
        client=Client(enforce_csrf_checks=True);client.force_login(self.equipe)
        self.assertEqual(client.post(reverse('devolver',args=[self.copia.pk])).status_code,403)

    def test_upload_invalido(self):
        resposta=self.client.post(reverse('importar-acervo'),{'arquivo':SimpleUploadedFile('antigo.xls',b'invalido')})
        self.assertContains(resposta,'Use .xlsx ou .csv')

    def test_preparacao_cria_equipe_e_nao_solicita_senha_novamente(self):
        from django.core.management import call_command
        with patch('builtins.input', return_value='bibliotecaria'), patch('acervo.management.commands.preparar_biblioteca.getpass', return_value='SenhaForteLocal2026!'):
            call_command('preparar_biblioteca', stdout=io.StringIO())
        usuario=get_user_model().objects.get(username='bibliotecaria')
        self.assertTrue(usuario.check_password('SenhaForteLocal2026!'))
        self.assertTrue(usuario.has_perm('acervo.marca_devolucao'))
        with patch('builtins.input') as entrada:
            call_command('preparar_biblioteca', se_vazio=True, stdout=io.StringIO())
            entrada.assert_not_called()

    def test_cadastro_manual_minimo_e_codigo_fixo(self):
        resposta=self.client.post(reverse('adicionar-livro'),{'titulo':'Livro sem metadados','autor':'','descricao':'','isbn':'','lingua':''})
        self.assertEqual(resposta.status_code,302)
        livro=Livro.objects.get(titulo='Livro sem metadados')
        resposta=self.client.post(reverse('adicionar-copia'),{'livro':livro.pk,'codigo':'','editora':'','estado':'d'})
        self.assertEqual(resposta.status_code,302)
        copia=LivroCopia.objects.get(livro=livro)
        self.assertTrue(copia.codigo.startswith('BIB-'))
        self.assertEqual(copia.estado,'d')
