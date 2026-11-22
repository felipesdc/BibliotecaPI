from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.db import connection
from django.test import SimpleTestCase, TestCase, override_settings, Client
from django.urls import reverse

from . import acessos
from .backups import criar_copia_sqlite, abrir_backup
from .models import BackupRegistro, ConfiguracaoBiblioteca, Livro, LivroCopia


class CopiaSQLiteTests(SimpleTestCase):
    def test_copia_consistente_privada_sem_modificar_origem(self):
        with TemporaryDirectory() as pasta:
            origem = Path(pasta) / 'origem com espaço.sqlite3'
            with closing(sqlite3.connect(origem)) as db:
                db.execute('CREATE TABLE exemplo (id INTEGER PRIMARY KEY, nome TEXT)')
                db.execute("INSERT INTO exemplo(nome) VALUES ('Fictício')")
                db.commit()
            configuracao = SimpleNamespace(DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': origem}}, BACKUP_DIR=Path(pasta)/'copias')
            with patch('acervo.backups.settings', configuracao):
                arquivo = criar_copia_sqlite()
                with closing(sqlite3.connect(arquivo)) as copia:
                    self.assertEqual(copia.execute('SELECT nome FROM exemplo').fetchone(), ('Fictício',))
                    self.assertEqual(copia.execute('PRAGMA quick_check').fetchone(), ('ok',))
                self.assertEqual(arquivo.stat().st_mode & 0o777, 0o600)
                self.assertNotEqual(arquivo, criar_copia_sqlite())

    def test_falha_de_copia_remove_arquivo_parcial(self):
        with TemporaryDirectory() as pasta:
            origem = Path(pasta) / 'origem.sqlite3'
            origem.touch()
            destino = Path(pasta) / 'backups'
            configuracao = SimpleNamespace(DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': origem}}, BACKUP_DIR=destino)
            with patch('acervo.backups.settings', configuracao), patch('acervo.backups.sqlite3.connect', side_effect=sqlite3.OperationalError('falha fictícia')):
                with self.assertRaises(sqlite3.OperationalError):
                    criar_copia_sqlite()
            self.assertEqual(list(destino.iterdir()), [])

    def test_download_recusa_traversal_e_symlink(self):
        with TemporaryDirectory() as pasta, override_settings(BACKUP_DIR=Path(pasta)):
            alvo = Path(pasta)/'origem.sqlite3'
            alvo.write_bytes(b'ficticio')
            link = Path(pasta)/'biblioteca-link.sqlite3'
            link.symlink_to(alvo)
            for nome in ['../origem.sqlite3', str(alvo), link.name]:
                with self.assertRaises(OSError):
                    abrir_backup(nome)


class GestaoBibliotecaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        acessos.configurar_grupos()
        cls.gestor = acessos.criar_usuario(None, username='gestor_gestao', papel='gestor', senha='GestaoFicticia2026!', exigir_troca=False)
        cls.atendente = acessos.criar_usuario(cls.gestor, username='atendente_gestao', papel='atendente', senha='GestaoFicticia2026!', exigir_troca=False)
        cls.consulta = acessos.criar_usuario(cls.gestor, username='consulta_gestao', papel='consulta', senha='GestaoFicticia2026!', exigir_troca=False)
        cls.livro = Livro.objects.create(titulo='Título fictício de etiquetas')
        cls.copia = LivroCopia.objects.create(livro=cls.livro, codigo='ETIQUETA-001')

    def setUp(self):
        self.client.force_login(self.gestor)

    def test_configuracao_publica_validacao_e_concorrencia(self):
        url = reverse('configuracao')
        dados = {'nome': 'Biblioteca fictícia do bairro', 'email': 'contato@example.invalid', 'telefone': '(00) fictício', 'orientacoes': '<script>Orientação fictícia</script>', 'versao': 1}
        self.assertEqual(self.client.post(url, dados).status_code, 302)
        self.assertEqual(ConfiguracaoBiblioteca.atual().versao, 2)
        r = self.client.get(reverse('index'))
        self.assertContains(r, 'Biblioteca fictícia do bairro')
        self.assertContains(r, 'contato@example.invalid')
        self.assertContains(r, '&lt;script&gt;')
        self.assertNotContains(r, '<script>Orientação')
        self.assertContains(self.client.post(url, {**dados, 'nome': 'Tentativa antiga'}), 'mudou em outra operação')
        self.assertEqual(ConfiguracaoBiblioteca.atual().nome, dados['nome'])
        self.assertEqual(self.client.post(url, {**dados, 'versao': 2, 'email': 'invalido'}).status_code, 200)
        self.assertEqual(ConfiguracaoBiblioteca.atual().versao, 2)

    def test_permissoes_das_novas_rotas(self):
        for usuario in [self.atendente, self.consulta]:
            self.client.force_login(usuario)
            for url in [reverse('backups'), reverse('configuracao')]:
                self.assertEqual(self.client.get(url).status_code, 403)
                self.assertEqual(self.client.post(url, {}).status_code, 403)
        self.assertFalse(self.atendente.has_perm('acervo.manage_backups'))
        self.assertTrue(self.atendente.has_perm('acervo.print_etiquetas'))
        self.client.force_login(self.consulta)
        self.assertEqual(self.client.get(reverse('etiquetas')).status_code, 403)

    def test_backup_painel_geracao_download_e_arquivo_ausente(self):
        with TemporaryDirectory() as pasta, override_settings(BACKUP_DIR=Path(pasta)):
            arquivo = Path(pasta)/'biblioteca-teste.sqlite3'
            with closing(sqlite3.connect(arquivo)) as db:
                db.execute('CREATE TABLE teste (valor TEXT)')
            with patch('acervo.views_gestao.criar_copia_sqlite', return_value=arquivo) as criar:
                self.assertEqual(self.client.get(reverse('backups')).status_code, 200)
                criar.assert_not_called()
                r = self.client.post(reverse('backups'))
                self.assertRedirects(r, reverse('backups'))
            registro = BackupRegistro.objects.get()
            self.assertEqual(registro.criado_por, self.gestor)
            self.assertContains(self.client.get(reverse('backups')), 'Baixar último backup')
            url = reverse('baixar-backup', args=[registro.pk])
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200)
            self.assertIn('attachment', r['Content-Disposition'])
            self.assertIn('no-store', r['Cache-Control'])
            self.assertTrue(b''.join(r.streaming_content).startswith(b'SQLite format 3'))
            r.close()
            self.client.force_login(self.atendente)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.client.force_login(self.gestor)
            arquivo.unlink()
            self.assertEqual(self.client.get(url).status_code, 404)
            self.assertContains(self.client.get(reverse('backups')), 'Arquivo não disponível')

    def test_backup_falha_nao_cria_registro_e_exige_csrf(self):
        with patch('acervo.views_gestao.criar_copia_sqlite', side_effect=OSError('erro fictício')), self.assertLogs('acervo.views_gestao', level='ERROR'):
            r = self.client.post(reverse('backups'))
            self.assertContains(r, 'Não foi possível gerar a cópia')
        self.assertFalse(BackupRegistro.objects.exists())
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.gestor)
        self.assertEqual(c.post(reverse('backups')).status_code, 403)

    def test_etiquetas_selecao_escape_e_limites(self):
        url = reverse('etiquetas')
        self.client.force_login(self.atendente)
        self.assertContains(self.client.get(url, {'q': 'ETIQUETA-001'}), 'ETIQUETA-001')
        self.assertContains(self.client.post(url, {}), 'Este campo é obrigatório')
        r = self.client.post(url, {'exemplares': [self.copia.pk]})
        self.assertContains(r, 'Folha de etiquetas')
        self.assertContains(r, 'ETIQUETA-001')
        self.assertContains(r, '62 × 35 mm')
        self.assertContains(self.client.post(url, {'exemplares': ['inexistente']}), 'Revise os dados')
        for i in range(60):
            LivroCopia.objects.create(livro=self.livro, codigo=f'LOTE-{i:02}')
        r = self.client.post(url, {'exemplares': list(LivroCopia.objects.values_list('pk', flat=True))})
        self.assertContains(r, 'no máximo 60')
        self.assertContains(self.client.get(url), 'primeiros 60')
        self.assertContains(self.client.get(url, {'q': 'inexistente'}), 'Nenhum exemplar encontrado')

    def test_migracao_amplia_permissoes_em_grupos_existentes(self):
        import importlib
        from django.apps import apps
        from django.contrib.auth.models import Group
        migracao = importlib.import_module('acervo.migrations.0011_backupregistro_configuracaobiblioteca_reserva')
        for nome in acessos.GRUPOS.values():
            Group.objects.get(name=nome).permissions.clear()
        migracao.ampliar_perfis(apps, SimpleNamespace(connection=connection))
        gestor = Group.objects.get(name=acessos.GRUPOS['gestor'])
        atendente = Group.objects.get(name=acessos.GRUPOS['atendente'])
        self.assertTrue(gestor.permissions.filter(codename='manage_backups').exists())
        self.assertTrue(atendente.permissions.filter(codename='manage_reservas').exists())
        self.assertFalse(atendente.permissions.filter(codename='manage_backups').exists())
