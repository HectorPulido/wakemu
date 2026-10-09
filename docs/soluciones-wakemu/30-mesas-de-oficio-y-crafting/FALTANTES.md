# Información pendiente — 30

La receta de Pólvora de cañón (2227) ya fue aceptada manualmente: el usuario confirmó un lote de 100 Bombas y 20.000 XP de Minero. Esa aceptación cubre esa ruta de producción; no implica que todas las recetas o modalidades estén habilitadas.

## Pendientes respaldados por fuente

| ID | Brecha | Evidencia actual | Próximo paso seguro |
| --- | --- | --- | --- |
| 1 | Velocidad de oficio específica del personaje | `local_game_server.py` entrega `craft_speed_modifier=0` al handler ordinario. El getter nativo aplica `round(raw_duration / (1 + modifier/100))` con el stat2002/tipo8 indexado por oficio. `server/protocol/aptitude-effects.json` no contiene una fila stat2002; las 12.254 plantillas de `item-equipment-effects.json` tampoco incluyen ese stat. El snapshot persistido del actor deriva características de combate, no el par stat/tipo indexado por oficio. | Localizar y exportar el carrier/fuente nativo de ese modificador por oficio; probar un valor no cero obtenido del actor antes de reemplazar el baseline. No inferirlo de una característica de combate. |
| 2 | Recetas condicionadas o con flags | `crafting._recipe()` rechaza campos nativos no vacíos (`raw_clT`, `raw_cvc`, `raw_cvd`, `raw_ckE`). En el catálogo de 5.449 recetas, 271 cumplen al menos uno de esos criterios/flags (252 con `raw_clT`, 252 con `raw_ckE`, 16 con `raw_cvd` distinto de false; hay solapamiento). | Implementar evaluadores/autorización solo tras cerrar semántica temporal, criterio, descubrimiento y flags con consumidor nativo y fixtures. El rechazo actual es fail-closed; no habilitar por aproximación. |
| 3 | Modalidad de otro artesano | El cliente emite `13515` para esa rama; el dispatcher actual conecta `12231` y `13382`, no `13515`. El significado/validación del i64 adicional y los dos participantes sigue sin resolverse. | Cotejar permiso, recurso/coste y respuesta nativa de la modalidad; después diseñar operación atómica con ambos actores y pruebas de ownership/retry. |
| 4 | Duración total de lotes | La fórmula nativa por receta y el timer de ocupación están cotejados; no se ha demostrado si multiplicar el timer por cantidad es la regla oficial. El servicio conserva `native_craft_speed_sequential_batch_v1` como política local explícita. | Mantenerlo documentado como política local hasta encontrar la regla/consumer nativo del lote. |
| 5 | Cobertura de recetas del catálogo | El catálogo nativo y la ruta ordinaria existen; la aceptación de Minero valida una receta/producto concreto, no condiciones, modos o restricciones de todas las estaciones. | Ampliar cobertura por familias de definición y políticas ya acreditadas; no repetir la prueba manual de Minero como sustituto. |

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
