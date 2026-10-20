"""Consultas somente de leitura ao cadastro de colaboradores da Senior."""

from ConexaoSQL import DatabaseConnectionSQL


FILIAL_PARA_UNIDADE = {
    2: "HE",
    1: "CORP",
    4: "CNBH",
    6: "CNVN",
    5: "CNCT",
    15: "CESP",
}

FILIAIS_ELEGIVEIS = tuple(FILIAL_PARA_UNIDADE)
EMPRESA_ELEGIVEL = 1
SITUACAO_TRABALHANDO = 1
CARGOS_NAO_ELEGIVEIS = ("%ESTAGI%", "%APRENDIZ%", "%RESIDENTE%")

BASE_SELECT = """
    SELECT DISTINCT TOP (50)
        CONVERT(varchar(20), a.numcad) AS matricula,
        a.nomfun AS nome_completo,
        a.codcar AS cd_cargo,
        b.titred AS ds_cargo,
        a.codccu AS cd_centro_custo,
        c.nomccu AS ds_centro_custo,
        a.codfil AS cd_filial,
        d.nomfil AS ds_filial
    FROM r034fun a
    LEFT JOIN r024car b ON b.codcar = a.codcar
    LEFT JOIN r018ccu c ON c.codccu = a.codccu AND c.numemp = a.numemp
    LEFT JOIN r030fil d ON d.codfil = a.codfil AND d.numemp = a.numemp
    WHERE a.sitafa = ?
      AND a.numemp = ?
      AND a.tipcol = 1
      AND UPPER(ISNULL(b.titred, '')) NOT LIKE ?
      AND UPPER(ISNULL(b.titred, '')) NOT LIKE ?
      AND UPPER(ISNULL(b.titred, '')) NOT LIKE ?
"""


class SeniorConnectionError(Exception):
    """Indica que não foi possível consultar a base Senior."""


def _executar_consulta(sql, parametros):
    conexao = DatabaseConnectionSQL()
    if not conexao.conectar():
        raise SeniorConnectionError("Não foi possível conectar à base Senior.")
    try:
        return conexao.execute_query(sql, parametros)
    except Exception as exc:
        raise SeniorConnectionError("A consulta à base Senior falhou.") from exc
    finally:
        conexao.close()


def _preparar_colaborador(registro):
    colaborador = dict(registro)
    colaborador["matricula"] = str(colaborador.get("matricula") or "").strip()
    colaborador["nome_completo"] = str(colaborador.get("nome_completo") or "").strip()
    colaborador["cargo"] = str(colaborador.get("ds_cargo") or "").strip()
    colaborador["setor"] = str(colaborador.get("ds_centro_custo") or "").strip()
    try:
        colaborador["unidade"] = FILIAL_PARA_UNIDADE.get(int(colaborador.get("cd_filial")))
    except (TypeError, ValueError):
        colaborador["unidade"] = None
    return colaborador


def buscar_colaboradores(termo):
    termo = str(termo or "").strip()
    if len(termo) < 2:
        return []

    termo_matricula = termo.lstrip("0") or "0"
    sql = BASE_SELECT + """
      AND a.codfil IN (2, 1, 4, 6, 5, 15)
      AND (
          a.nomfun LIKE ?
          OR CONVERT(varchar(20), a.numcad) LIKE ?
      )
      ORDER BY nome_completo, matricula
    """
    registros = _executar_consulta(
        sql,
        (
            SITUACAO_TRABALHANDO,
            EMPRESA_ELEGIVEL,
            *CARGOS_NAO_ELEGIVEIS,
            f"%{termo}%",
            f"%{termo_matricula}%",
        ),
    )
    return [_preparar_colaborador(registro) for registro in registros]


def buscar_colaborador_por_matricula(matricula):
    matricula = str(matricula or "").strip()
    matricula = matricula.lstrip("0") or "0"
    if not matricula.isdigit():
        return None

    sql = BASE_SELECT.replace("SELECT TOP (50)", "SELECT TOP (1)") + """
      AND a.codfil IN (2, 1, 4, 6, 5, 15)
      AND CONVERT(varchar(20), a.numcad) = ?
      ORDER BY matricula
    """
    registros = _executar_consulta(
        sql,
        (SITUACAO_TRABALHANDO, EMPRESA_ELEGIVEL, *CARGOS_NAO_ELEGIVEIS, matricula),
    )
    return _preparar_colaborador(registros[0]) if registros else None


def cpf_do_colaborador(matricula):
    matricula = str(matricula or "").strip()
    matricula = matricula.lstrip("0") or "0"
    if not matricula.isdigit():
        return None

    sql = """
        SELECT TOP (1) a.numcpf AS cpf
        FROM r034fun a
        LEFT JOIN r024car b ON b.codcar = a.codcar
        WHERE a.sitafa = ?
          AND a.numemp = ?
          AND a.tipcol = 1
          AND UPPER(ISNULL(b.titred, '')) NOT LIKE ?
          AND UPPER(ISNULL(b.titred, '')) NOT LIKE ?
          AND UPPER(ISNULL(b.titred, '')) NOT LIKE ?
          AND CONVERT(varchar(20), a.numcad) = ?
    """
    registros = _executar_consulta(
        sql,
        (SITUACAO_TRABALHANDO, EMPRESA_ELEGIVEL, *CARGOS_NAO_ELEGIVEIS, matricula),
    )
    return registros[0].get("cpf") if registros else None

