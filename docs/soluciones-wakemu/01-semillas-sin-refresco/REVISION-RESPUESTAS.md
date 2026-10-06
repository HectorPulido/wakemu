# Semillas: contrato de consumo y límite de reproducción

> **Corrección del cotejo, implementación actual:** la revisión completa de
> `bJt.d/e` demuestra que la llamada desde `cgN.a(cAZ)` solo muestra
> `item.selfDrop`; no resta cantidad. `cYt.eXi` avanza objetivos y tampoco
> actualiza la pila. La afirmación anterior de que12954 consume visualmente
> era incorrecta. Una prueba GUI registró cinco plantaciones confirmadas desde
> una pila5: PostgreSQL quedó sin el objeto y la interfaz conservó5. El servidor
> ahora emite12470 con UID y delta-1 una sola vez después del ACK; replay y
> cancelación no emiten delta. Validación del cambio gráfico pendiente.


## Evidencia nativa

`cgN` despacha12954 a `a(cAZ)`. La rama consulta éxito, pero finalmente ambas variantes obtienen semilla mediante `dev.getItem()` y llaman `bJt.d(item,1)`. La inspección inicial de esa llamada fue incompleta. El cuerpo de `bJt.d/e` solo muestra el mensaje de pérdida: **el ACK no resta la cantidad; el servidor debe publicar12470 por el consumo confirmado**. La reproducción posterior acreditó estado activo de `dev`, plantaciones aplicadas y cantidad visual desactualizada. No se infiere un UID de los prefijos del paquete sin consumidor verificado.

## Cotejo del servidor

`Plantings.complete` atiende13429 (`B result + h kind`), exige kind2 y resultados2completado/3cancelado, verifica generación y duración. Si no hay ticket devuelve sin paquetes; con ticket aplicado quita la reserva. La transacción de `planting.complete` consume semilla y guarda el recurso/recibo; publica13135 y12954. La protección del ticket debe conservarse para que un completado repetido no provoque otro ACK que reste sobre el inventario local.

La política solicitada es éxito/fallo consumen una; cancelación no consume; solo éxito da XP. La ausencia de RNG de fallo se audita en issue4, no se corrige añadiendo deltas de inventario.

## Prueba GUI en curso y límites

Luna/low confirmó Audit Builds nivel100, mapa879, celda transitable y plantable estricta(-3,0,0), ground457/region66601/suitability0.7. La tecla inventario del inspector existente abrió UI y la pila mostró5 semillas de Cardo; tooltip confirmó referencia de semilla y Herbolario0.

El clic al objetivo movió al PJ: **no estaba activo el modo plantar**, no hubo plantación ni consumo. Esta observación no reproduce el bug del usuario y no demuestra que las semillas se refresquen correctamente. Falta resolver activación nativa del modo y obtener una operación real. Capturas privadas permanecen en.runtime; no se distribuye cliente.


## Nuevo síntoma: extracción ilimitada de semillas del mismo monstruo

El usuario reportó que puede obtener semillas indefinidamente sin cooldown. **Se confirmó la configuración del código actual:** `local_game_server.py`, ruta13481, pasa `quantity=1,cooldown_seconds=0`. `monster_collect.Harvests` bloquea ocupaciones simultáneas mientras se recolecta, pero las libera después; eso no impone espera entre acciones. La duración de3000ms no equivale a un cooldown posterior.

La tabla `monster_harvest_receipts` ya conserva éxito y tiempo. `complete` consulta el último `completed_at` por `monster_id/action_id` y compara con el cooldown del ticket. El valor0 evita el bloqueo. `begin` no consulta ese tiempo: incluso con política no nula permite iniciar una acción que después rechazará por cooldown.

Se probó en SQLite desechable la acción nativa **3724** del monstruo **ref1/jalató**, que entrega semilla **7361**. Tres operaciones consecutivas, avanzando3s cada vez, entregaron tres semillas del mismo monstruo y crearon tres recibos. Con cooldown de prueba10s, la primera entregó y las dos siguientes rechazaron al completar; ambas sí habían iniciado. [Resultados y hashes](probe-extraccion-repetida-monstruo.json). El probe inicial del fixture usaba lana2246; se corrigió a la acción de semillas y se conservaron ambos resultados para no confundir materiales con semillas. No hubo GUI ni cambios a datos de jugadores.

### Solución concreta del servidor

Resolver y persistir una política de regeneración por familia/acción y un estado `next_collect_at` por criatura y acción. El tiempo exacto no está acreditado como oficial:10s fue una prueba de validación, no un valor recomendado. Examinar la mecánica nativa de estado disponible/agotado para distinguir regeneración temporal de una extracción por etapa de vida.

Validar disponibilidad al iniciar **y volver a comprobarla al completar**, bajo la misma autoridad que reserva la criatura. Confirmar semilla, recibo y próximo instante disponible en una transacción; dos personajes no pueden cosechar simultáneamente el mismo estado. Cancelar o fallar antes de obtener el objeto no debe gastar disponibilidad. Un reintento con el mismo token devuelve el recibo, sin otra semilla ni reiniciar el cooldown.

La clave debe incluir mapa, instancia e identidad durable de criatura: el recibo actual consulta solo `monster_id/action_id`. Cotejar si IDs se reutilizan al recrear grupos antes de migrar; un mob nuevo no hereda por accidente el cooldown de otro, y mover la misma criatura no lo elimina. Usar reloj consistente del servidor y conservar el estado tras reinicio/reconexión. No limitar únicamente al personaje: otro jugador no debe saltarse la disponibilidad común si esa es la regla acreditada.

Publicar el estado de disponibilidad con el carrier nativo correspondiente o un rechazo visible acreditado; no aceptar visualmente una barra que está condenada a fallar. Quedan por cotejar ese estado/carrier y el intervalo/condición nativos, más una prueba GUI con dos personajes. Se incorpora al issue01 y se relaciona con reproducción/población02/03/20; no se aplicó ningún fix.

## Ampliación: política en base de datos

Por instrucción del usuario, el cooldown debe ser un parámetro persistente por especie/acción, con fallback global, validación de unidad y rango y revisión congelada al reservar la extracción. Su estado de disponibilidad por criatura también debe persistir: son datos diferentes. No sustituir el literal cero por otra constante ni por una variable de entorno como solución final. [Diseño transversal y variables de Compose](../PARAMETROS-SERVIDOR-EN-DB.md).
