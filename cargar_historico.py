import os
import json
import time
import statistics
from datetime import datetime, timedelta, timezone

import requests
import gspread
from google.oauth2.service_account import Credentials

API_KEY = os.environ.get("FOOTBALL_API_KEY")
API_BASE = "https://v3.football.api-sports.io"
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
TEMPORADAS = [2024, 2025]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

with open("ligas.json", encoding="utf-8") as f:
    LIGAS = json.load(f)


def hora_peru():
    return (datetime.now(timezone.utc) - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M")


def conectar_google():
    creds_json_env = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if creds_json_env:
        creds_dict = json.loads(creds_json_env)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(SHEET_ID)


def asegurar_encabezados(ws, encabezados):
    primera_fila = ws.row_values(1)
    if primera_fila != encabezados:
        ws.clear()
        ws.append_row(encabezados)


def append_en_lotes(ws, filas, tamano=1000):
    for i in range(0, len(filas), tamano):
        ws.append_rows(filas[i:i + tamano])


def obtener_fixtures(liga_id, temporada):
    headers = {"x-apisports-key": API_KEY}
    params = {"league": liga_id, "season": temporada, "status": "FT"}
    resp = requests.get(f"{API_BASE}/fixtures", headers=headers, params=params)
    data = resp.json()
    if data.get("errors"):
        print(f"  Aviso: liga {liga_id} temporada {temporada}: {data['errors']}")
        return []
    return data.get("response", [])


def modalidad_por_ronda(fixtures):
    """'paralelo' si dos o mas partidos de la misma ronda comparten horario de inicio, si no 'secuencial'."""
    por_ronda = {}
    for fx in fixtures:
        ronda = fx["league"]["round"]
        por_ronda.setdefault(ronda, []).append(fx)

    modalidad = {}
    for partidos in por_ronda.values():
        horarios = [p["fixture"]["timestamp"] for p in partidos]
        etiqueta = "paralelo" if len(horarios) != len(set(horarios)) else "secuencial"
        for p in partidos:
            modalidad[p["fixture"]["id"]] = etiqueta
    return modalidad


def construir_filas(fixtures, liga_nombre, liga_pais, temporada):
    modalidad = modalidad_por_ronda(fixtures)
    filas = []
    for fx in fixtures:
        fecha_peru = datetime.fromtimestamp(fx["fixture"]["timestamp"], tz=timezone.utc) - timedelta(hours=5)
        goles_local = fx["goals"]["home"]
        goles_visitante = fx["goals"]["away"]
        es_empate = goles_local == goles_visitante
        filas.append({
            "fixture_id": fx["fixture"]["id"],
            "liga": liga_nombre,
            "pais": liga_pais,
            "temporada": temporada,
            "fecha": fecha_peru.strftime("%Y-%m-%d"),
            "hora_peru": fecha_peru.strftime("%H:%M"),
            "equipo_local": fx["teams"]["home"]["name"],
            "equipo_visitante": fx["teams"]["away"]["name"],
            "goles_local": goles_local,
            "goles_visitante": goles_visitante,
            "es_empate": "SI" if es_empate else "NO",
            "modalidad": modalidad.get(fx["fixture"]["id"], "secuencial"),
        })
    filas.sort(key=lambda f: (f["fecha"], f["hora_peru"]))
    return filas


def calcular_analisis(filas_liga):
    rachas = []
    racha_actual = 0
    for fila in filas_liga:
        if fila["es_empate"] == "SI":
            rachas.append(racha_actual)
            racha_actual = 0
        else:
            racha_actual += 1

    if len(rachas) >= 2:
        promedio = statistics.mean(rachas)
        desviacion = statistics.stdev(rachas)
    elif len(rachas) == 1:
        promedio = rachas[0]
        desviacion = 0
    else:
        promedio = 0
        desviacion = 0

    umbral = max(round(promedio + desviacion), 1) if rachas else 5
    racha_maxima = max(rachas) if rachas else 0
    ultimo_partido = filas_liga[-1] if filas_liga else None

    return {
        "total_partidos": len(filas_liga),
        "total_empates": sum(1 for f in filas_liga if f["es_empate"] == "SI"),
        "promedio_racha": round(promedio, 2),
        "desviacion_std": round(desviacion, 2),
        "umbral_alerta": umbral,
        "racha_maxima": racha_maxima,
        "racha_actual": racha_actual,
        "alerta_activa": "SI" if racha_actual >= umbral else "NO",
        "ultimo_partido": (
            f"{ultimo_partido['equipo_local']} {ultimo_partido['goles_local']}-"
            f"{ultimo_partido['goles_visitante']} {ultimo_partido['equipo_visitante']}"
        ) if ultimo_partido else "",
        "fecha_ultimo_partido": ultimo_partido["fecha"] if ultimo_partido else "",
    }


def calcular_ranking_empates(filas_liga, liga_nombre):
    equipos = {}
    for fila in filas_liga:
        for equipo in (fila["equipo_local"], fila["equipo_visitante"]):
            stats = equipos.setdefault(equipo, {"total": 0, "empates": 0})
            stats["total"] += 1
            if fila["es_empate"] == "SI":
                stats["empates"] += 1

    filas = []
    for equipo, stats in equipos.items():
        pct = round(100 * stats["empates"] / stats["total"], 1) if stats["total"] else 0
        filas.append([equipo, liga_nombre, stats["total"], stats["empates"], pct])
    return filas


def main():
    sheet = conectar_google()

    ws_partidos = sheet.worksheet("Partidos")
    ws_analisis = sheet.worksheet("Analisis")
    ws_racha = sheet.worksheet("Racha_Actual")
    ws_ranking = sheet.worksheet("Ranking_Empates")
    ws_estado = sheet.worksheet("Estado")

    asegurar_encabezados(ws_partidos, [
        "fixture_id", "liga", "pais", "temporada", "fecha", "hora_peru",
        "equipo_local", "equipo_visitante", "goles_local", "goles_visitante",
        "es_empate", "modalidad",
    ])
    asegurar_encabezados(ws_analisis, [
        "liga", "pais", "total_partidos", "total_empates",
        "promedio_racha", "desviacion_std", "umbral_alerta", "racha_maxima",
    ])
    asegurar_encabezados(ws_racha, [
        "liga", "racha_actual", "umbral_alerta", "alerta_activa",
        "ultimo_partido", "fecha_ultimo_partido", "ultima_actualizacion",
    ])
    asegurar_encabezados(ws_ranking, ["equipo", "liga", "total_partidos", "total_empates", "pct_empates"])
    asegurar_encabezados(ws_estado, ["clave", "valor"])

    filas_partidos_todas = []
    filas_analisis_todas = []
    filas_racha_todas = []
    filas_ranking_todas = []

    for liga in LIGAS:
        print(f"Procesando {liga['nombre']} ({liga['pais']})...")
        filas_liga = []
        for temporada in TEMPORADAS:
            fixtures = obtener_fixtures(liga["id"], temporada)
            filas_liga.extend(construir_filas(fixtures, liga["nombre"], liga["pais"], temporada))
            time.sleep(1)

        filas_liga.sort(key=lambda f: (f["fecha"], f["hora_peru"]))
        filas_partidos_todas.extend(filas_liga)

        analisis = calcular_analisis(filas_liga)
        filas_analisis_todas.append([
            liga["nombre"], liga["pais"], analisis["total_partidos"], analisis["total_empates"],
            analisis["promedio_racha"], analisis["desviacion_std"], analisis["umbral_alerta"],
            analisis["racha_maxima"],
        ])
        filas_racha_todas.append([
            liga["nombre"], analisis["racha_actual"], analisis["umbral_alerta"], analisis["alerta_activa"],
            analisis["ultimo_partido"], analisis["fecha_ultimo_partido"], hora_peru(),
        ])
        filas_ranking_todas.extend(calcular_ranking_empates(filas_liga, liga["nombre"]))

        print(f"  {analisis['total_partidos']} partidos | umbral: {analisis['umbral_alerta']} | racha actual: {analisis['racha_actual']}")

    if filas_partidos_todas:
        append_en_lotes(ws_partidos, [[
            f["fixture_id"], f["liga"], f["pais"], f["temporada"], f["fecha"], f["hora_peru"],
            f["equipo_local"], f["equipo_visitante"], f["goles_local"], f["goles_visitante"],
            f["es_empate"], f["modalidad"],
        ] for f in filas_partidos_todas])

    if filas_analisis_todas:
        append_en_lotes(ws_analisis, filas_analisis_todas)
    if filas_racha_todas:
        append_en_lotes(ws_racha, filas_racha_todas)
    if filas_ranking_todas:
        append_en_lotes(ws_ranking, filas_ranking_todas)

    ws_estado.append_row(["ultima_carga_historico", hora_peru()])

    print("\n===== RESUMEN =====")
    print(f"Ligas procesadas: {len(LIGAS)}")
    print(f"Partidos totales cargados: {len(filas_partidos_todas)}")


if __name__ == "__main__":
    main()
