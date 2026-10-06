# Etapas y acciones verificadas contra datos nativos

## Fallo concreto del crecimiento

`PlantingRuntime.mature` consulta exclusivamente `stage=1` y cambia la planta a 2 si esa etapa existe. En ejecuciones posteriores, el recurso ya no entra en la consulta. No hay transición 2→3 ni 3→4. No es un problema de esperar más tiempo: el recurso queda fuera del mecanismo.

## Cardo como caso de control

La extracción ejecutada de los datos instalados para la referencia 60 devuelve lo siguiente. La semilla es 4275 y la profesión 72. [Resultado completo del probe](probe-etapas-nativas.json).

| Etapa | Acciones nativas | Producto de referencia |
| --- | --- | --- |
| 1 | 329 | Ninguno (0) |
| 2 | 201 | 2504 |
| 3 | 203 y 100 | 2504 y semilla 4275 |
| 4 | 1475 | 11447 |
| 16 | Ninguna | Ninguno |

Los datos de las acciones indican duración 3000 ms; **esa duración no demuestra un tiempo de crecimiento**. El estado 16 no debe tratarse como una etapa final cosechable: no tiene acciones y `bOm.bcP()` devuelve falso para ese estado. Otros parámetros permanecen identificados por su getter nativo en el JSON; no se les atribuye significado de XP o rendimiento sin seguir sus consumidores.

## Solución del servidor que debe implementarse

Sustituir el salto fijo 1→2 por transiciones explícitas por referencia y etapa, con vencimiento persistido y tiempos constantes configurables, como pidió el usuario. No ordenar todos los números de etapa y asumir que son etapas sucesivas: estados especiales y variantes raras requieren reglas distintas. La misma tabla debe resolver las acciones válidas para recolección; la acción que existe en etapa 3 puede no existir en etapa 2.

Añadir casos para árboles, incluyendo fresnos, y otras plantas. Al reiniciar, procesar cada vencimiento una sola vez y publicar el estado correspondiente sin cambiar `ownerAccount` a una fecha. Debe funcionar también al descargar y recargar la zona, siguiendo la política de zonas ocupadas del documento general.

## Límites de la comprobación

Se ejecutó extracción nativa y se inspeccionó el scheduler; no se implementaron transiciones ni se afirma una prueba gráfica de crecimiento completo. Falta determinar reglas nativas de las variantes especiales y completar el inventario de transiciones de las demás especies; son tareas técnicas del auditor, no decisiones pendientes del usuario.


## Cotejo PostgreSQL del 6 de octubre

La migración `004_combat_ecosystem.sql` mantiene `planting_growth_outbox.resource_uid` como clave primaria única. `mature()` inserta con `ON CONFLICT(resource_uid) DO NOTHING`, y `publish_growth()` marca la fila publicada sin retirarla. Por tanto, agregar solamente el salto 2→3 al scheduler dejaría esa segunda transición sin evento: la primera fila del mismo recurso bloquearía la inserción. Además, la publicación vegetal está codificada como `state_packet(resource, 2)`, ignorando la etapa del evento.

La implementación requiere cambiar juntos estos contratos:

- Identidad de evento por recurso y revisión/transición, independiente de la identidad del recurso. No sobrescribir eventos pendientes con estados posteriores.
- Próximo vencimiento persistido por recurso; conservar `creation_time` como nacimiento, sin reutilizarlo como fecha de cada transición ni como propietario.
- Publicar la etapa almacenada en cada evento, conservando el orden por recurso y confirmando la transición SQL antes de emitir paquetes.
- Ensayar al menos dos transiciones consecutivas del mismo recurso, reintento de publicación y reinicio entre commit y envío. Un test de 1→2 no prueba crecimiento completo.

La propiedad pública corregida en issue5 no cambia este scheduler. La extracción del grafo nativo y tiempos configurables sigue en revisión; no se asume que 4→16 sea un crecimiento normal.


## Resultado de extracción completa

Las533 definiciones contienen15 firmas distintas de estados. Las254 acciones de semilla apuntan a253 recursos, todos con etapa1, y solo cinco firmas:107 recursos `[1,2]`,100 `[1,2,3,4,16]`,32 `[1,2,3,16]`,10 `[1,2,3,4,5,16]` y5 `[1,16]`. Se inspeccionó el loader `bbO` y las definiciones `aNl/aNm`: generan estados y sus acciones, pero no exponen sucesor temporal ni tiempo de crecimiento. No tratar `duration_ms` de acción como duración de etapa.

También se comprobó que `publish_growth()` marca `published=true` antes de que el caller `grow_planted_resources()` emita al mundo. Una excepción o caída entre ambas operaciones pierde la difusión en vivo. Los snapshots SQL recuperan el estado al reentrar, pero no reparan a jugadores presentes. La confirmación de entrega debe pasar a la operación posterior a emisión; la recuperación reenvía el evento exacto y conserva identidad/revisión.


## Cambio de publicación en verificación

`Plantings.mature` y `publish_growth` ahora exigen un callback de publicación. El daemon entrega los paquetes dentro de ese callback; solo después de completarlo se marca el evento como publicado. Si falla, la fila sigue pendiente. La publicación vegetal utiliza `resource["stage"]` del evento en lugar del literal2. Se están verificando fallos/reintentos y todos los callers antes de recargar. Esto corrige el orden de entrega, pero todavía no añade las transiciones sucesivas ni cambia la clave única del outbox.


### Límite de la confirmación de envío

El callback completa la llamada a `WORLD.emit_location`; no es un ACK del cliente. `World._send` captura errores de socket por destinatario y cierra esa conexión, cuya siguiente entrada recupera snapshots. No afirmar entrega a todos los clientes por el mero retorno del callback. Para grupos nacidos de semillas, la recuperación también debe distinguir el payload original de un grupo que ya se movió o entró en combate: `groups.register` rechaza rosters distintos y un reenvío del spawn original podría ser obsoleto. Este caso requiere cotejo propio, sin revivir grupos derrotados ni alterar claims de combate.


## Gate de publicación

21 pruebas PostgreSQL OK: plantación, runtime, contexto y caso enfocado de consumo/recibo/crecimiento del Store. Incluyen callback con evento todavía pendiente, fallo de entrega y reintento del mismo payload, etapa variable y conexión AST del daemon. La prueba de empaquetado detectó el hash anterior del catálogo; actualización del manifiesto y repetición pendientes. Código aún no recargado.
