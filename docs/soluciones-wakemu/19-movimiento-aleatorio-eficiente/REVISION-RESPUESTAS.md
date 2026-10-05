# Movimiento: requisito frente al comportamiento real

`wander_monsters` espera un intervalo global aleatorio de 3–6 segundos, obtiene las zonas con jugadores y llama `wander_location` para cada una. Dentro, cada grupo disponible se intenta mover una vez: no hay una tirada del 25%. `plan` elige una traslación legal aleatoria, pero de **un paso**, y `movement_packet` codifica explícitamente steps=1. Eso explica la sincronización por tick y por qué no satisface aún 1–5 pasos.

Sí existen exclusión de grupos en combate/recolección, cercanía a jugadores, aristas dirigidas legales, alturas, ocupación y CAS bajo lock. Se ejecutaron los dos tests existentes de `test_monster_wander.py`; pasan. Esas pruebas certifican esas garantías acotadas, no la distribución solicitada ni un codec multi-paso.

La propuesta del servidor debe conservarlas y programar vencimientos por grupo alrededor del periodo solicitado de 5 segundos, con tirada independiente del 25% y longitud aleatoria 1–5. Reservar y validar cada arista del recorrido, no solo destino, y mantener ocupación durante animación. Cotejar el formato multi-paso antes de emitirlo. Procesar únicamente zonas ocupadas y evitar reconstruir geometría/snapshot global por cada grupo. No se cambia el cliente ni se implementa el movimiento en esta auditoría.


## Paso actual ejecutado

Se ejecutó `monster_wander.plan` con dos miembros y aristas sintéticas: ambos se trasladan con el mismo delta y se emite un paquete de un paso por miembro. Sin jugadores no genera plan. Esta función selecciona un candidato cuando existe, sin sorteo de 25%; el caller comparte intervalo aleatorio de 3–6 segundos para las zonas activas. Por tanto, lo actual no acredita la política solicitada de 5 segundos, probabilidad independiente y pasos aleatorios.

Parametrizar intervalo/probabilidad/rango de pasos en DB y sortear por grupo activo; construir ruta sobre aristas verificadas paso a paso, respetando ocupación, recolección y combate. Mantener commit/CAS de movimiento antes de emitir, con una revisión por plan; no mover todos los grupos por usar un único temporizador. Cotejar el encoder de rutas multipaso antes de ampliar el paquete actual. [Probe](probe-paso-grupo-actual.json). No se modificó movimiento real.


## Ruta multipaso nativa ejecutada

Se ejecutó `aAT.eY → aWH` para 0, 1, 3 y 255 pasos. Cabecera de 11 bytes: x/y i32, z i16, cantidad u8; un byte por paso con dirección en 3 bits y delta de altura con signo en 5 bits (−16…15). Fixtures incluyeron ambos extremos de altura. El codec conservó las cantidades y tamaños 11, 12, 14 y 266 bytes. Esto acredita capacidad del formato, no recorrido válido ni animación.

Para pasos aleatorios, configurar un rango pequeño acreditado por política y limitarlo a 255; construir cada arista legal y detenerse al bloquearse. No emitir una cantidad aleatoria con deltas inventados ni extrapolar que 255 pasos sea seguro para simulación. El paquete actual 13852 incluye actor i64 antes de esa ruta; mantener identidad/posición inicial autoritativas y verificar endpoint/animación en UI antes de certificar. [Probe](probe-ruta-multipaso-nativa.json).


## Persistencia de movimiento: regresión actual

`RedisGroups.move_members` permite solo cambios x/y/z, exige estado disponible y roster esperado, incrementa revisión y escribe mediante journal CAS. `wander_location` emite después de esa confirmación. Se ejecutó la suite existente `tests.test_monster_wander`: **2 tests OK**, SQLite temporal + MemoryRedis, cubriendo proximidad/ocupación, recuperación, flush y rechazo de snapshot antiguo. No equivale a Redis real ni a fallo entre commit y broadcast.

La solución multipaso debe preservar ese orden y añadir recuperación de publicación: si el proceso cae después de confirmar posición y antes de emitir, los clientes necesitan snapshot/reconciliación o outbox ordenado. No hacer rollback ficticio del traslado ya confirmado ni repetir rutas desde origen obsoleto. La suite actual no verifica25%/5 segundos/multipaso. [Ejecución y límites](probe-regresion-movimiento-actual.json).
