# Información pendiente — E01

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Archivo/boot exactos de la corrupción histórica y integridad actual. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 2 | Backups disponibles, tiempos yWAL/SHM; journals posteriores. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Origen físico del daño y alcance de datos perdidos. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

1. Revisa todo. Nada que decidir

Revisa tambien si vale la pena usar postgres en vez de sqlite

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
