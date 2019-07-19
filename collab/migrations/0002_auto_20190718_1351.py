# Generated by Django 2.2 on 2019-07-18 13:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('collab', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='object_type',
            field=models.CharField(choices=[('comment', 'Commentaire'), ('feature', 'Signalement'), ('attachment', 'Pièce jointe'), ('project', 'Projet')], max_length=100, verbose_name="Type de l'objet lié"),
        ),
    ]