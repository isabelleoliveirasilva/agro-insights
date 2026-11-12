import json

import pytest

from src.etl import extract


def test_montar_url_segue_padrao_sidra():
    url = extract.montar_url(5457, ["214", "215", "216"], "782", ["40124"])
    assert url == (
        "https://apisidra.ibge.gov.br/values/t/5457/n3/all/v/214,215,216/p/last%205/c782/40124"
    )


def test_buscar_json_rejeita_resposta_vazia(monkeypatch):
    class RespostaFalsa:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"NC": "Nível Territorial (Código)"}]  # só o cabeçalho

    monkeypatch.setattr(extract.requests, "get", lambda *a, **k: RespostaFalsa())
    with pytest.raises(ValueError):
        extract.buscar_json("http://exemplo")


def test_salvar_json_cria_pasta_e_grava(tmp_path):
    destino = tmp_path / "raw" / "ibge_pam.json"
    extract.salvar_json([{"cab": 1}, {"V": "10"}], destino)
    assert json.loads(destino.read_text(encoding="utf-8")) == [{"cab": 1}, {"V": "10"}]
