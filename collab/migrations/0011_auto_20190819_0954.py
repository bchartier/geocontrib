# Generated by Django 2.2 on 2019-08-19 07:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('collab', '0010_auto_20190809_0913'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stackedevent',
            name='state',
            field=models.CharField(choices=[('pending', "Tâche en attente d'exécution"), ('failed', 'Echec de la tâche'), ('successful', 'Tâche terminée avec succès')], default='pending', max_length=20, verbose_name='État'),
        ),
    ]