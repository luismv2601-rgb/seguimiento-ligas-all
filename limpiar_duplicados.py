"""Borra de 'Partidos' las filas duplicadas por fixture_id, dejando la primera.

Los duplicados los produjo una condicion de carrera: dos corridas de actualizar.py
que se solapaban leian la lista de fixture_id ya cargados antes de que la otra
escribiera, asi que las dos veian el mismo partido como nuevo y las dos lo
agregaban. El grupo de concurrencia en actualizar.yml lo evita de aca en adelante;
este script limpia lo que quedo.

Es de un solo uso, pero se deja en el repo: si vuelve a aparecer un duplicado por
cualquier otra via, ya esta la herramienta.

Por defecto **no escribe nada**: hay que pasar CONFIRMAR=si para que borre.

Solo borra una fila si es identica campo por campo a la primera aparicion de ese
fixture_id. Si difieren, la deja y la reporta: dos filas distintas con el mismo id
no son una copia sino un dato a mirar a mano.
"""
import os
import json

import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = os.environ.get("GOOGLE_SHEET_ID")
CONFIRMAR = os.environ.get("CONFIRMAR", "").strip().lower() in ("si", "sí", "yes", "true")
PESTANA = "Partidos"

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
    ws = sheet.worksheet(PESTANA)
    valores = ws.get_all_values()
    if len(valores) < 2:
        print("Pestana vacia, no hay nada que hacer.")
        return

    encabezado = valores[0]
    col = encabezado.index("fixture_id")
    print(f"{PESTANA}: {len(valores) - 1} filas de datos.")

    primera = {}          # fixture_id -> (nro de fila, contenido)
    a_borrar = []         # indices base 0
    distintas = []        # mismo id pero contenido distinto: no se tocan

    for i, fila in enumerate(valores):
        if i == 0 or not any(str(c).strip() for c in fila):
            continue
        fid = str(fila[col]).strip()
        if not fid:
            continue
        if fid not in primera:
            primera[fid] = (i + 1, fila)
            continue
        if fila == primera[fid][1]:
            a_borrar.append(i)
            print(f"  duplicado exacto: fixture_id {fid} en fila {i + 1} "
                  f"(original en fila {primera[fid][0]})")
        else:
            distintas.append((fid, i + 1, primera[fid][0]))

    if distintas:
        print(f"\n  ATENCION: {len(distintas)} filas comparten fixture_id pero difieren. "
              f"No se borran, hay que mirarlas a mano:")
        for fid, fila_dup, fila_orig in distintas:
            print(f"    fixture_id {fid}: filas {fila_orig} y {fila_dup}")

    print(f"\nDuplicados exactos encontrados: {len(a_borrar)}")
    if not a_borrar:
        return

    if not CONFIRMAR:
        print("\nENSAYO: no se borro nada. Pasar CONFIRMAR=si para aplicar.")
        return

    # Bloques contiguos, borrados de abajo hacia arriba para no correr los indices
    # de los que todavia faltan.
    bloques = []
    for i in a_borrar:
        if bloques and i == bloques[-1][1] + 1:
            bloques[-1][1] = i
        else:
            bloques.append([i, i])

    sheet.batch_update({"requests": [
        {"deleteDimension": {"range": {
            "sheetId": ws.id, "dimension": "ROWS",
            "startIndex": ini, "endIndex": fin + 1,
        }}}
        for ini, fin in reversed(bloques)
    ]})
    print(f"Borradas {len(a_borrar)} filas en {len(bloques)} bloques.")

    quedan = ws.get_all_values()
    ids = [f[col] for f in quedan[1:] if any(str(c).strip() for c in f)]
    repetidos = {i for i in ids if ids.count(i) > 1}
    print(f"Verificacion: {len(quedan) - 1} filas, duplicados restantes: {len(repetidos)}")


if __name__ == "__main__":
    main()
