import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SCHEMA = RAIZ / "sql" / "schema.sql"
CONSULTAS = RAIZ / "sql" / "queries.sql"


def _ler_consultas():
    """Separa o queries.sql em instruções (cada uma termina em ';' fora de comentários)."""
    consultas, acumulado = [], ""
    for linha in CONSULTAS.read_text(encoding="utf-8").splitlines(keepends=True):
        acumulado += linha
        if sqlite3.complete_statement(acumulado):
            consultas.append(acumulado.strip())
            acumulado = ""
    return consultas


def _banco_de_teste():
    """Banco pequeno, com valores que dá para conferir de cabeça."""
    con = sqlite3.connect(":memory:")
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.executemany(
        "insert into produtos values (?, ?, ?, ?, ?)",
        [
            (1, "Semente Soja Alfa-10", "Semente", "Soja", 100.0),
            (2, "Herbicida Milho Beta-20", "Herbicida", "Milho", 150.0),
        ],
    )
    con.executemany(
        "insert into vendas values (?, ?, ?, ?, ?, ?)",
        [
            (1, "2024-01-10", 1, "MT", 10, 1000.0),
            (2, "2024-01-20", 1, "PR", 5, 500.0),
            (3, "2024-02-05", 2, "MT", 2, 300.0),
        ],
    )
    con.executemany(
        "insert into producao values (?, ?, ?, ?, ?, ?)",
        [
            (2023, "MT", "Soja", 10.0, 100.0, 1000.0),
            (2024, "MT", "Soja", 10.0, 150.0, 1500.0),
            (2024, "PR", "Soja", 20.0, 50.0, 500.0),
            (2024, "MT", "Milho", 5.0, None, None),
            (2024, "GO", "Milho", 4.0, 80.0, 400.0),
        ],
    )
    con.executemany(
        "insert into clima values (?, ?, ?, ?)",
        [
            ("2024-01-10", "MT", 27.0, 10.0),
            ("2024-01-20", "MT", 26.0, 30.0),
            ("2024-02-05", "MT", 28.0, 0.0),
        ],
    )
    return con


def _executar(numero):
    con = _banco_de_teste()
    try:
        return [dict(linha) for linha in con.execute(_ler_consultas()[numero - 1])]
    finally:
        con.close()


def test_arquivo_tem_cinco_consultas():
    assert len(_ler_consultas()) == 5


def test_consulta_1_top_produtos_com_participacao():
    linhas = _executar(1)
    assert [linha["nome"] for linha in linhas] == [
        "Semente Soja Alfa-10",
        "Herbicida Milho Beta-20",
    ]
    assert linhas[0]["receita"] == 1500.0
    assert linhas[0]["participacao_pct"] == 83.33
    assert linhas[1]["participacao_pct"] == 16.67


def test_consulta_2_vendas_por_regiao_e_mes():
    linhas = _executar(2)
    campos = ("mes", "regiao", "receita", "posicao_no_mes")
    resumo = [tuple(linha[campo] for campo in campos) for linha in linhas]
    assert resumo == [
        ("2024-01", "Centro-Oeste", 1000.0, 1),
        ("2024-01", "Sul", 500.0, 2),
        ("2024-02", "Centro-Oeste", 300.0, 1),
    ]


def test_consulta_3_maiores_produtores_do_ultimo_ano():
    linhas = _executar(3)
    campos = ("cultura", "uf", "posicao", "produtividade_t_ha")
    resumo = [tuple(linha[campo] for campo in campos) for linha in linhas]
    # MT/Milho tem quantidade nula e fica de fora; 2023 não entra (último ano = 2024)
    assert resumo == [
        ("Milho", "GO", 1, 20.0),
        ("Soja", "MT", 1, 15.0),
        ("Soja", "PR", 2, 2.5),
    ]
    assert {linha["ano"] for linha in linhas} == {2024}


def test_consulta_4_crescimento_anual_com_lag():
    por_chave = {(linha["cultura"], linha["ano"]): linha for linha in _executar(4)}
    assert por_chave[("Soja", 2023)]["variacao_pct"] is None
    assert por_chave[("Soja", 2024)]["quantidade_t"] == 200.0
    assert por_chave[("Soja", 2024)]["ano_anterior"] == 100.0
    assert por_chave[("Soja", 2024)]["variacao_pct"] == 100.0
    assert por_chave[("Soja", 2024)]["ufs_com_dado"] == 2
    assert por_chave[("Milho", 2024)]["ufs_com_dado"] == 1  # MT veio nulo


def test_consulta_5_chuvoso_x_seco():
    linhas = {linha["tipo_mes"]: linha for linha in _executar(5)}
    assert linhas["chuvoso"]["uf"] == "MT"
    assert linhas["chuvoso"]["chuva_media_mm"] == 40.0
    assert linhas["chuvoso"]["receita_media"] == 1000.0
    assert linhas["seco"]["chuva_media_mm"] == 0.0
    assert linhas["seco"]["receita_media"] == 300.0
