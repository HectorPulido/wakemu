# Información pendiente — 14

## Pendientes específicos

| ID | Dato o decisión | Cómo resolverlo | Impacto |
| --- | --- | --- | --- |
| 1 | El body 13241 está verificado como `>qB` (actor ID, `autoLock`); no lleva fight ID. Si un personaje retirado inicia otra pelea antes de que cierre la colocación anterior, el mismo actor ID puede apuntar a dos marcadores. | Se prioriza el actor registrado actualmente; el alias histórico solo resuelve cuando no existe uno actual. Hace falta un carrier nativo adicional para distinguir ambos marcadores, si existe. | La unión al marcador anterior no se puede garantizar en esa colisión |
| 2 | Registro compartido y política de ACK multi-cliente aún no implementados. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |
| 3 | Cupos, reparto de premios y abandono parcial. | Inspección dirigida, fixture o decisión explícita | Impide certificar esa parte del flujo |

1. Revisa todo. Nada que decidir
3. hablamos de eso en 10 y 9

## Alias del líder retirado

El servicio conserva aparte el ID del líder jugador que el marcador público anunció al crear la pelea. Tras el ACK de retirada, un compañero vivo y conectado del mismo equipo puede usar ese ID durante colocación; el alias no reserva el ID del personaje y se elimina al comenzar la pelea o al cerrar el registro. El handler vuelve a resolver el objetivo dentro del registro y comprueba que siga apuntando a la misma pelea antes de persistir la admisión.

Como 13241 solo transporta el actor ID, una pelea nueva del mismo personaje tiene prioridad y hace que el alias histórico quede oculto mientras esa pelea esté registrada. No se afirma que el cliente pueda elegir entre dos marcadores que anuncian el mismo ID; no se encontró un segundo identificador en el request verificado.

## Reglas para completar la especificación

No inventar fórmulas oficiales, opcodes, flags o carriers. Para una regla configurable, fijar rango, default, redondeo, límites y versión. Para mensajes, demostrar encoder/decoder con fixture y consumidor nativo; no publicar archivos propietarios. Para una política de producto, documentar la elección antes de escribir tests que la congelen.

Los pasos que dependen de estos datos siguen siendo propuestas. Se puede avanzar en medición y pruebas de regresión de piezas confirmadas sin declarar cerrado el recorrido. Actualizar el cotejo si cambia la implementación concurrente.
