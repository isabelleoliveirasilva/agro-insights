"""API Flask do Agro Insights (somente leitura).

Uso:
    flask --app src.api.app run
"""

import sqlite3
from pathlib import Path

from flask import Flask, current_app, g, jsonify, request
from werkzeug.exceptions import HTTPException

from src.etl.load import resolver_caminho_do_banco

MENSAGENS_HTTP = {
    404: "Rota não encontrada.",
    405: "Método não permitido para esta rota.",
}

# Parâmetro da URL -> coluna da tabela `produtos`
FILTROS_PRODUTOS = {"categoria": "categoria", "cultura": "cultura_alvo"}


class BancoIndisponivel(RuntimeError):
    """O arquivo do banco não existe (o ETL ainda não foi executado)."""


def _casefold(texto):
    """Comparação sem diferença de maiúsculas/minúsculas, inclusive com acentos."""
    return texto.casefold() if isinstance(texto, str) else texto


def get_db():
    """Devolve a conexão da requisição atual, abrindo-a na primeira chamada.

    A conexão é somente leitura: a API nunca altera o banco, e um caminho errado
    não cria um arquivo vazio por acidente (o que o sqlite3 faria por padrão).
    """
    if "db" not in g:
        caminho = Path(current_app.config["DATABASE"])
        if not caminho.exists():
            current_app.logger.error("Banco não encontrado em %s", caminho)
            raise BancoIndisponivel(
                "Banco de dados não encontrado. Rode: python -m src.etl.run_all"
            )
        con = sqlite3.connect(f"{caminho.resolve().as_uri()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        con.create_function("casefold", 1, _casefold, deterministic=True)
        g.db = con
    return g.db


def fechar_db(_erro=None):
    """Fecha a conexão ao final de cada requisição."""
    con = g.pop("db", None)
    if con is not None:
        con.close()


def create_app(database=None):
    """Cria a aplicação. `database` permite apontar para outro arquivo (usado nos testes)."""
    app = Flask(__name__)
    app.config["DATABASE"] = str(database or resolver_caminho_do_banco())
    app.json.ensure_ascii = False  # mantém acentos legíveis ("Café", e não "Caf\u00e9")
    app.json.sort_keys = False  # preserva a ordem das colunas
    app.teardown_appcontext(fechar_db)

    @app.errorhandler(HTTPException)
    def tratar_erro_http(erro):
        return jsonify(erro=MENSAGENS_HTTP.get(erro.code, erro.description)), erro.code

    @app.errorhandler(BancoIndisponivel)
    def tratar_banco_indisponivel(erro):
        return jsonify(erro=str(erro)), 503

    @app.errorhandler(sqlite3.Error)
    def tratar_erro_de_banco(erro):
        app.logger.error("Erro no banco: %s", erro)
        return jsonify(erro="Banco de dados incompleto. Rode: python -m src.etl.run_all"), 503

    @app.get("/health")
    def health():
        get_db().execute("select 1").fetchone()
        return jsonify(status="ok")

    @app.get("/produtos")
    def listar_produtos():
        sql = "select id, nome, categoria, cultura_alvo, preco from produtos"
        condicoes, valores = [], []
        for parametro, coluna in FILTROS_PRODUTOS.items():
            valor = request.args.get(parametro, "").strip()
            if valor:
                condicoes.append(f"casefold({coluna}) = casefold(?)")
                valores.append(valor)
        if condicoes:
            sql += " where " + " and ".join(condicoes)
        sql += " order by id"

        produtos = [dict(linha) for linha in get_db().execute(sql, valores)]
        return jsonify(total=len(produtos), produtos=produtos)

    return app
