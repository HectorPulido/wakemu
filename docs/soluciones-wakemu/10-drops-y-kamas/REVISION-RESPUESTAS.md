# Revisión de respuestas — drops y kamas

## Lo acreditado actualmente

`combat_rewards` declara y cumple que **no genera loot**. Solo persiste XP y kamas de una política de importes fijos; `kamas` tiene default0. El wallet es por cuenta (`account_wallets.account_id`), mientras XP es por personaje. La actualización de ambos y el recibo se realiza dentro de `BEGIN IMMEDIATE`. No hay un servicio de tiradas, asignación de objetos o entregas pendientes en esa transacción.

La prueba actual de [recibos](../09-experiencia-de-combate/probe-recibos-y-generacion.json) conserva17 kamas al repetir una petición bajo la misma generación, pero alcanza34 al premiar el mismo Fight bajo otra generación. Es una prueba del servicio con SQLite desechable, no de recuperación real ni de un exploit. Aplicar la identidad durable de combate descrita en [XP](../09-experiencia-de-combate/REVISION-RESPUESTAS.md).

`return_to_world` envía13021 con i64 de wallet y13873 con el estado de kamas de cuenta. Es posterior al callback12925. La desconexión entre commit y callback requiere restaurar el wallet persistente al login; no volver a concederlo. El resumen muestra `gained_kamas` del recibo, no el saldo total.

## Datos y transacción que faltan

La fuente existente es `server/protocol/monster-encyclopedia.json`, extraída por `ExportMonsterEncyclopedia.java`: contiene referencias de monstruo e ítem, probabilidad, cantidades, tiradas y condiciones. Se corrigió la omisión de revisar este catálogo y el código Dofus indicado por el usuario. Véanse [FUENTES-Y-CONTRATO-LOOT.md](FUENTES-Y-CONTRATO-LOOT.md) y [FORMULAS-DOFUS.md](../09-experiencia-de-combate/FORMULAS-DOFUS.md). Versionar la política derivada de esas fuentes, sin inventar relaciones desde el catálogo de ítems.

Congelar los enemigos, participantes y modificadores en el resultado del combate. Registrar cada tirada y la lista final una sola vez por `fight_uuid`/participante. El multiplicador de drop debe aplicarse explícitamente a probabilidad, con clamp a10000 en una escala0–10000, sin multiplicar además cantidades por accidente. Esta política es propuesta, todavía no una reproducción acreditada de Dofus. Los multiplicadores de Stasis comprobados en29 se añaden según su contrato, sin sustituir ni duplicar el factor global.

Por cada resultado crear una entrega durable con UID, referencia, cantidad y propiedades finales. En la misma transición confirmar el recibo y el saldo de kamas; la posterior colocación en inventario es recuperable. Si no cabe, conservar `pending_delivery` y comunicarlo: jamás borrar el premio ni sobrescribir un slot. Usar una clave única de entrega para que reclamar/reconectar no regenere UIDs o propiedades. Validar equipo por unidad y su identificación según22, sin apilar equipos con estados incompatibles.

## Comprobaciones aún necesarias

Fuentes de loot, fórmulas de referencia y contrato del detalle nativo ya fueron localizados y cotejados; el fixture12755 con Esquirlas×3 pasa el parser nativo. Faltan integrar ese contrato, resolver condiciones complejas y semántica de filas repetidas, política original de inventario lleno, compatibilidad con Redis, tiradas reproducibles y entrega real con dos clientes. Probar crash antes y después del commit, inventario lleno, overflow, desconexión antes12925 y dos personajes de una misma cuenta para no acreditar el wallet dos veces. Los cinco tests de recompensas aprobados no cubren esos casos. No se implementaron cambios.
