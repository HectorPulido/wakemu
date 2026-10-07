# Cobertura del catálogo de drops instalado

Revisión directa de `server/protocol/monster-encyclopedia.json.gz` y bytecode de `client/lib/wakfu-client.jar` (repetida el 2026-10-07 contra el consumidor de la enciclopedia y todas las clases del JAR que contienen `csE`).

- 16.138 filas de botín de monstruos; 686 llevan `complex_criteria=true` y el resolver las rechaza conservadoramente.
- Ninguna de las 16.138 filas tiene `is_loot_table=true`. Existen 2.204 tablas externas exportadas, pero su existencia no acredita una dependencia de estas filas de monstruos.
- `native_csE` (`m_rollMax`): 14.795 filas con −1 y 1.343 con 1. El cargador `bbo` pasa `aMf.csE()` a `fqH.gF(byte)`, y `fqG.csE()` devuelve el byte guardado. El análisis de las clases del cliente encontró el getter en la representación `bld.toString`, pero no un consumidor de tiradas que limite premios. La UI `brq` sí consulta probabilidad, referencia y marca de tabla; no llama a `csE`. Se conserva en el recibo y no se usa como cap porque unidad/alcance/reset siguen sin contrato acreditado.
- Condiciones nativas presentes: MIN_STASIS_LEVEL (3.069), CAN_BE_LOOTED_IN_STELE (634), MIN_SCORE (268), ONLY_IN_DUNGEON (212), NOT_IN_DUNGEON (177), ONLY_WHEN_DOWNSCALED (160), NOT_IN_INFINITE_WAVES (134). Contar condiciones no prueba que el contexto de cada combate esté completo.

El bytecode acredita `aMf.csH → ble.gq → bld.csH`. El consumidor `brB.dIp` devuelve la etiqueta `loot.client.criterion.complex` cuando el booleano está activo; en esa rama no presenta la lista legible de `csG`. De las 686 filas con el flag, cinco también exportan una condición simple (MIN_STASIS_LEVEL), pero la marca continúa activa y el catálogo no aporta la expresión completa que esa etiqueta resume. El resolver conserva el rechazo para las 686: conocer una condición enumerada no demuestra que sea la única.

La exportación contiene siete enum names de condición en las filas observadas; enum IDs `NOT_ALREADY_KNOWN` (6) y `ONLY_ON_NEO_SERVERS` (8) están definidos por el cliente pero aparecen cero veces en las 16.138 filas actuales. No se extrapolan desde su existencia en el enum.

`bbo` convierte `aMf.csE()` (short) a byte antes de `fqH.gF`; aunque se buscó el método en todas las clases instaladas que contienen el símbolo, no apareció un ejecutor de sorteos que determine si el límite corresponde al grupo o al jugador. La validación de un Mimic garantizado y sus recibos no cierra esa semántica. La siguiente prueba del sistema debe incluir dos propietarios y una fila con límite1 solo después de identificar esa regla nativa.

Comandos de inspección: `javap -classpath client/lib/wakfu-client.jar -p -c aMf`, `bbo`, `ble`, `bld` y `brB`. Investigación sin cambios a probabilidades, tasas SQL ni cliente.
