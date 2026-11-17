"""Executa o pipeline completo: extração, transformação e carga.

Uso:
    python -m src.etl.run_all                    # tudo, inclusive as chamadas às APIs
    python -m src.etl.run_all --pular-extracao   # reaproveita o que já está em data/raw/
"""

import argparse
import logging

from dotenv import load_dotenv

from src.etl import extract, generate_fake, load, transform

logger = logging.getLogger(__name__)


def executar(pular_extracao=False):
    """Roda as três etapas em ordem e devolve a contagem de linhas por tabela."""
    if pular_extracao:
        logger.info("1/3 Extração pulada: usando os arquivos existentes em data/raw/")
    else:
        logger.info("1/3 Extração")
        extract.extrair_ibge_pam()
        extract.extrair_clima()
        generate_fake.gerar_dados_ficticios()

    logger.info("2/3 Transformação")
    transform.transformar_tudo()

    logger.info("3/3 Carga")
    contagens = load.carregar_banco()

    logger.info("Pipeline concluído: %s", contagens)
    return contagens


def main(argv=None):
    parser = argparse.ArgumentParser(description="Pipeline ETL do Agro Insights.")
    parser.add_argument(
        "--pular-extracao",
        action="store_true",
        help="não chama as APIs nem gera dados fictícios; usa os arquivos de data/raw/",
    )
    args = parser.parse_args(argv)

    load_dotenv(load.ROOT / ".env")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    executar(pular_extracao=args.pular_extracao)


if __name__ == "__main__":
    main()
