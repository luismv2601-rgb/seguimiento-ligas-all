# Seguimiento Ligas All

## Alcance del proyecto

Sistema automatizado que monitorea ligas de fútbol y calcula, para cada una, un **umbral estadístico** (no fijo) a partir del cual una racha de partidos consecutivos sin empate se considera inusual — y dispara una alerta en **Google Calendar**.

A diferencia de versiones anteriores del proyecto (umbral fijo en 5 para todas las ligas), acá el umbral se calcula por liga a partir de su propio histórico: **promedio + 1 desviación estándar** de las rachas observadas entre 2024 y 2025.

Actualmente hay **6 ligas activas**, elegidas después de un rollout por etapas (1 → 3 → 6 ligas) para validar la calidad de los datos antes de escalar:

| Liga | País |
|---|---|
| Ekstraklasa | Polonia |
| Primera División | Perú |
| Serie A | Brasil |
| Liga Profesional Argentina | Argentina |
| Liga MX | México |
| Primera A | Colombia |

El catálogo completo vive en `ligas.json` (39 ligas/torneos definidos, cada una con un flag `"activa": true/false`) — agregar o quitar una liga del seguimiento es solo cambiar ese flag, sin tocar código.

Además del umbral de rachas, el sistema calcula:
- **Modalidad de programación** (`secuencial` / `paralelo`): si los partidos de una misma ronda se juegan uno detrás del otro o varios al mismo tiempo (se considera solapamiento si dos partidos arrancan con menos de 2 horas de diferencia).
- **Ranking de empates** por equipo dentro de cada liga.

---

## Arquitectura

```
API-Football (api-sports.io)
        │
        ├──► cargar_historico.py  (una sola vez / bajo demanda)
        │         └──► carga 2024+2025, calcula el baseline estadístico
        │
        └──► actualizar.py  (cada 2 horas, GitHub Actions)
                  └──► carga partidos nuevos, actualiza rachas, dispara alertas

                            │
                            ▼
                     Google Sheets (5 pestañas)
                     ├── Partidos       (histórico completo, partido por partido)
                     ├── Analisis       (umbral estadístico fijo por liga, calculado 2024-2025)
                     ├── Racha_Actual   (racha vigente y récord, se actualiza en vivo)
                     ├── Ranking_Empates (equipos ordenados por % de empates)
                     └── Estado        (bitácora: última ejecución, errores)

                            │
                            ▼
                     Google Calendar (alerta cuando una racha nueva cruza el umbral)
```

### Las 5 pestañas del Sheet

**Partidos** — un partido por fila: `fixture_id, liga_id, liga, pais, temporada, fecha, hora_peru, equipo_local, equipo_visitante, goles_local, goles_visitante, es_empate, modalidad`

**Analisis** — el baseline fijo por liga (calculado una sola vez con 2024-2025, no se recalcula automáticamente): `liga_id, pais, liga, temporadas_analizadas, total_partidos, total_empates, promedio_racha, desviacion_std, umbral_alerta, racha_maxima, partidos_secuenciales, pct_secuenciales`. Ordenado por `pct_secuenciales` descendente.

**Racha_Actual** — el estado vivo de cada liga: `liga_id, liga, pais, racha_actual, umbral_alerta, racha_maxima, alerta_activa, ultimo_partido, fecha_ultimo_partido, ultima_actualizacion`. `racha_maxima` sí se actualiza en vivo (como "récord corriendo") si la racha actual supera el máximo histórico.

**Ranking_Empates** — un equipo por fila: `equipo, liga_id, liga, pais, total_partidos, total_empates, pct_empates`. Ordenado por `pct_empates` descendente (nota: equipos con pocos partidos jugados pueden aparecer arriba por variación estadística de muestra chica).

**Estado** — bitácora simple (`clave, valor`) con la fecha de la última carga/ejecución y errores si los hay.

### `liga_id`, no nombre

Varias ligas comparten nombre entre países (ej. "Serie A" en Italia y Brasil, "Primera División" en varios países de Sudamérica). Por eso todo el sistema agrupa por `liga_id` (el ID numérico de API-Football), no por el nombre — el nombre y el país son solo columnas de lectura.

### Umbral fijo, no recalculado

El `umbral_alerta` de cada liga se calcula **una sola vez** con el histórico 2024-2025 y queda fijo — `actualizar.py` no lo recalcula en cada corrida. Es la misma lógica de un gráfico de control estadístico: si el umbral se recalculara incluyendo los datos más recientes, una racha real y anómala terminaría subiendo su propio umbral de comparación. Un re-baseline (recalcular con una ventana de temporadas más reciente) es una operación manual y ocasional, no automática.

### Racha continua, sin reset por temporada

La racha no se reinicia al cambiar de temporada (ej. de 2025 a 2026) — se cuenta como una sola secuencia cronológica continua de partidos, igual que se hizo al calcular el baseline. Solo se reinicia cuando ocurre un empate real.

---

## Configuración necesaria

### Secrets de GitHub

Agregar en **Settings → Secrets and variables → Actions**:

| Secret | Descripción |
|---|---|
| `FOOTBALL_API_KEY` | API key de API-Football (api-sports.io), plan Pro |
| `GOOGLE_CREDENTIALS_JSON` | JSON completo de la cuenta de servicio de Google Cloud |
| `GOOGLE_SHEET_ID` | ID del Google Sheet (de la URL, entre `/d/` y `/edit`) |
| `GOOGLE_CALENDAR_ID` | ID del Google Calendar donde se crean las alertas |

### Google Cloud

Cuenta de servicio con las siguientes APIs habilitadas: **Google Sheets API**, **Google Calendar API**, **Google Drive API**. Debe tener permisos de edición sobre el Sheet y el Calendar correspondientes.

### Workflows de GitHub Actions

- **`cargar_historico.yml`** — manual (`workflow_dispatch`). Correrlo solo cuando se necesite una carga histórica completa (ej. al agregar una liga nueva, o para hacer un re-baseline).
- **`actualizar.yml`** — automático, cron cada 2 horas (`0 */2 * * *`), más disparo manual disponible. Este es el que mantiene el sistema al día.

### Agregar o quitar una liga

Editar `ligas.json`, cambiar el flag `"activa"` de la liga deseada a `true` o `false`. Si se activa una liga nueva, correr `cargar_historico.yml` manualmente para cargar su histórico 2024-2025 antes de que `actualizar.yml` empiece a mantenerla al día.

---

Ver CHANGELOG.md para el historial de versiones.
