# Información pendiente — 3

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Reglas de familia/madurez/sexo y probabilidad. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 2 | Máximos de miembros y población, prioridad ante falta de celda. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Qué bootstrap existente se conserva al retirar respawn y qué datos históricos migrar. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |


1. Familia es importante, madurez va por nivel, sexo ignoremoslo, y probabilidad 5% de posibilidades de subir de nivel cada cierto tiempo por ejemplo, pero depende del nivel actual vs el nivel del proximo monstruo
2. maximo 8 miembros, cada que un mob se reproduce hay posibilidad de subir en 1 al mob y posibilidad de generar un nuevo mob (para esto puedes usar la idea de las semillas)
3. Eliminar el respawn, no debe haber respawn artificial

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
