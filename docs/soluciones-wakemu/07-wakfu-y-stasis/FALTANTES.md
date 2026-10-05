# Información pendiente — 7

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Fórmula/rangos y límites de Wakfu/Stasis para esta versión. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 2 | Codec del valor personal y periodicidad de publicación. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Reglas de atribución al plantar, cosechar y destruir. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

1. Hay que hacer una formula que sea modificable en la db, lo unico que hay que tener en cuenta es que al matar mobs en "peligro de extincion" de la zona, de stasis, al igual que plantar cosas cuando hay sobreproduccion. mantener el equilibrio debe darte wakfu.
2. Hay que revisar esto en el codigo y en internet.
3. Lo mismo que en la regla 1, si plantas cuando hay sobrepoblacion, stasis, si plantas cuando hay equilibro o peligro de extincion wakfu

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
