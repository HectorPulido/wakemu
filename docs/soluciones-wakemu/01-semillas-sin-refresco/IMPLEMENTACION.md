# Issue1 — Semillas y extracción repetida

## Cooldown en implementación

La migración008 añade `settings.monster_harvest`: `quantity=1`,
`cooldown_seconds=60`. Es una política local configurable, no una tasa oficial.
La cantidad exige entero1–32767; cooldown finito, positivo y máximo86400s.
Datos ausentes o inválidos rechazan la acción, sin fallback de entorno.

`Harvests.begin` lee la política PostgreSQL y consulta la disponibilidad antes
de crear ocupación. `complete` vuelve a comprobarla bajo advisory lock
por mapa/instancia/criatura/acción. La entrega y el recibo se confirman juntos.
Dos completados concurrentes no pueden entregar la misma disponibilidad;
cancelaciones, inventario lleno y rollback no gastan el cooldown.

El ticket congela la política de inicio: modificar la configuración no cambia
una operación en curso. Las nuevas solicitudes usan la política actual y vuelven
a comprobar los recibos persistidos antes de crear ocupación. Los recibos existentes preservan cooldown tras reinicio.

El dispatcher ya no fija `quantity=1,cooldown_seconds=0`; toda la política
procede de PostgreSQL. El cotejo previo del ACK resultó incorrecto:12954 solo muestra el mensaje de
pérdida. La plantación ahora emite12470(uid,-1) después de13135/12954 cuando
la transacción aplica el consumo. Repetir el resultado devuelve paquetes vacíos.

## Evidencia pendiente

Luna prepara regresiones PostgreSQL de disponibilidad inicial/final, fronteras,
concurrencia, cancelación, scopes, configuración inválida y reconexión.008 aún
no está cargada. La reproducción visual de plantar y refrescar cantidades sigue
pendiente y es necesaria para cerrar el issue completo.

## Reproducción real de la cantidad desactualizada

Audiluna (cuenta audit2, personaje1) recibió5 semillas1752. Las operaciones
registradas entre02:12:17 y02:12:32 UTC consumieron cuatro; SQL mostraba1
mientras `41-seed-hotbar-drop.png` conservaba5 en inventario. Otra operación
confirmada agotó la pila y dejó cinco recibos; el cliente seguía mostrando5.
Las capturas privadas están en `.runtime/local/audit-postgres-visual/`.
El bytecode privado `seed-inventory-bJt.javap` acredita el mensaje sin mutación;
`seed-planting-cYt.javap` acredita el avance de objetivos. No se editó el cliente.

## Gate y carga del servidor

Luna verificó conjuntamente `test_monster_collect`, `test_live_console`,
`test_postgres_store_auth`, `test_planting`, `test_planting_runtime` y
`test_inventory_resync`: **61/61 pruebas**,13.509s. Comprueban UID/delta-1,
última unidad, cancelación y replay sin paquetes; política en DB, fronteras de
cooldown, scopes, reinicio, política congelada y concurrencia de dos recolectores.
La imagen se reconstruyó y `world` se recreó. PostgreSQL acredita versiones1–8
y la política de extracción cantidad1/cooldown60. La comprobación GUI posterior
al cambio está pendiente; no se declara cerrado el issue.

## Refresco real confirmado

En la misma conexión de Audiluna, una plantación completó a02:50:13 UTC del6deoctubre: SQL pasó de5 a4 semillas de trigo. La captura privada `81-plant-attempt.png`, inspeccionada por root antes de cualquier reconexión, muestra «Has perdido1x Semilla de trigo» y el acceso rápido con cantidad4. La captura77 tenía cantidad5. Esto acredita el delta12470 inmediato y corrige el síntoma original. La comprobación gráfica del cooldown de extracción de semillas de monstruos sigue pendiente; su política y concurrencia están cubiertas por las61 pruebas previas.
# Prueba manual posterior: extracción y apilado

El usuario verificó0→1 semillas, rechazo inmediato durante regeneración y1→2 tras esperar. Los recibos reales de personaje1/Tofu muestran acción180 y referencia7358; acción9 entrega plumas2254 y no debe confundirse con semillas. El cooldown es funcional, pero quedaron dos defectos: mensaje técnico en inglés y nuevas semillas en dos slots/UIDs diferentes.

En fuente, `Harvests.complete` busca un stack compatible en el bolsillo base, respeta el máximo del catálogo y conserva UID al incrementar mediante12470 positivo. Si el bolsillo está lleno pero ese stack admite la cantidad, no exige un slot libre. El recibo y la cantidad se confirman en la misma transacción. Gate y despliegue de esta ampliación pendientes. No consolida retrospectivamente los dos stacks que ya existen.

Contrato nativo de disponibilidad cotejado:13421 (`cyg`), i64 ID del NPC + i32 acción + bool. `cFc` resuelve el NPC `bje` y su set de acciones deshabilitadas; el consumidor de recursos consulta ese mismo objetivo. Un probe con dos NPC confirmó aislamiento. Para esta prueba corresponde acción180; debe deshabilitarse al completar y restaurarse al vencer, incluido bootstrap/reconexión y observadores. Encoder añadido, integración todavía pendiente. El rechazo autoritativo del servidor se conserva frente a clientes modificados.

La ampliación de apilado pasó **17/17 pruebas PostgreSQL** de `test_monster_collect`: UID estable/12470 positivo, bolsillo lleno con stack disponible, stack máximo/nuevo slot y rollback si falla el recibo, sin avanzar la secuencia al hacer merge. Disponibilidad integrada después en fuente: publicación13421 a mapa/instancia tras commit; un drenaje global reabre acciones al vencer; snapshot de recibos/política PostgreSQL restaura acciones bloqueadas después de publicar NPCs al entrar. El camino rápido no consulta SQL en cada paquete. La excepción tipada de regeneración corrige un menú obsoleto con13421, sin publicar el mensaje técnico en chat. Gate de esta última integración y despliegue aún pendientes; los17 tests anteriores no certifican estos cambios nuevos.

## Despliegue del 6 de octubre: apilado y disponibilidad

Gate actualizado: **43 pruebas OK**, recolección, migraciones, cleanup y deadline de colocación. La migración011 persiste `regenerates_until`: cambiar la política no adelanta un cooldown existente; tickets nuevos adoptan la política nueva. El respawn vuelve a publicar disponibilidad después del NPC. Docker world quedó healthy con imagen `3b33b876b3bc4e91b0906eda8d7d36abf98d77aafc61e07c688354a0bd2f2f31`; startup aplicó010 y011 y la consulta confirmó cero recibos sin deadline. Apilado/disponibilidad cargados, recorrido visual posterior pendiente. Los dos stacks antiguos no se fusionan automáticamente.

## Validación manual después del despliegue

El usuario confirmó recolección, botón nativo deshabilitado con «Recolectado recientemente», recuperación tras65 segundos y segunda extracción. Ambos recibos del Tofu `-2192249442565077268`, acción180, completaron a05:32:19 y05:33:27 UTC usando el mismo UID1099511628100. Cada deadline quedó60 segundos después de completar. La captura muestra stack3 junto al stack1 que existía antes del parche: las dos semillas nuevas se añadieron al primero; no apareció un UID nuevo. Una consulta posterior muestra solo ese UID, cantidad4/slot1; no se atribuye la consolidación posterior al parche porque no fusiona stacks antiguos automáticamente. El usuario confirmó explícitamente que el cooldown funcionó bien. Esto acredita la ampliación de apilado y disponibilidad visual, además del refresco de plantación previamente probado.
