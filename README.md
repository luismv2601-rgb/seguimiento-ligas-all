# Seguimiento Ligas All

## Alcance del proyecto

Sistema automatizado que monitorea ligas de fútbol y calcula, para cada una, un **umbral estadístico** (no fijo) a partir del cual una racha de partidos consecutivos sin empate se considera inusual — y dispara una alerta en **Google Calendar**.

A diferencia de versiones anteriores del proyecto (umbral fijo en 5 para todas las ligas), acá el umbral se calcula por liga a partir de su propio histórico: **promedio + 1 desviación estándar** de las rachas observadas entre 2024 y 2025.

Actualmente hay **43 ligas activas** — 24 europeas, 9 de Norte y Centroamérica, 8 sudamericanas y 2 asiáticas — sumadas en un rollout por etapas (1 → 3 → 6 → 9 → 17 → 24 → 31 → 43) para validar la calidad de los datos antes de escalar:

| `liga_id` | Liga | País | Región |
|---|---|---|---|
| 342 | Premier League | Armenia | Europa |
| 218 | Bundesliga | Austria | Europa |
| 116 | Premier League | Bielorrusia | Europa |
| 172 | First League | Bulgaria | Europa |
| 345 | Czech Liga | Chequia | Europa |
| 210 | HNL | Croacia | Europa |
| 119 | Superliga | Dinamarca | Europa |
| 179 | Premiership | Escocia | Europa |
| 332 | Super Liga | Eslovaquia | Europa |
| 373 | 1. SNL | Eslovenia | Europa |
| 110 | Premier League | Gales | Europa |
| 271 | NB I | Hungría | Europa |
| 365 | Virsliga | Letonia | Europa |
| 261 | National Division | Luxemburgo | Europa |
| 371 | First League | Macedonia | Europa |
| 355 | First League | Montenegro | Europa |
| 103 | Eliteserien | Noruega | Europa |
| 106 | Ekstraklasa | Polonia | Europa |
| 283 | Liga I | Rumania | Europa |
| 235 | Premier League | Rusia | Europa |
| 286 | Super Liga | Serbia | Europa |
| 113 | Allsvenskan | Suecia | Europa |
| 207 | Super League | Suiza | Europa |
| 333 | Premier League | Ucrania | Europa |
| 479 | Canadian Premier League | Canadá | Norte y Centroamérica |
| 162 | Primera División | Costa Rica | Norte y Centroamérica |
| 370 | Primera División | El Salvador | Norte y Centroamérica |
| 253 | Major League Soccer | Estados Unidos | Norte y Centroamérica |
| 339 | Liga Nacional | Guatemala | Norte y Centroamérica |
| 234 | Liga Nacional | Honduras | Norte y Centroamérica |
| 262 | Liga MX | México | Norte y Centroamérica |
| 396 | Primera División | Nicaragua | Norte y Centroamérica |
| 304 | Liga Panameña de Fútbol | Panamá | Norte y Centroamérica |
| 128 | Liga Profesional Argentina | Argentina | Sudamérica |
| 344 | Primera División | Bolivia | Sudamérica |
| 71 | Serie A | Brasil | Sudamérica |
| 265 | Primera División | Chile | Sudamérica |
| 239 | Primera A | Colombia | Sudamérica |
| 242 | Liga Pro | Ecuador | Sudamérica |
| 281 | Primera División | Perú | Sudamérica |
| 299 | Primera División | Venezuela | Sudamérica |
| 169 | Super League | China | Asia |
| 292 | K League 1 | Corea del Sur | Asia |

La `region` no es decorativa: la web agrupa la lista por continente y la lee de la columna homónima de `Racha_Actual`, que `actualizar.py` mantiene sincronizada con este archivo.

Varias son ligas de calendario, con la temporada dentro del mismo año: Noruega, Suecia, Chile, Ecuador, Venezuela, Bolivia, Panamá, MLS, Canadá, Corea y China. El resto cruza de un año al siguiente.

**Consumo de API.** Cada corrida de `actualizar.py` hace 2 llamadas por liga, o sea 86 con las 43 activas. Entre Cloud Scheduler (15 al día, ventana 09:00–23:00 hora Perú) y el cron de GitHub (~5) son unas **1.720 llamadas diarias**, más 172 de `proximos.py`. Antes de sumar muchas ligas más conviene mirar el límite del plan en el dashboard de api-sports.io: cada liga nueva suma ~40 llamadas diarias.

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
                     Google Sheets (7 pestañas)
                     ├── Partidos       (histórico completo, solo partidos jugados)
                     ├── Analisis       (umbral estadístico fijo por liga, calculado 2024-2025)
                     ├── Racha_Actual   (racha vigente y récord, se actualiza en vivo)
                     ├── Ranking_Empates (equipos ordenados por % de empates)
                     ├── Estado         (bitácora: última ejecución, errores)
                     ├── Analisis 2     (rachas extremas por temporada — analisis_extremos.py)
                     └── Proximos       (partidos programados — proximos.py, diario)

                            │
                            ▼
                     Google Calendar (alerta cuando una racha nueva cruza el umbral)
```

### Las 7 pestañas del Sheet

**Partidos** — un partido por fila: `fixture_id, liga_id, liga, pais, temporada, fecha, hora_peru, equipo_local, equipo_visitante, goles_local, goles_visitante, es_empate, modalidad`

**Analisis** — el baseline fijo por liga (calculado una sola vez con 2024-2025, no se recalcula automáticamente): `liga_id, pais, liga, temporadas_analizadas, total_partidos, total_empates, promedio_racha, desviacion_std, umbral_alerta, racha_maxima, partidos_secuenciales, pct_secuenciales`. Ordenado por `pct_secuenciales` descendente.

**Racha_Actual** — el estado vivo de cada liga: `liga_id, liga, pais, racha_actual, umbral_alerta, racha_maxima, alerta_activa, ultimo_partido, fecha_ultimo_partido, ultima_actualizacion, region`. `racha_maxima` sí se actualiza en vivo (como "récord corriendo") si la racha actual supera el máximo histórico.

> `region` va **al final** y no en el medio a propósito: `actualizar.py` escribe las rachas por rango `D:J`, así que insertar una columna antes correría todo. La mantiene sincronizada con `ligas.json` la función `asegurar_region()`, en cada corrida horaria.

**Ranking_Empates** — un equipo por fila: `equipo, liga_id, liga, pais, total_partidos, total_empates, pct_empates`. Ordenado por `pct_empates` descendente (nota: equipos con pocos partidos jugados pueden aparecer arriba por variación estadística de muestra chica).

### Regla de orden: `Analisis` y `Ranking_Empates`

Las dos deben quedar siempre ordenadas de mayor a menor por su columna de porcentaje. `cargar_historico.py` ordena solo el lote que está agregando y lo pega al final, así que sumar una liga rompe el orden global — pasó en las dos.

`actualizar.py` las reordena en cada corrida horaria con `ordenar_por_columna()`. Las pestañas a ordenar están declaradas en `ORDEN_PESTANAS`; agregar otra es una línea. Ordena el rango en el lugar, sin reescribir valores, para que los decimales con coma del locale no se reinterpreten, y no toca nada si ya está ordenada.

**Estado** — bitácora simple (`clave, valor`) con la fecha de la última carga/ejecución y errores si los hay.

**Analisis 2** — reporte derivado, una fila por liga: cuántas rachas alcanzaron el **doble** del umbral por temporada, qué porcentaje representan sobre los empates de esa temporada, y los largos concretos. Se regenera entera con `analisis_extremos.yml`, una vez por día y también a mano.

**Proximos** — partidos programados de los próximos 14 días: `fixture_id, liga_id, liga, pais, temporada, fecha, hora_peru, equipo_local, equipo_visitante, ronda, dias_para`. Solo estado `NS`, o sea con hora confirmada; los `TBD` quedan afuera. Se reescribe entera una vez por día con `proximos.yml`.

> **Por qué los programados no van en `Partidos`.** Un partido sin jugar trae los goles en `None`, y en Python `None == None` es `True`, así que `es_empate` daría `"SI"` y cada partido futuro cortaría todas las rachas. Además `actualizar.py` deduplica por `fixture_id`: una vez cargado, nunca se le escribiría el resultado real al jugarse. `Partidos` es *append-only* con deduplicación; los programados necesitan una tabla que se reescriba.

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

| Workflow | Disparo | Para qué |
|---|---|---|
| `actualizar.yml` | cada hora de 09:00 a 23:00 hora Perú (ver abajo) | Mantiene el sistema al día: partidos nuevos, rachas y alertas |
| `proximos.yml` | diario, 05:00 hora Perú | Regenera la pestaña `Proximos` |
| `analisis_extremos.yml` | diario, 05:30 hora Perú | Regenera la pestaña `Analisis 2` |
| `cargar_historico.yml` | manual | Carga el baseline 2024-2025 de las ligas que no lo tengan |
| `buscar_ligas.yml` | manual | Busca el `liga_id` de un país antes de agregarlo |
| `estado_ligas.yml` | manual | Dice si la temporada de una liga ya arrancó y cuándo juega |

### Quién dispara `actualizar.yml`

**Google Cloud Scheduler es el disparador principal**, y el cron de GitHub quedó como respaldo. Los dos conviven a propósito.

| Disparador | Frecuencia | Rol |
|---|---|---|
| Google Cloud Scheduler (job `actualizar-seguimiento-ligas`) | `0 9-23 * * *`, `America/Lima` | Principal |
| `schedule` de GitHub Actions (`0 0,2,4,14,16,18,20,22 * * *`) | ~5 veces al día, irregular | Respaldo |

**Ventana horaria: 09:00 a 23:00 hora Perú.** Entre las 00:00 y las 08:00 no arranca ningún partido, así que correr en esa franja gastaba llamadas a la API sin encontrar nada. Se cierra a las 23:00 y no a las 22:00 para alcanzar a los partidos que empiezan cerca de las 20:30 y terminan pasadas las 22:00.

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
