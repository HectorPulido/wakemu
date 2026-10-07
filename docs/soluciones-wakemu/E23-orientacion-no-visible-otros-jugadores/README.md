# E23 — Orientación invisible para otros jugadores

**En revision.** El usuario confirma que las flechas giran al personaje en su cliente, pero otro jugador no observa el cambio. El montaje del Dragopavo sí se publica correctamente entre ambos clientes.

## Cotejo inicial

El handler13655 de `server/local_game_server.py` solo atiende orientación si existe `fight`; prepara los paquetes de orientación y los envía a la conexión solicitante. Este fragmento no acredita difusión a los otros participantes. Fuera de combate debe investigarse además el mensaje nativo de giro y su actualización del snapshot de mundo. No se asume que ambos contextos compartan el mismo opcode.

## Verificación requerida

Dos jugadores en el mismo mapa/instancia: cuatro direcciones en exploración, colocación y turno; observador ya conectado y observador que entra después; ningún envío a otra instancia. Conservar dirección en snapshot y respetar permisos del actor. Cotejar la captura antes de cambiar el dispatcher. No modificar hechizos ni su orientación automática; E22 sigue separado.

## Carrier y límite del cotejo

Solicitud13655: actor i64 + dirección u8. Respuesta13494 incluye encabezado de acción de combate (fight/action/sequence) además de actor y dirección: no es un paquete genérico de9 bytes. El consumidor ejecuta la acción nativa de orientación. Antes de difundirlo a jugadores en exploración hay que comprobar si necesitan un contexto de combate instalado; conocer el opcode no acredita recepción visual en observadores externos. La prueba de dos clientes distingue exploración, movimiento y colocación.

## Prueba de dos clientes — resultado del usuario

1. Ambos personajes visibles en la misma zona.
2. Caminar se refleja correctamente en el observador.
3. Los cuatro giros manuales dejan al actor observado en la misma orientación.
4. Salir al selector y volver con el observador tampoco recupera la orientación actual del actor.
5. Durante colocación, el observador no ve al actor en modo combate ni ve sus giros.

Las capturas entregadas acreditan la divergencia. El fallo no se limita a una animación local: tampoco se restaura el facing al reentrar el observador. Deben verificarse tanto la publicación de giros como el snapshot inicial. La falta de representación externa del combate se cotejará aparte con el sistema de visibilidad de combates (issue16); un fanout de13494 por sí solo no acredita esa integración.

## Cotejo de exploración y snapshot

El evento mundial correcto es12401 (`ctz`): actor i64 + dirección u8; `cgN.a(ctz)` cambia el actor de mundo o espera a que termine su animación. Es respuesta, no solicitud. El request13655 comprobado se produce desde las interfaces de colocación/turno; todavía no se ha acreditado un request independiente de giro en exploración.

`characters` no persiste dirección; `wire.spawn_player` reemplaza XYZ del fixture, pero conserva su orientación, y `native_transports.bootstrap` usa dirección3 por defecto. Esto explica una vía concreta para snapshots incorrectos. La solución requiere dirección autoritativa persistente y su serialización nativa, además de difusión; no basta retransmitir13494.

El modo combate externo tiene otro carrier:13753 (`cuY`), consumido por `ckM` para instalar la burbuja/modelo de combate externo. Su integración pertenece a visibilidad de combates, issue16.

## Preparación en fuente, sin desplegar

Migración029 añade dirección nativa0–7 por personaje, default3. `wire.position` conserva XYZ y los demás campos del rE y sustituye únicamente su byte de dirección cuando existe el campo autoritativo. `native_transports.bootstrap` usa la dirección del personaje salvo override explícito del destino. Tests de fixture/SQL y conservación de campos delegados.

La persistencia y publicación de cambios manuales están conectadas en fuente como se detalla abajo. La aceptación visual sigue pendiente. La imagen d875 fue construida antes de029 y de esta integración.

`world_orientation.save` guarda dirección bajo el lease de sesión/personaje y devuelve el evento mundial12401. La ruta de exploración puede exigir ausencia de fase durable de combate; la ruta de combate requiere validación previa del runtime. No reemplaza acciones13494 ni modifica costes/hechizos. Helper integrado al dispatcher en fuente; regresiones de permisos, sesión caducada y codec verificadas en el gate siguiente.

## Dispatcher en fuente

13655 fuera de combate acepta solo el actor seleccionado y exige ausencia de combate durable; guarda dirección y publica12401 al mundo. En combate conserva `orient_actor`,13494, flush y checkpoint; después guarda la dirección del personaje seleccionado y envía12401 solo a observadores. No retransmite la acción de combate como evento mundial. Todavía no desplegado. La dirección final de movimiento también se conserva en el buffer de posiciones. Falta acreditar qué UI produce el giro en exploración y realizar aceptación visual.

## Dirección de movimiento y recuperación en fuente

El último paso validado de13331 actualiza dirección junto con XYZ en `Positions.move`. El batch PostgreSQL y su CAS incluyen dirección; Redis journal v2 conserva baseline/current completos y valida el rango0–7. No añade SQL por cada movimiento. El giro manual hace flush previo y reattach después del guardado para no dejar un baseline que sobrescriba la nueva dirección.

Antes del despliegue, el servidor anterior debe vaciar su journal v1 mediante salida ordenada. El nuevo contrato no interpreta registros antiguos como si tuvieran dirección. Gate aislado completado: **137 pruebas OK** con PostgreSQL y Redis DB15. Incluye recuperación tras caída, CAS de giro tras caminata pendiente, dirección en bootstrap y difusión mundial, publicación de monturas y migraciones. Cien movimientos no generan SQL por movimiento. Aún sin despliegue ni aceptación visual de la corrección.

## Artefacto preparado

Imagen `a5e33d94d8c06953899cc20324433dacbf6dbfb9c165f3a4c044e5519b2c9bc1` construida con migración029 e integración de orientación. El contenedor activo sigue en `f7599765`, saludable; no se reinició durante las pruebas manuales del usuario. Construir la imagen no acredita despliegue ni aceptación visual.
