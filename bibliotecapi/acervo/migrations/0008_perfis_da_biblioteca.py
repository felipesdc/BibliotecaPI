from django.db import migrations

GRUPOS = {'gestor': 'Biblioteca · Gestor', 'atendente': 'Biblioteca · Atendente', 'consulta': 'Biblioteca · Consulta interna'}
PERMISSOES = {'gestor': ['view_livro', 'add_livro', 'change_livro', 'delete_livro', 'view_livrocopia', 'add_livrocopia', 'change_livrocopia', 'delete_livrocopia', 'view_autor', 'add_autor', 'change_autor', 'delete_autor', 'view_genero', 'add_genero', 'change_genero', 'delete_genero', 'view_lingua', 'add_lingua', 'change_lingua', 'delete_lingua', 'view_leitor', 'add_leitor', 'change_leitor', 'delete_leitor', 'marca_devolucao', 'view_relatorios', 'manage_usuarios'], 'atendente': ['view_livro', 'view_livrocopia', 'view_autor', 'view_genero', 'view_lingua', 'view_leitor', 'add_leitor', 'change_leitor', 'marca_devolucao'], 'consulta': ['view_livro', 'view_livrocopia', 'view_autor', 'view_genero', 'view_lingua']}


def configurar_e_migrar(apps, schema_editor):
    banco = schema_editor.connection.alias
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    User = apps.get_model('auth', 'User')
    Perfil = apps.get_model('acervo', 'PerfilAcesso')
    Evento = apps.get_model('acervo', 'EventoAcesso')
    grupos = {}
    for papel, nome in GRUPOS.items():
        grupo, _ = Group.objects.using(banco).get_or_create(name=nome)
        permissoes = []
        for codigo in PERMISSOES[papel]:
            modelo = {'marca_devolucao': 'livrocopia', 'view_relatorios': 'emprestimo', 'manage_usuarios': 'perfilacesso'}.get(codigo, codigo.split('_', 1)[1])
            tipo, _ = ContentType.objects.using(banco).get_or_create(app_label='acervo', model=modelo)
            permissao, _ = Permission.objects.using(banco).get_or_create(content_type=tipo, codename=codigo, defaults={'name': codigo.replace('_', ' ')})
            permissoes.append(permissao)
        grupo.permissions.set(permissoes)
        grupos[papel] = grupo
    legados = {'Bibliotecários': 'gestor', 'Gestores da demonstração': 'gestor', 'Atendentes da demonstração': 'atendente'}
    for usuario in User.objects.using(banco).all().iterator():
        if usuario.is_superuser or (usuario.is_staff and usuario.username != 'gestor_demo') or usuario.user_permissions.exists():
            continue
        nomes = set(usuario.groups.values_list('name', flat=True))
        if nomes - set(legados):
            continue
        papel = 'gestor' if any(legados[n] == 'gestor' for n in nomes) else 'atendente' if nomes else 'consulta'
        usuario.groups.set([grupos[papel]])
        if usuario.is_staff:
            usuario.is_staff = False
            usuario.save(using=banco, update_fields=['is_staff'])
        Perfil.objects.using(banco).get_or_create(usuario=usuario, defaults={'papel': papel})
        Evento.objects.using(banco).create(usuario=usuario, acao='migrado', detalhes={'papel': papel})


class Migration(migrations.Migration):
    dependencies = [('acervo', '0007_eventoacesso_perfilacesso')]
    operations = [migrations.RunPython(configurar_e_migrar, migrations.RunPython.noop)]
