# Información pendiente — 24

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Resuelto en fuente: `PASSEPORT_INFO` se reemplaza por el default `00` al serializar los layouts que lo contienen; antes se copiaba de la plantilla. | `wire.py`, `test_wire.py`; binding `ddU` → `pvpLadderEntry` → nación del personaje en REVISION-RESPUESTAS.md | Gate automático pasó; falta aceptación visual `/passport` tras entrar y reconectar |
| 2 | Nación propia `0` es “Neutral” en el locale y es el valor que lee el modelo del pasaporte. | Parser qZ y revisión nativa documentados | No confundir territorio con ciudadanía; falta confirmar UI actual |
| 3 | Ciudadanía, compañía, sincronización pública de nación y geografía territorial son carriers distintos. | `social.py`, `wire.py`, `territory_cells.py` | Falta identificar autoridad nativa de propiedad/alineamiento de lugares; no hay mapeo de nación territorial verificado |

La referencia de item no es necesaria para investigar el pasaporte: el comando nativo `/passport` abre `passportDialog` y enlaza `pvpLadderEntry`. La brecha hallada en el serializador era el byte independiente `PASSEPORT_INFO`, no un objeto de inventario.

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
