# 11. No se puede intercambiar con otros personajes

Intercambiar objetos y kamas entre dos cuentas con confirmaciones revisadas y transferencia atómica.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Solucionado parcialmente.** Aceptación del usuario2026-10-07 sobre imagen `3b80ca96`: cancelar desde el iniciador y rechazar desde el destinatario funcionan; kamas se actualizan inmediatamente; cancelación del intercambio activo correcta y estado conservado tras cambiar de personaje y reiniciar ambos clientes. Gate de imagen333 pruebas aprobado. **Retirar una cantidad parcial sigue sin funcionar visualmente**, incluso con la preferencia nativa y el arrastre indicados; el encoder12203/cantidad1 no acreditaba ese flujo UI. Retirar la pila completa sí funciona. El usuario considera ese detalle de baja prioridad y acepta continuar con otros issues; se conserva como limitación pendiente, sin pedir repetir ahora la prueba completa.

## Dependencias

0, 13, 22, 32, 34. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Suma de kamas y cantidades se conserva; una misma revisión requiere las dos confirmaciones actuales.

- [Contratos nativos, rechazo bilateral probado y transacción requerida](REVISION-RESPUESTAS.md).

## Contratos verificados — 2026-10-06

Nueva extracción del cliente instalado: cuI12538 entrega exchangeId y participante en dos i64 (16 bytes); cuH13535 entrega exchangeId, estado byte y dos identidades i64 (25 bytes). El consumidor chn construye la sesión y distingue las ramas0–4. El recorrido de los eventos locales de respuesta hasta12997 quedó confirmado en el cotejo posterior.

`server/wakfu_server/items/exchange_wire.py` prepara los codecs de solicitudes y estos dos carriers. La confirmación13406 conserva su contrato de un solo i64: la revisión de oferta debe gestionarse en el servidor. Pruebas automáticas delegadas; sin handlers ni transferencia de inventarios. Evidencia privada: trade-wire-extraction.json y trade-inbound-carriers.javap.txt en .runtime/local/review-continuacion-20261004.

Cotejo posterior: daR conecta dhI19106→coD12997 resultado0 (aceptar) y dhJ19851→resultado1 (rechazar); busy4 pertenece a otra rama y no se acepta como respuesta de invitación. Gate de codecs:7 pruebas OK en Docker, incluidas cantidades cero de edición12203 y offsets exactos. Los eventos internos RP/RS no son paquetes de red; aún falta identificar los carriers de contenido, disponibilidad y finalización.

Migración037 y `items/player_exchanges.py` preparan invitaciones persistentes para dos cuentas distintas, generaciones de ambas sesiones, bloqueo ordenado, aceptar/rechazar y outbox transaccional. El esquema conserva recibos y ofrece revisiones de publicación/confirmación. La revisión automática detectó y corrigió que una tercera identidad pudiera entrar en el intercambio: constraints diferidos ahora validan el par real y el estado. Gate PostgreSQL en curso. Sin transferencia de propiedad ni despliegue; no se pide prueba manual parcial.

Gate inicial:18 pruebas de codecs/invitaciones/ofertas de kamas/constraints OK y8 de migraciones PostgreSQL OK. Incluye caducidad, cancelación con contraparte desconectada, carreras y rollback. Posteriormente se añadieron ofertas de objetos y catálogo completo: verificación ampliada pendiente.

Catálogo nativo reproducible mediante `sniffer/java/ExportAllItemExchangeMetadata.java`:20230 registros exportados y cargados, cero errores;82 criterios EXCHANGE denegados (False/Faux),17201 referencias NOT_BOUND y3029 vinculadas al recoger. `exchange_rules.py` evalúa criterio y vínculo; referencias/expresiones desconocidas no adquieren permiso. `inventory_item_bindings` conserva estado porUID; `offer_item` valida propiedad, cantidad y equipo de todas las builds antes de registrar una oferta, sin mover ni consumir unidades. Los cambios de objetos/kamas invalidan ambas confirmaciones. Pruebas nuevas delegadas.

Consumidor central cho identificado: contenido13636/12034, retirada13084/13720, kamas13412, disponibilidad13486 y cierre12235. El byte de contenido es resultadofbW, no tipo de objeto. Los objetos se representan mediante vj binario, no item protobuf. Se cotejan variantes y dominio de identidad del participante antes de conectar el dispatcher; confirmación bilateral y transferencia atómica siguen pendientes.

## Transferencia bilateral en fuente — 2026-10-06

Gate anterior ampliado:33 pruebas OK (codecs, catálogo, ofertas, lifecycle y migraciones). Ahora `confirm` exige la revisión publicada actual; la segunda confirmación ejecuta ambos inventarios, ambas wallets, recibo único y outbox en una transacción. `exchange_transfer.py` calcula capacidad tras retirar ambas ofertas, conserva UID de unidades completas, asigna UID nuevo a splits y solo fusiona stacks con metadata idéntica. Captura y restaura metadata de elementos, vínculos y monturas sin reinicializarla. Retirada múltiple13113 es atómica. Secuencia de entrega separada de revisión permite publicar estados de listo sin cambiar la oferta aceptada.

Gate aislado PostgreSQL: **51 pruebas OK**, incluyendo commit único concurrente, conservación, capacidad, rollback, snapshots hidratados y metadata de unidades divididas. Gate posterior de snapshots: **49 pruebas OK** con cobertura solapada, no sumable al anterior. `exchange_snapshot.py` calcula diferencias de cantidades y publica ambos estados de confirmación después de todo el contenido. `exchange_inventory.py` prepara retirada de representaciones anteriores e inserción del inventario SQL con ProtoItem completo; sus pruebas detectaron y corrigieron el rechazo de la mochila básica con referencia0.

Gate conjunto posterior: **61 pruebas OK** en PostgreSQL aislado (25,492 segundos), incluyendo cuatro regresiones de reconciliación: fixture cwP byte por byte, candidatos UID anteriores/posteriores/ofrecidos, rechazo de snapshots ajenos y conservación de ProtoPet en inserciones12471 y registro13078. Este gate incluye las pruebas anteriores; los totales no se suman.

Carrier de monturas: vj representa los datos básicos, sin campo ProtoPet; al cerrar se restaura el estado completo por12471 y13078. El codec admite monturas válidas, manteniendo la elegibilidad nativa y la cantidad unitaria. Gate posterior wire/inventario/snapshot: **21 pruebas OK**, incluida conservación del estado original y rechazo de cantidad2. Cobertura solapada con los gates anteriores.

Dispatcher delegado en preparación; ningún cambio de intercambio está desplegado todavía. No se presenta esta verificación de fuente como aceptación completa del juego, ni se solicita una prueba manual parcial.

Protección frente a combate: `_lock_pair` consulta participantes en `placement`/`active` después de bloquear ambas sesiones y personajes, con el mismo orden que la entrada a combate. Rechaza invitaciones y confirmaciones sin modificar ofertas, recibos ni inventarios; estados `finished`/`aborted` no bloquean. Solo se consulta el registro durable: no se modifica el motor de combate. Gate final de esta etapa: **70 pruebas OK** en 28,631 segundos; comando dentro de Docker con PostgreSQL aislado y fuente montada:

```sh
python3 -m unittest test_exchange_inventory test_exchange_snapshot test_exchange_rules test_exchange_wire test_player_exchanges test_mount_codec test_postgres_migrations -q
```

`py_compile` y `git diff --check` también pasan. Este gate sustituye los totales anteriores para esta etapa; todavía falta integración del dispatcher y verificación del flujo completo.

Integración posterior en fuente: `exchange_dispatch.py` autentica ambas sesiones, serializa por intercambio y entrega outbox por revisión/secuencia. `local_game_server.py` conecta los ocho opcodes nativos y añade limpieza/entrega periódica. Se conserva `canceled_by` y la lista de UID ofrecidos dentro de la transacción de cancelación, antes de eliminar membresías, para restaurar ambas pantallas correctamente. Pruebas del dispatcher en PostgreSQL aislado y revisión de reintentos en curso. El runtime sigue en la imagen previa: **sin despliegue ni prueba manual solicitada**.

Cotejo de productores UI cKq/daP:13037 añade la cantidad arrastrada y12203 retira la cantidad arrastrada; ambas solicitudes llevan deltas, no totales acumulados. El dispatcher usa operaciones `add`/`remove`, calculadas dentro del bloqueo transaccional. Retirar más de lo ofrecido o delta0 se rechaza sin mutación. Los codecs conservan el layout nativo incluso cuando una cantidad debe ser rechazada por la autoridad. Pruebas de esta corrección y del caso de ACK SQL confirmado cuya respuesta se pierde siguen en curso.

Gate integrado posterior: seis pruebas del dispatcher OK y63 del conjunto de intercambio OK (28,068 segundos; suites solapadas). Se comprueba transferencia y reconciliación bilateral, cancelación, pérdida de ACK antes/después del commit, fallo parcial de envío y reemplazo de generación. La recuperación de ACK confirmado actualiza el snapshot local sin repetir paquetes aditivos; el destinatario con entrega pendiente recibe sus deltas en orden.

Imagen construida `wakemu-exchanges:20261006`, SHA `de6358a25f76404c2064cb327916a29a821208eae005fec8f71c4795a43be22f`. Gate amplio de imagen **en ejecución**, sin montar fuente, protocolos ni migraciones. **No desplegada todavía.** [Prueba general preparada](PRUEBA-GENERAL.md); no solicitarla hasta terminar la verificación y preparar ambos saldos.

Despliegue posterior confirmado: gate amplio **223 pruebas OK** en115,790 segundos, sin mounts de fuente/protocolos/migraciones. Se corrigieron tres fixtures antiguos conservando sus assertions y se repitió el gate completo. La imagen indicada está cargada, SQL037 aplicado, Docker healthy y listeners15556/15558 activos. Hashes de seis archivos principales del runtime coinciden con la imagen probada. Backup previo privado conservado. Audiluna y Prueba Oficios: saldo de prueba preparado de0 a100 kamas por cuenta. [Prueba general lista](PRUEBA-GENERAL.md); pendiente del usuario.

Prueba manual posterior **fallida**: rechazo/cancelación de invitaciones no cierra ambas pantallas; la resincronización emite pérdidas de todos los objetos y las cantidades/saldos visibles no se actualizan. SQL acredita recibo4: cuatro semillas transferidas mediante UID dividido, residual2 y receptor4; saldos de cuentas93/107. No se detecta pérdida durable en ese recibo. Cotejo nativo confirma que12235 cierra intercambios activos, mientras13535/status2 cancela invitaciones; la cancelación guarda ahora su fase anterior en el outbox.

Corrección posterior **solo en fuente, no desplegada**: sustituir reconciliación masiva12919/12471 por13713 formatoBAGS35 y13078 registro completo con ProtoPet. Las retiradas12919 notificaban selfDrop y producían los avisos observados. Para el recibo, usar12753/cye con saldo absoluto: chS aplica `foF.tR` al modelo de cartera ya instalado y notifica sus observadores.13021/chW es bootstrap: crea y registra otro `foF`, por lo que no refresca referencias de UI existentes.13873 mantiene la caché de sincronización. Nuevas regresiones delegadas antes del siguiente despliegue. No repetir todavía la prueba manual anterior.

Actualización vigente: lo anterior quedó desplegado en `wakemu-exchanges-professions:20261007`, SHA `3805039015f0aead5d8b943214a251fdf50cfd1ce281321c36b5b87cfdb3042f`. Gate completo de imagen302 pruebas OK en130,644s, sin montar fuente/protocolos/migraciones; health y listeners confirmados. Incluye tests de respuesta tardía, permisos del iniciador/destinatario, cancelación concurrente y decodificación del inventario/ProtoPet/saldo. Backup previo privado conservado. Los204 módulos de combate tienen idéntico hash agregado frente a la imagen anterior. Prueba manual general preparada con retiro parcial nativo y saldos iniciales anotados, sin presuponer100 kamas.

Despliegue que sustituye al anterior: `wakemu-exchange-ui:20261007`, SHA `3b80ca965a7f222b7af301d0603e86ced766fce70def0ebbff991001be5b0c36`;333 pruebas OK en157,954s sobre imagen sin fuente/protocolos/migraciones montados. Health y listeners15556/15558 confirmados; cuatro hashes críticos del runtime coinciden con la imagen. Backup privado previo conservado. Los204 módulos de combate siguen idénticos. Captura real12997/result1 y cartera12753 incorporadas en pruebas; manual pendiente.
