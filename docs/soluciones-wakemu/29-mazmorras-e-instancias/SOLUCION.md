# Solución del servidor — mazmorras

Esta especificación parte de código y contratos cotejados. Migración 065 y `maps/dungeon_instances.py` implementan el núcleo durable de sesión/roster como componente aislado; no lo conecta al transporte ni cambia posiciones. Los puntos sin fuente acreditada siguen abiertos; no se sustituyen por reglas arbitrarias.

## Datos de entrada y salas

Para el recorrido normal candidato de Jalató: elemento 26842 en mapa 527, destino 2504, plantilla de instancia **91**, definición **90**, mapa interior **1086**. Para la variante `IsNeoServer()`: destino 4759, plantilla 199, definición 207, interior 1459. La selección debe proceder de configuración del servidor; no elegir por el nivel del personaje ni mezclar las variantes.

Extraer metadatos de `aKU`/`aLY` y enlaces del catálogo `native-generic-teleporters.json`. El recorrido normal tiene enlaces 26845→2506 y 26850→2510 entre sectores del mismo 1086; retornos 26849/26853 y salidas 26843/26844. Reutilizar geometría nativa. La identidad de sala necesita sector/encuentro además de mapa e instancia. [Datos comprobados](SALAS-Y-CICLO-DE-INSTANCIA.md).

**Bloqueante:** `[1,2,3,39,41,44]` es pertenencia de monstruos, no población por sala. No implementar el spawn hasta acreditar cantidades, niveles, posiciones y jefe por encuentro. No rellenarlo ordenando la familia por nivel.

## Hooks de acceso que hay que sustituir por autoridad de instancia

`maps/generic_transports.py::resolve` rechaza hoy condiciones y `cyZ >= 0`, y solo admite instancia 0. Las pruebas directas confirman que entrada y puerta interior fallan por criterio, y una puerta instanciada falla por contexto. `world_static.interaction` también exige instancia 0. La nueva autoridad de sesión no está conectada a esos handlers. Estos guards deben pasar a validar pertenencia, proximidad, variante y puerta habilitada contra la sesión de mazmorra. **No eliminar los guards ni aceptar cualquier instance_id.**

Separar definición90, plantilla91 y sesión viva: cada ejecución tendrá un ID propio, membresía, dificultad, sector actual y encuentros resueltos. Mantener grupos de monstruos y presencia por `(map_id, instance_id)`, y encuentros por `(instance_id, room_id, encounter_id)`. Entradas repetidas al mismo recorrido deben recuperar la sesión autorizada, sin crear otra ni repoblar.

## Resolución de combate y desbloqueo

Integrar la resolución donde el dispatcher usa `combat_lifecycle.prepare_finish`, conservando los recibos existentes de premios. Validar que el combate pertenece al encuentro/instancia, registrar el resultado una vez y habilitar solo su siguiente enlace. Ningún cliente debe poder avanzar enviando 12925, cambiando coordenadas o atravesando una puerta con un encuentro sin resolver.

12925 es limpieza/retorno del cliente: `combat_lifecycle.return_to_world` ya valida ID de combate y persiste salud una vez. El bloque12925 de `local_game_server.py` debe recuperar posición/contexto de la instancia para cada participante, conservar salud y liberar el lease sin borrar progreso. La confirmación de un miembro no puede gobernar el retorno de todos. Un ACK repetido debe recuperar el mismo estado sin volver a premiar.

Al perder/abandonar, el código actual restaura el grupo de monstruos y devuelve a la posición guardada; deja HP0 sin resurrección implícita cuando corresponde. No basta para definir derrota en mazmorra. **Reintento, expulsión, reentrada y conservación de avance aún necesitan acreditación nativa** antes de congelarlos en código/tests. Las pruebas existentes de combate individual no prueban esas políticas.

## Contexto de interfaz y dificultad

Sustituir el contexto constante de `native_transports.bootstrap` por el `ProtoDungeon` de la sesión al entrar y volver de combate. Campos y fixtures están en [INTERFAZ-Y-PROTOCOLO.md](INTERFAZ-Y-PROTOCOLO.md): nivel máximo/mínimo, dificultad, disponibilidad, permiso de aumentar, combate activo y IDs autorizados. Mantener exploración normal con su contexto correspondiente.

XP/drop: estado7447, característica115/116; grupos335565/335577 si `GetInstanceLevelMax()>0`, 335571/335583 si `<=0`. [Tablas concretas](DIFICULTAD-Y-MULTIPLICADORES.md). Aplicar el orden acreditado de bonus; no un multiplicador común a XP/drop/vida/daño. Los factores de PV y aumentos de PA/PM/voluntad de la enciclopedia ya están acreditados en ese documento; su aplicación efectiva en combate, daño, resistencias, elegibilidad y redondeo autoritativo siguen abiertos. Fijar revisión de configuración por encuentro para evitar cambios durante resolución.

12520 actualiza progreso personal por definición/dificultad; no es progreso de sala. Acreditar cuándo se actualiza el récord y mantenerlo separado del avance de sesión. No mandar la sala actual como dificultad.

## Dependencia real de grupos

Implementar la autoridad de party del issue15 y cotejar sus mensajes antes de certificar una mazmorra compartida. `COMBAT_GROUPS` no proporciona membresía de jugadores. La sesión de mazmorra debe decidir acceso por miembros autorizados y mantener su progreso aunque cambie el líder; las reglas exactas de expulsión, incorporación tardía y desconexión siguen por verificar.

## Criterio de cierre

Recorrido real completo con composición acreditada, selector coherente, victoria y derrota, reentrada y dos grupos independientes; pruebas de duplicados/fallos sin premios dobles ni saltos de sala. No se considera resuelto por llegar a1086. [Pruebas y límites](PRUEBAS.md).


## Integración concreta del escalado: restricciones actuales

El cotejo actual identifica dos etapas que deben compartir autoridad, no un parche al serializador:

1. `maps/monsters.py::owned_instance` calcula curvas por referencia/nivel y fija `instance_id=0`. Debe distinguir la definición base del actor de encuentro y recibir contexto de sesión autorizado (ID, tipo, dificultad, revisión de configuración). Conservar valores base separados de valores efectivos.
2. `combat_bootstrap.create_placement` reconstruye cada miembro con `owned_instance` y exige igualdad completa. Cambiar HP, PA/PM o `instance_id` solo en el diccionario externo fallaría ese guard. La validación debe reconstruir el mismo actor de encuentro desde su contexto persistido; nunca desactivar la comparación.
3. `combat_actor_snapshot.build_npc_snapshot` reconstruye curvas base; `_finish` sustituye HP/AP/MP/WP desde recursos vivos del actor. Eso puede conservar recursos escalados si la etapa anterior los inicializa correctamente, pero **voluntad** necesita aplicar su aumento a la característica correspondiente antes de fijar el snapshot. Confirmar identidad numérica desde el registro; no asumir que es el índice de HP o resistencia.

Escalar una sola vez desde la base, fijar la revisión durante el encuentro y producir recursos/estado serializado desde ese resultado. Reconexión y reintento deben recuperar HP actual, no curar mediante reconstrucción del máximo. Validar cotas nativas y decidir redondeo efectivo solo con fuente acreditada. El contexto constante no-mazmorra de `native_transports.bootstrap` debe reemplazarse mediante la sesión, no mediante campos enviados por el jugador.

[Cotejo y hashes del código inspeccionado](probe-cotejo-construccion-actores-mazmorra.json). No se ejecutaron hechizos, se alteraron actores ni se implementó esta integración.
