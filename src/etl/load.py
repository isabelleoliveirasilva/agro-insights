"""Carga dos dados tratados no banco SQLite."""

import logging
import os
import sqlite3
from pathlib import Path

import pandas as pd
from pandas.errors import DatabaseError

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = ROOT / "data" / "processed"
SCHEMA_PATH = ROOT / "sql" / "schema.sql"
DB_PADRAO = "data/processed/agro.db"

# A ordem importa: tabelas "pai" vêm antes das que apontam para elas (chaves estrangeiras).
# A tabela `estados` não está aqui porque o próprio schema.sql já a popula.
ORDEM_DE_CARGA = ["produtos", "vendas", "producao", "clima"]
TABELAS = ["estados", *ORDEM_DE_CARGA]


class ErroDeCarga(RuntimeError):
    """Falha ao carregar os dados no banco (a mensagem indica a tabela)."""


def resolver_caminho_do_banco(db_path=None):
    """Argumento > variável DATABASE_PATH (.env) > padrão. Caminho relativo parte da raiz."""
    caminho = Path(db_path or os.getenv("DATABASE_PATH") or DB_PADRAO)
    return caminho if caminho.is_absolute() else ROOT / caminho


def conectar(db_path):
    """Abre a conexão com a validação de chaves estrangeiras ligada (o SQLite não a liga)."""
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def criar_banco(con, schema_path=None):
    """Cria as tabelas, índices e os dados de referência a partir do schema.sql."""
    schema = Path(schema_path or SCHEMA_PATH).read_text(encoding="utf-8")
    con.executescript(schema)


def carregar_tabelas(con, tabelas):
    """Insere os DataFrames na ordem certa e confere a integridade referencial."""
    for nome in ORDEM_DE_CARGA:
        try:
            tabelas[nome].to_sql(nome, con, if_exists="append", index=False)
        except (sqlite3.Error, DatabaseError) as erro:
            # Conforme a versão do pandas, o erro chega de uma ou de outra classe.
            raise ErroDeCarga(f"Falha ao carregar a tabela '{nome}': {erro}") from erro
        logger.info("%s: %d linhas carregadas", nome, len(tabelas[nome]))

    violacoes = con.execute("PRAGMA foreign_key_check").fetchall()
    if violacoes:
        raise ErroDeCarga(f"{len(violacoes)} violação(ões) de chave estrangeira após a carga")


def contar_linhas(con):
    """Devolve {tabela: nº de linhas} para conferência."""
    return {nome: con.execute(f"select count(*) from {nome}").fetchone()[0] for nome in TABELAS}


def carregar_banco(processed_dir=None, db_path=None, schema_path=None):
    """Recria o banco do zero a partir dos CSVs tratados (carga idempotente).

    O banco novo é montado num arquivo temporário e só substitui o anterior se tudo der
    certo. Assim, uma carga com erro nunca destrói um banco que estava funcionando.
    """
    pasta = Path(processed_dir) if processed_dir else PROCESSED_DIR
    destino = resolver_caminho_do_banco(db_path)
    destino.parent.mkdir(parents=True, exist_ok=True)

    tabelas = {nome: pd.read_csv(pasta / f"{nome}.csv") for nome in ORDEM_DE_CARGA}

    temporario = destino.with_name(destino.name + ".tmp")
    temporario.unlink(missing_ok=True)
    con = conectar(temporario)
    try:
        criar_banco(con, schema_path)
        carregar_tabelas(con, tabelas)
        contagens = contar_linhas(con)
    except Exception:
        con.close()
        temporario.unlink(missing_ok=True)
        raise
    con.close()
    temporario.replace(destino)

    logger.info("Banco pronto em %s", destino)
    return contagens


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print(carregar_banco())
