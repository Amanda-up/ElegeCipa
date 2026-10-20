from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eleicao", "0012_eleicao_unidade_vagas_eleitor_unidade"),
    ]

    operations = [
        migrations.AddField(
            model_name="candidato",
            name="data_admissao",
            field=models.DateField(
                blank=True,
                db_index=True,
                null=True,
                verbose_name="Data de admissão",
            ),
        ),
    ]
