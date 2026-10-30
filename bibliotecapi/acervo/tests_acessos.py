import importlib
import io
import json
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model, SESSION_KEY
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import connection
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from . import acessos
from .middleware import CHAVE_VERSAO
from .models import EventoAcesso, PerfilAcesso

SENHA = 'EntradaFicticia!2026'
NOVA = 'NovaPassagemPessoal!2026'


class GestaoAcessosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        acessos.configurar_grupos()
        cls.gestor = acessos.criar_usuario(None, username='gestor', first_name='Gestão', papel='gestor', senha=SENHA, exigir_troca=False)
        cls.atendente = acessos.criar_usuario(cls.gestor, username='atendente', first_name='Atendimento', papel='atendente', senha=SENHA, exigir_troca=False)
        cls.consulta = acessos.criar_usuario(cls.gestor, username='consulta', first_name='Consulta', papel='consulta', senha=SENHA, exigir_troca=False)

    def setUp(self):
        self.client.force_login(self.gestor)

    def versao(self, usuario):
        return PerfilAcesso.objects.get(usuario=usuario).versao_sessao

    def dados_edicao(self, usuario, **extras):
        return {'first_name':usuario.first_name,'last_name':usuario.last_name,'email':usuario.email,'papel':PerfilAcesso.objects.get(usuario=usuario).papel,'versao':self.versao(usuario),**extras}

    def test_matriz_de_perfis(self):
        for usuario, permissoes in [(self.gestor,['manage_usuarios','view_relatorios','add_livro','marca_devolucao']), (self.atendente,['marca_devolucao','view_leitor','add_leitor']), (self.consulta,['view_livro','view_livrocopia'])]:
            atual=get_user_model().objects.get(pk=usuario.pk)
            for permissao in permissoes:self.assertTrue(atual.has_perm('acervo.'+permissao))
            self.assertFalse(atual.is_staff);self.assertFalse(atual.is_superuser)
            self.assertFalse(atual.has_perm('auth.change_user'))
        for usuario in [self.atendente,self.consulta]:
            self.assertFalse(usuario.has_perm('acervo.manage_usuarios'))
            self.assertFalse(usuario.has_perm('acervo.view_relatorios'))
        self.assertFalse(self.atendente.has_perm('acervo.add_livro'))
        self.assertFalse(self.atendente.has_perm('acervo.export_acervo'))
        self.assertFalse(self.consulta.has_perm('acervo.view_leitor'))
        self.assertFalse(self.consulta.has_perm('acervo.marca_devolucao'))

    def test_gestao_bloqueada_no_servidor_para_outros_perfis(self):
        urls=[reverse('usuarios'),reverse('criar-usuario'),reverse('editar-usuario',args=[self.atendente.pk]),reverse('desativar-usuario',args=[self.atendente.pk]),reverse('reativar-usuario',args=[self.atendente.pk]),reverse('redefinir-senha-usuario',args=[self.atendente.pk])]
        self.client.logout()
        self.assertEqual(self.client.get(urls[0]).status_code,302)
        for usuario in [self.atendente,self.consulta]:
            self.client.force_login(usuario)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code,403)
                self.assertEqual(self.client.post(url,{}).status_code,403)
        self.assertEqual(EventoAcesso.objects.count(),3)

    def test_cadastro_por_interface_hash_perfil_e_campos_extras(self):
        resposta=self.client.post(reverse('criar-usuario'),{'username':'nova_conta','first_name':'Pessoa','last_name':'Fictícia','email':'pessoa@example.invalid','papel':'atendente','password1':SENHA,'password2':SENHA,'is_superuser':'on','is_staff':'on','user_permissions':'1'})
        self.assertEqual(resposta.status_code,302)
        usuario=get_user_model().objects.get(username='nova_conta')
        self.assertTrue(usuario.check_password(SENHA));self.assertNotEqual(usuario.password,SENHA)
        self.assertFalse(usuario.is_staff);self.assertFalse(usuario.is_superuser)
        self.assertTrue(usuario.perfil_biblioteca.exigir_troca_senha)
        self.assertEqual(usuario.perfil_biblioteca.papel,'atendente')
        self.assertEqual(list(usuario.groups.values_list('name',flat=True)),[acessos.GRUPOS['atendente']])

    def test_rejeita_senha_fraca_e_nome_de_acesso_duplicado(self):
        for nome,senha in [('GESTOR',SENHA),('fraca','123')]:
            resposta=self.client.post(reverse('criar-usuario'),{'username':nome,'first_name':'Nome','papel':'consulta','password1':senha,'password2':senha})
            self.assertEqual(resposta.status_code,200)
        self.assertEqual(get_user_model().objects.count(),3)

    def test_lista_filtros_formularios_e_confirmacao_sem_mutacao_get(self):
        resposta=self.client.get(reverse('usuarios'),{'q':'atendente','papel':'atendente','situacao':'ativo'})
        self.assertContains(resposta,'atendente');self.assertNotContains(resposta,'gestor</small>')
        for nome in ['editar-usuario','desativar-usuario','reativar-usuario','redefinir-senha-usuario']:
            self.assertEqual(self.client.get(reverse(nome,args=[self.atendente.pk])).status_code,200)
        self.atendente.refresh_from_db();self.assertTrue(self.atendente.is_active)
        self.assertEqual(self.versao(self.atendente),1)

    def test_alteracao_perfil_troca_permissoes_e_invalida_sessao(self):
        outro=Client();outro.force_login(self.atendente)
        resposta=self.client.post(reverse('editar-usuario',args=[self.atendente.pk]),self.dados_edicao(self.atendente,papel='consulta'))
        self.assertEqual(resposta.status_code,302)
        atual=get_user_model().objects.get(pk=self.atendente.pk)
        self.assertEqual(atual.perfil_biblioteca.papel,'consulta')
        self.assertFalse(atual.has_perm('acervo.marca_devolucao'))
        self.assertEqual(outro.get(reverse('leitores')).status_code,302)
        self.assertNotIn(SESSION_KEY,outro.session)

    def test_desativar_reativar_nao_revive_sessao_antiga(self):
        outro=Client();outro.force_login(self.atendente)
        for nome in ['desativar-usuario','reativar-usuario']:
            resposta=self.client.post(reverse(nome,args=[self.atendente.pk]),{'versao':self.versao(self.atendente)})
            self.assertEqual(resposta.status_code,302)
        self.atendente.refresh_from_db();self.assertTrue(self.atendente.is_active)
        self.assertEqual(outro.get(reverse('leitores')).status_code,302)
        self.assertNotIn(SESSION_KEY,outro.session)
        self.assertTrue(outro.login(username='atendente',password=SENHA))
        self.assertEqual(outro.get(reverse('leitores')).status_code,200)

    def test_conta_inativa_nao_autentica(self):
        acessos.definir_ativo(self.gestor,self.atendente.pk,ativo=False,versao=1)
        self.assertFalse(Client().login(username='atendente',password=SENHA))
        self.assertTrue(get_user_model().objects.filter(pk=self.atendente.pk).exists())
        self.assertTrue(EventoAcesso.objects.filter(usuario=self.atendente,acao='desativado').exists())

    def test_proibe_autodesativacao_e_alteracao_do_proprio_perfil(self):
        with self.assertRaises(ValidationError):acessos.definir_ativo(self.gestor,self.gestor.pk,ativo=False,versao=1)
        with self.assertRaises(ValidationError):acessos.editar_usuario(self.gestor,self.gestor.pk,**self.dados_edicao(self.gestor,papel='consulta'))
        self.gestor.refresh_from_db();self.assertTrue(self.gestor.is_active)

    def test_ultimo_gestor_nao_pode_ser_desativado_ou_rebaixado(self):
        root=get_user_model().objects.create_superuser('tecnico',password=SENHA)
        with self.assertRaises(ValidationError):acessos.definir_ativo(root,self.gestor.pk,ativo=False,versao=1)
        with self.assertRaises(ValidationError):acessos.editar_usuario(root,self.gestor.pk,**self.dados_edicao(self.gestor,papel='atendente'))
        self.assertEqual(PerfilAcesso.objects.filter(papel='gestor',usuario__is_active=True).count(),1)

    def test_outro_gestor_pode_ser_desativado_com_historico_preservado(self):
        outro=acessos.criar_usuario(self.gestor,username='segundo',papel='gestor',senha=SENHA,exigir_troca=False)
        acessos.definir_ativo(self.gestor,outro.pk,ativo=False,versao=1)
        self.assertEqual(EventoAcesso.objects.filter(usuario=outro).count(),2)
        self.assertEqual(PerfilAcesso.objects.filter(papel='gestor',usuario__is_active=True).count(),1)

    def test_contas_tecnicas_e_personalizadas_sao_protegidas(self):
        root=get_user_model().objects.create_superuser('root',password=SENHA)
        staff=get_user_model().objects.create_user('staff',is_staff=True)
        personalizado=get_user_model().objects.create_user('customizado')
        personalizado.user_permissions.add(Permission.objects.get(content_type__app_label='acervo',codename='view_livro'))
        for usuario in [root,staff,personalizado]:
            for nome in ['editar-usuario','desativar-usuario','redefinir-senha-usuario']:
                self.assertEqual(self.client.get(reverse(nome,args=[usuario.pk])).status_code,403)
                self.assertEqual(self.client.post(reverse(nome,args=[usuario.pk]),{'versao':0}).status_code,403)

    def test_operacao_com_versao_antiga_nao_sobrescreve(self):
        acessos.editar_usuario(self.gestor,self.atendente.pk,**self.dados_edicao(self.atendente,first_name='Nome atual'))
        with self.assertRaises(ValidationError):acessos.definir_ativo(self.gestor,self.atendente.pk,ativo=False,versao=1)
        with self.assertRaises(ValidationError):acessos.editar_usuario(self.gestor,self.atendente.pk,**self.dados_edicao(self.atendente,first_name='Nome obsoleto',versao=1))
        self.atendente.refresh_from_db();self.assertEqual(self.atendente.first_name,'Nome atual');self.assertTrue(self.atendente.is_active)

    def test_senha_temporaria_obriga_troca_e_mantem_apenas_sessao_atual(self):
        usuario=acessos.criar_usuario(self.gestor,username='primeiro_acesso',papel='atendente',senha=SENHA)
        cliente=Client();self.assertTrue(cliente.login(username=usuario.username,password=SENHA))
        outro=Client();outro.force_login(usuario)
        self.assertRedirects(cliente.get(reverse('index')),reverse('password_change'),fetch_redirect_response=False)
        resposta=cliente.post(reverse('password_change'),{'old_password':SENHA,'new_password1':NOVA,'new_password2':NOVA})
        self.assertRedirects(resposta,reverse('password_change_done'))
        usuario.refresh_from_db();self.assertFalse(usuario.perfil_biblioteca.exigir_troca_senha)
        self.assertTrue(usuario.check_password(NOVA));self.assertEqual(cliente.get(reverse('leitores')).status_code,200)
        self.assertEqual(outro.get(reverse('leitores')).status_code,302)
        self.assertNotIn(SESSION_KEY,outro.session)
        self.assertIn(SESSION_KEY,cliente.session)

    def test_redefinicao_por_gestor_e_troca_propria(self):
        resposta=self.client.post(reverse('redefinir-senha-usuario',args=[self.atendente.pk]),{'new_password1':NOVA,'new_password2':NOVA,'versao':1})
        self.assertEqual(resposta.status_code,302)
        self.atendente.refresh_from_db();self.assertTrue(self.atendente.check_password(NOVA))
        self.assertTrue(self.atendente.perfil_biblioteca.exigir_troca_senha)
        self.assertRedirects(self.client.get(reverse('redefinir-senha-usuario',args=[self.gestor.pk])),reverse('password_change'),fetch_redirect_response=False)
        self.assertFalse(self.gestor.check_password(NOVA))

    def test_csrf_obrigatorio_para_gerenciar_contas(self):
        cliente=Client(enforce_csrf_checks=True);cliente.force_login(self.gestor)
        self.assertEqual(cliente.post(reverse('desativar-usuario',args=[self.atendente.pk]),{'versao':1}).status_code,403)

    def test_sessao_legada_sem_versao_pede_novo_login(self):
        sessao=self.client.session;sessao.pop(CHAVE_VERSAO);sessao.save()
        self.assertEqual(self.client.get(reverse('usuarios')).status_code,302)
        self.assertNotIn(SESSION_KEY,self.client.session)

    def test_editar_proprio_nome_mantem_sessao_atual(self):
        resposta=self.client.post(reverse('editar-usuario',args=[self.gestor.pk]),self.dados_edicao(self.gestor,first_name='Nome atualizado'))
        self.assertEqual(resposta.status_code,302)
        self.assertEqual(self.client.get(reverse('usuarios')).status_code,200)

    def test_historico_de_acesso_nao_contem_senhas(self):
        acessos.redefinir_senha(self.gestor,self.atendente.pk,senha=NOVA,versao=1)
        texto=json.dumps(list(EventoAcesso.objects.values('acao','detalhes')))
        self.assertNotIn(SENHA,texto);self.assertNotIn(NOVA,texto)
        self.assertNotIn('password',texto)

    def test_migracao_preserva_senha_e_converte_grupos_conhecidos(self):
        legado=get_user_model().objects.create_user('legado',password=SENHA)
        legado.groups.add(Group.objects.create(name='Bibliotecários'))
        senha_anterior=legado.password
        tecnico=get_user_model().objects.create_superuser('administracao',password=SENHA)
        migracao=importlib.import_module('acervo.migrations.0008_perfis_da_biblioteca')
        migracao.configurar_e_migrar(apps,SimpleNamespace(connection=connection))
        legado.refresh_from_db()
        self.assertEqual(legado.password,senha_anterior)
        self.assertEqual(legado.perfil_biblioteca.papel,'gestor')
        self.assertFalse(PerfilAcesso.objects.filter(usuario=tecnico).exists())
        self.assertTrue(legado.has_perm('acervo.manage_usuarios'))

    @override_settings(DEMO_MODE=True)
    def test_consulta_nao_expoe_dados_pessoais_nem_gestao(self):
        self.client.force_login(self.consulta)
        self.assertEqual(self.client.get(reverse('livros')).status_code,200)
        for nome in ['leitores','historico','todos-emprestimos','relatorios','exportar-acervo','usuarios','importar-acervo']:
            self.assertEqual(self.client.get(reverse(nome)).status_code,403,nome)

    def test_troca_de_senha_nao_sobrescreve_mudanca_simultanea_de_acesso(self):
        from django.contrib.auth.forms import PasswordChangeForm
        from django.test import RequestFactory
        from .views_acessos import AlterarMinhaSenha
        for operacao in ['cadastro','desativacao']:
            with self.subTest(operacao=operacao):
                usuario=acessos.criar_usuario(self.gestor,username='corrida_'+operacao,first_name='Nome inicial',papel='atendente',senha=SENHA,exigir_troca=False)
                form=PasswordChangeForm(usuario,{'old_password':SENHA,'new_password1':NOVA,'new_password2':NOVA})
                self.assertTrue(form.is_valid())
                request=RequestFactory().post('/accounts/password_change/')
                request.user=usuario
                request.session={CHAVE_VERSAO:1}
                if operacao=='cadastro':
                    acessos.editar_usuario(self.gestor,usuario.pk,**self.dados_edicao(usuario,first_name='Nome preservado'))
                else:
                    acessos.definir_ativo(self.gestor,usuario.pk,ativo=False,versao=1)
                view=AlterarMinhaSenha();view.setup(request)
                view.form_valid(form)
                usuario.refresh_from_db()
                self.assertTrue(usuario.check_password(SENHA))
                self.assertTrue(form.non_field_errors())
                if operacao=='cadastro':self.assertEqual(usuario.first_name,'Nome preservado')
                else:self.assertFalse(usuario.is_active)
