"""Unidades eleitorais e correspondência com os códigos de filial da Senior."""

UNIDADES_ELEITORAIS = (
    ("HE", "HE (filiais 1, 2 e 7: HE, CORP e LAB)"),
    ("CNVN", "CNVN"),
    ("CNBH", "CNBH"),
    ("CNCT", "CNCT"),
    ("CESP", "CESP"),
)

FILIAIS_POR_UNIDADE = {
    "HE": (1, 2, 7),
    "CNVN": (6,),
    "CNBH": (4,),
    "CNCT": (5,),
    "CESP": (15,),
}

FILIAL_PARA_UNIDADE = {
    codfil: unidade
    for unidade, codigos in FILIAIS_POR_UNIDADE.items()
    for codfil in codigos
}
