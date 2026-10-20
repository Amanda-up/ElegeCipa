import pandas as pd
from django.core.management.base import BaseCommand
from ...models import Eleitor
from ...utils import hash_matricula
from ...unidades import FILIAL_PARA_UNIDADE, UNIDADES_ELEITORAIS

class Command(BaseCommand):
    help = "Importa matrículas e CPFs de um arquivo Excel ou CSV e cria Eleitor com hash"

    def add_arguments(self, parser):
        parser.add_argument("file", type=str, help="Caminho do arquivo xlsx/xls/csv")
        parser.add_argument("--sheet", type=str, default=0, help="Nome ou índice da planilha (se Excel)")
        parser.add_argument("--mat-col", type=str, default="matricula", help="Nome da coluna com matrículas")
        parser.add_argument("--cpf-col", type=str, default="CPF", help="Nome da coluna com CPFs")
        parser.add_argument("--filial-col", type=str, default="codfil", help="Coluna opcional com código da filial Senior")
        parser.add_argument("--unit-col", type=str, default="unidade", help="Coluna opcional com a unidade eleitoral")

    def handle(self, *args, **options):
        path = options["file"]
        sheet = options["sheet"]
        mat_col = options["mat_col"]
        cpf_col = options["cpf_col"]
        filial_col = options["filial_col"]
        unit_col = options["unit_col"]

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

        created = 0
        skipped = 0
        cpfs_corrigidos = 0
        sem_unidade = 0
        unidades_validas = {codigo for codigo, _ in UNIDADES_ELEITORAIS}

        for _, row in df.iterrows():
            mat = row.get(mat_col, "")
            if pd.isna(mat):
                mat = ""
            mat = str(mat)
            mat = mat.strip()
            if not mat:
                skipped += 1
                continue

            cpf = row.get(cpf_col, "")
            cpf = "" if pd.isna(cpf) else str(cpf).strip()

            unidade_raw = row.get(unit_col, "")
            unidade = "" if pd.isna(unidade_raw) else str(unidade_raw).strip().upper()
            if unidade in ("CORP", "LAB"):
                unidade = "HE"
            if unidade not in unidades_validas:
                codfil = row.get(filial_col, "")
                try:
                    unidade = FILIAL_PARA_UNIDADE.get(int(float(codfil)))
                except (TypeError, ValueError):
                    unidade = None
            if unidade not in unidades_validas:
                unidade = None
                sem_unidade += 1

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
                defaults={"cpf_hash": h_cpf, "unidade": unidade}
            )
            if not created_flag:
                campos_atualizados = []
                if h_cpf and not obj.cpf_hash:
                    obj.cpf_hash = h_cpf
                    campos_atualizados.append("cpf_hash")
                if unidade and obj.unidade != unidade:
                    obj.unidade = unidade
                    campos_atualizados.append("unidade")
                if campos_atualizados:
                    obj.save(update_fields=campos_atualizados)

            if created_flag:
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Import concluída: {created} criados, {skipped} pulados, {cpfs_corrigidos} CPFs corrigidos, "
            f"{sem_unidade} sem unidade reconhecida."
        ))
