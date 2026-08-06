"""Reconstruye la pestana 'Ranking_Empates' entera a partir de 'Partidos'.

Hace falta porque la condicion de carrera entre corridas solapadas de
actualizar.py no solo duplicaba partidos: tambien escribia los contadores en la
fila equivocada. actualizar.py lee el numero de fila de cada equipo al arrancar y
al final reordena la pestana por pct_empates; con dos corridas encimadas, la
segunda escribia sobre numeros de fila que la primera ya habia movido. Quedaron
38 filas con datos de otro equipo y 2 filas repetidas.

'Partidos' es la fuente de verdad: el ranking es una suma sobre esa pestana, asi
que se puede recalcular exacto. El script es idempotente — correrlo dos veces
deja lo mismo.

Por defecto **no escribe nada**: hay que pasar CONFIRMAR=si.

No usa clear() antes de escribir: sobrescribe desde A1 y despues borra la cola
sobrante. Asi la pestana nunca queda vacia si algo falla en el medio.
"""
import os
import json

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
CONFIRMAR = os.environ.get("CONFIRMAR", "").strip().lower() in ("si", "sí", "yes", "true")

ENCABEZADOS = ["equipo", "liga_id", "liga", "pais", "total_partidos", "total_empates", "pct_empates"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def conectar():
    creds_json_env = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json_env:
        creds = Credentials.from_service_account_info(json.loads(creds_json_env), scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(SHEET_ID)


def main():
    sheet = conectar()
    ws_partidos = sheet.worksheet("Partidos")
    ws_ranking = sheet.worksheet("Ranking_Empates")

    valores = ws_partidos.get_all_values()
    cab = valores[0]
    ix = {c: cab.index(c) for c in
          ("liga_id", "liga", "pais", "equipo_local", "equipo_visitante", "es_empate")}

    equipos = {}
    leidas = 0
    for fila in valores[1:]:
        if not any(str(c).strip() for c in fila):
            continue
        leidas += 1
        liga_id = str(fila[ix["liga_id"]]).strip()
        for equipo in (fila[ix["equipo_local"]], fila[ix["equipo_visitante"]]):
            equipo = str(equipo).strip()
            if not equipo:
                continue
            e = equipos.setdefault((liga_id, equipo), {
                "liga": fila[ix["liga"]], "pais": fila[ix["pais"]], "total": 0, "empates": 0})
            e["total"] += 1
            if fila[ix["es_empate"]] == "SI":
                e["empates"] += 1

    filas = []
    for (liga_id, equipo), e in equipos.items():
        pct = round(100 * e["empates"] / e["total"], 1) if e["total"] else 0
        filas.append([equipo, int(liga_id), e["liga"], e["pais"], e["total"], e["empates"], pct])

    # Mismo criterio que ORDEN_PESTANAS en actualizar.py: pct_empates de mayor a menor.
    filas.sort(key=lambda f: (-f[6], f[2], f[0]))

    previas = ws_ranking.get_all_values()
    sobrantes = len(previas) - (len(filas) + 1)
    print(f"Partidos leidos: {leidas}")
    print(f"Ranking_Empates: {len(previas) - 1} filas ahora -> {len(filas)} reconstruidas "
          f"({sobrantes:+d})")

    if not CONFIRMAR:
        print("\nENSAYO: no se escribio nada. Pasar CONFIRMAR=si para aplicar.")
        print("Primeras 5 filas que quedarian:")
        for f in filas[:5]:
            print("   ", f)
        return

    ws_ranking.update(values=[ENCABEZADOS] + filas, range_name="A1")
    if sobrantes > 0:
        ws_ranking.delete_rows(len(filas) + 2, len(previas))
        print(f"Borradas {sobrantes} filas de cola que sobraban.")

    quedaron = ws_ranking.get_all_values()
    print(f"Verificacion: {len(quedaron) - 1} filas escritas.")


if __name__ == "__main__":
    main()
