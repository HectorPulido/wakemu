# Información pendiente — 21

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Host/IP remoto, puertos necesarios, TLS/túnel y firewall. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 2 | Prioridad actual del pedido.env de tools versus restricción de cambios solo server. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Política de exposición de API/test/admin y evidencia de auth. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

1. Revisa todo. Nada que decidir

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
