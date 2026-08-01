"""Muestra el estado de la temporada actual de una o varias ligas de API-Football.

Sirve para decidir cuando conviene sumar una liga: si ya arranco, cuantas fechas
lleva, y si no arranco, cuando esta programado el primer partido.

Uso:  python estado_ligas.py 39 140 135 78 61
"""
import os
import sys
import time
from datetime import datetime, timezone

import requests

API_KEY = os.environ.get("FOOTBALL_API_KEY")
API_BASE = "https://v3.football.api-sports.io"
HEADERS = {"x-apisports-key": API_KEY}

TERMINADOS = {"FT", "AET", "PEN"}


def get(path, params):
    resp = requests.get(f"{API_BASE}/{path}", headers=HEADERS, params=params)
    data = resp.json()
    if data.get("errors"):
        print(f"  ERROR: {data['errors']}")
        return None
    return data.get("response", [])


def estado(liga_id):
    ligas = get("leagues", {"id": liga_id})
    if not ligas:
        print(f"  id={liga_id}: no existe o sin datos.")
        return
    liga = ligas[0]["league"]
    pais = ligas[0]["country"]["name"]
    temporadas = ligas[0]["seasons"]
    actual = next((t for t in temporadas if t["current"]), None) or max(temporadas, key=lambda t: t["year"])
    anio = actual["year"]

    time.sleep(1)
    fixtures = get("fixtures", {"league": liga_id, "season": anio})
    if fixtures is None:
        return

    if not fixtures:
        print(f"  id={liga_id:<5} {pais:<15} {liga['name']:<22} temp={anio}  SIN FIXTURES PUBLICADOS")
        return

    ahora = datetime.now(timezone.utc)
    jugados = [f for f in fixtures if f["fixture"]["status"]["short"] in TERMINADOS]
    pendientes = sorted(
        [f for f in fixtures if f["fixture"]["status"]["short"] == "NS"],
        key=lambda f: f["fixture"]["timestamp"],
    )

    def fecha(fx):
        return datetime.fromtimestamp(fx["fixture"]["timestamp"], tz=timezone.utc).strftime("%Y-%m-%d")

    inicio_oficial = actual.get("start", "?")
    if jugados:
        ultimo = max(jugados, key=lambda f: f["fixture"]["timestamp"])
        marca = "EN CURSO"
        detalle = f"{len(jugados)} jugados, ultimo {fecha(ultimo)}"
    else:
        marca = "NO INICIADA"
        if pendientes:
            prox = pendientes[0]
            dias = (datetime.fromtimestamp(prox["fixture"]["timestamp"], tz=timezone.utc) - ahora).days
            detalle = f"arranca {fecha(prox)} (en {dias} dias)"
        else:
            detalle = "sin partidos programados"

    prox_txt = ""
    if pendientes:
        prox_txt = f" | proximo {fecha(pendientes[0])}"

    print(f"  id={liga_id:<5} {pais:<15} {liga['name']:<22} temp={anio} [{marca}] "
          f"{detalle} | {len(pendientes)} programados{prox_txt} | inicio oficial {inicio_oficial}")


def main():
    ids = sys.argv[1:]
    if not ids:
        print("Pasar al menos un liga_id. Ej: python estado_ligas.py 39 140 135")
        sys.exit(1)
    print(f"Consultando {len(ids)} ligas...\n")
    for lid in ids:
        estado(lid)
        time.sleep(1)


if __name__ == "__main__":
    main()
