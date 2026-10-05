# Intercambio: contratos nativos y propiedad

## Solicitudes acreditadas

Se ejecutaron encoders nativos con identidades sintéticas, conservando frame y payload. `daP` es el consumidor de eventos de UI de intercambio; usa mensajes distintos del movimiento ordinario12804.

| Opcode/clase | Cuerpo comprobado | Uso cotejado |
| --- | --- | --- |
| 13140/coE | i64 identidad destino | Solicitud dirigida; falta cotejar invitación/respuesta completas |
| 13037/coA | i64 UID objeto, i64 exchange_id, i16 cantidad | Oferta de objeto desde evento UI |
| 12781/coH | i64 exchange_id, i64 kamas | Cambio de kamas ofrecidos |
| 13406/coI | i64 exchange_id | Validación desde UI; no lleva revisión de oferta |
| 12027/coC | i64 exchange_id | Cierre desde evento UI; causa de cierre requiere cotejo |
| 13113/coB | i64 exchange_id, i32 cantidad, lista i64 UIDs | Retirada de objetos; layout leído, fixture aún pendiente |
| 12203/coF | i64 UID, i64 exchange_id, i16 cantidad | Edición de cantidad; layout leído, fixture aún pendiente |

Fixture13037: UID67890, sesión456, cantidad2. **El UID precede a exchange_id**, a diferencia de12781. No compartir un parser suponiendo que todos empiezan por exchange_id. Los opcodes anteriores no tienen handlers en el dispatcher actual; tampoco ramas específicas en `protocol_codec.py`.

## Restricciones del objeto

`daP.bD(fnR)` consulta `fnR.ggY()` y criterio `fpC.a(fnE.sGH)`; se ejecutó el enum y `sGH` es **EXCHANGE**. También aparece exclusión explícita de objetos procedentes de compañero. Estos controles de UI no sustituyen el servidor. Falta resolver semántica de `ggY`, persistencia/evaluación del criterio y restricciones por objeto; no se afirma que todos los objetos del catálogo sean transferibles.

## Prueba de inventario actual

SQLite temporal exclusiva, dos cuentas/personajes, objeto2021 cantidad1 en bolsa propia. Intentar12804 hacia bolsa del segundo personaje devuelve `Foreign item/container or unsupported container type`. Estado completo de ambos personajes idéntico antes/después, UID/propietario/cantidad conservados. [Resultado ejecutado](probe-inventario-bilateral-rechazado.json).

`inventory_move.transfer` solo selecciona origen/destino/objeto bajo un character_id y valida una sesión. Es correcto para movimiento propio; no permite consentimiento ni transferencia entre cuentas. Su transacción SQL no acredita una transacción bilateral.

## Solución concreta exclusivamente del servidor

Crear autoridad de sesión de intercambio con dos propietarios/generaciones, estado de invitación y oferta aceptada, UIDs/cantidades/kamas y revisión interna. Cada cambio de oferta invalida **ambas** confirmaciones.13406 solo envía exchange_id: la revisión no se puede inventar dentro de su paquete; el servidor debe registrar a qué oferta corresponde cada aceptación y publicar invalidación nativa, cuyo carrier aún falta cotejar.

Reservar objetos/kamas contra el resto de operaciones —mover, equipar, plantar, gastar— o revalidarlos bajo los mismos locks antes de commit. `inventory_move` no debe aceptar bolsas ajenas para facilitar el intercambio. Al confirmar ambos, validar las dos leases vigentes y la misma oferta; planificar espacios/merges de ambos inventarios considerando también lo que sale; comprobar criterios EXCHANGE y cantidad real. Una falta de espacio en un lado revierte toda la transferencia.

Commit bilateral en una única transacción de la autoridad durable elegida: débito/crédito de kamas, cambios de propietario/cantidad, espacios y recibo de exchange_id/revisión. Conservar UID y metadata al transferir un objeto entero; al dividir, reservar UID nuevo y preservar sus propiedades. No reconstruir un objeto por referencia como si fuera un grant nuevo. No mezclar SQL viejo con inventarios/wallets pendientes de Redis; la frontera con journals debe quedar acreditada antes de implementar.

Publicar resultados a ambas partes después de commit. Retry o caída tras commit recupera el recibo, no vuelve a transferir. Cancelación antes de commit libera reservas; después de commit no revierte un lado. No mutar wallets en dos llamadas separadas y anunciar éxito antes de confirmar ambos inventarios.

## Evidencia pendiente que impide cierre

Invitación/aceptación/rechazo completos, snapshot y deltas de oferta, invalidación de confirmaciones, cierre y resultado; requisitos exactos de distancia/mapa/combate; metadata de objetos ligados/compañeros; integración SQL/Redis; intercambio real con dos clientes incluyendo cancelación y disconnect. No se afirma reproducción end-to-end. [Frames sintéticos y hashes](probe-contratos-intercambio.json).
