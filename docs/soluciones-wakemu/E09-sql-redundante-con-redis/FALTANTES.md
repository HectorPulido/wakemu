# Información pendiente — E09

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Contrato completo de snapshot y qué lecturas deben seguir inmediatas. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 2 | Todos los writers y su mecanismo invalidation/version. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Carga y latencia del Redis realmente desplegado. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

1. Ya eso lo hablamos antes

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
