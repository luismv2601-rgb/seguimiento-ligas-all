"""Busca ligas en API-Football por pais y muestra su ID, para verificarlo antes
de agregarlo a ligas.json. Un ID equivocado no da error: simplemente no trae partidos.

Uso:  python buscar_ligas.py Belarus Armenia Latvia
"""
import os
import sys
import time

import requests

API_KEY = os.environ.get("FOOTBALL_API_KEY")
API_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}


def buscar(pais):
    resp = requests.get(f"{API_BASE}/leagues", headers=HEADERS, params={"country": pais})
    data = resp.json()
    if data.get("errors"):
        print(f"  ERROR: {data['errors']}")
        return
    if not data.get("response"):
        print("  Sin resultados. Ojo: el nombre del pais va en ingles (ej. 'Belarus', no 'Bielorrusia').")
        return

    for item in data["response"]:
        liga = item["league"]
        temporadas = item["seasons"]
        actual = next((t["year"] for t in temporadas if t["current"]), None)
        anios = sorted(t["year"] for t in temporadas)
        cobertura = "SI" if {2024, 2025} <= set(anios) else "NO"
        print(f"  id={liga['id']:<5} tipo={liga['type']:<7} {liga['name']}")
        print(f"        temporada actual: {actual or '-'} | rango: {anios[0]}-{anios[-1]} | tiene 2024+2025: {cobertura}")


def main():
    paises = sys.argv[1:]
    if not paises:
        print("Pasar al menos un pais. Ej: python buscar_ligas.py Belarus Armenia Latvia")
        sys.exit(1)

    for pais in paises:
        print(f"\n===== {pais} =====")
        buscar(pais)
        time.sleep(1)


if __name__ == "__main__":
    main()
