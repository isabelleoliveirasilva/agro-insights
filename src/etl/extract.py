"""Extração de dados brutos: PAM (IBGE/SIDRA) e clima (Open-Meteo)."""

import json
import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"

# ---------------------------------------------------------------------------
# IBGE / SIDRA
# ---------------------------------------------------------------------------
SIDRA_BASE_URL = "https://apisidra.ibge.gov.br/values"
TABELA_PAM = 5457
CLASSIFICACAO_PRODUTO = "782"

# Códigos das variáveis da tabela 5457 (confirmados com explorar_sidra.py).
VARIAVEIS = ["214", "215", "216"]  # quantidade produzida, valor da produção, área colhida

# Produtos (código -> nome).
PRODUTOS = {
    "40124": "Soja (em grão)",
    "40122": "Milho (em grão)",
    "40106": "Cana-de-açúcar",
    "40139": "Café (em grão) Total",
    "40127": "Trigo (em grão)",
    "40130": "Algodão arbóreo (em caroço)",
}

# ---------------------------------------------------------------------------
# Open-Meteo (histórico)
# ---------------------------------------------------------------------------
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"
VARIAVEIS_CLIMA = ["temperature_2m_mean", "precipitation_sum"]
FUSO_HORARIO = "America/Sao_Paulo"  # obrigatório quando se pedem variáveis diárias
PERIODO_CLIMA = ("2021-01-01", "2025-12-31")  # alinhado aos anos da PAM extraída

# UF -> (cidade de referência, latitude, longitude)
CIDADES = {
    "MT": ("Cuiabá", -15.60, -56.10),
    "GO": ("Goiânia", -16.68, -49.25),
    "PR": ("Londrina", -23.31, -51.16),
    "RS": ("Passo Fundo", -28.26, -52.41),
    "SP": ("Ribeirão Preto", -21.18, -47.81),
    "MS": ("Campo Grande", -20.47, -54.62),
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
    logger.info("Salvo em %s", caminho)
    return caminho


def extrair_ibge_pam(produtos=None, periodo="last 5", destino=None):
    """Extrai a PAM por estado e salva em data/raw/ibge_pam.json."""
    produtos = produtos or list(PRODUTOS)
    destino = destino or RAW_DIR / "ibge_pam.json"
    url = montar_url(TABELA_PAM, VARIAVEIS, CLASSIFICACAO_PRODUTO, produtos, periodo)
    dados = buscar_json(url)
    return salvar_json(dados, destino)


def montar_params_clima(latitude, longitude, inicio, fim):
    """Monta os parâmetros da requisição à Open-Meteo (dados diários)."""
    return {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": inicio,
        "end_date": fim,
        "daily": ",".join(VARIAVEIS_CLIMA),
        "timezone": FUSO_HORARIO,
    }


def buscar_clima(latitude, longitude, inicio, fim, timeout=30):
    """Busca o clima diário de uma coordenada e devolve o JSON da resposta."""
    params = montar_params_clima(latitude, longitude, inicio, fim)
    logger.info("GET %s %s", OPEN_METEO_URL, params)
    resposta = requests.get(OPEN_METEO_URL, params=params, timeout=timeout)
    resposta.raise_for_status()
    dados = resposta.json()
    if "daily" not in dados:
        raise ValueError("Resposta da Open-Meteo sem o bloco 'daily'")
    return dados


def extrair_clima(cidades=None, periodo=PERIODO_CLIMA, destino=None):
    """Extrai o clima de uma cidade de referência por UF e salva em data/raw/clima.json."""
    cidades = cidades or CIDADES
    destino = destino or RAW_DIR / "clima.json"
    inicio, fim = periodo
    resultado = {}
    for uf, (cidade, latitude, longitude) in cidades.items():
        resultado[uf] = {
            "cidade": cidade,
            "dados": buscar_clima(latitude, longitude, inicio, fim),
        }
    return salvar_json(resultado, destino)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    extrair_ibge_pam()
    extrair_clima()
