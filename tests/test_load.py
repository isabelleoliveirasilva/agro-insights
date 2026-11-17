import sqlite3

import pandas as pd
import pytest

from src.etl import load


def _gravar_csvs(pasta, produto_da_venda=1):
    pasta.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {
            "id": [1, 2],
            "nome": ["Semente Soja Alfa-10", "Herbicida Soja Beta-20"],
            "categoria": ["Semente", "Herbicida"],
            "cultura_alvo": ["Soja", "Soja"],
            "preco": [100.0, 50.5],
        }
    ).to_csv(pasta / "produtos.csv", index=False)
    pd.DataFrame(
        {
            "id": [1, 2, 3],
            "data_venda": ["2024-01-05", "2024-01-06", "2024-01-07"],
            "produto_id": [1, 2, produto_da_venda],
            "uf": ["MT", "PR", "GO"],
            "quantidade": [5, 3, 2],
            "valor_total": [500.0, 151.5, 200.0],
        }
    ).to_csv(pasta / "vendas.csv", index=False)
    pd.DataFrame(
        {
            "ano": [2023, 2023],
            "uf": ["MT", "RO"],
            "cultura": ["Soja", "Soja"],
            "area_colhida_ha": [1000.0, None],
            "quantidade_t": [3000.0, None],
            "valor_mil_reais": [9000.0, None],
        }
    ).to_csv(pasta / "producao.csv", index=False)
    pd.DataFrame(
        {
            "data_leitura": ["2024-01-01", "2024-01-02"],
            "uf": ["MT", "MT"],
            "temperatura_media": [26.0, None],
            "precipitacao_mm": [1.2, 0.0],
        }
    ).to_csv(pasta / "clima.csv", index=False)


def _contar(banco, tabela):
    con = sqlite3.connect(banco)
    try:
        return con.execute(f"select count(*) from {tabela}").fetchone()[0]
    finally:
        con.close()


def test_carregar_banco_cria_tabelas_e_conta_linhas(tmp_path):
    _gravar_csvs(tmp_path / "processed")
    contagens = load.carregar_banco(
        processed_dir=tmp_path / "processed",
        db_path=tmp_path / "agro.db",
        schema_path=load.SCHEMA_PATH,
    )
    assert contagens == {"estados": 27, "produtos": 2, "vendas": 3, "producao": 2, "clima": 2}


def test_carga_e_idempotente(tmp_path):
    _gravar_csvs(tmp_path / "processed")
    argumentos = {"processed_dir": tmp_path / "processed", "db_path": tmp_path / "agro.db"}
    primeira = load.carregar_banco(**argumentos)
    segunda = load.carregar_banco(**argumentos)
    assert primeira == segunda


def test_valores_ausentes_viram_null_no_banco(tmp_path):
    _gravar_csvs(tmp_path / "processed")
    banco = tmp_path / "agro.db"
    load.carregar_banco(processed_dir=tmp_path / "processed", db_path=banco)

    con = sqlite3.connect(banco)
    try:
        nulos = con.execute("select count(*) from producao where quantidade_t is null").fetchone()
    finally:
        con.close()
    assert nulos[0] == 1


def test_violacao_de_chave_estrangeira_falha_e_preserva_o_banco_anterior(tmp_path):
    processed, banco = tmp_path / "processed", tmp_path / "agro.db"
    _gravar_csvs(processed)
    load.carregar_banco(processed_dir=processed, db_path=banco)

    _gravar_csvs(processed, produto_da_venda=999)  # produto inexistente
    with pytest.raises(load.ErroDeCarga, match="vendas"):
        load.carregar_banco(processed_dir=processed, db_path=banco)

    assert _contar(banco, "vendas") == 3  # o banco anterior continua intacto
    assert not banco.with_name("agro.db.tmp").exists()


def test_caminho_do_banco_le_a_variavel_de_ambiente(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "outro.db"))
    assert load.resolver_caminho_do_banco() == tmp_path / "outro.db"

    monkeypatch.setenv("DATABASE_PATH", "data/processed/agro.db")
    assert load.resolver_caminho_do_banco() == load.ROOT / "data" / "processed" / "agro.db"
