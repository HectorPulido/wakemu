# Diagnóstico — recursos vegetales bloqueados como ajenos

## Causa comprobada

El servidor serializa `creation_time` en el campo 7 de 13135, que el descriptor nativo identifica como `ownerAccount`. La prueba ejecutada con el encoder real y el decoder nativo devuelve la fecha como identificador de cuenta. `cWn` compara ese valor positivo con la cuenta del personaje y puede devolver `RESOURCE_RESERVED` (`bOd.kEa`). Es un fallo común de publicación de recursos, no exclusivo de Cardo; el usuario confirma fresnos y otras especies.

[Bytes, cadena de consumidores y alcance](REVISION-RESPUESTAS.md) · [resultado reproducible](probe-propiedad-recursos.json).

## Segundo problema independiente

El cliente usa 12995 para la acción vegetal: `cWn` construye `cmC` con `zg` protobuf (action_id, x, y). `server/protocol_codec.py` sabe decodificarlo, pero el dispatcher de juego inspeccionado no lo maneja. La ruta existente 13481 es recolección de monstruos; no implementa recolección vegetal. Por eso quitar la falsa propiedad no basta para obtener cosecha, XP o cambio de etapa.

## Propuesta y límites

Mantener fecha y propiedad en campos separados; enviar propietario 0 para recursos públicos y completar el handler vegetal con validación y transición durable. No requiere parche del cliente. La prueba aislada acredita el contrato erróneo y el cotejo confirma la ausencia de handler; queda pendiente capturar el recorrido gráfico completo con Cardo, fresno y otra especie. No se han aplicado fixes.
