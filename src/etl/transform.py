"""Limpeza e padronização dos dados brutos (IBGE, clima, produtos e vendas)."""

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

# Código IBGE da unidade da federação -> sigla
UF_POR_CODIGO = {
    11: "RO",
    12: "AC",
    13: "AM",
    14: "RR",
    15: "PA",
    16: "AP",
    17: "TO",
    21: "MA",
    22: "PI",
    23: "CE",
    24: "RN",
    25: "PB",
    26: "PE",
    27: "AL",
    28: "SE",
    29: "BA",
    31: "MG",
    32: "ES",
    33: "RJ",
    35: "SP",
    41: "PR",
    42: "SC",
    43: "RS",
    50: "MS",
    51: "MT",
    52: "GO",
    53: "DF",
}
UFS_VALIDAS = set(UF_POR_CODIGO.values())

# Código do produto no SIDRA -> cultura padronizada (mesmo vocabulário de produtos.cultura_alvo)
CULTURA_POR_CODIGO = {
    "40124": "Soja",
    "40122": "Milho",
    "40106": "Cana-de-açúcar",
    "40139": "Café",
    "40127": "Trigo",
    "40130": "Algodão",
}

# Código da variável do SIDRA -> coluna da tabela `producao`
COLUNA_POR_VARIAVEL = {
    "214": "quantidade_t",
    "215": "valor_mil_reais",
    "216": "area_colhida_ha",
}
COLUNAS_PRODUCAO = [
    "ano",
    "uf",
    "cultura",
    "area_colhida_ha",
    "quantidade_t",
    "valor_mil_reais",
]

# Símbolos do IBGE: "-" é zero verdadeiro; os demais indicam dado indisponível.
SIMBOLO_ZERO = "-"
SIMBOLOS_AUSENTES = {"..", "...", "X"}

# Limites de plausibilidade para o clima
TEMPERATURA_MIN, TEMPERATURA_MAX = -30.0, 60.0


def _converter_valor_sidra(valor):
    """Converte o texto do SIDRA em número: '-' vira 0; '..', '...' e 'X' viram NaN."""
    if valor is None:
        return float("nan")
    texto = str(valor).strip()
    if texto == SIMBOLO_ZERO:
        return 0.0
    if texto in SIMBOLOS_AUSENTES:
        return float("nan")
    try:
        return float(texto)
    except ValueError:
        return float("nan")


def _exigir_mapeamento(df, coluna, origem, nome):
    """Falha com uma mensagem clara se algum código não estiver no dicionário."""
    desconhecidos = sorted(df.loc[df[coluna].isna(), origem].astype(str).unique())
    if desconhecidos:
        raise ValueError(f"{nome} desconhecido(s) no JSON do IBGE: {desconhecidos}")


def limpar_ibge(dados):
    """Transforma a lista do SIDRA (1º item = cabeçalho) na tabela `producao`."""
    if len(dados) < 2:
        raise ValueError("JSON do IBGE sem registros")

    colunas = {"D1C": "uf_codigo", "D2C": "variavel", "D3C": "ano", "D4C": "produto", "V": "valor"}
    df = pd.DataFrame(dados[1:]).rename(columns=colunas)
    df = df[["uf_codigo", "variavel", "ano", "produto", "valor"]].copy()

    df["valor"] = df["valor"].map(_converter_valor_sidra)
    df["ano"] = pd.to_numeric(df["ano"]).astype(int)
    df["uf"] = pd.to_numeric(df["uf_codigo"]).astype(int).map(UF_POR_CODIGO)
    df["cultura"] = df["produto"].astype(str).map(CULTURA_POR_CODIGO)
    df["coluna"] = df["variavel"].astype(str).map(COLUNA_POR_VARIAVEL)

    _exigir_mapeamento(df, "uf", "uf_codigo", "Código de UF")
    _exigir_mapeamento(df, "cultura", "produto", "Código de produto")
    _exigir_mapeamento(df, "coluna", "variavel", "Código de variável")

    # pivot falha se houver chave duplicada, o que serve como checagem de integridade
    largo = df.pivot(index=["ano", "uf", "cultura"], columns="coluna", values="valor")
    largo = largo.reindex(columns=list(COLUNA_POR_VARIAVEL.values())).reset_index()
    largo.columns.name = None
    producao = largo[COLUNAS_PRODUCAO].sort_values(["ano", "uf", "cultura"])
    return producao.reset_index(drop=True)


def limpar_clima(dados):
    """Transforma o JSON da Open-Meteo (um bloco por UF) na tabela `clima`."""
    partes = []
    for uf, item in dados.items():
        diario = item["dados"]["daily"]
        partes.append(
            pd.DataFrame(
                {
                    "data_leitura": diario["time"],
                    "uf": uf,
                    "temperatura_media": diario["temperature_2m_mean"],
                    "precipitacao_mm": diario["precipitation_sum"],
                }
            )
        )
    clima = pd.concat(partes, ignore_index=True)

    clima["data_leitura"] = pd.to_datetime(clima["data_leitura"], errors="coerce")
    clima["temperatura_media"] = pd.to_numeric(clima["temperatura_media"], errors="coerce")
    clima["precipitacao_mm"] = pd.to_numeric(clima["precipitacao_mm"], errors="coerce")

    clima = clima.dropna(subset=["data_leitura"])
    clima = clima[clima["uf"].isin(UFS_VALIDAS)]
    clima = clima.drop_duplicates(subset=["data_leitura", "uf"])

    # Valores implausíveis viram nulo (o schema aceita NULL nas medidas)
    fora = ~clima["temperatura_media"].between(TEMPERATURA_MIN, TEMPERATURA_MAX)
    clima.loc[fora & clima["temperatura_media"].notna(), "temperatura_media"] = float("nan")
    clima.loc[clima["precipitacao_mm"] < 0, "precipitacao_mm"] = float("nan")

    clima["data_leitura"] = clima["data_leitura"].dt.strftime("%Y-%m-%d")
    return clima.sort_values(["uf", "data_leitura"]).reset_index(drop=True)


def limpar_produtos(df):
    """Padroniza o catálogo de produtos (tipos, espaços, duplicados e nulos)."""
    df = df.copy()
    for coluna in ("nome", "categoria", "cultura_alvo"):
        df[coluna] = df[coluna].str.strip()
    df["id"] = pd.to_numeric(df["id"], errors="coerce")
    df["preco"] = pd.to_numeric(df["preco"], errors="coerce")

    antes = len(df)
    df = df.dropna(subset=["id", "nome", "categoria", "cultura_alvo", "preco"])
    df = df[df["preco"] >= 0].drop_duplicates(subset="id")
    df["id"] = df["id"].astype(int)
    logger.info("produtos: %d linha(s) removida(s) na limpeza", antes - len(df))
    return df.reset_index(drop=True)


def limpar_vendas(df, produtos):
    """Padroniza as vendas e remove linhas que violariam o schema do banco."""
    df = df.copy()
    df["uf"] = df["uf"].str.strip().str.upper()
    df["data_venda"] = pd.to_datetime(df["data_venda"], errors="coerce")
    for coluna in ("id", "produto_id", "quantidade", "valor_total"):
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

    antes = len(df)
    df = df.dropna(subset=["id", "data_venda", "produto_id", "uf", "quantidade", "valor_total"])
    df = df[(df["quantidade"] > 0) & (df["valor_total"] >= 0)]
    df = df[df["produto_id"].isin(produtos["id"]) & df["uf"].isin(UFS_VALIDAS)]
    df = df.drop_duplicates(subset="id")

    df["data_venda"] = df["data_venda"].dt.strftime("%Y-%m-%d")
    for coluna in ("id", "produto_id", "quantidade"):
        df[coluna] = df[coluna].astype(int)
    logger.info("vendas: %d linha(s) removida(s) na limpeza", antes - len(df))
    return df.reset_index(drop=True)


def transformar_tudo(raw_dir=None, processed_dir=None):
    """Lê data/raw/, limpa tudo e grava os CSVs tratados em data/processed/."""
    raw = Path(raw_dir) if raw_dir else RAW_DIR
    saida = Path(processed_dir) if processed_dir else PROCESSED_DIR
    saida.mkdir(parents=True, exist_ok=True)

    ibge = json.loads((raw / "ibge_pam.json").read_text(encoding="utf-8"))
    clima = json.loads((raw / "clima.json").read_text(encoding="utf-8"))
    produtos = limpar_produtos(pd.read_csv(raw / "produtos.csv"))
    vendas = limpar_vendas(pd.read_csv(raw / "vendas.csv"), produtos)

    resultado = {
        "producao": limpar_ibge(ibge),
        "clima": limpar_clima(clima),
        "produtos": produtos,
        "vendas": vendas,
    }
    for nome, tabela in resultado.items():
        tabela.to_csv(saida / f"{nome}.csv", index=False)
        logger.info("%s.csv: %d linhas", nome, len(tabela))
    return resultado


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    transformar_tudo()
