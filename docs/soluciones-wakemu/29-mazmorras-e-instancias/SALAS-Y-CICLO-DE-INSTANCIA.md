# Mazmorras: salas, resultados, interfaz y grupos

## Procedencia comprobada de las salas

Las salas usan geometría y elementos interactivos del contenido instalado. El catálogo exportado `server/protocol/native-generic-teleporters.json` permite reconstruir enlaces; no contiene la población de cada encuentro. La lectura nativa de `aKU`, mediante `bam`, produjo 151 definiciones.

La definición candidata 90 contiene mapa interior 1086, exterior 527, tipo `DUNGEON_3_ROOMS` y referencias de monstruos `[1,2,3,39,41,44]`. Es una lista de pertenencia a la mazmorra: **no demuestra cantidades, niveles ni distribución por sala**. La variante 207 usa interior 1459 y reemplaza 44 por 5791. No mezclar ambas variantes.

| Enlace nativo | Origen | Destino normal |
| --- | --- | --- |
| Entrada 26842 / destino 2504 | 527: −245,−90,2 | 1086: 4,−12,0 |
| Puerta 26845 / destino 2506 | 1086: 0,−27,0 | 1086: 152,−10,0 |
| Puerta 26850 / destino 2510 | 1086: 150,−26,0 | 1086: 151,−149,0 |
| Retornos 26849 y 26853 | Sectores posteriores de 1086 | Sector anterior |
| Salidas 26843 y 26844 | 1086 | 527: −245,−89,0 |

El mismo mapa contiene varios sectores; identificar una sala solo por `map_id` es incorrecto. Los destinos distinguen `not IsNeoServer()` de `IsNeoServer()`, que selecciona 1459. La entrada referencia `cyZ=91` o `199`, IDs de plantilla `aLY`. Se ejecutó su lectura: **91 → definición 90; 199 → definición 207**. El consumidor `bEk` hace `fqv.WQ(cyZ)`, toma `fqA.gkF()` y busca `eQN.QN(...)`. [Prueba de correspondencia](probe-plantillas-instancia.json). No confundir plantilla/definición con el ID de una sesión viva de mazmorra. Coordenadas y condiciones completas: [prueba de lectura](probe-puertas-salas.json).

`generic_transports.resolve` rechaza criterios, `cyZ >= 0` e instancias distintas de cero. Por tanto, este resolver no implementa el recorrido de mazmorra. Quitar esos controles sin una autoridad de instancia permitiría saltar el progreso; no es una solución válida.

## Ganar, perder y volver al mundo: comportamiento actual

`combat_lifecycle.prepare_finish` entrega premios locales al ganador; `combat_results.finish_messages` envía 12238 y 12755. El retorno espera 12925 con ID de combate válido. `return_to_world` persiste salud; el dispatcher restaura posición/bootstrap y resuelve el lease de monstruos. Al perder o abandonar restaura el grupo; al ganar lo marca derrotado. **Nada de ese recorrido registra sala superada ni desbloquea una puerta de mazmorra.** El premio local tampoco acredita recompensas ni multiplicadores oficiales.

La integración necesaria tiene dos hitos distintos: resolución autoritativa del combate, que registra una única vez el resultado del encuentro; y limpieza 12925 de cada cliente, que permite devolverlo a exploración. Un ACK repetido o ausente no debe duplicar premios, avanzar otra sala ni bloquear a los demás miembros. La puerta debe consultar encuentro/sala de la instancia, no la presencia de un monstruo o un flag enviado por el cliente.

Las reglas exactas de derrota —reintento, expulsión, posición de retorno, conservación del avance y reentrada— **siguen sin acreditarse en el contrato nativo**. No se presenta una política inventada como comportamiento oficial. Falta ejecutar victoria, derrota y abandono dentro de una instancia real; no se ha probado ese ciclo completo.

## Interfaz y dificultad

`native_transports.bootstrap` emite 13974 con un contexto `eUZ` de valores no mazmorra. Teletransportar al mapa no suministra el contexto de mazmorra ni acredita selector, puertas o progreso. Se debe cotejar cada campo y mensaje que consume la UI existente, sin cambiar el cliente.

El cargador `bam` consulta estado 7447 y grupos 335583/335577. Ya se extrajeron las diez entradas y el consumidor acredita drop normal/competitivo; también se identificaron dos series de XP. [Tablas, semántica acreditada y límites](DIFICULTAD-Y-MULTIPLICADORES.md). Vida, daño, resistencias, cálculo efectivo del servidor siguen pendientes. No aplicar un único multiplicador genérico.

## Grupos de jugadores

`COMBAT_GROUPS` y su lease representan monstruos; no equivalen a un grupo de jugadores. `characters/social.py` adapta inicialización social, pero no aporta el servicio de invitación/membresía. Falta cotejar protocolo y autoridad de party antes de afirmar que una mazmorra admite grupos.

La instancia necesita membresía y progreso propios, separados del ID de party: comprobar qué sucede al salir, expulsar, cambiar líder o desconectar durante sala/combate; quién fija dificultad; quién puede incorporarse tarde; y qué participantes reciben el resultado. Dos parties en el mismo mapa deben tener mobs, puertas y progreso independientes. Estas transiciones deben probarse con dos personajes/grupos; el combate individual actual no las demuestra.

## Límites que impiden considerar terminada la solución

Composición exacta por sala, contrato de inicialización de la instancia, tabla completa de dificultad, contratos de UI y party, y reglas verificadas de derrota/reentrada. Las puertas y la geometría ya tienen fuente concreta; la población y estas reglas aún requieren investigación. No hubo cambios de implementación.
