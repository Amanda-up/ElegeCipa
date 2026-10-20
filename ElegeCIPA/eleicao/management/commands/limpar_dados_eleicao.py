from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import Candidato, Eleicao, Eleitor, Voto


class Command(BaseCommand):
    help = (
        "Apaga eleições, candidatos, votos e eleitores; preserva superusuários "
        "e contas não vinculadas a eleitores."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Confirma a exclusão permanente dos dados eleitorais.",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        contagens = {
            "eleições": Eleicao.objects.count(),
            "candidatos": Candidato.objects.count(),
            "votos": Voto.objects.count(),
            "eleitores": Eleitor.objects.count(),
        }
        contas_eleitor_ids = list(
            Eleitor.objects.filter(user__isnull=False)
            .values_list("user_id", flat=True)
            .distinct()
        )
        contas_eleitor = User.objects.filter(
            pk__in=contas_eleitor_ids,
            is_superuser=False,
        ).count()

        self.stdout.write("Registros que serão removidos:")
        for nome, quantidade in contagens.items():
            self.stdout.write(f"  {nome}: {quantidade}")
        self.stdout.write(f"  contas vinculadas a eleitores (não superusuários): {contas_eleitor}")

        if not options["confirmar"]:
            self.stdout.write(
                self.style.WARNING(
                    "Prévia: nada foi apagado. Use --confirmar após conferir as contagens."
                )
            )
            return

        with transaction.atomic():
            Voto.objects.all().delete()
            Candidato.objects.all().delete()
            Eleicao.objects.all().delete()
            Eleitor.objects.all().delete()
            User.objects.filter(
                pk__in=contas_eleitor_ids,
                is_superuser=False,
            ).delete()

        self.stdout.write(self.style.SUCCESS("Dados eleitorais removidos com sucesso."))
