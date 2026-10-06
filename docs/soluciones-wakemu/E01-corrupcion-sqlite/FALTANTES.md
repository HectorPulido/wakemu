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

## Estado después del corte a PostgreSQL

La decisión está tomada: PostgreSQL como único backend, base nueva sin importación ni compatibilidad SQLite. Los tres puntos históricos anteriores no son decisiones pendientes del usuario ni requisitos para mantener SQLite. El origen físico del daño histórico no se da por demostrado.

Aceptación visual acreditada: personaje nuevo creado desde UI, selector y reentrada al mapa tras reinicio, e inventario propio persistido. Última imagen healthy y migraciones1–8 presentes. El gate final de persistencia actual pasó77/77. No quedan pendientes de implementación de E01; el origen físico histórico no se atribuye sin evidencia. La restauración poblada ya se comprobó; véase [IMPLEMENTACION.md](IMPLEMENTACION.md).
