# Información pendiente — 19

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Rango/distribución de pasos y política de escalonado. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 2 | Codec multi-paso y ocupación durante animación. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | ObjetivoCPU/latencia y proximidad deseada. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

1. de 1 a 5 pasos en un rango con cierta posibiloidad
2. Creo que eso ya esta funcionando
3. Minimo impacto posible

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
