# Seguimiento Ligas All

## Alcance del proyecto

Sistema automatizado que monitorea ligas de fútbol y calcula, para cada una, un **umbral estadístico** (no fijo) a partir del cual una racha de partidos consecutivos sin empate se considera inusual — y dispara una alerta en **Google Calendar**.

A diferencia de versiones anteriores del proyecto (umbral fijo en 5 para todas las ligas), acá el umbral se calcula por liga a partir de su propio histórico: **promedio + 1 desviación estándar** de las rachas observadas entre 2024 y 2025.

Actualmente hay **17 ligas activas**, sumadas en un rollout por etapas (1 → 3 → 6 → 9 → 17) para validar la calidad de los datos antes de escalar:

| `liga_id` | Liga | País | Región |
|---|---|---|---|
| 106 | Ekstraklasa | Polonia | Europa |
| 116 | Premier League | Bielorrusia | Europa |
| 342 | Premier League | Armenia | Europa |
| 365 | Virsliga | Letonia | Europa |
| 103 | Eliteserien | Noruega | Europa |
| 113 | Allsvenskan | Suecia | Europa |
| 283 | Liga I | Rumania | Europa |
| 235 | Premier League | Rusia | Europa |
| 207 | Super League | Suiza | Europa |
| 119 | Superliga | Dinamarca | Europa |
| 179 | Premiership | Escocia | Europa |
| 218 | Bundesliga | Austria | Europa |
| 281 | Primera División | Perú | Sudamérica |
| 71 | Serie A | Brasil | Sudamérica |
| 128 | Liga Profesional Argentina | Argentina | Sudamérica |
| 239 | Primera A | Colombia | Sudamérica |
| 262 | Liga MX | México | Centroamérica |

Noruega y Suecia son ligas de calendario (marzo-noviembre); el resto sigue el ciclo europeo o sudamericano habitual.

`ligas.json` define solo las ligas activas (cada una con `"activa": true`) — agregar una liga nueva es agregar su entrada al archivo con `"activa": true` y correr `cargar_historico.yml` para cargar su histórico; poner `"activa": false` en una liga existente la saca del seguimiento sin borrarla del archivo, si se prefiere pausarla en vez de eliminarla.

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
        └──► actualizar.py  (cada hora, Google Cloud Scheduler)
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

**Analisis 2** — reporte derivado, una fila por liga: cuántas rachas alcanzaron el **doble** del umbral por temporada, qué porcentaje representan sobre los empates de esa temporada, y los largos concretos. Se regenera entera con `analisis_extremos.yml` (manual); no la consume nada más.

### Alertas de Calendar: solo si el cruce es reciente

Una alerta se crea únicamente cuando un partido **de los últimos 2 días** (`DIAS_MAX_PARA_ALERTAR` en `actualizar.py`) hace que la racha alcance el umbral. El filtro existe porque al activar una liga con la temporada ya empezada entran cientos de partidos en una sola corrida, y sin él cada cruce histórico generaría un evento fechado hoy — pasó al sumar 8 ligas el 1-ago-2026 y creó 11 alertas falsas.

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
- **`actualizar.yml`** — el que mantiene el sistema al día. Tiene dos disparadores (ver abajo), más disparo manual disponible.

### Quién dispara `actualizar.yml`

**Google Cloud Scheduler es el disparador principal**, y el cron de GitHub quedó como respaldo. Los dos conviven a propósito.

| Disparador | Frecuencia | Rol |
|---|---|---|
| Google Cloud Scheduler (job `actualizar-seguimiento-ligas`) | cada hora en punto, `America/Lima` | Principal |
| `schedule` de GitHub Actions (`0 */2 * * *`) | ~8 veces al día, irregular | Respaldo |

El motivo es que los `schedule` de GitHub Actions son best-effort: en la práctica descartan ~1 de cada 3 disparos y se retrasan hasta ~90 minutos, dejando huecos de hasta 4 horas justo en la franja nocturna donde terminan los partidos sudamericanos. Cloud Scheduler sí es puntual.

Se dejó el cron de GitHub porque si el job de Cloud Scheduler falla, **falla en silencio**: el sistema degrada a las ~8 corridas diarias en vez de quedarse en cero.

El job hace `POST` a `https://api.github.com/repos/luismv2601-rgb/seguimiento-ligas-all/actions/workflows/actualizar.yml/dispatches` con cuerpo `{"ref":"master"}`, y se autentica con un PAT fine-grained de GitHub (`cloud-scheduler-ligas`, permiso *Actions: Read and write*) enviado en el header `Authorization`.

> ⚠️ **El PAT vence el 1 de agosto de 2027.** Cuando venza, el job empieza a recibir 401 y deja de disparar sin ninguna alerta. Los logs del job en Cloud Scheduler son el lugar donde se ve.

Costo: USD 0 — Cloud Scheduler incluye 3 jobs gratis por cuenta de facturación y este usa 1 (GCP igual exige tener facturación habilitada).

### Agregar o quitar una liga

Editar `ligas.json`, cambiar el flag `"activa"` de la liga deseada a `true` o `false`. Si se activa una liga nueva, correr `cargar_historico.yml` manualmente para cargar su histórico 2024-2025 antes de que `actualizar.yml` empiece a mantenerla al día.

**`cargar_historico.yml` es seguro de correr con ligas ya cargadas:** omite entera cualquier liga que ya tenga su fila en `Analisis`, y filtra los partidos por `fixture_id`. Correrlo dos veces no duplica nada.

Antes de agregar una liga hay que verificar su ID contra la API con `buscar_ligas.yml` (input: nombres de países en inglés). Un `liga_id` equivocado no da error — la liga simplemente no trae partidos y queda muda. Ojo con los nombres: en varios países la liga llamada *"First League"* o *"1. Liga"* es la **segunda** división.

### Re-baseline de una liga ya cargada

`cargar_historico.yml` no sirve para esto, justamente porque no pisa datos existentes. Para recalcular el umbral de una liga que ya está cargada hay que borrarle a mano sus filas del Sheet (`Partidos`, `Analisis`, `Racha_Actual`, `Ranking_Empates`) y recién ahí correr el workflow.

---

## Visualización móvil

Existe una página web complementaria para ver este seguimiento desde el celular: [`seguimiento-ligas-all-web`](https://github.com/luismv2601-rgb/seguimiento-ligas-all-web) — en vivo en https://luismv2601-rgb.github.io/seguimiento-ligas-all-web/. Lee el Sheet directamente como CSV público, así que no necesita ningún cambio en este repo salvo cuando cambien los `gid` de las pestañas.

---

Ver CHANGELOG.md para el historial de versiones.
