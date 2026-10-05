# Información pendiente — 16

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Protocolo completo de observar/salir y alcance de 13753. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 2 | Política de privacidad, límites y ACK de observadores. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Qué efectos deben ser visibles en un snapshot intermedio, no solo replay desde inicio. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

1, 2. Revisa todo. Nada que decidir
3. todo debe ser visible en tiempo real, no hay replay desde el principio

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
