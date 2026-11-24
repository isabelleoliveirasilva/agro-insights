import sqlite3
from pathlib import Path

import pytest

from src.api.app import create_app, get_db

SCHEMA = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"

PRODUTOS = [
    (1, "Semente Soja Alfa-10", "Semente", "Soja", 250.5),
    (2, "Herbicida Soja Beta-20", "Herbicida", "Soja", 120.0),
    (3, "Fungicida Café Gama-30", "Fungicida", "Café", 310.9),
]


def _criar_banco(pasta):
    banco = pasta / "agro.db"
    con = sqlite3.connect(banco)
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.executemany("insert into produtos values (?, ?, ?, ?, ?)", PRODUTOS)
    con.commit()
    con.close()
    return banco


def _cliente(pasta):
    return create_app(database=_criar_banco(pasta)).test_client()


def test_health_responde_ok(tmp_path):
    resposta = _cliente(tmp_path).get("/health")
    assert resposta.status_code == 200
    assert resposta.get_json() == {"status": "ok"}


def test_lista_todos_os_produtos(tmp_path):
    resposta = _cliente(tmp_path).get("/produtos")
    corpo = resposta.get_json()
    assert resposta.status_code == 200
    assert resposta.mimetype == "application/json"
    assert corpo["total"] == 3
    assert list(corpo["produtos"][0]) == ["id", "nome", "categoria", "cultura_alvo", "preco"]
    assert corpo["produtos"][0]["preco"] == 250.5


def test_json_preserva_os_acentos(tmp_path):
    texto = _cliente(tmp_path).get("/produtos").get_data(as_text=True)
    assert "Café" in texto
    assert "\\u00e9" not in texto


def test_filtros_ignoram_maiusculas_e_acentos(tmp_path):
    cliente = _cliente(tmp_path)

    def ids(**filtros):
        corpo = cliente.get("/produtos", query_string=filtros).get_json()
        return [produto["id"] for produto in corpo["produtos"]]

    assert ids(cultura="soja") == [1, 2]
    assert ids(cultura="CAFÉ") == [3]
    assert ids(categoria="semente", cultura="soja") == [1]
    assert ids(cultura="trigo") == []


def test_filtro_sem_resultado_devolve_lista_vazia(tmp_path):
    resposta = _cliente(tmp_path).get("/produtos?cultura=trigo")
    assert resposta.status_code == 200
    assert resposta.get_json() == {"total": 0, "produtos": []}


def test_filtro_e_parametrizado_e_nao_aceita_injecao_de_sql(tmp_path):
    resposta = _cliente(tmp_path).get("/produtos", query_string={"cultura": "' OR '1'='1"})
    assert resposta.get_json()["total"] == 0


def test_rota_inexistente_devolve_json_404(tmp_path):
    resposta = _cliente(tmp_path).get("/nao-existe")
    assert resposta.status_code == 404
    assert resposta.get_json() == {"erro": "Rota não encontrada."}


def test_metodo_nao_permitido_devolve_json_405(tmp_path):
    resposta = _cliente(tmp_path).post("/produtos")
    assert resposta.status_code == 405
    assert "erro" in resposta.get_json()


def test_banco_inexistente_devolve_503_sem_criar_arquivo(tmp_path):
    caminho = tmp_path / "nao_existe.db"
    cliente = create_app(database=caminho).test_client()
    resposta = cliente.get("/health")
    assert resposta.status_code == 503
    assert "run_all" in resposta.get_json()["erro"]
    assert not caminho.exists()


def test_banco_sem_tabelas_devolve_503(tmp_path):
    caminho = tmp_path / "vazio.db"
    sqlite3.connect(caminho).close()
    resposta = create_app(database=caminho).test_client().get("/produtos")
    assert resposta.status_code == 503


def test_conexao_da_api_e_somente_leitura(tmp_path):
    app = create_app(database=_criar_banco(tmp_path))
    with app.app_context(), pytest.raises(sqlite3.OperationalError):
        get_db().execute("delete from produtos")
