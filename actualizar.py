import os
import json
import time
from datetime import datetime, timedelta, timezone

import requests
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

API_KEY = os.environ.get("FOOTBALL_API_KEY")
API_BASE = "https://v3.football.api-sports.io"
SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
CALENDAR_ID = os.environ.get("GOOGLE_CALENDAR_ID")
HEADERS = {"x-apisports-key": API_KEY}

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar",
]

with open("ligas.json", encoding="utf-8") as f:
    LIGAS = [liga for liga in json.load(f) if liga.get("activa", True)]


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
    sheet = gc.open_by_key(SHEET_ID)
    calendar_service = build("calendar", "v3", credentials=creds)
    return sheet, calendar_service


def obtener_temporada_actual(liga_id):
    resp = requests.get(f"{API_BASE}/leagues", headers=HEADERS, params={"id": liga_id})
    data = resp.json()
    if not data.get("response"):
        return None
    temporadas = data["response"][0]["seasons"]
    actual = next((t["year"] for t in temporadas if t["current"]), None)
    return actual or max(t["year"] for t in temporadas)


def obtener_fixtures(liga_id, temporada):
    params = {"league": liga_id, "season": temporada, "status": "FT"}
    resp = requests.get(f"{API_BASE}/fixtures", headers=HEADERS, params=params)
    data = resp.json()
    if data.get("errors"):
        print(f"  Aviso: liga {liga_id} temporada {temporada}: {data['errors']}")
        return []
    return data.get("response", [])


def modalidad_por_ronda(fixtures):
    por_ronda = {}
    for fx in fixtures:
        por_ronda.setdefault(fx["league"]["round"], []).append(fx)
    modalidad = {}
    for partidos in por_ronda.values():
        conteo_horarios = {}
        for p in partidos:
            ts = p["fixture"]["timestamp"]
            conteo_horarios[ts] = conteo_horarios.get(ts, 0) + 1
        for p in partidos:
            ts = p["fixture"]["timestamp"]
            modalidad[p["fixture"]["id"]] = "paralelo" if conteo_horarios[ts] > 1 else "secuencial"
    return modalidad


def construir_fila(fx, liga, temporada, modalidad):
    fecha_peru = datetime.fromtimestamp(fx["fixture"]["timestamp"], tz=timezone.utc) - timedelta(hours=5)
    goles_local = fx["goals"]["home"]
    goles_visitante = fx["goals"]["away"]
    return {
        "fixture_id": str(fx["fixture"]["id"]),
        "liga_id": liga["id"],
        "liga": liga["nombre"],
        "pais": liga["pais"],
        "temporada": temporada,
        "fecha": fecha_peru.strftime("%Y-%m-%d"),
        "hora_peru": fecha_peru.strftime("%H:%M"),
        "equipo_local": fx["teams"]["home"]["name"],
        "equipo_visitante": fx["teams"]["away"]["name"],
        "goles_local": goles_local,
        "goles_visitante": goles_visitante,
        "es_empate": "SI" if goles_local == goles_visitante else "NO",
        "modalidad": modalidad.get(fx["fixture"]["id"], "secuencial"),
    }


def cargar_ids_procesados(ws_partidos):
    valores = ws_partidos.col_values(1)[1:]  # sin encabezado
    return set(valores)


def cargar_estado_racha(ws_racha):
    valores = ws_racha.get_all_records()
    estado = {}
    for i, row in enumerate(valores):
        estado[int(row["liga_id"])] = {
            "fila": i + 2,
            "racha_actual": int(row["racha_actual"] or 0),
            "umbral_alerta": int(row["umbral_alerta"] or 5),
        }
    return estado


def cargar_ranking_existente(ws_ranking):
    valores = ws_ranking.get_all_records()
    ranking = {}
    for i, row in enumerate(valores):
        ranking[(int(row["liga_id"]), row["equipo"])] = {
            "fila": i + 2,
            "total": int(row["total_partidos"] or 0),
            "empates": int(row["total_empates"] or 0),
        }
    return ranking


def crear_alerta_calendar(calendar_service, liga_nombre, liga_pais, umbral, ultimos_partidos):
    detalle = "\n".join(
        f"{p['equipo_local']} {p['goles_local']}-{p['goles_visitante']} {p['equipo_visitante']}"
        for p in ultimos_partidos
    )
    hoy = hora_peru()[:10]
    evento = {
        "summary": f"⚠️ {umbral}+ partidos sin empate — {liga_nombre} ({liga_pais})",
        "description": f"Ultimos {len(ultimos_partidos)} partidos sin empate:\n{detalle}",
        "start": {"date": hoy},
        "end": {"date": hoy},
    }
    calendar_service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()
    print(f"  Alerta creada en Calendar para {liga_nombre} ({liga_pais})")


def main():
    sheet, calendar_service = conectar_google()
    ws_partidos = sheet.worksheet("Partidos")
    ws_racha = sheet.worksheet("Racha_Actual")
    ws_ranking = sheet.worksheet("Ranking_Empates")
    ws_estado = sheet.worksheet("Estado")

    ids_procesados = cargar_ids_procesados(ws_partidos)
    estado_racha = cargar_estado_racha(ws_racha)
    ranking = cargar_ranking_existente(ws_ranking)

    filas_partidos_nuevas = []
    actualizaciones_racha = []
    equipos_tocados = set()  # (liga_id, equipo) modificados en esta corrida
    errores = []

    for liga in LIGAS:
        try:
            print(f"Revisando {liga['nombre']} ({liga['pais']}) [id {liga['id']}]...")
            temporada = obtener_temporada_actual(liga["id"])
            time.sleep(1)
            if temporada is None:
                print("  No se encontro temporada actual, se omite.")
                continue

            fixtures = obtener_fixtures(liga["id"], temporada)
            time.sleep(1)
            if not fixtures:
                continue

            modalidad = modalidad_por_ronda(fixtures)
            fixtures.sort(key=lambda fx: fx["fixture"]["timestamp"])

            nuevos = [fx for fx in fixtures if str(fx["fixture"]["id"]) not in ids_procesados]
            if not nuevos:
                print("  Sin partidos nuevos.")
                continue

            info_racha = estado_racha.get(liga["id"], {"fila": None, "racha_actual": 0, "umbral_alerta": 5})
            racha_actual = info_racha["racha_actual"]
            umbral = info_racha["umbral_alerta"]
            ultimos_no_empate = []
            ultimo_partido_texto = ""
            ultima_fecha = ""

            for fx in nuevos:
                fila = construir_fila(fx, liga, temporada, modalidad)
                filas_partidos_nuevas.append(fila)
                ids_procesados.add(fila["fixture_id"])

                for equipo in (fila["equipo_local"], fila["equipo_visitante"]):
                    clave = (liga["id"], equipo)
                    if clave not in ranking:
                        ranking[clave] = {"fila": None, "total": 0, "empates": 0}
                    ranking[clave]["total"] += 1
                    if fila["es_empate"] == "SI":
                        ranking[clave]["empates"] += 1
                    equipos_tocados.add(clave)

                if fila["es_empate"] == "SI":
                    racha_actual = 0
                    ultimos_no_empate = []
                else:
                    racha_actual += 1
                    ultimos_no_empate.append(fila)
                    if len(ultimos_no_empate) > umbral:
                        ultimos_no_empate.pop(0)
                    if racha_actual == umbral:
                        crear_alerta_calendar(calendar_service, liga["nombre"], liga["pais"], umbral, ultimos_no_empate)

                ultimo_partido_texto = f"{fila['equipo_local']} {fila['goles_local']}-{fila['goles_visitante']} {fila['equipo_visitante']}"
                ultima_fecha = fila["fecha"]

            actualizaciones_racha.append({
                "fila": info_racha["fila"],
                "liga_id": liga["id"],
                "liga": liga["nombre"],
                "pais": liga["pais"],
                "racha_actual": racha_actual,
                "umbral_alerta": umbral,
                "alerta_activa": "SI" if racha_actual >= umbral else "NO",
                "ultimo_partido": ultimo_partido_texto,
                "fecha_ultimo_partido": ultima_fecha,
            })

            print(f"  {len(nuevos)} partidos nuevos | racha actual: {racha_actual} (umbral {umbral})")

        except Exception as e:
            print(f"  ERROR procesando {liga['nombre']} ({liga['pais']}): {e}")
            errores.append(f"{liga['nombre']} ({liga['pais']}): {e}")

    # ---- Escribir Partidos (una sola llamada) ----
    if filas_partidos_nuevas:
        ws_partidos.append_rows([[
            f["fixture_id"], f["liga_id"], f["liga"], f["pais"], f["temporada"], f["fecha"], f["hora_peru"],
            f["equipo_local"], f["equipo_visitante"], f["goles_local"], f["goles_visitante"],
            f["es_empate"], f["modalidad"],
        ] for f in filas_partidos_nuevas])

    # ---- Actualizar Racha_Actual en un solo batch_update ----
    batch_racha = []
    nuevas_filas_racha = []
    for act in actualizaciones_racha:
        valores = [act["racha_actual"], act["umbral_alerta"], act["alerta_activa"],
                   act["ultimo_partido"], act["fecha_ultimo_partido"], hora_peru()]
        if act["fila"]:
            batch_racha.append({"range": f"D{act['fila']}:I{act['fila']}", "values": [valores]})
        else:
            nuevas_filas_racha.append([act["liga_id"], act["liga"], act["pais"]] + valores)

    if batch_racha:
        ws_racha.batch_update(batch_racha)
    if nuevas_filas_racha:
        ws_racha.append_rows(nuevas_filas_racha)

    # ---- Actualizar Ranking_Empates en un solo batch_update ----
    batch_ranking = []
    nuevas_filas_ranking = []
    for clave in equipos_tocados:
        liga_id, equipo = clave
        datos = ranking[clave]
        pct = round(100 * datos["empates"] / datos["total"], 1) if datos["total"] else 0
        if datos["fila"]:
            batch_ranking.append({"range": f"E{datos['fila']}:G{datos['fila']}",
                                   "values": [[datos["total"], datos["empates"], pct]]})
        else:
            liga_nombre = next((l["nombre"] for l in LIGAS if l["id"] == liga_id), "")
            liga_pais = next((l["pais"] for l in LIGAS if l["id"] == liga_id), "")
            nuevas_filas_ranking.append([equipo, liga_id, liga_nombre, liga_pais, datos["total"], datos["empates"], pct])

    if batch_ranking:
        ws_ranking.batch_update(batch_ranking)
    if nuevas_filas_ranking:
        ws_ranking.append_rows(nuevas_filas_ranking)

    ws_estado.append_row(["ultima_ejecucion", hora_peru()])
    if errores:
        ws_estado.append_row(["errores_" + hora_peru(), "; ".join(errores)])

    print("\n===== RESUMEN =====")
    print(f"Partidos nuevos: {len(filas_partidos_nuevas)}")
    print(f"Ligas con actividad: {len(actualizaciones_racha)}")
    if errores:
        print(f"Errores: {len(errores)}")


if __name__ == "__main__":
    main()
