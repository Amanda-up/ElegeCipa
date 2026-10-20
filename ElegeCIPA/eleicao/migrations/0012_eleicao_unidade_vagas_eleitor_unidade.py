from django.db import migrations, models
from django.db.models import Q


UNIDADES = [
    ("HE", "HE (filiais 1, 2 e 7: HE, CORP e LAB)"),
    ("CNVN", "CNVN"),
    ("CNBH", "CNBH"),
    ("CNCT", "CNCT"),
    ("CESP", "CESP"),
]


def preencher_unidade_eleicoes_existentes(apps, schema_editor):
    Eleicao = apps.get_model("eleicao", "Eleicao")
    Candidato = apps.get_model("eleicao", "Candidato")

    Candidato.objects.filter(unidade__in=["CORP", "LAB"]).update(unidade="HE")
    unidades_validas = {codigo for codigo, _ in UNIDADES}
    for eleicao in Eleicao.objects.all().iterator():
        unidades = set(
            Candidato.objects.filter(eleicao_id=eleicao.pk)
            .values_list("unidade", flat=True)
            .distinct()
        )
        if len(unidades) == 1:
            unidade = next(iter(unidades))
        else:
            # Eleições antigas podiam reunir candidatos de várias filiais.
            # Como não há unidade eleitoral histórica, preservamos todos no evento legado HE.
            unidade = "HE"
            if unidades:
                Candidato.objects.filter(eleicao_id=eleicao.pk).update(unidade=unidade)
        eleicao.unidade = unidade if unidade in unidades_validas else "HE"
        eleicao.save(update_fields=["unidade"])


class Migration(migrations.Migration):

    dependencies = [
        ("eleicao", "0011_candidato_matricula_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="eleicao",
            name="unidade",
            field=models.CharField(
                choices=UNIDADES,
                default="HE",
                max_length=10,
                verbose_name="Estabelecimento",
            ),
        ),
        migrations.AddField(
            model_name="eleicao",
            name="vagas_efetivos",
            field=models.PositiveSmallIntegerField(default=6, verbose_name="Quantidade de efetivos"),
        ),
        migrations.AddField(
            model_name="eleicao",
            name="vagas_suplentes",
            field=models.PositiveSmallIntegerField(default=4, verbose_name="Quantidade de suplentes"),
        ),
        migrations.AddField(
            model_name="eleitor",
            name="unidade",
            field=models.CharField(
                blank=True,
                choices=UNIDADES,
                db_index=True,
                max_length=10,
                null=True,
                verbose_name="Estabelecimento eleitoral",
            ),
        ),
        migrations.AlterField(
            model_name="candidato",
            name="unidade",
            field=models.CharField(choices=UNIDADES, max_length=10),
        ),
        migrations.RunPython(preencher_unidade_eleicoes_existentes, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="eleicao",
            constraint=models.UniqueConstraint(
                condition=Q(vigente=True),
                fields=("unidade",),
                name="eleicao_vigente_unica_por_unidade",
            ),
        ),
    ]
