# Changelog

## v1.8.0 - 2026-08-06
- **Ventana horaria 09:00–23:00 hora Perú.** Entre las 00:00 y las 08:00 no arranca ningún partido, así que esas corridas gastaban 86 llamadas cada una para no encontrar nada. El cron de Cloud Scheduler pasa de `0 * * * *` a `0 9-23 * * *` y el de respaldo de GitHub a las 8 horas UTC que caen dentro de la ventana. Cierra a las 23:00 y no a las 22:00 para alcanzar los partidos que arrancan ~20:30 y terminan pasadas las 22:00. Consumo de 2.924 a 1.892 llamadas diarias (−35%)
- **`actualizar.py` saca de `Proximos` los partidos que ya dejaron de serlo**, en la misma corrida horaria. `Partidos` se actualizaba cada hora pero `Proximos` una vez por día, así que un partido ya jugado seguía figurando como programado hasta 17 horas — verificado en vivo: 8 partidos del 5 de agosto, entre ellos Boca-Estudiantes de las 17:00. Se borra por dos criterios: el `fixture_id` entró como jugado en esa corrida, o su horario pasó hace más de 4 horas. No cuesta ninguna llamada a la API
- **`proximos.yml` pasa a dos disparos diarios** (09:00 y 21:00 UTC). Con uno solo, un salto del cron dejaba la pestaña 48 horas vieja
- **`analisis_extremos.yml` pasa a tener cron diario** (10:30 UTC). Era la única pestaña que no se actualizaba sola
- **3 ligas más: Georgia (327), Kazajistán (389) y Estonia (329).** De 43 a **46 activas**. Son tres de las nueve ligas de verano descartadas el 2 de agosto por estar avanzadas; revisadas de nuevo, son las únicas que todavía tienen media temporada por delante (85, 80 y 77 partidos programados). Entraron 1.066 partidos de baseline y 356 de la temporada en curso. El filtro de alertas suprimió 13 cruces históricos sin crear un solo evento

## v1.7.0 - 2026-08-02
- **De 24 a 43 ligas activas.** Primero 7: Bolivia (344), Canadá (479), Panamá (304), Guatemala (339), El Salvador (370), Honduras (234) y Nicaragua (396). Después 12 europeas que arrancaron entre el 18 de julio y el 2 de agosto: Ucrania (333), Croacia (210), Serbia (286), Chequia (345), Eslovaquia (332), Hungría (271), Bulgaria (172), Eslovenia (373), Macedonia (371), Montenegro (355), Luxemburgo (261) y Gales (110)
- Bolivia cierra el hueco de Sudamérica: era la única de las 10 de CONMEBOL que nunca había estado en el catálogo. Se revisaron además 32 países europeos que el catálogo original no cubría
- La región `Norteamérica` pasa a `Norte y Centroamérica`, para no multiplicar los grupos de la app al sumar las centroamericanas
- **Regla nueva:** `Ranking_Empates` también queda siempre ordenada, por `pct_empates`. Tenía el mismo problema que `Analisis`: tras sumar 7 ligas la pestaña acumulaba 237 saltos de orden y los 111 equipos nuevos quedaban al fondo, lo que la hacía parecer desactualizada aunque los datos estuvieran completos. `ordenar_analisis()` pasa a ser `ordenar_por_columna()` y las hojas se declaran en `ORDEN_PESTANAS`
- El filtro de alertas quedó probado en producción tres veces. En las cargas masivas suprimió 45 y 10 cruces históricos sin crear un solo evento; al sumar las europeas dejó pasar una alerta real de Gales (racha 3 → 9 con partidos del día) y suprimió una de Bulgaria del 27 de julio, distinguiendo lo viejo de lo nuevo dentro de la misma corrida

## v1.6.0 - 2026-08-01
- 7 ligas más: Chile (265), Ecuador (242) y Venezuela (299) de Sudamérica, Costa Rica (162) y MLS (253) de Norteamérica, y Corea del Sur (292) y China (169) de Asia. De 17 a **24 ligas activas**. Entraron 3.958 partidos de baseline y 969 de la temporada en curso, sin un solo duplicado
- **Primera prueba real del filtro de alertas:** esos 969 partidos produjeron 45 cruces de umbral, todos de meses atrás, y **no se creó ninguna alerta**. Con el código de la mañana habrían sido 45 eventos basura en el Calendar
- `proximos.py` + workflow `proximos.yml`: pestaña `Proximos` con los partidos programados de los próximos 14 días, solo los que tienen hora confirmada (estado `NS`). Corre una vez por día. Va aparte de `Partidos` porque un partido sin jugar trae los goles en `None` y `None == None` da `True`: se leería como empate y cortaría todas las rachas
- `ligas.json` pasa a continentes reales: México y Costa Rica de Centroamérica a Norteamérica, Estados Unidos de "Resto del mundo" a Norteamérica, y Corea y China a Asia
- Columna `region` en `Racha_Actual`, que la web necesita para agrupar por continente. Va al final de la fila porque `actualizar.py` escribe las rachas por rango `D:J`. `asegurar_region()` la crea y la mantiene sincronizada con `ligas.json` en cada corrida horaria, sin migración manual
- `estado_ligas.py` + workflow: dice si la temporada de una liga ya arrancó, cuántas fechas lleva y cuándo es el próximo partido

## v1.5.0 - 2026-08-01
- 11 ligas europeas nuevas: Bielorrusia (116), Armenia (342), Letonia (365), Noruega (103), Suecia (113), Rumania (283), Rusia (235), Suiza (207), Dinamarca (119), Escocia (179) y Austria (218). De 6 a 17 ligas activas
- **Corrección:** `actualizar.py` creaba una alerta de Calendar por cada cruce de umbral al incorporar una temporada entera de golpe. Al sumar las 8 ligas con temporada en curso se generaron 11 eventos fechados hoy por cruces de marzo, abril y mayo. Ahora solo alerta si el partido que cruzó el umbral tiene 2 días o menos (`DIAS_MAX_PARA_ALERTAR`), y reporta cuántas omitió
- `estado_ligas.py` + workflow `estado_ligas.yml`: muestra si la temporada de una liga ya arrancó, cuántas fechas lleva y cuándo es el próximo partido. Sirve para decidir el momento de sumar una liga
- `Analisis 2` unificada en una sola tabla (antes eran dos), con `liga_id`, `pais` y `racha_maxima`
- **Regla nueva:** la pestaña `Analisis` queda siempre ordenada de mayor a menor por `pct_secuenciales`. `cargar_historico.py` ordenaba solo el lote que agregaba y lo pegaba al final, así que sumar ligas rompía el orden global. Ahora `actualizar.py` la reordena en cada corrida horaria, sin reescribir valores y sin tocar nada si ya está ordenada
- README: tabla de las 17 ligas activas con su `liga_id` y región

## v1.4.0 - 2026-08-01
- **Corrección importante:** `cargar_historico.py` duplicaba todos los datos de las ligas ya cargadas. Procesaba todas las ligas activas y hacía `append` sin deduplicar, así que correrlo para sumar una liga nueva repetía el histórico completo de las anteriores en las 4 pestañas
- Ahora es idempotente: omite entera cualquier liga que ya tenga fila en `Analisis` y filtra los partidos por `fixture_id`. Correrlo dos veces no cambia nada
- `buscar_ligas.py` + workflow `buscar_ligas.yml`: consulta `/leagues` por país y muestra id, tipo, temporada actual y si cubre 2024+2025, para verificar un `liga_id` antes de agregarlo. Un ID equivocado no falla, solo deja la liga muda
- README: aviso de que `cargar_historico.yml` es seguro de repetir, y sección sobre cómo hacer un re-baseline (hay que borrar las filas a mano primero)

## v1.3.0 - 2026-08-01
- Google Cloud Scheduler pasa a ser el disparador principal de `actualizar.yml`: job `actualizar-seguimiento-ligas` (`us-central1`, cron horario, zona `America/Lima`) que llama al endpoint `workflow_dispatch` de la API de GitHub
- El cron `schedule` de GitHub Actions se mantiene como respaldo. Se midieron sus disparos reales: descarta ~1 de cada 3, se retrasa hasta ~90 min y deja huecos de hasta 4h en la franja nocturna donde terminan los partidos sudamericanos
- Sin costo adicional: el tier gratis de Cloud Scheduler cubre 3 jobs y el consumo de API-Football sube a ~380 requests/día, muy por debajo del plan Pro
- README: sección nueva "Quién dispara `actualizar.yml`" con la config del job y el vencimiento del PAT (1-ago-2027)

## v1.2.0 - 2026-07-27
- `ligas.json` limpiado: se quitaron las 33 ligas inactivas del catálogo, queda solo con las 6 ligas activas

## v1.1.0 - 2026-07-27
- README: referencia a la web complementaria `seguimiento-ligas-all-web` para visualización móvil

## v1.0.0 - 2026-07-27
- `actualizar.py`: carga incremental de partidos nuevos, actualización de rachas en vivo y alertas de Calendar por transición (solo cuando un partido nuevo hace cruzar el umbral, no retroactivo)
- `racha_maxima` en Racha_Actual: se actualiza como "récord corriendo" si la racha en vivo supera el máximo histórico
- Workflows de GitHub Actions: `actualizar.yml` (cron cada 2 horas) y `cargar_historico.yml` (manual), probados en el entorno real de GitHub Actions
- Set final de 6 ligas activas tras rollout por etapas (1 → 3 → 6), validado columna por columna en las 5 pestañas
- README con arquitectura, esquema de datos y guía de configuración

## v0.3.0 - 2026-07-27
- Corrección: `liga_id` como clave única en Partidos/Analisis/Racha_Actual/Ranking_Empates (varias ligas comparten nombre entre países y se mezclaban)
- Corrección: `modalidad` (secuencial/paralelo) calculada por partido individual y por solapamiento real de horario (partido de ~2 horas), no por igualdad exacta de horario ni por ronda completa
- Nuevas columnas en Analisis: `temporadas_analizadas`, `partidos_secuenciales`, `pct_secuenciales`
- Ranking_Empates y Analisis ordenados por porcentaje descendente
- Flag `"activa"` en `ligas.json` para controlar qué ligas procesan los scripts sin tocar código

## v0.2.0 - 2026-07-26
- `cargar_historico.py`: carga de partidos 2024-2025 por liga desde API-Football
- Cálculo de umbral estadístico por liga (promedio + 1 desviación estándar de rachas sin empate, a nivel de liga completa, no por equipo)
- `ligas.json` con 39 ligas/torneos, IDs verificados contra la API (incluye corrección de Ecuador y el formato Apertura/Clausura de Paraguay y Uruguay)
- Ranking de empates por equipo

## v0.1.0 - 2026-07-26
- Proyecto `seguimiento-ligas-all` inicializado: repositorio GitHub, Google Cloud project, cuenta de servicio, Google Sheet (5 pestañas) y Google Calendar
- Fuente de datos: API-Football (api-sports.io), plan Pro
