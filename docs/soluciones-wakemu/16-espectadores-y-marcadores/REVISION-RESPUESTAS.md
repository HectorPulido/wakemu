# Espectadores: salida nativa y separación del encuentro

## Contrato comprobado de salida

Se inspeccionó `LeaveSpectatorModeCommand`: crea `bvU` y llama `bGG()`. Esta función verifica `biB.drh()`, desmonta frames del combate y cambia `is_in_fight_spectator` a false. Si encuentra el encuentro actual, emite **`cpg`, opcode 12154**, categoría 3, cuerpo **i32 ID de encuentro**. Encoder ejecutado con ID sintético 456: `0000000b032f7a000001c8` (frame completo).

No se encontró rama 12154 en el dispatcher ni codec Python actuales. La salida requiere quitar la subscription del encuentro indicado, sin declarar derrota del personaje ni repartir premios. La limpieza local del cliente ocurre antes de enviar esa notificación: no asumir que una confirmación tardía puede mantenerlo observando.

## Código del servidor

`combat_groups.Groups` administra leases de grupos NPC y sus estados available/fighting/defeated; no contiene suscripciones de espectadores. Su documentación sobre observers alude a grupos disponibles del mundo, no a participantes que ven un combate. No reutilizar esa colección como roster del encuentro.

13753 aparece en filtrado de paquetes de la captura original para mapas distintos de 1134. Eso no demuestra creación/retirada de marcadores propios ni lista actual de combates. Falta seguir su decoder y distinguir claramente mundo de bootstrap del combate.

## Solución concreta y pruebas pendientes

Registrar los encuentros vivos por mapa/instancia e implementar subscriptions separadas de actores controlados. Una salida 12154 valida lease de conexión, ID y subscription; elimina únicamente la observación de esa sesión. La repetición o salida después de cierre debe ser idempotente, sin liberar el lease NPC ni alterar victoria/derrota. Reconnect no hereda la subscription de una generación anterior.

Entrada debe enviar el **estado actual**, conforme a la respuesta del usuario, más eventos posteriores a una revisión consistente; no un replay desde el inicio. Verificar carrier de entrada, bootstrap de espectador y retorno al mundo antes de implementar. ACK de observador no debe condicionar turnos activos. Probar salida local, desconexión y cierre simultáneo con dos participantes y un observador; el observador no adquiere autoridad de acciones.

## Alcance real

Prueba ejecutada: encoder nativo de salida; cotejo de bytecode y fuentes. **No hubo sesión de espectador ni prueba multijugador**, y todavía no se resolvió la entrada/marker completo. No se modificó fuente ni se tocaron hechizos. Issue abierto.

## 13753: creación de encuentro externo, no un marcador arbitrario

Se siguió `cuY` hasta `ckM`: el consumidor identifica explícitamente una creación de **external fight**, obtiene el modelo con `eHb()` y crea `buG`. También interpreta `eHe()` como datos serializados para su escena y utiliza `eHc()/eHd()` para buscar/crear entidades de presentación. Por tanto, publicar solo ID/posición como un marcador simplificado no satisface ese contrato.

Parser ejecutado con un cuerpo **sintético de 40 bytes**, sin actores ni datos de escena: devuelve true; getters fight=456, type=2, referencias=123/789/1000 y tail vacío. Esta prueba valida lectura del envelope, **no creación visual**: `ckM` requiere modelo y datos de escena adecuados.

Layout inspeccionado: i32 encuentro, byte tipo, dos i64 referencias, i16, otro i64, byte cantidad de IDs + i64 por ID, i16 cantidad de actores + (i64 ID,byte dato) por actor, byte estado `fbZ`, cuatro boolean, byte cantidad de pares + (i16,i16) por par, y resto como blob. La semántica de las referencias, flags y pares debe resolverse por consumidor antes de emitir datos reales. Mantener separado el marker del mundo del bootstrap de participante/espectador, aunque compartan ID de encuentro.

Siguiente requisito concreto: construir el blob de escena desde el encuentro propio y demostrar `ckM` con entidades vigentes; después verificar qué acción del encuentro externo emite entrada de espectador. El parseo exitoso de ceros no acredita visibilidad, acceso ni permisos.

## Entrada de espectador resuelta en el cliente

`cWf.eUZ()` selecciona `cWb.nEj`; se ejecutó el enum y devuelve **ATTEND_FIGHT**. Su acción obtiene la frontera del encuentro, intenta acercarse y, en `eVq()`, toma `big.bqo()` como ID de combate. Si ya es el encuentro actual, no vuelve a enviar; en otro caso emite **`coL`, opcode 13413**, categoría 3, cuerpo i32 ID. Encoder ejecutado con 456: `0000000b033465000001c8`.

No hay handler/decoder 13413 en las fuentes Python inspeccionadas. La ruta de entrada no contiene selección de actor ni equipo: su implementación debe crear una subscription de observación, no autorizar participación basándose solamente en el ID. Validar existencia, mapa/instancia, acceso y generación; rechazar encuentro terminado. La restricción de frontera en UI no sustituye una validación del servidor ante una solicitud directa.

Con esto quedan identificadas solicitudes **13413 entrada / 12154 salida**, además del anuncio externo 13753. Todavía faltan el bootstrap de observador y las respuestas de rechazo; no se ha ejecutado observación real ni demostrado que esas tres piezas por sí solas basten.

## Codec de anuncio ya existente

`combat_multiplayer_wire.external()/decode_external()` ya codifican 13753 y exigen dos líderes existentes y topología propia. Reutilizar este codec; la brecha es integración/ciclo y significado de datos, no ausencia de encoder. Las doce pruebas `test_combat_shared` pasaron, con payloads sintéticos que no acreditan visibilidad nativa.
