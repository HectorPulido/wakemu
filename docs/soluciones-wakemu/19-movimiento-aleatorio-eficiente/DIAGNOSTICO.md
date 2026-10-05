# Diagnóstico — 19

## Contexto registrado

**Confirmado:** `local_game_server.py::wander_monsters` usa un tick global aleatorio de 3 a 6 segundos. `maps/monster_wander.py::wander_location` intenta mover cada grupo elegible, sin tirada del 25%; `movement_packet` codifica un solo paso. La dirección es aleatoria entre candidatos, pero no la decisión de moverse.

**Posible solución según lo solicitado:** evaluación cada 5 segundos, oportunidad independiente del 25% por grupo y número aleatorio acotado de pasos válidos. Mantener miembros del grupo coordinados, colisiones y alturas; evitar sincronía visual si se decide distribuir evaluaciones. Acordar el rango de pasos. **Validación:** RNG controlado, distribución aproximada del 25%, grupos en combate/recolección inmóviles.

Asegurarnos de que esto sea suoper eficiente, unicamente mover monstuos en mapas donde haya gente

## Lectura actual

El plan elige entre movimientos válidos de un paso, sin tirada previa del 25 %. Recorre aristas por grupo; la propuesta requiere índice compartido y decisión independiente.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Rango/distribución de pasos y política de escalonado.
- Codec multi-paso y ocupación durante animación.
- ObjetivoCPU/latencia y proximidad deseada.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
