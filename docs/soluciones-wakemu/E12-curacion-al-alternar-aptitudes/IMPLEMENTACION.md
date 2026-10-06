# E12 — Salud reversible al cambiar builds

## Implementación en curso

La migración `007_canonical_health.sql` añade `hp_damage` y `health_dead` a
`characters`. Inicializa la herida desde el estado PostgreSQL actual; no importa
SQLite ni reinstala journals. No puede reconstruir heridas históricas ya borradas
por el defecto anterior.

`health_policy.reconfigure` conserva la herida al cambiar máximo. Un vivo tiene
como mínimo un HP; muerte explícita conserva cero. Caso esperado:
`1370/1470 → 950/1050 → 1370/1470`. Esta es una política de servidor reversible;
la evidencia del efecto nativo `eZI` respalda el ajuste por delta, pero no acredita
el contrato completo del guardado de builds.

Guardar, activar, borrar e inicializar salud usan la función compartida dentro
de sus transacciones existentes. Consumo, sincronización y regeneración actualizan
la herida mediante el cambio efectivo de HP. El retorno de combate traduce el
cambio de déficit desde el actor al personaje persistido en la misma transacción
que registra el recibo de salida.

## Validación pendiente

Luna prepara regresiones PostgreSQL para aptitudes, cambios activos/inactivos,
borrado, muerte, reconexión, regeneración, consumibles, rollback y sesiones
reemplazadas. Deben revisarse especialmente heridas mayores que el máximo reducido,
curación en ese estado y máximos temporales de combate. La migración todavía no
está cargada en el servidor; no se declara el issue resuelto.

## Heridas mayores que el máximo reducido

La curación reduce primero la herida canónica; el HP emitido siempre se deriva
del resultado, incluso si parte de la curación queda oculta por el mínimo de un
HP. Ejemplo: máximo60, herida100, HP1; curación55 deja herida45 y HP15, no HP56.
Al reconectar se mantienen esos mismos15 HP. Regeneración usa una línea base de
herida y tiempo, sin sobrecontar ticks ni descartar fracciones. La migración
sincroniza esa línea base al reiniciar la regeneración; avanzar `last_at` no la
reinicia. Esta política explícita requiere aceptación mediante regresiones.

## Carga y gate PostgreSQL

La imagen se reconstruyó y `world` se recreó en Docker local. El entrypoint
aplicó007; PostgreSQL acredita versiones1–7. Compose marca `world` healthy y
`/health` devuelve `ok=true,storage=postgresql`. Audiluna conserva60/60 HP,
herida0 y muertefalse.

Luna ejecutó las seis suites dirigidas juntas: `test_builds`,
`test_build_capacity`, `test_health`, `test_health_tick_writes`,
`test_inventory_consumables`, `test_combat_health`: **50/50 pruebas**,
10.385s, en schemas PostgreSQL aislados con007. Cubren reversibilidad activa,
edición inactiva sin reiniciar regeneración, rollback, lease obsoleto, comida
con heridas ocultas, ticks fraccionarios, muerte y máximos temporales de combate.
Las pruebas y los archivos runtime modificados pasan `git diff --check`
dirigido. Sigue pendiente confirmar el ciclo de aptitudes en la interfaz.
