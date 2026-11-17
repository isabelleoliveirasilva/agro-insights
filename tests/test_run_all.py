from src.etl import extract, generate_fake, load, run_all, transform


def _registrar_chamadas(monkeypatch):
    chamadas = []

    def passo(nome, retorno=None):
        def _executar(*args, **kwargs):
            chamadas.append(nome)
            return retorno

        return _executar

    monkeypatch.setattr(extract, "extrair_ibge_pam", passo("ibge"))
    monkeypatch.setattr(extract, "extrair_clima", passo("clima"))
    monkeypatch.setattr(generate_fake, "gerar_dados_ficticios", passo("ficticios"))
    monkeypatch.setattr(transform, "transformar_tudo", passo("transformar"))
    monkeypatch.setattr(load, "carregar_banco", passo("carregar", {"vendas": 1}))
    return chamadas


def test_executar_roda_as_etapas_na_ordem(monkeypatch):
    chamadas = _registrar_chamadas(monkeypatch)
    resultado = run_all.executar()
    assert chamadas == ["ibge", "clima", "ficticios", "transformar", "carregar"]
    assert resultado == {"vendas": 1}


def test_executar_pode_pular_a_extracao(monkeypatch):
    chamadas = _registrar_chamadas(monkeypatch)
    run_all.executar(pular_extracao=True)
    assert chamadas == ["transformar", "carregar"]


def test_main_repassa_a_flag_pular_extracao(monkeypatch):
    recebido = {}
    monkeypatch.setattr(run_all, "executar", lambda **kwargs: recebido.update(kwargs))
    run_all.main(["--pular-extracao"])
    assert recebido == {"pular_extracao": True}
