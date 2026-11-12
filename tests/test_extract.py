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


def test_montar_params_clima_pede_variaveis_diarias_e_fuso():
    params = extract.montar_params_clima(-15.6, -56.1, "2021-01-01", "2021-12-31")
    assert params["daily"] == "temperature_2m_mean,precipitation_sum"
    assert params["timezone"] == "America/Sao_Paulo"
    assert params["start_date"] == "2021-01-01"
    assert params["end_date"] == "2021-12-31"


def test_buscar_clima_rejeita_resposta_sem_daily(monkeypatch):
    class RespostaFalsa:
        def raise_for_status(self):
            pass

        def json(self):
            return {"error": True, "reason": "parâmetro inválido"}

    monkeypatch.setattr(extract.requests, "get", lambda *a, **k: RespostaFalsa())
    with pytest.raises(ValueError):
        extract.buscar_clima(-15.6, -56.1, "2021-01-01", "2021-12-31")


def test_extrair_clima_salva_uma_entrada_por_uf(monkeypatch, tmp_path):
    monkeypatch.setattr(extract, "buscar_clima", lambda *a, **k: {"daily": {"time": []}})
    cidades = {"MT": ("Cuiabá", -15.6, -56.1), "PR": ("Londrina", -23.3, -51.2)}
    destino = tmp_path / "clima.json"

    extract.extrair_clima(cidades=cidades, destino=destino)

    salvo = json.loads(destino.read_text(encoding="utf-8"))
    assert set(salvo) == {"MT", "PR"}
    assert salvo["MT"]["cidade"] == "Cuiabá"
    assert "daily" in salvo["MT"]["dados"]
