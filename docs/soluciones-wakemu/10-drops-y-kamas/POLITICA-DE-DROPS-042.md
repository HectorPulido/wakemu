# Política de drops de combate, migración042

## Fuentes y alcance

Los objetos, probabilidades, cantidades, filas, valores `roll_count` y condiciones salen de `server/protocol/monster-encyclopedia.json.gz`, exportado de las tablas nativas instaladas. El planificador no consulta drops Dofus ni convierte referencias entre juegos. Para `Sombrero de jalató`, el catálogo Wakfu mantiene cinco filas independientes: referencias de monstruo1,2,3,39,41; probabilidad base exacta `0.008` (0.8%); `roll_count=-1`; cantidad1; sin condición; `native_csE=-1`; `native_csF=0`.

La mecánica numérica toma como referencia de implementación el código local de Starloco leído en modo solo lectura: `Fight.java` prepara filas por enemigo no invocado, calcula el multiplicador por jugador y compara el azar con `drop.getLocalPercent() * max(1, getPros()/100) * conquista * desafío * estrellas * rateDrop * bonusBrecha`. `Fight.java` deja la probabilidad sin limitar antes de compararla con `Math.random()*100`, por lo que un umbral mayor de100% garantiza el éxito. La comparación usa `<`, no `<=`. No se importan objetos ni tasas de la tabla Dofus.

La conversión respeta la diferencia de stat: Wakfu stat33 `PROSPECTION` tiene valor nativo inicial0 y se interpreta como bonus; PP efectivo es `100 + bonus`. Por eso bonus0 produce el piso de1x de la función Dofus, mientras que bonus50 produce1.5x. El bonus nativo se guarda separado del PP efectivo.

La rutina Dofus para desafíos acumula bonus ganados, aplica un mínimo de1 y luego suma ese porcentaje a1. En esa fuente el caso sin desafío termina en1.01x. El planner mantiene ese comportamiento de referencia exacto; no redondea el porcentaje base de Wakfu ni trunca el resultado. Los factores de conquista y brecha se reciben por argumentos explícitos en basis points, actualmente con default1x; el caller debe suministrar contexto autoritativo si llega a usarlos. Migración042 aporta `drop_rate_bp` versionado, inicializado en10000 (1x). No cambia el cliente ni el porcentaje mostrado por la enciclopedia.

## Tiradas, filas y condiciones

`roll_count <= 0` produce un intento por jugador, conforme al sentinel nativo descrito por la UI; un valor positivo produce ese número de intentos. Cada fila conserva su índice de origen. Las filas repetidas idénticas no se agrupan ni descartan: se resuelven como identidades de fila distintas, con sus intentos por jugador. Esta es una política explícita de adaptación, apoyada en la estructura de filas nativas y en el modelo de Dofus `Fight.java`, que copia las filas del pool para cada ganador; la UI Wakfu sí agrupa entradas visualmente, pero eso no acredita un pool servidor. El catálogo actual contiene 55 grupos duplicados exactos en 50 monstruos, es decir, 99 filas adicionales sobre el deduplicado; siete de esas filas adicionales no tienen condiciones y las restantes están condicionadas por Stasis o Stele. La cantidad se elige uniformemente en el rango inclusivo de cada fila. El azar se representa como un entero uniforme de53 bits; la tasa y la comparación usan `Decimal`, sin conversión binaria ni truncado. Solo el umbral de comparación se limita a1; se guarda también la probabilidad sin limitar.

Las condiciones simples acreditadas se comparan contra campos del contexto del combate: mazmorra, Stasis, oleadas infinitas, downscaling, Stele y score. Si el campo necesario no está presente, la fila no es elegible. Criterios complejos y tablas externas se excluyen porque este workspace no tiene acreditado un evaluador servidor para sus expresiones/enlaces. `native_csF` se conserva y se compara como mínimo de prospección; todas las16138 filas nativas actuales tienen valor0. `native_csE` (`m_rollMax`) se conserva en receipt, pero no se usa para limitar intentos: se acreditaron el campo, su copia al getter `fqG.csE()` y su representación; no se encontró consumidor que determine su unidad, ámbito o reinicio. El contraste Dofus documentado es un filtro de elegibilidad del pool por prospección total, no evidencia para interpretar el rollMax Wakfu. No se crean pools compartidos ni se deduplican filas automáticamente.

La fórmula no trunca el azar ni el porcentaje. La semilla/valor del draw de53 bits, probabilidad base, probabilidad calculada, umbral efectivo, rango de cantidad y resultado se guardan por jugador/monstruo/índice de fila/índice de intento. El mismo ledger permite mostrar el resumen y entregar el objeto sin volver a tirar.

## Persistencia y transacción

`combat_drops.resolve(store, db, ...)` recibe una conexión dentro de una transacción activa. Requiere el receipt `fight_rewards` ya creado para el personaje ganador, verifica sesión/cuenta/personaje, congela la política versionada y persiste el batch y cada intento. Debe llamarse después del receipt de victoria y antes de confirmar esa misma transacción. Una excepción revierte XP/kamas y drops juntos. Repetir el mismo fight/personaje devuelve el batch persistido, aun si luego cambia la política.

`report_loots(batch)` produce la forma `FightLoot` de `FightReport` para los éxitos; `delivery_items(batch)` ofrece claves estables a la capa de inventario. Esta migración no entrega los objetos ni cablea el resumen: la capa de inventario/temporal debe consumir estos recibos dentro de la misma transacción y el caller debe derivar el reporte del batch confirmado.

## Límites

- Las condiciones complejas y tablas externas permanecen fail-closed.
- No hay conexión de la API con `combat_lifecycle`, `local_game_server`, inventario, inventario temporal ni `FightReport` en esta fase.
- El significado y el ámbito de `m_rollMax` siguen sin estar demostrados; en particular, `1` no se interpreta como cap por fila, enemigo, jugador o pelea.
- El umbral Dofus de prospección grupal `drop.ceil * rateProspectThreshold` no se copia: no es equivalente a `m_minProspection`, y el catálogo Wakfu observado tiene mínimo0 en todas las filas.
- Los factors de desafío/conquista/brecha carecen todavía de productores Wakfu autoritativos en el runtime; 042 conserva defaults explícitos (rateDrop1x) y el caller debe evitar inventar valores.

## Verificación

Los tests `server/tests/test_combat_drops.py` cubren probabilidad0/1, umbral exacto para el0.8% nativo con factor de desafío de referencia, piso/bonus de prospección, cap comparativo, condiciones, cantidades, filas repetidas conservando índice y tirada por jugador, shape del resumen y replay transaccional con cambio de política.
