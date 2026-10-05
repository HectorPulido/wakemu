# Información pendiente — 9

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Fórmula base y reparto entre jugadores/companions. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 2 | Nombre/rango del multiplicador y política de ceros/fracciones. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Configuración efectiva del mundo que produjo el síntoma y captura de subida por XP (distinta de !nivel). | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

1. Fijemos como lo hace dofus y clonemos eso, importante mantener en la base de datos un multiplicador
2. Revisar codigo e intenrnet
3. Revisar codigo y solucionar

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
