# Generated by Django 4.2.10 on 2024-02-10 13:46

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('usuario', '0003_alter_usuario_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usuario',
            name='id',
            field=models.UUIDField(default=uuid.UUID('6ca52cb2-d632-4f8f-90eb-5153ca7ff72b'), editable=False, primary_key=True, serialize=False),
        ),
    ]
