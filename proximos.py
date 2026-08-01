"""Genera la pestana 'Proximos' del Sheet con los partidos que faltan jugarse.

Va aparte de 'Partidos' a proposito. 'Partidos' guarda solo lo jugado y es la
fuente del calculo de rachas: un partido sin resultado trae goles en None y
None == None da True, o sea que se leeria como empate y cortaria todas las
rachas. Ademas actualizar.py deduplica por fixture_id, asi que si el partido ya
estuviera cargado nunca se le escribiria el resultado al jugarse.

Esta pestana se reescribe entera en cada corrida, asi que no necesita
deduplicar ni actualizar filas.

Solo toma partidos con estado NS (hora confirmada). Los TBD, que todavia no
tienen horario definido, quedan afuera.
"""
import os
import json
import time
from datetime import datetime, timedelta, timezone

import requests
import gspread
from google.oauth2.service_account import Credentials

API_KEY = os.environ.get("FOOTBALL_API_KEY")
API_BASE = "https://v3.football.api-sports.io"
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
HEADERS = {"x-apisports-key": API_KEY}
PESTANA = "Proximos"

# Cuantos dias hacia adelante mirar. Dos semanas cubre un par de fechas en
# cualquier liga sin inflar la pestana.
DIAS_ADELANTE = int(os.environ.get("DIAS_ADELANTE", "14"))

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

with open("ligas.json", encoding="utf-8") as f:
    LIGAS = [liga for liga in json.load(f) if liga.get("activa", True)]

ENCABEZADOS = [
    "fixture_id", "liga_id", "liga", "pais", "temporada",
    "fecha", "hora_peru", "equipo_local", "equipo_visitante",
    "ronda", "dias_para",
]


def ahora_peru():
    return datetime.now(timezone.utc) - timedelta(hours=5)


def conectar_google():
    creds_json_env = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json_env:
        creds = Credentials.from_service_account_info(json.loads(creds_json_env), scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(SHEET_ID)


def obtener_temporada_actual(liga_id):
    resp = requests.get(f"{API_BASE}/leagues", headers=HEADERS, params={"id": liga_id})
    data = resp.json()
    if not data.get("response"):
        return None
    temporadas = data["response"][0]["seasons"]
    actual = next((t["year"] for t in temporadas if t["current"]), None)
    return actual or max(t["year"] for t in temporadas)


def obtener_programados(liga_id, temporada):
    params = {"league": liga_id, "season": temporada, "status": "NS"}
    resp = requests.get(f"{API_BASE}/fixtures", headers=HEADERS, params=params)
    data = resp.json()
    if data.get("errors"):
        print(f"  Aviso: liga {liga_id} temporada {temporada}: {data['errors']}")
        return []
    return data.get("response", [])


def main():
    sheet = conectar_google()
    hoy = ahora_peru()
    limite = hoy + timedelta(days=DIAS_ADELANTE)

    filas = []
    for liga in LIGAS:
        try:
            print(f"Revisando {liga['nombre']} ({liga['pais']}) [id {liga['id']}]...")
            temporada = obtener_temporada_actual(liga["id"])
            time.sleep(1)
            if temporada is None:
                print("  Sin temporada actual, se omite.")
                continue

            fixtures = obtener_programados(liga["id"], temporada)
            time.sleep(1)

            proximos = []
            for fx in fixtures:
                cuando = datetime.fromtimestamp(fx["fixture"]["timestamp"], tz=timezone.utc) - timedelta(hours=5)
                if not (hoy <= cuando <= limite):
                    continue
                proximos.append((cuando, fx))

            proximos.sort(key=lambda par: par[0])
            for cuando, fx in proximos:
                filas.append([
                    str(fx["fixture"]["id"]),
                    liga["id"], liga["nombre"], liga["pais"], temporada,
                    cuando.strftime("%Y-%m-%d"), cuando.strftime("%H:%M"),
                    fx["teams"]["home"]["name"], fx["teams"]["away"]["name"],
                    fx["league"].get("round", ""),
                    (cuando.date() - hoy.date()).days,
                ])
            print(f"  {len(proximos)} programados en los proximos {DIAS_ADELANTE} dias.")

        except Exception as e:
            print(f"  ERROR procesando {liga['nombre']} ({liga['pais']}): {e}")

    filas.sort(key=lambda f: (f[5], f[6]))

    contenido = [
        [f"Partidos programados con hora confirmada · proximos {DIAS_ADELANTE} dias · actualizado {hoy.strftime('%Y-%m-%d %H:%M')} (hora Peru)"],
        ENCABEZADOS,
    ] + filas

    try:
        ws = sheet.worksheet(PESTANA)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=PESTANA, rows=max(len(contenido) + 50, 200), cols=len(ENCABEZADOS) + 2)
        print(f"Pestana '{PESTANA}' creada.")

    ws.update(values=contenido, range_name="A1")

    print("\n===== RESUMEN =====")
    print(f"Ligas revisadas: {len(LIGAS)}")
    print(f"Partidos programados cargados: {len(filas)}")
    if filas:
        print(f"Rango: {filas[0][5]} a {filas[-1][5]}")


if __name__ == "__main__":
    main()
