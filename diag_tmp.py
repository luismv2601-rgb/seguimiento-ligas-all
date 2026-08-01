"""Diagnostico temporal: reproduce exactamente lo que hace actualizar.py
para unas ligas puntuales, y lo compara contra lo que hay en el Sheet."""
import os
import json
import time

import requests
import gspread
from google.oauth2.service_account import Credentials

API_KEY = os.environ.get("FOOTBALL_API_KEY")
API_BASE = "https://v3.football.api-sports.io"
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
HEADERS = {"x-apisports-key": API_KEY}
SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

creds = Credentials.from_service_account_info(json.loads(os.environ["GOOGLE_CREDENTIALS_JSON"]), scopes=SCOPES)
sheet = gspread.authorize(creds).open_by_key(SHEET_ID)
ws = sheet.worksheet("Partidos")

ids_sheet = set(ws.col_values(1)[1:])
print(f"fixture_id en el Sheet: {len(ids_sheet)}")
print()

for lid in ("103", "113", "218"):
    r = requests.get(f"{API_BASE}/leagues", headers=HEADERS, params={"id": lid}).json()
    temporadas = r["response"][0]["seasons"]
    marcadas = [t["year"] for t in temporadas if t["current"]]
    elegida = next((t["year"] for t in temporadas if t["current"]), None) or max(t["year"] for t in temporadas)
    print(f"--- liga {lid} ({r['response'][0]['league']['name']}) ---")
    print(f"  temporadas con current=True: {marcadas}")
    print(f"  actualizar.py elegiria: {elegida}")
    time.sleep(1)

    for temp in (elegida, 2026):
        fx = requests.get(f"{API_BASE}/fixtures", headers=HEADERS,
                          params={"league": lid, "season": temp, "status": "FT"}).json()
        resp = fx.get("response", [])
        errs = fx.get("errors")
        ids = {str(f["fixture"]["id"]) for f in resp}
        nuevos = ids - ids_sheet
        print(f"  season={temp}: {len(resp)} FT devueltos | errors={errs} | ya en Sheet={len(ids & ids_sheet)} | NUEVOS={len(nuevos)}")
        time.sleep(1)
    print()
