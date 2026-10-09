# Información pendiente — 29

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | Integrar la sesión durable con el acceso normal candidato de Jalató. Existe `maps/dungeon_instances.py` + migración 065 y `maps/dungeon_transport.py`; migración 068 registra el modo del servidor. Aún no hay caller de transporte ni cambio de mapa. Migración 070 añade política ProtoDungeon SQL versionada pero sin valores sembrados, porque las capturas no acreditan contexto de Jalató ni `allowed_ids`. | Cotejar el visitor de `IsNeoServer()` con la clave global `server.group.isneo`, configurar una política desde evidencia autorizada, añadir proximidad/celda de origen y ejecutar el ciclo de entrada antes de conectar 12296 | Bloquea el acceso funcional; no se resuelve quitando guards, suponiendo que `allowed_ids` es la party ni pasando plantilla 91 como `instance_id` |
| 2 | Dificultad/XP/loot, rejoin, lockouts y reset de instancia. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Protocolo de UI mazmorra, stasis y fin, no solo teleport. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

La instrucción del usuario es revisar e implementar el recorrido sin solicitar decisiones rutinarias; Jalató es el primer candidato. No hay una decisión del usuario pendiente para continuar la inspección. La clave y el default del modo sí están en el enum de configuración nativo; el visitor que conecta la clave con el criterio no fue localizado y la relación se documenta como inferencia. La composición por sala y las políticas de derrota/reintento deben permanecer cerradas hasta acreditarlas.

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
