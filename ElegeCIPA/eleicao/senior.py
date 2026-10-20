"""Consultas somente de leitura ao cadastro de colaboradores da Senior."""

from ConexaoSQL import DatabaseConnectionSQL
from .unidades import FILIAL_PARA_UNIDADE, FILIAIS_POR_UNIDADE


FILIAIS_ELEGIVEIS = tuple(FILIAL_PARA_UNIDADE)
EMPRESA_ELEGIVEL = 1
SITUACAO_TRABALHANDO = 1
CARGOS_NAO_ELEGIVEIS = ("ESTAG%", "ACADEM%", "APRENDIZ%", "RESIDENTE%")

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


def _filtro_filiais(unidade=None):
    if unidade:
        filiais = FILIAIS_POR_UNIDADE.get(unidade, ())
    else:
        filiais = FILIAIS_ELEGIVEIS
    if not filiais:
        return "AND 1 = 0", ()
    placeholders = ", ".join("?" for _ in filiais)
    return f"AND a.codfil IN ({placeholders})", tuple(filiais)


def buscar_colaboradores(termo, unidade=None):
    termo = str(termo or "").strip()
    if len(termo) < 2:
        return []

    termo_matricula = termo.lstrip("0") or "0"
    filtro_filiais, parametros_filiais = _filtro_filiais(unidade)
    sql = BASE_SELECT + f"""
      {filtro_filiais}
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
            *parametros_filiais,
            f"%{termo}%",
            f"%{termo_matricula}%",
        ),
    )
    return [_preparar_colaborador(registro) for registro in registros]


def buscar_colaborador_por_matricula(matricula, unidade=None):
    matricula = str(matricula or "").strip()
    matricula = matricula.lstrip("0") or "0"
    if not matricula.isdigit():
        return None

    filtro_filiais, parametros_filiais = _filtro_filiais(unidade)
    sql = BASE_SELECT.replace("SELECT DISTINCT TOP (50)", "SELECT DISTINCT TOP (1)") + f"""
      {filtro_filiais}
      AND CONVERT(varchar(20), a.numcad) = ?
      ORDER BY matricula
    """
    registros = _executar_consulta(
        sql,
        (
            SITUACAO_TRABALHANDO,
            EMPRESA_ELEGIVEL,
            *CARGOS_NAO_ELEGIVEIS,
            *parametros_filiais,
            matricula,
        ),
    )
    return _preparar_colaborador(registros[0]) if registros else None


def dados_do_colaborador_para_login(matricula):
    matricula = str(matricula or "").strip()
    matricula = matricula.lstrip("0") or "0"
    if not matricula.isdigit():
        return None

    sql = """
        SELECT TOP (1) a.numcpf AS cpf, a.codfil AS cd_filial
        FROM r034fun a
        LEFT JOIN r024car b ON b.codcar = a.codcar
        WHERE a.sitafa = ?
          AND a.numemp = ?
          AND a.tipcol = 1
          AND UPPER(ISNULL(b.titred, '')) NOT LIKE ?
          AND UPPER(ISNULL(b.titred, '')) NOT LIKE ?
          AND UPPER(ISNULL(b.titred, '')) NOT LIKE ?
          AND UPPER(ISNULL(b.titred, '')) NOT LIKE ?
          AND a.codfil IN (1, 2, 7, 4, 6, 5, 15)
          AND CONVERT(varchar(20), a.numcad) = ?
    """
    registros = _executar_consulta(
        sql,
        (SITUACAO_TRABALHANDO, EMPRESA_ELEGIVEL, *CARGOS_NAO_ELEGIVEIS, matricula),
    )
    if not registros:
        return None
    registro = registros[0]
    try:
        unidade = FILIAL_PARA_UNIDADE.get(int(registro.get("cd_filial")))
    except (TypeError, ValueError):
        unidade = None
    if not unidade:
        return None
    return {"cpf": registro.get("cpf"), "unidade": unidade}


def cpf_do_colaborador(matricula):
    """Compatibilidade com chamadas antigas que só precisam do CPF."""
    dados = dados_do_colaborador_para_login(matricula)
    return dados["cpf"] if dados else None

