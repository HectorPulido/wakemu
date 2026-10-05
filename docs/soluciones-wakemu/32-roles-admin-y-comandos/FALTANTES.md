# Información pendiente — 32

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Política exacta de comandos públicos versus restringidos. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 2 | Mecanismo autorizado de concesión/revoke y principal del cron. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Contrato HTTP401/403 y revalidación de jobs ya encolados. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

1. Admin -> todos los comandos !, jugador -> solo los permitidos, hay que poner eso modificable

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
