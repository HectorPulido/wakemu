# 28. Bonus de área

> Current release2026-10-11: complete shared World/AI/ecology/admin deployed and automatically verified. Migration123; stable window released08:07 UTC. [Deployment evidence](../../reports/SYSTEMS-DEPLOYMENT-20261011.md). Graphical acceptance remains pending; any earlier prepared/not-deployed wording below is historical. Native planting bonus stays disabled pending its separate native-display acceptance.


Aplicar y retirar los efectos del territorio con reglas nativas verificadas y sin acumulación duplicada.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md) · [Contratos y límites](REVISION-RESPUESTAS.md)

## Estado actual

Hay código fuente para publicar población regional y para derivar el estado nativo del protector a partir de sus deseos y poblaciones por familia. El estado se calcula como `1917` cuando ningún deseo está satisfecho, `1915` cuando algunos lo están, y `1916` cuando todos lo están; sin deseos elegibles no se deriva un estado.

El catálogo compacto [territory-protector-bonuses.json](../../../server/protocol/territory-protector-bonuses.json) se genera con `python3 server/tools/export_territory_protector_bonuses.py`. Conserva efectos de `combat-state-definitions.json` y deseos de las tablas nativas `aMD/aME/aMF` exportadas en `monster-encyclopedia.json`, unidos por región a `ecology-regions.json`, con hashes de las tres fuentes. Se encontraron 105 territorios nativos; 101 se enlazan con un mapa/región y todos esos pares existen en el grid nativo de celdas. Los cuatro sin correspondencia quedan rechazados en vez de asignarles un mapa supuesto. `characters/territory_bonuses.py` comprueba los rangos inclusivos de población y deriva el estado y sus filas nativas. Sus pruebas dirigidas pasan 8/8.

`current_region()` ya obtiene el estado desde un snapshot completo de la instancia actual y falla cerrado si alguna entidad no puede ubicarse. Plantación y cosecha pasan el modificador nativo de XP de oficio a `profession_store.award`: primero se aplica el porcentaje territorial (`+10%`, `+30%` o `−10%`) y luego el multiplicador de cuenta. El recibo registra la XP resultante y el replay sigue sin emitir una segunda delta.

Los estados territoriales también derivan Sabiduría `36` y Prospección `33` en el snapshot de stats del actor de combate: `+30/+60` para estados 1915/1916 y `−10` para 1917. Se calcula de nuevo desde el territorio del personaje al crear el actor y se añade como modificador no persistente a `equipment_stats.bonuses`; no se acumula entre llamadas. El carrier de combate existente publica esos valores en el actor y las fórmulas de recompensas/drops consumen su `effect_stats`.

No se encontró un carrier nativo verificado para refrescar esas dos estadísticas en la UI de personaje fuera de combate al entrar/salir de región; no se envía un opcode inventado. Tampoco se ha ejecutado una comprobación GUI de esa transición. Ese refresco visual queda pendiente.

El cotejo del catálogo/JAR precisa la frontera: `12789` (`cuE`) sí actualiza la satisfacción del protector/ecosistema y sus propiedades de presentación mediante `chl`, pero no es una modificación de características del jugador. `12847` es bootstrap de actores dentro del combate; `13912` sincroniza efectos de combatientes ya registrados en una pelea; `13613` es ganancia XP/hechizos; `13713` refresca bolsas. Ninguno acredita el refresh de Sabiduría/Prospección ni el alta/baja de estados `1915/1916/1917` en el actor de mundo. Detalle y campos en [FALTANTES](FALTANTES.md).

## Efectos nativos recuperados

- `1915` (“al menos una voluntad”): efectos 94088/94089 (`+30` classes 166/162) y 94331/94332 (`+10` classes 2007/2008).
- `1916` (“todas las voluntades”): efectos 94090/94091 (`+60` classes 166/162) y 94329/94330 (`+30` classes 2007/2008).
- `1917` (“ninguna voluntad”): efectos 252635/252636 (classes 167/163, definidos como operaciones de pérdida) y 252637/252638 (`-10` classes 2007/2008).

El bytecode nativo `fwX.gA` usa solo tres casos: cero completados es “unsatisfied”, todos completados es “satisfied”, y cualquier valor intermedio es “half satisfied”. Los bytes 12789 y los modelos `bRT`/`bRU` publican y muestran poblaciones/progreso del ecosistema; no prueban por sí solos que el servidor aplique esos estados al personaje.

## Validación

Gate Docker fuente montada, esquema PostgreSQL aislado: `test_territory_bonuses`, `test_combat_actor_snapshot`, `test_combat_reward_context`, `test_profession_store`, `test_planting_runtime` y `test_resource_collect` → 84/84. Cubre límites, rangos inclusivos, conteos intermedios, región sin deseos, rechazo de mapas sin correspondencia, pertenencia al grid, snapshot incompleto, porcentajes de XP nativos y su orden respecto del multiplicador global, estadísticas 33/36 del actor, ausencia de acumulación, XP del recibo y regresiones de plantación/cosecha. No certifica refresco visual fuera de combate.

La población regional tiene cobertura aparte en [revisión de respuestas](REVISION-RESPUESTAS.md); esa cobertura no valida la aplicación de los efectos al personaje.


## Revalidación del despliegue — 7 de octubre

**Solucionado parcialmente.** El cálculo territorial está presente en r9: hash del módulo idéntico a fuente, attachment en dispatcher y XP de plantación/cosecha comprobados en el contenedor activo. Gate del dominio12/12 aprobado. Quedan carrier visual fuera de combate, TLS de transición y aceptación del sistema completo.

## Current implementation review — 2026-10-11

`territory_bonuses.refresh_world` now builds an exploration characteristic refresh using the existing native `13046` envelope, format 3, with `fightID=-1`. The payload contains complete owned public characteristics, including explicit native defaults, so leaving a satisfied region removes Wisdom/Prospection instead of leaving omitted zero values on the client. Actor direction, HP, equipment, aptitudes and active build remain authoritative. Derived regional values are never persisted or added repeatedly.

The dispatcher should invoke this helper in `send_planting_context`, independently of the weather-publication flag. Existing entry, transition and accepted-walk paths then refresh regional bonuses, including satisfaction changes within the same region. This source change does not establish deployment or graphical acceptance. Idle characters still need a subsequent context publication to observe ecological changes; combat uses its existing fresh entry snapshot.

Automated regression coverage was added for initial publication, unchanged snapshots, regional bonus removal, serialization retry, complete zero-valued characteristics, preserved direction and the exploration fight identifier. Execution is delegated to the validation agent; do not treat this paragraph as a passing test result.

Manual acceptance: open the characteristic panel and ecosystem panel together; record Wisdom/Prospection and regional wish satisfaction. Walk into a region with different satisfaction, then return, repeat twice and reconnect. Expected deltas are +30/+30 for partial satisfaction, +60/+60 for all wishes, and -10/-10 for none, relative to the same equipment/build baseline; regions without wishes contribute zero. No stacking, movement-direction reset, HP reset or combat transition should occur. Harvest/plant until satisfaction changes and move once: characteristics must follow the new state. Finally start and finish a normal fight and verify the exploration values remain correct afterward.

## Stationary refresh — 2026-10-11

Prepared, not deployed. A bounded ecology worker domain (`bonuses`, migration123) prepares complete regional populations outside gameplay locks. The owner session publishes native13046 from current character stats only outside combat and spectating, and acknowledges after successful delivery. Epoch, durable scope revision, generation, peer, location and fresh-context fences reject obsolete observations. Inline ecology uses the same producer. No unchanged-stat spam or repeated weather packets. Final integrated gate:80 tests passed, plus the updated15-test module including one-slot fairness and actual World projection fences. Coordinated deployment and graphical acceptance pending.
