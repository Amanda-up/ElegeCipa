from django.core.management.base import BaseCommand, CommandError

from ...models import Candidato
from ...senior import SeniorConnectionError, buscar_colaborador_por_matricula


class Command(BaseCommand):
    help = "Atualiza datas de admissão dos candidatos consultando a Senior"

    def handle(self, *args, **options):
        candidatos = Candidato.objects.filter(
            matricula__isnull=False,
            data_admissao__isnull=True,
        ).exclude(matricula="")
        atualizados = 0
        sem_data = 0

        for candidato in candidatos.iterator():
            try:
                colaborador = buscar_colaborador_por_matricula(
                    candidato.matricula,
                    unidade=candidato.unidade,
                )
            except SeniorConnectionError as exc:
                raise CommandError(
                    "Falha ao consultar a Senior. O processo foi interrompido; "
                    "execute novamente após restabelecer a conexão."
                ) from exc

            data_admissao = colaborador.get("data_admissao") if colaborador else None
            if not data_admissao:
                sem_data += 1
                continue

            candidato.data_admissao = data_admissao
            candidato.save(update_fields=["data_admissao"])
            atualizados += 1

        self.stdout.write(self.style.SUCCESS(
            f"Datas atualizadas: {atualizados}; sem data disponível na Senior: {sem_data}."
        ))
