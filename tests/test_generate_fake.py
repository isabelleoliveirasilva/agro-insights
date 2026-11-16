import pandas as pd

from src.etl import generate_fake as gf


def test_produtos_tem_colunas_do_schema_e_nomes_unicos():
    produtos = gf.gerar_produtos()
    assert list(produtos.columns) == ["id", "nome", "categoria", "cultura_alvo", "preco"]
    assert len(produtos) == 18
    assert produtos["nome"].is_unique
    assert (produtos["preco"] > 0).all()


def test_toda_cultura_tem_semente_e_dois_defensivos_distintos():
    produtos = gf.gerar_produtos()
    for cultura, grupo in produtos.groupby("cultura_alvo"):
        categorias = sorted(grupo["categoria"])
        assert categorias.count("Semente") == 1, cultura
        assert len(set(categorias)) == 3, cultura


def test_geracao_e_reprodutivel_com_a_mesma_semente():
    p1, p2 = gf.gerar_produtos(), gf.gerar_produtos()
    pd.testing.assert_frame_equal(p1, p2)
    v1 = gf.gerar_vendas(p1, n=500)
    v2 = gf.gerar_vendas(p2, n=500)
    pd.testing.assert_frame_equal(v1, v2)


def test_vendas_respeitam_a_integridade_do_schema():
    produtos = gf.gerar_produtos()
    vendas = gf.gerar_vendas(produtos, n=2000)
    colunas = ["id", "data_venda", "produto_id", "uf", "quantidade", "valor_total"]
    assert list(vendas.columns) == colunas
    assert vendas["id"].is_unique
    assert vendas["produto_id"].isin(produtos["id"]).all()
    assert vendas["uf"].isin(list(gf.PESO_UF)).all()
    assert (vendas["quantidade"] > 0).all()
    assert (vendas["valor_total"] >= 0).all()
    assert vendas["data_venda"].between("2024-01-01", "2025-12-31").all()


def test_sementes_vendem_mais_no_periodo_de_plantio():
    produtos = gf.gerar_produtos()
    vendas = gf.gerar_vendas(produtos, n=5000)
    sementes = vendas.merge(produtos[["id", "categoria"]], left_on="produto_id", right_on="id")
    sementes = sementes[sementes["categoria"] == "Semente"]
    mes = pd.to_datetime(sementes["data_venda"]).dt.month
    assert mes.between(9, 11).mean() > 0.5


def test_gerar_dados_ficticios_grava_os_csvs(tmp_path):
    gf.gerar_dados_ficticios(destino=tmp_path, n_vendas=300)
    produtos = pd.read_csv(tmp_path / "produtos.csv")
    vendas = pd.read_csv(tmp_path / "vendas.csv")
    assert len(produtos) == 18
    assert len(vendas) == 300
