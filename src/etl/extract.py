"""Extração de dados da Produção Agrícola Municipal (PAM) via API SIDRA do IBGE."""

import json
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

SIDRA_BASE_URL = "https://apisidra.ibge.gov.br/values"
TABELA_PAM = 5457
CLASSIFICACAO_PRODUTO = "782"

# Códigos das variáveis da tabela 5457.
VARIAVEIS = ["214", "215", "216"]  # quantidade produzida, valor da produção, área colhida

# Produtos (código -> nome).
PRODUTOS = {
    "40124": "Soja (em grão)",
    "40122": "Milho (em grão)",
    "40106": "Cana-de-açucar",
    "40139": "Café (em grão) Total",
    "40127": "Trigo (em grão)",
    "40130": "Algodão arbóreo (em caroço)",
}


def montar_url(tabela, variaveis, classificacao, produtos, periodo="last 5", nivel="n3"):
    """Monta a URL da API SIDRA. `nivel` n3 = unidades da federação (estados)."""
    return (
        f"{SIDRA_BASE_URL}/t/{tabela}/{nivel}/all"
        f"/v/{','.join(variaveis)}"
        f"/p/{periodo.replace(' ', '%20')}"
        f"/c{classificacao}/{','.join(produtos)}"
    )


def buscar_json(url, timeout=30):
    """Faz a requisição e devolve a lista de registros (a 1ª linha é o cabeçalho)."""
    logger.info("GET %s", url)
    resposta = requests.get(url, timeout=timeout)
    resposta.raise_for_status()
    dados = resposta.json()
    if not isinstance(dados, list) or len(dados) < 2:
        raise ValueError("Resposta vazia ou inesperada da API SIDRA")
    return dados


def salvar_json(dados, caminho):
    """Salva os dados brutos em JSON, criando a pasta se necessário."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Salvo em %s (%d registros)", caminho, len(dados) - 1)
    return caminho


def extrair_ibge_pam(produtos=None, periodo="last 5", destino=None):
    """Extrai a PAM por estado e salva em data/raw/ibge_pam.json."""
    produtos = produtos or list(PRODUTOS)
    destino = destino or RAW_DIR / "ibge_pam.json"
    url = montar_url(TABELA_PAM, VARIAVEIS, CLASSIFICACAO_PRODUTO, produtos, periodo)
    dados = buscar_json(url)
    return salvar_json(dados, destino)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    extrair_ibge_pam()
