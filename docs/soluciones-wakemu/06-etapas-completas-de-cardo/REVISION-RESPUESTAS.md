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


## Semántica de estado: límites confirmados

`fAk`, obtenido por `bOm.ejd()→bOt.ejg()`, describe tamaño visual (`SMALL/MEDIUM/TALL/TINY`), no madurez. `bOm.eiZ()` es el ID de etapa y `bOm.IC(actionId)` resuelve la acción del estado. `bOm.bcP()` rechaza explícitamente16, mientras los demás estados consultan una bandera del recurso. No se encontró en esos consumidores una etiqueta que pruebe que4/5 sean estados raros ni un sucesor temporal. Toda política local de transiciones debe declararse como configuración del emulador, sin atribuirle origen oficial.

## Outbox reutilizable después de cosecha — verificación actual

La finalización de flora reemplaza el evento anterior por la etapa resultante dentro de su transacción. `mature()` actualiza la fila existente en1→2 y vuelve a dejarla pendiente, en lugar de ignorar el conflicto deUID; así la cosecha que regresa a1 puede regenerar y publicar2. Las confirmaciones de `publish_growth()` y `acknowledge_publication()` comparan el contenido exacto del recurso (y del grupo cuando procede), evitando que una confirmación tardía marque publicada una transición nueva.

Gate combinado **78 pruebas OK** en PostgreSQL aislado: incluye sustitución de eventos, fallo/reintento sin volver a dar productos/XP, regeneración1→2 y reemplazo de evento durante el callback de envío. Esta modificación está en fuente y aún no desplegada con DB016. No constituye crecimiento2→3 ni un grafo completo de etapas; eso sigue pendiente de implementación con política PostgreSQL. Tampoco prueba retirada espacial del actor al emitir etapa0.

## Grafo persistente de crecimiento — implementación017

`017_resource_growth_transitions.sql` define401 aristas explícitas para141 referencias y cinco referencias sin transición, cubriendo las146 vegetales plantables presentes en el catálogo. Es una política local del emulador: recorrer en orden ascendente las etapas catalogadas, excluyendo0 y16. No atribuye ese orden a una regla oficial ni afirma que4/5 sean raras. Cinco referencias solo tienen etapa1 y no reciben una arista inventada hacia16. Las semillas de monstruos quedan fuera del grafo y conservan su comportamiento anterior.

Cardo60 y Fresno139 quedan configurados1→2→3→4,30.000ms por transición. Las diez referencias plantables con etapa5 continúan4→5; las32 con etapas1/2/3 terminan en3. Cada fila se edita en PostgreSQL mediante `resource_reference`, `from_stage`, `to_stage`, `delay_ms`: por ejemplo `UPDATE resource_growth_transitions SET delay_ms=60000 WHERE resource_reference=139 AND from_stage=2;`. El rango admitido es1.000–86.400.000ms. Clave primaria por referencia/etapa origen, arista ascendente sin0/16 y etapas nativas verificadas antes de mutar el recurso evitan ciclos y destinos inventados.

El scheduler selecciona la arista debida por recurso/etapa, bloquea el recurso y vuelve a leer la política con `FOR SHARE`. Una reserva de cosecha activa impide la transición. El nuevo ancla temporal se calcula como inicio anterior más duración, preservando el tiempo transcurrido sin acumular deriva de ticks: una planta atrasada puede avanzar una arista por tick hasta ponerse al día. `creation_time` se usa como entrada de etapa en milisegundos, igual que en la regeneración tras cosecha; no describe un campo nativo identificado como timestamp. La etapa y su outbox se confirman juntos. Al reabrir el servidor, PostgreSQL conserva ambos. El índice por referencia/etapa/reloj apoya la búsqueda.

Gate combinado **91 pruebas OK** en PostgreSQL aislado: diez pruebas nuevas de grafo cubren recorrido completo, terminales4/5, límites temporales, cambio de política, reservas, persistencia, catch-up y recuperación del outbox. Se comprobaron las401 aristas contra las etapas nativas. DB017 y el código nuevo **no desplegados** mientras se verifica la retirada visual necesaria para completar la cosecha.

## Recarga y verificación SQL

DB017 aplicada en el servidor local el6 de octubre, imagen `14d2bde313b38cd0d82f7df2b895880e542d79258326de985417952aba327541`. Health PostgreSQL y Docker saludables. Consulta real:401 aristas para141 referencias; las otras5 de las146 plantables solo tienen etapa1. Cardo60/Fresno139 tienen1→2→3→4 con30000ms por transición. Gate92 aprobado en PostgreSQL aislado. Falta aceptación en juego; no se declara solución total.
