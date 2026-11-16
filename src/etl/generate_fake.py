"""Geração de dados fictícios: catálogo de produtos e vendas.

Todos os nomes são inventados e genéricos. Não representam produtos ou marcas reais.
Os dados são reproduzíveis: a mesma semente sempre gera o mesmo resultado.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

SEED = 42
N_VENDAS = 20_000
PERIODO_VENDAS = ("2024-01-01", "2025-12-31")

CULTURAS = ["Soja", "Milho", "Cana-de-açúcar", "Café", "Trigo", "Algodão"]
LETRAS = ["Alfa", "Beta", "Gama", "Delta", "Sigma", "Omega"]

# Faixa de preço (mínimo, máximo) por categoria de produto.
PRECOS = {
    "Semente": (180.0, 650.0),
    "Herbicida": (90.0, 380.0),
    "Fungicida": (120.0, 520.0),
    "Inseticida": (100.0, 420.0),
}

# Sazonalidade de vendas por categoria (peso relativo de janeiro a dezembro).
# Sementes vendem mais no plantio (set-nov); defensivos acompanham o ciclo da lavoura.
SAZONALIDADE = {
    "Semente": [1, 1, 1, 1, 1, 1, 2, 4, 10, 12, 10, 4],
    "Herbicida": [6, 2, 1, 1, 1, 1, 1, 3, 8, 12, 12, 10],
    "Fungicida": [10, 10, 6, 2, 1, 1, 1, 1, 2, 5, 10, 12],
    "Inseticida": [10, 8, 4, 1, 1, 1, 1, 2, 4, 8, 12, 12],
}

# UFs onde há vendas e o peso de cada uma (soma = 1). Todas existem na tabela `estados`.
PESO_UF = {
    "MT": 0.22,
    "PR": 0.14,
    "RS": 0.14,
    "GO": 0.12,
    "MS": 0.10,
    "SP": 0.10,
    "MG": 0.08,
    "BA": 0.05,
    "SC": 0.03,
    "TO": 0.02,
}


def gerar_produtos(seed=SEED):
    """Gera o catálogo: 1 semente e 2 defensivos por cultura (18 produtos no total)."""
    rng = np.random.default_rng(seed)
    defensivos = [c for c in PRECOS if c != "Semente"]
    registros = []
    for i, cultura in enumerate(CULTURAS):
        for j in range(3):
            n = i * 3 + j
            # j = 0 é a semente; j = 1 e 2 alternam os defensivos entre as culturas.
            categoria = "Semente" if j == 0 else defensivos[(i + j - 1) % len(defensivos)]
            minimo, maximo = PRECOS[categoria]
            registros.append(
                {
                    "id": n + 1,
                    "nome": f"{categoria} {cultura} {LETRAS[n % len(LETRAS)]}-{(n + 1) * 10}",
                    "categoria": categoria,
                    "cultura_alvo": cultura,
                    "preco": round(float(rng.uniform(minimo, maximo)), 2),
                }
            )
    return pd.DataFrame(registros)


def gerar_vendas(produtos, n=N_VENDAS, periodo=PERIODO_VENDAS, seed=SEED):
    """Gera `n` vendas com sazonalidade por categoria e peso por UF."""
    rng = np.random.default_rng(seed + 1)
    datas = pd.date_range(start=periodo[0], end=periodo[1], freq="D")
    meses = datas.month.to_numpy()

    escolhidos = rng.integers(0, len(produtos), size=n)
    produto_ids = produtos["id"].to_numpy()[escolhidos]
    categorias = produtos["categoria"].to_numpy()[escolhidos]
    precos = produtos["preco"].to_numpy()[escolhidos]

    # Cada categoria sorteia suas datas conforme a própria sazonalidade.
    posicao_data = np.zeros(n, dtype=int)
    for categoria, sazonalidade in SAZONALIDADE.items():
        mascara = categorias == categoria
        peso_dia = np.array(sazonalidade, dtype=float)[meses - 1]
        peso_dia = peso_dia / peso_dia.sum()
        posicao_data[mascara] = rng.choice(len(datas), size=int(mascara.sum()), p=peso_dia)

    ufs = rng.choice(list(PESO_UF), size=n, p=list(PESO_UF.values()))
    quantidade = np.clip(rng.lognormal(2.5, 0.6, size=n).round(), 1, None).astype(int)
    desconto = rng.uniform(0.90, 1.00, size=n)

    vendas = pd.DataFrame(
        {
            "data_venda": datas[posicao_data].strftime("%Y-%m-%d"),
            "produto_id": produto_ids,
            "uf": ufs,
            "quantidade": quantidade,
            "valor_total": (quantidade * precos * desconto).round(2),
        }
    )
    vendas = vendas.sort_values("data_venda", kind="stable").reset_index(drop=True)
    vendas.insert(0, "id", vendas.index + 1)
    return vendas


def gerar_dados_ficticios(destino=None, seed=SEED, n_vendas=N_VENDAS):
    """Gera e salva produtos.csv e vendas.csv (por padrão em data/raw/)."""
    destino = Path(destino) if destino else RAW_DIR
    destino.mkdir(parents=True, exist_ok=True)

    produtos = gerar_produtos(seed)
    vendas = gerar_vendas(produtos, n=n_vendas, seed=seed)

    produtos.to_csv(destino / "produtos.csv", index=False)
    vendas.to_csv(destino / "vendas.csv", index=False)
    logger.info("Salvos %d produtos e %d vendas em %s", len(produtos), len(vendas), destino)
    return produtos, vendas


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    gerar_dados_ficticios()
