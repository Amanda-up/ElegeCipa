import pandas as pd
from django.core.management.base import BaseCommand
from ...models import Eleitor
from ...utils import hash_matricula

class Command(BaseCommand):
    help = "Importa matrículas e CPFs de um arquivo Excel ou CSV e cria Eleitor com hash"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str, help="Caminho do arquivo xlsx/xls/csv")
        parser.add_argument("--sheet", type=str, default=0, help="Nome ou índice da planilha (se Excel)")
        parser.add_argument("--mat-col", type=str, default="matricula", help="Nome da coluna com matrículas")
        parser.add_argument("--cpf-col", type=str, default="CPF", help="Nome da coluna com CPFs")

    def handle(self, *args, **options):
        path = options["file"]
        sheet = options["sheet"]
        mat_col = options["mat_col"]
        cpf_col = options["cpf_col"]

        # Lê arquivo
        try:
            if path.lower().endswith(".csv"):
                df = pd.read_csv(path, dtype=str)
            else:
                df = pd.read_excel(path, sheet_name=sheet, dtype=str)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Erro ao ler o arquivo: {e}"))
            return

        # Normaliza nomes de colunas
        df.columns = [c.strip() for c in df.columns]

        if mat_col not in df.columns:
            self.stderr.write(self.style.ERROR(f"Coluna '{mat_col}' não encontrada no arquivo."))
            return
        if cpf_col not in df.columns:
            self.stderr.write(self.style.ERROR(f"Coluna '{cpf_col}' não encontrada no arquivo."))
            return

        mats = df[mat_col].dropna().astype(str)
        cpfs = df[cpf_col].dropna().astype(str)

        created = 0
        skipped = 0
        cpfs_corrigidos = 0

        for i, mat in enumerate(mats):
            mat = mat.strip()
            if not mat:
                skipped += 1
                continue

            cpf = cpfs.iloc[i].strip() if i < len(cpfs) else ""

            # CORREÇÃO: Recuperar zeros à esquerda do CPF
            if cpf:
                # Remove qualquer caractere não numérico
                cpf_limpo = ''.join(filter(str.isdigit, cpf))
                
                # Se o CPF tem menos de 11 dígitos, preenche com zeros à esquerda
                if cpf_limpo.isdigit() and len(cpf_limpo) < 11:
                    cpf_corrigido = cpf_limpo.zfill(11)
                    if cpf != cpf_corrigido:
                        cpfs_corrigidos += 1
                        if cpfs_corrigidos <= 5:  # Mostra apenas os primeiros 5 para debug
                            self.stdout.write(f"🔧 CPF corrigido: '{cpf}' -> '{cpf_corrigido}'")
                    cpf = cpf_corrigido
                else:
                    cpf = cpf_limpo

            h_mat = hash_matricula(mat)
            h_cpf = hash_matricula(cpf) if cpf else None

            obj, created_flag = Eleitor.objects.get_or_create(
                matricula_hash=h_mat,
                defaults={"cpf_hash": h_cpf}
            )
            if not created_flag and h_cpf and not obj.cpf_hash:
                obj.cpf_hash = h_cpf
                obj.save(update_fields=["cpf_hash"])

            if created_flag:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Import concluída: {created} criados, {skipped} pulados, {cpfs_corrigidos} CPFs corrigidos."
        ))