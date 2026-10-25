from django.db import migrations
from django.db.models import Q


def preencher_codigos(apps, schema_editor):
    copia = apps.get_model('acervo', 'LivroCopia')
    banco = schema_editor.connection.alias
    for exemplar in copia.objects.using(banco).filter(Q(codigo__isnull=True) | Q(codigo='')).iterator():
        base = 'BIB-' + exemplar.pk.hex
        codigo, sufixo = base, 1
        while copia.objects.using(banco).filter(codigo=codigo).exists():
            codigo = f'{base}-{sufixo}'
            sufixo += 1
        copia.objects.using(banco).filter(pk=exemplar.pk).update(codigo=codigo)


class Migration(migrations.Migration):
    dependencies = [('acervo', '0004_alter_livrocopia_estado')]
    operations = [migrations.RunPython(preencher_codigos, migrations.RunPython.noop)]
