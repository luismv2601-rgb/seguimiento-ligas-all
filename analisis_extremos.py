"""Genera la pestana 'Analisis 2' del Sheet con dos tablas sobre rachas extremas.

Tabla 1: por liga y temporada, cuantas rachas alcanzaron el doble del umbral,
         y que porcentaje representan sobre los empates de esa temporada.
Tabla 2: los largos concretos de esas rachas, por liga y temporada.

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
    filas_t2 = []

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

        fila1 = [lid, info["liga"], info["pais"], umbral, doble]
        fila2 = [lid, info["liga"], info["pais"], doble]
        for t in temporadas:
            sup = sorted(sup_por_temp.get(t, []), reverse=True)
            emp = empates_por_temp.get(t, 0)
            pct = round(100 * len(sup) / emp, 1) if emp else 0
            fila1 += [len(sup), emp, pct]
            fila2.append(", ".join(str(x) for x in sup) if sup else "-")

        total_sup = sum(1 for largo, _ in rachas if largo >= doble)
        fila1 += [total_sup, len(rachas)]
        fila2.append(en_curso[0] if en_curso else 0)

        filas_t1.append(fila1)
        filas_t2.append(fila2)

    enc1 = ["liga_id", "liga", "pais", "umbral", "doble_umbral"]
    for t in temporadas:
        enc1 += [f"{t}_rachas_>=doble", f"{t}_empates", f"{t}_pct_sobre_empates"]
    enc1 += ["total_rachas_>=doble", "total_rachas"]

    enc2 = ["liga_id", "liga", "pais", "doble_umbral"]
    enc2 += [f"{t}_valores_>=doble" for t in temporadas]
    enc2 += ["racha_en_curso"]

    contenido = [
        [f"TABLA 1 - Rachas MAYORES O IGUALES al doble del umbral (actualizado {hora_peru()})"],
        ["Por temporada: cuantas rachas llegaron a >= doble del umbral, y que % representan sobre los empates de esa temporada. El criterio es >=, no exactamente el doble: con doble=12 se cuentan 12, 13, 14..."],
        enc1,
    ]
    contenido += filas_t1
    contenido += [
        [],
        ["TABLA 2 - Largos concretos de las rachas >= doble del umbral, por temporada"],
        ["La ultima columna es la racha que sigue viva hoy (0 si el ultimo partido fue empate)"],
        enc2,
    ]
    contenido += filas_t2

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
