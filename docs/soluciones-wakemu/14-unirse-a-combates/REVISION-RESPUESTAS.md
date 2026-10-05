# Unirse al combate: ruta nativa y servicio existente

## Solicitud y objetivo

Bytecode de `bvC`: la acción construye `coU` con **`big.Sn()` del actor objetivo**, y un boolean de configuración (`bWD.lzc`), no con el ID i32 del encuentro. `coU` emite **13241**, categoría 3, cuerpo i64 objetivo + boolean; coincide con `combat_multiplayer_wire.decode_join()` (9 bytes). La opción exacta de configuración debe verificarse antes de atribuirle reglas nuevas; el codec del servidor la denomina auto_lock.

`cWS` también contiene 13311 (`crY`), pero el sitio inspeccionado toma el ID de territorio `bLO.d()`: no confundir esa petición auxiliar con la entrada 13241. Observar usa 13413 y requiere una autorización diferente.

## Implementación que ya existe

Hay un servicio **`combat_shared.Registry`**, no únicamente un codec. `tests.test_combat_shared` se ejecutó: **12 pruebas aprobadas**. Una prueba une dos sesiones a la misma FSM, asigna una celda libre, publica 13091/13026 al participante existente y bootstrap al nuevo, mantiene secuencias alineadas, exige listo de ambos y rechaza control fuera del turno autorizado.

El test utiliza `actor_payload` con bytes de ejemplo `ownstats/owneffects` y bootstrap `owned-bootstrap`: **no acredita serializers nativos válidos ni entrada en cliente**. Las fuentes actuales del dispatcher no contienen handler 13241; falta integrar el servicio existente en la ruta de red, evitando crear otra FSM aislada por conexión.

## Solución específica del servidor

Resolver objetivo 13241 en el registro de encuentros vivos de su mapa/instancia; validar lease, fase de colocación, cupo/celdas/equipo y admisión vigente. Reutilizar `Registry.join()` y los outboxes ordenados, proporcionando payloads nativos reales y bootstrap del encuentro compartido. Incorporar listo, movimiento, desconexión y salida al mismo registro; no basta llamar a join y dejar las acciones posteriores en el `fight` privado de cada conexión.

Los codecs 13091 y 13753 ya existen en `combat_multiplayer_wire`; 13753 requiere dos líderes presentes y topología propia. Registrar ciclo de anuncio/retiro y impedir IDs heredados. Envío a clientes lentos, revisión de entrada y recuperación deben preservar una única FSM y leases, sin permitir que una sesión nueva controle actores de otra cuenta.

## Evidencia y límites

Pruebas ejecutadas: doce del servicio compartido; inspección nativa de acción/encoder y cotejo del dispatcher. El encoder 13241 se ejecutó después con ambas variantes del boolean y se cotejó con el decoder de producción; no hubo entrada GUI multijugador. Hay una segunda cuenta/cliente propios en preparación, pero no se presenta autenticación como prueba de participación. Faltan serializers reales, integración y validación visual; issue abierto y sin fixes.

## Encoder ejecutado

[Dos frames nativos](probe-solicitud-nativa-join.json) para objetivo sintético 12345: auto_lock false/true. `decode_join()` devuelve ese objetivo y boolean sin restos. Se conserva la distinción actor objetivo frente a ID de encuentro; esta prueba no acredita fase, cupo ni admisión de un jugador real.

## Boolean de solicitud identificado

`bWD.lzc` corresponde nativamente a **AUTO_LOCK_FIGHTS_KEY**, clave `autoLockFights`. Esto confirma el nombre auto_lock del decoder; falta verificar quién puede bloquear un encuentro existente y cómo se transmite/cancela el bloqueo. `Registry.join()` aplica el valor tras admitir al nuevo actor, por lo que deben probarse permisos y efecto sobre posteriores entradas.
