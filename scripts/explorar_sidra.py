"""Script de exploração (descartável): lista variáveis e produtos da tabela 5457.

Uso:  python explorar_sidra.py
"""

import requests

URL = "https://servicodados.ibge.gov.br/api/v3/agregados/5457/metadados"
TERMOS = ("soja", "milho", "cana", "café", "trigo", "algod")

meta = requests.get(URL, timeout=30)
meta.raise_for_status()
meta = meta.json()

print("=== VARIÁVEIS ===")
for v in meta.get("variaveis", []):
    print(v["id"], "-", v["nome"], f"({v.get('unidade', '')})")

print("\n=== CLASSIFICAÇÕES (produtos filtrados) ===")
for c in meta.get("classificacoes", []):
    print(f"\nclassificação c{c['id']}: {c['nome']}")
    for cat in c.get("categorias", []):
        if any(t in cat["nome"].lower() for t in TERMOS):
            print("  ", cat["id"], "-", cat["nome"])
