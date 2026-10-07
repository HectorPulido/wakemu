# Información pendiente — 26

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Request/ACK y selector primaria/secundaria | Confirmado offline: 12177/12234, 13090/12451; bool 13090 elige primaria (`true`) o secundaria (`false`) | Branch fuente conectado; falta aceptación cliente |
| 2 | Retirada con muebles/plantas/visitantes | No borrar ni mover sala con bienes o actores; no se ha verificado política nativa de cierre | Impide certificar salas ocupadas |
| 3 | UID durable de gemas iniciales y compatibilidad de layouts viejos | La gema fija de entrada sigue usando UID virtual `character_id*256+1`; 051 solo registra transferencias físicas | Falta migración/normalización de instalaciones preexistentes si las hay |
| 4 | Stack split y respuesta incremental | Helper propone 12470 → 12471 → 12234 para que el cliente resuelva el UID nuevo | Falta verificar visualmente esta secuencia |

1. Revisa todo. Nada que decidir

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
