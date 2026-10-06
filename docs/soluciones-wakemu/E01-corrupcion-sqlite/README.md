# E01. Corrupción histórica de SQLite interrumpe crecimiento

Sustituir la persistencia SQLite por PostgreSQL y verificar integridad, concurrencia y recuperación del servidor.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Implementación validada individualmente.** El Docker principal usa PostgreSQL con ocho migraciones. Se retiraron los journals obsoletos de builds y grupos; Redis conserva el journal de posiciones. Se verificó restauración con personaje, equipo, build y recompensa. [Evidencia y límites](IMPLEMENTACION.md).

## Dependencias

0, 2, 3, 6, 20. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

La base nueva no importa ni repara automáticamente el SQLite anterior. Recovery no inventa objetos/progreso; las operaciones relacionadas confirman juntas y las recompensas no se duplican tras reintentos. Una segunda instancia no puede recuperar la base de un world vivo.

[Evaluación SQLite/PostgreSQL y migración concreta](SQLITE-VS-POSTGRESQL.md): recomendación de PostgreSQL para el servidor multijugador; migración aplicada al Docker local; no se afirma un benchmark comparativo.

[Migración definitiva: tablas, tipos, relaciones, locks y cutover](MIGRACION-POSTGRESQL-TABLAS.md). Sin retrocompatibilidad SQLite, conforme a la instrucción del usuario.

## Estado actual: resuelto

PostgreSQL único cargado y healthy, sin importación ni fallback SQLite.
Gate específico77/77, restauración poblada y comprobación visual de personaje,
mapa e inventario tras reinicio acreditados. [Evidencia](IMPLEMENTACION.md).
Esto cierraE01 individualmente, no el objetivo de los demás issues.

La suite completa actual del servidor terminó con 1,737 tests: 12 FAIL, 59
ERROR y 1 omitido. Los fallos reportados son de suites de combate/políticas
nativas y artefactos ausentes; no se clasificaron como errores de PostgreSQL.
Esa suite general permanece roja; resultado y categorías están en
[Pruebas](PRUEBAS.md).
