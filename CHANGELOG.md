# Changelog

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
