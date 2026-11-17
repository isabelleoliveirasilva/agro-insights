import json

import pandas as pd
import pytest

from src.etl import generate_fake as gf
from src.etl import transform as tf

CABECALHO = {"NC": "Nível Territorial (Código)", "V": "Valor"}


def _linha(uf, variavel, ano, produto, valor):
    return {"V": valor, "D1C": uf, "D2C": variavel, "D3C": ano, "D4C": produto}


def test_ufs_validas_tem_as_27_unidades_da_federacao():
    assert len(tf.UFS_VALIDAS) == 27


def test_limpar_ibge_converte_simbolos_e_pivota():
    dados = [
        CABECALHO,
        _linha("51", "214", "2023", "40124", "1000"),
        _linha("51", "215", "2023", "40124", "-"),  # zero verdadeiro
        _linha("51", "216", "2023", "40124", "..."),  # indisponível
        _linha("11", "214", "2023", "40124", "X"),  # omitido
    ]
    producao = tf.limpar_ibge(dados)

    assert list(producao.columns) == tf.COLUNAS_PRODUCAO
    assert len(producao) == 2
    mt = producao[producao["uf"] == "MT"].iloc[0]
    assert mt["cultura"] == "Soja"
    assert mt["quantidade_t"] == 1000.0
    assert mt["valor_mil_reais"] == 0.0
    assert pd.isna(mt["area_colhida_ha"])
    ro = producao[producao["uf"] == "RO"].iloc[0]
    assert pd.isna(ro["quantidade_t"])


def test_limpar_ibge_rejeita_produto_desconhecido():
    dados = [CABECALHO, _linha("51", "214", "2023", "99999", "10")]
    with pytest.raises(ValueError, match="produto"):
        tf.limpar_ibge(dados)


def test_limpar_ibge_rejeita_chaves_duplicadas():
    dados = [
        CABECALHO,
        _linha("51", "214", "2023", "40124", "10"),
        _linha("51", "214", "2023", "40124", "20"),
    ]
    with pytest.raises(ValueError):
        tf.limpar_ibge(dados)


def test_limpar_clima_trata_nulos_negativos_e_duplicados():
    dados = {
        "MT": {
            "cidade": "Cuiabá",
            "dados": {
                "daily": {
                    "time": ["2024-01-01", "2024-01-02", "2024-01-02"],
                    "temperature_2m_mean": [26.1, None, None],
                    "precipitation_sum": [0.0, -1.0, -1.0],
                }
            },
        }
    }
    clima = tf.limpar_clima(dados)

    assert list(clima.columns) == ["data_leitura", "uf", "temperatura_media", "precipitacao_mm"]
    assert len(clima) == 2
    assert clima.loc[0, "data_leitura"] == "2024-01-01"
    assert clima.loc[0, "temperatura_media"] == 26.1
    assert pd.isna(clima.loc[1, "temperatura_media"])
    assert pd.isna(clima.loc[1, "precipitacao_mm"])


def test_limpar_produtos_padroniza_e_remove_invalidos():
    bruto = pd.DataFrame(
        {
            "id": [1, 1, 2, 3, 4],
            "nome": ["  Semente Soja Alfa-10 ", "duplicado", "Herbicida X", "Sem preço", None],
            "categoria": ["Semente", "Semente", "Herbicida", "Fungicida", "Semente"],
            "cultura_alvo": ["Soja", "Soja", "Milho", "Trigo", "Café"],
            "preco": [100.0, 100.0, -5.0, None, 50.0],
        }
    )
    produtos = tf.limpar_produtos(bruto)
    assert produtos["id"].tolist() == [1]
    assert produtos.loc[0, "nome"] == "Semente Soja Alfa-10"


def test_limpar_vendas_remove_linhas_que_violam_o_schema():
    produtos = pd.DataFrame({"id": [1, 2]})
    bruto = pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5, 6, 6],
            "data_venda": ["2024-01-05"] * 4 + ["xx", "2024-02-01", "2024-02-01"],
            "produto_id": [1, 2, 1, 999, 1, 1, 1],
            "uf": [" mt ", "PR", "XX", "SP", "GO", "RS", "RS"],
            "quantidade": [5, 0, 3, 2, 1, 4, 4],
            "valor_total": [100.0, 50.0, 30.0, 20.0, 10.0, 40.0, 40.0],
        }
    )
    vendas = tf.limpar_vendas(bruto, produtos)
    # sobram: id 1 (uf normalizada) e id 6 (duplicata removida)
    assert vendas["id"].tolist() == [1, 6]
    assert vendas.loc[0, "uf"] == "MT"
    assert vendas.loc[0, "data_venda"] == "2024-01-05"


def test_transformar_tudo_gera_os_quatro_csvs(tmp_path):
    raw, saida = tmp_path / "raw", tmp_path / "processed"
    gf.gerar_dados_ficticios(destino=raw, n_vendas=200)
    ibge = [CABECALHO, _linha("51", "214", "2023", "40124", "1000")]
    (raw / "ibge_pam.json").write_text(json.dumps(ibge), encoding="utf-8")
    clima = {
        "MT": {
            "cidade": "Cuiabá",
            "dados": {
                "daily": {
                    "time": ["2024-01-01"],
                    "temperature_2m_mean": [26.0],
                    "precipitation_sum": [1.2],
                }
            },
        }
    }
    (raw / "clima.json").write_text(json.dumps(clima), encoding="utf-8")

    tf.transformar_tudo(raw_dir=raw, processed_dir=saida)

    for nome in ("producao", "clima", "produtos", "vendas"):
        assert (saida / f"{nome}.csv").exists()
    assert len(pd.read_csv(saida / "vendas.csv")) == 200
