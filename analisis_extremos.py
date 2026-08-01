"""Genera la pestana 'Analisis 2' del Sheet: una tabla de rachas extremas.

Una fila por liga y una columna por temporada. Cada celda de temporada se lee:
    rachas >= doble del umbral / total de empates de la temporada (%) -> largos concretos
Ejemplo: "2 de 66 (3%) -> 13, 12".

El criterio es >=, no exactamente el doble: con doble=12 se cuentan 12, 13, 14...

Lee de las pestanas Partidos y Analisis; no las modifica. Reescribe 'Analisis 2'
entera en cada corrida (es un reporte derivado, no una fuente de datos).

El umbral sale de la pestana Analisis, o sea del baseline 2024-2025 ya calculado.
"""
import os
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
PESTANA = "Analisis 2"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def hora_peru():
    return (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")


def conectar_google():
    creds_json_env = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json_env:
        creds = Credentials.from_service_account_info(json.loads(creds_json_env), scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(SHEET_ID)


def entero(valor, defecto=0):
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return defecto


def calcular_rachas(partidos):
    """Rachas cerradas por un empate, como (largo, temporada del ultimo partido).

    La racha es continua: no se reinicia al cambiar de temporada, igual que en
    cargar_historico.py y actualizar.py. Se le atribuye la temporada del partido
    que la cerro.
    """
    rachas = []
    largo = 0
    temporada = None
    for p in partidos:
        if p["es_empate"] == "SI":
            if largo > 0:
                rachas.append((largo, temporada))
            largo = 0
            temporada = None
        else:
            largo += 1
            temporada = p["temporada"]
    en_curso = (largo, temporada) if largo > 0 else None
    return rachas, en_curso


def main():
    sheet = conectar_google()
    partidos = sheet.worksheet("Partidos").get_all_records()
    analisis = sheet.worksheet("Analisis").get_all_records()

    umbrales = {}
    for fila in analisis:
        lid = str(fila.get("liga_id", "")).strip()
        if lid:
            umbrales[lid] = {
                "liga": fila.get("liga", ""),
                "pais": fila.get("pais", ""),
                "umbral": entero(fila.get("umbral_alerta")),
            }

    por_liga = defaultdict(list)
    for p in partidos:
        por_liga[str(p.get("liga_id", "")).strip()].append(p)

    temporadas = sorted({str(p.get("temporada", "")).strip() for p in partidos if str(p.get("temporada", "")).strip()})

    filas_t1 = []

    for lid in sorted(por_liga, key=lambda x: umbrales.get(x, {}).get("liga", "")):
        info = umbrales.get(lid)
        if not info:
            print(f"Aviso: liga_id {lid} esta en Partidos pero no en Analisis, se omite.")
            continue

        ps = sorted(por_liga[lid], key=lambda r: (str(r.get("fecha", "")), str(r.get("hora_peru", ""))))
        umbral = info["umbral"]
        doble = 2 * umbral

        empates_por_temp = defaultdict(int)
        for p in ps:
            if p["es_empate"] == "SI":
                empates_por_temp[str(p["temporada"]).strip()] += 1

        rachas, en_curso = calcular_rachas(ps)
        sup_por_temp = defaultdict(list)
        for largo, temp in rachas:
            if largo >= doble:
                sup_por_temp[str(temp).strip()].append(largo)

        fila = [lid, info["liga"], info["pais"], umbral, doble]
        for t in temporadas:
            sup = sorted(sup_por_temp.get(t, []), reverse=True)
            emp = empates_por_temp.get(t, 0)
            pct = round(100 * len(sup) / emp, 1) if emp else 0
            texto = f"{len(sup)} de {emp} ({pct}%)".replace(".", ",")
            if sup:
                texto += " -> " + ", ".join(str(x) for x in sup)
            fila.append(texto)

        total_sup = sum(1 for largo, _ in rachas if largo >= doble)
        fila += [en_curso[0] if en_curso else 0, total_sup, len(rachas)]
        filas_t1.append(fila)

    enc1 = ["liga_id", "liga", "pais", "umbral", "doble_umbral"]
    enc1 += list(temporadas)
    enc1 += ["racha_en_curso", "total_>=doble", "total_rachas"]

    contenido = [
        [f"Rachas MAYORES O IGUALES al doble del umbral (actualizado {hora_peru()})"],
        ["Cada celda de temporada se lee: rachas >= doble / total de empates de esa temporada (porcentaje) -> los largos concretos."],
        enc1,
    ]
    contenido += filas_t1

    try:
        ws = sheet.worksheet(PESTANA)
        ws.clear()
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=PESTANA, rows=max(len(contenido) + 10, 50), cols=max(len(enc1) + 2, 20))
        print(f"Pestana '{PESTANA}' creada.")

    ws.update(values=contenido, range_name="A1")

    print(f"\n{PESTANA} actualizada: {len(filas_t1)} ligas, temporadas {', '.join(temporadas)}")
    for f in filas_t1:
        print(f"  {f[1]} ({f[2]}) umbral={f[3]} doble={f[4]} -> {f[-2]} rachas de {f[-1]}")


if __name__ == "__main__":
    main()
