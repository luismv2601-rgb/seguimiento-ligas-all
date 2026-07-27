# Changelog

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
