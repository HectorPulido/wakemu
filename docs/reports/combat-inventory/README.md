# Inventario de combate y seguimiento

Hay **722 hechizos de clase**: 383 activos y 339 pasivos. Incluye **6129 estados**, **55480 definiciones de efectos** y **227 familias** contando los estados.

Además se siguen **91 hechizos extra** otorgados por estados, innatas y otras rutas explícitas en [hechizos-extra.csv](hechizos-extra.csv). Sus rutas y revisión individual figuran en inventory.json. Esta lista todavía no acredita cobertura exhaustiva de transformaciones ni referencias dinámicas; no se incluyen en las cifras de ejecución del catálogo normal.

**86 de 107 familias de los árboles de hechizos tienen ruta de ejecución registrada. Esto NO es el porcentaje de hechizos terminados.** La implementación tiene límites; las pasivas necesitan además sus eventos e instalación. Hechizos con prueba individual completa registrada: **2**. Las victorias previas no se convierten automáticamente en pruebas completas de cada hechizo.

Que una ruta exista en código no demuestra que esté cargada ni probada jugando. Consultar el reporte de progreso para conocer el último despliegue y sus verificaciones.

## Cómo evitar repetir trabajo

- Consultar primero esta tabla, el detalle de clase y las evidencias en review.json.
- Escribir responsable, estado, evidencia, límites y siguiente prueba en [review.json](review.json). El generador nunca lo modifica si ya existe.
- Repetir una prueba solo si cambia su código/dependencia, aparece un fallo o queda pendiente un caso.
- Regenerar con `python3 server/tools/build_spell_inventory.py`. Las huellas SHA256 identifican las fuentes exactas de cada inventario.
- Revisar el [historial existente](../progress.txt) antes de abrir otra investigación.

Para dar un hechizo por comprobado, su evidencia debe indicar fecha, personaje/nivel/equipo, escenario, resultado esperado, resultado observado y casos pendientes. Usar estados: Sin revisión individual → En análisis → Implementado parcialmente → Listo para probar → Probado en juego. Si falla, registrar el caso concreto; conservar la evidencia anterior. Las notas pueden contener campos adicionales: el inventario mantiene el objeto review completo.

## Clases

| Clase | Activos | Pasivos | Prueba completa individual |
|---|---|---|---|
| [Feca](clases/1.md) | 21 | 18 | 0 |
| [Osamodas](clases/2.md) | 21 | 17 | 0 |
| [Anutrof](clases/3.md) | 21 | 17 | 0 |
| [Sram](clases/4.md) | 21 | 15 | 0 |
| [Xelor](clases/5.md) | 21 | 20 | 0 |
| [Zurcarák](clases/6.md) | 21 | 20 | 0 |
| [Aniripsa](clases/7.md) | 21 | 20 | 0 |
| [Yopuka](clases/8.md) | 21 | 20 | 0 |
| [Ocra](clases/9.md) | 21 | 19 | 0 |
| [Sadida](clases/10.md) | 21 | 20 | 0 |
| [Sacrógrito](clases/11.md) | 21 | 20 | 2 |
| [Pandawa](clases/12.md) | 21 | 17 | 0 |
| [Tymador](clases/13.md) | 21 | 20 | 0 |
| [Zobal](clases/14.md) | 21 | 19 | 0 |
| [Uginak](clases/15.md) | 21 | 19 | 0 |
| [Steamer](clases/16.md) | 21 | 20 | 0 |
| [Selotrop](clases/18.md) | 21 | 20 | 0 |
| [Hipermago](clases/19.md) | 26 | 18 | 0 |

## Prioridades comunes

Familias sin ruta de entrada, ordenadas por número de hechizos relacionados. Dependencias conservadoras; el orden no demuestra que implementar una familia baste para completar esos hechizos.

| Familia | Hechizos relacionados | Estado |
|---|---|---|
| 430 | 84 | Sin manejador |
| 345 | 42 | Sin manejador |
| 28 | 41 | Sin manejador |
| 1080 | 17 | Sin manejador |
| 1099 | 16 | Sin manejador |
| 47 | 13 | Sin manejador |
| 349 | 12 | Sin manejador |
| 332 | 11 | Sin manejador |
| 560 | 11 | Sin manejador |
| 561 | 11 | Sin manejador |
| 562 | 11 | Sin manejador |
| 563 | 11 | Sin manejador |
| 325 | 10 | Sin manejador |
| 1030 | 10 | Sin manejador |
| 305 | 8 | Sin manejador |

[Lista completa de prioridades](prioridades.csv)

## Archivos completos

- [Hechizos](hechizos.csv): uno por hechizo, con estados, condiciones, familias, responsable y siguiente prueba.
- [Familias](familias.csv): cobertura de implementación y hechizos afectados.
- [Estados](estados.csv): nombre, descripción y dependencias.
- [Efectos](efectos.csv): identidad nativa, parámetros, objetivos, área, reloj y banderas.
- [Pruebas](pruebas.csv): funciones existentes; su presencia no implica que se hayan ejecutado o pasado.
- [Inventario JSON](inventory.json): relaciones completas y huellas de fuentes.

## Inconsistencias detectadas

9 estados contienen referencias candidatas ausentes del catálogo. No se ocultaron ni se rellenaron con datos inventados: aparecen en estados.csv. Se deben revisar los parámetros dinámicos y la interpretación antes de concluir que falta un estado real. Ninguno de los 722 hechizos de clase tiene una dependencia ausente detectada por este recorrido.

## Límites de este inventario

Las dependencias incluyen todas las ramas y niveles, aunque algunas sean excluyentes. No se infiere comportamiento por nombres ni se considera una familia implementada como soporte completo. Las referencias de estados se extraen de los parámetros nativos304/321; otros mecanismos dinámicos requieren revisión manual. Invocaciones, zonas, desbloqueos y eventos no quedan resueltos por extraer el catálogo. El catálogo de clases no cubre todos los hechizos propios de monstruos.

### Objetivo y criterio de terminado

Estado: Activo. Todas las clases: hechizos, pasivas y estados. Terminado significa reproducir en el juego lo descrito, incluidas condiciones y casos de fallo. No basta extraer eventos o pasar pruebas internas.
Evidencia: ['docs/reports/progress.txt']
Siguiente paso: Resolver primero motores comunes; después probar cada hechizo y pasiva.

### Lanzamiento común

Estado: Desplegado; lanzamientos concretos comprobados en cliente. La ruta común 13260 está cargada en el servidor. Sangre Ardiente funciona según prueba del usuario; Pie de Roca aplica armadura y los golpes de wonejo la consumen según prueba del cliente. Esto no acredita todos los hechizos ni todas sus condiciones.
Evidencia: ['server/wakfu_server/combat/combat_server_spell.py', 'server/wakfu_server/combat/combat_spell_transaction.py', 'server/wakfu_server/combat/combat_spell_commit.py', 'server/tests/test_combat_spell_transaction.py']
Siguiente paso: Completar el harness que detecta bloqueos del cliente, rechazos, latencia y ausencia del efecto esperado; verificar cada hechizo con escenarios propios.

### Características de jugadores y monstruos

Estado: Implementado y probado internamente. Datos nativos, equipo y aptitudes forman el snapshot. Serialización de máximos, porcentajes y recursos verificada con cliente Java. Dependencias automáticas de cambios de máximos aún necesitan revisión.
Evidencia: ['docs/protocol/native-actor-snapshot-audit.md', 'docs/protocol/native-snapshot-characteristics-wire.md', 'server/wakfu_server/combat/combat_actor_snapshot.py']
Siguiente paso: Comprobar equipo antes/durante/después del combate y tras reconectar.

### Daño y curación

Estado: Implementación parcial y pruebas internas. Elementos, dominios, resistencias, armadura/barrera y orientación. Ramas no soportadas rechazan. Curación sobre no muertos y todos los flags todavía requieren revisión.
Evidencia: ['server/wakfu_server/combat/combat_damage_handler.py', 'server/wakfu_server/combat/combat_healing_handler.py', 'server/wakfu_server/combat/combat_damage_healing.py']
Siguiente paso: Probar valores, orientación, objetivos múltiples y efectos encadenados en cliente.

### Bonificaciones y pérdidas de características

Estado: Implementación parcial; pruebas internas. Bonificaciones/pérdidas actuales, máximos de PA/PM/PW (31/41/191), modificador de coste PA (1065) y efecto nulo parametrizado (400) implementados. Reducciones de máximos 192/57 y otros límites especiales pendientes.
Evidencia: ['server/protocol/effect-characteristic-registry.json', 'server/wakfu_server/combat/combat_stat_handler.py']
Siguiente paso: Resolver reducciones de máximos y verificar aplicar/retirar sin acumulación.

### Aplicación y retirada de estados

Estado: Implementación parcial integrada. 304 aplica estado y sus hijos;321 retira o reduce, recreando hijos con UID y caster correctos. 17 pruebas de runtime y48 de estados reportadas por subagente. No implica eventos pasivos funcionales.
Evidencia: ['server/wakfu_server/combat/combat_state_handler.py', 'server/wakfu_server/combat/combat_state_decurse.py', 'docs/protocol/native-state-applicator-parameters.md']
Siguiente paso: Comprobar estado visible, hijos, reducción y desaparición en juego.

### Duración y expiración

Estado: Turnos implementados; realtime y retraso pendientes. Retira hijos antes del estado y preserva sincronización y recursos. Realtime y ejecución diferida rechazan hasta tener scheduler verificado.
Evidencia: ['server/wakfu_server/combat/combat_timed_expiration.py', 'docs/protocol/native-effect-timing-context.md']
Siguiente paso: Probar inicio/final de turno, muerte y fin del combate.

### Empujes, atracción, teletransportes e intercambio

Estado: Conectado a la entrada común; implementación parcial. Las seis familias de desplazamiento están conectadas. Transposición pasa la prueba interna desde la entrada común, sin modificar el combate original durante la preparación. Colisiones, altura, actores transportados y modos especiales siguen pendientes. Regresión del identificador base corregida: los efectos nuevos usan su UID propio. Las13 pruebas de transacción pasan, incluidos Soplido y Transposición.
Evidencia: ['server/wakfu_server/combat/combat_displacement.py', 'server/protocol/native-runtime-adapter-notes.md', 'server/tests/test_combat_spell_transaction.py']
Siguiente paso: Cargar el código y comprobar desplazamientos en terreno real.

### Eventos de pasivas y estados

Estado: Curación automática integrada y probada internamente; resto parcial. Proveedor ordinario enlazado por adaptador y factory: fases previas y posteriores, evento de curación, activación de grupo y retirada al agotarse. Root comprobó cinco pruebas de integración automática. Faltan otros emisores y orden global acreditado para varios propietarios.
Evidencia: ['docs/protocol/native-combat-event-audit.md', 'docs/protocol/native-state-carrier-client-audit.md', 'server/tests/test_combat_event_replay.py']
Siguiente paso: Extender ciclo común a daño, muerte y turnos; verificar pasivas jugando.

### Innatas y desbloqueo de hechizos

Estado: Instalador transaccional probado internamente. Instalación exhaustiva auditada: 339 pasivas en ambos niveles legales y 118 combinaciones, total796casos.330pasivas pasan ambosniveles;9bloqueadas conresponsable ycausa. Reversión en todos los casos; no acredita activación jugando.
Evidencia: ['docs/reports/progress.txt']
Siguiente paso: Auditar cada uno de los339pasivos y sus combinaciones; comprobar activación y desbloqueos jugando.

### Invocaciones y Osamodas

Estado: Pendiente. Autoridad actual trabaja con roster ordinario fijo. Faltan crear actor, propietario, control, turno, muerte y catálogo de invocaciones. No se considera resuelto por daño genérico.
Evidencia: ['server/wakfu_server/combat/combat_ordinary_authority.py']
Siguiente paso: Diseñar ciclo genérico de actores nuevos, reutilizable entre razas y monstruos.

### Zonas, glifos y efectos de suelo

Estado: Pendiente. 315 es creación de zona, no retirada de estado. Grupos sobre celdas y elegibilidad de terreno aún limitados.
Evidencia: ['server/wakfu_server/combat/combat_ordinary_authority.py', 'server/protocol/native-runtime-adapter-notes.md']
Siguiente paso: Resolver propiedad de zonas, entrada/salida y duración.

### Críticos, azar y ramas

Estado: Parcial. Probabilidad y bloqueo con reglas nativas. Rama crítica seleccionada explícitamente por configuración de prueba; sorteo nativo de críticos pendiente.
Evidencia: ['server/wakfu_server/combat/combat_ordinary_authority.py', 'server/wakfu_server/combat/combat_server_spell.py']
Siguiente paso: Resolver sorteo crítico nativo; comprobar ramas normal/crítica.

### Condiciones y selección de objetivos

Estado: Implementación parcial; pruebas internas. 128 alias nativos de características exportados. Condiciones de nivel/estado, enemigo, propiedades de combate, invocación propia, equipo, presencia de efecto, pertenencia al combate y radio físico implementadas con contexto explícito. 22 pruebas de condiciones y 6 de adaptador aprobadas por root; contextos especiales y condiciones restantes pendientes. Selector nulo corregido: área centrada en lanzador; fcE con bit1 conserva su centro de celda. Root verificó 13 pruebas de objetivos.
Evidencia: ['server/wakfu_server/combat/combat_runtime_adapter.py', 'server/wakfu_server/combat/combat_conditions.py']
Siguiente paso: Priorizar condiciones compartidas; no inventar valores para contextos desconocidos.

### Pruebas y comprobación real

Estado: Resultados dirigidos registrados; GUI pendiente. Resultados recientes comprobados por root: 13 pruebas de transacción, 8 de porcentaje de vida/actualización, 6 de eventos ordinarios y 22 de condiciones. La prueba completa del inventario pasa: catálogo, relaciones, regeneración determinista y conservación de notas manuales. No son una suite global ni comprobación jugando.
Evidencia: ['docs/reports/progress.txt', 'server/tests']
Siguiente paso: Cargar con autorización y registrar personaje, escenario, esperado, observado, fecha y versión por hechizo.

### Trabajo previo del proyecto

Estado: Conservar; no reabrir sin fallo nuevo. Movimiento, zaaps y dragopavos marcados OK por usuario. Inventario/equipo funcionan parcialmente con errores reportados. Ecosistema/semillas y merkasaco conservan historial propio. Este inventario cubre combate, no sustituye reporte global.
Evidencia: ['docs/reports/estado-actual.txt', 'docs/reports/analisis-eventos.txt', 'docs/reports/progress.txt']
Siguiente paso: Consultar historial antes de repetir auditoría; revisar multiplataforma en el futuro.

### Áreas orientadas y condición de nivel de estado

Estado: Correcciones internas acreditadas; juego pendiente. Repetición focal de 84 casos sobre 31 definiciones con fuentes estables. Desaparecen los errores originales anI/HasState; persisten otros bloqueos. No equivale a 31 hechizos completos. Ampliación2026-10-04: anE/anJ por puntos exportados y anv/cone paramétrico nativo;108 casos de cono y9 pruebas de geometría pasan. Tromba6469 legal/200 ya no rechazaanv; permanece condicionado a modos/estados.
Evidencia: ['docs/reports/combat-inventory/active-anI-hasstate-focus.json', 'server/protocol/native-oriented-area-audit.md', 'docs/protocol/native-has-state-level.md', 'server/protocol/native-cone-area-audit.md', 'server/tests/test_combat_cone_area.py', 'docs/reports/combat-inventory/native-cone-tromba-real-casts.json']
Siguiente paso: Resolver contenedores de estado y probar efectos en cliente.

### Contexto de estados durante efectos encadenados

Estado: Corregido y verificado internamente; cliente pendiente. Conserva el objeto nativo del estado durante todos sus hijos, aunque uno lo reemplace. Los UID obsoletos se rechazan fuera de esa ejecución. Tres pruebas y 16 casos reales de siete hechizos pasan con fuentes estables.
Evidencia: ['docs/reports/combat-state-container-scope.txt', 'docs/reports/combat-inventory/active-state-container-focus-v2.json', 'server/tests/test_combat_state_container_scope.py']
Siguiente paso: Comprobar en cliente después de cargar esta entrega; no interrumpir prueba actual.

### Condiciones con variables locales y alternativas

Estado: Implementado en motor común; cinco pruebas verificadas. Respeta árboles de variables, reasignación y alternativas condicionales nativas. Los criterios históricos ya parsean; las consultas a zonas todavía pendientes siguen rechazándose explícitamente.
Evidencia: ['docs/protocol/native-local-criteria.md', 'server/tests/test_combat_local_criteria.py', 'server/wakfu_server/combat/combat_local_criteria.py']
Siguiente paso: Conectar consultas de zonas cuando exista su autoridad nativa.

### Diagnóstico de solicitudes y efectos

Estado: Cargado y comprobado con solicitud TLS real. Correlación, estados antes/después, rechazo y tiempos; logs por lote y filtrado de credenciales.
Evidencia: ['server/tests/test_combat_diagnostics.py', 'server/tests/test_request_diagnostics.py', 'docs/reports/progress.txt']
Siguiente paso: Revisar los eventos reales durante las siguientes pruebas de cliente.

### group_level_transmission

Estado: Flag16 conectado a evaluación de hijos y campo4 eVt;27ReadyEniripsa validados. eYg/eZM transmiten fRR sólo cuando SP de familia=-1. Prioridad parentSP convertido short; después nivelPL real; nullPL0. Directspell exige level explícito. 19 pruebas focales y probeJAR PASS;27/27Ready reales conservan rollback con fuentes estables.
Evidencia: ['server/protocol/native-group-level-transmission-audit.md', 'docs/reports/combat-inventory/ready-group-level-transmission-focal.json']
Siguiente paso: Reutilizar contrato en949; ampliar contextos sin adivinar niveles de contenedor.

### ready_current_464

Estado: 464/464 inicios aprobados tras las correcciones recientes; versión cargada en servidor. 
Evidencia: ['docs/reports/combat-inventory/ready-current-recheck.json']
Siguiente paso: Verificar lanzamientos y activaciones durante turnos en cliente

### active_native_start_current

Estado: Revisión actual:383 hechizos activos en1514 casos; todavía incompleto. 
Evidencia: ['docs/reports/combat-inventory/active-native-start-recheck.json']
Siguiente paso: Ownership315 y consultas de áreas;familias865/447;pruebas reales cliente

### triggering_actor_identity

Estado: 16/16 casos antes rechazados ejecutan cambios sobre combatientes. 
Evidencia: ['docs/reports/combat-inventory/active-trigger-actors-focal.json', 'docs/protocol/native-trigger-identifiers.md', 'sniffer/java/ProbeNativeTriggerCaster.java']
Siguiente paso: Cargar cambios en servidor y verificar daño/estados visibles; ampliar casos de activación de pasivas durante turnos

### ready_routing_checkpoint

Estado: Regresión corregida:54/54 inicios básicos aprobados. 
Evidencia: ['docs/reports/combat-inventory/ready-routing-fixed.json']
Siguiente paso: Repetir todas las pasivas y verificar cliente antes de declarar soporte completo

### controller_deck_query

Estado: 12 casos antes rechazados ya se ejecutan:6 con cambios y6 sin efecto observado. 
Evidencia: ['docs/reports/combat-inventory/active-controller-deck-focal.json', 'docs/protocol/native-caster-controller.md']
Siguiente paso: Verificar costes y mazos con invocaciones/controladores reales; fuente desconocida sigue rechazada

### gui_sacro_sangre_5028

Estado: Pendiente. 
Evidencia: .runtime/local/instances/agent-spell-test/client-screen.png
Siguiente paso: Pendiente

### gui_movement_138995531

Estado: Pendiente. 
Evidencia: []
Siguiente paso: Pendiente

### forced_value_damage_healing

Estado: Pendiente. 
Evidencia: []
Siguiente paso: Pendiente

### value_transfer_orchestration

Estado: Pendiente. 
Evidencia: server/tests/test_combat_value_transfer.py
Siguiente paso: Pendiente

### resistance_cap_owned_stack

Estado: Pendiente. 
Evidencia: ['docs/reports/common-damage-armor-resistance-contracts.txt']
Siguiente paso: Pendiente

### group_flag15

Estado: validado_nativo_y_entrada_real. Flag15 KO no cambia eYg.bcd=true. Guard común admite y conserva flag;1542 niveles19/200 daño+muerte+curación0, fuentesestables yrollback2/2. No se amplía poblaciónKO sin autoridad.
Evidencia: ['docs/protocol/native-group-ko-flag15.md', 'docs/reports/combat-inventory/native-group-flag15-real-casts.json']
Siguiente paso: Pendiente

### triggered_zone_effect

Estado: validado_nativo_y_entrada_real. ePb fuentePK flag4 OR enumarea!=POINT; metadata178337.29tests+probenativoPASS.1542herido19/200 cura12/92,reaccionesnativas,rollback2/2 yfuentesestables. Sin defaultsdeactor ni forcingcriteria.
Evidencia: ['docs/protocol/native-triggered-zone-effect.md', 'docs/reports/combat-inventory/native-group-flag15-wounded-casts.json']
Siguiente paso: Pendiente

### weapon_damage

Estado: Entrada de armas integrada con motor común, costes/alcance/equipo autoritativos y daño de Luz. Auditoría: 463 armas pasan normal y crítico; persisten bloqueos por bonos de equipo, criterios y niveles superiores a 200. Aún pendiente despliegue y prueba gráfica.. 
Evidencia: ['server/protocol/weapon-combat-rules.json', 'server/protocol/weapon-combat-effects.json.gz', 'docs/reports/combat-inventory/weapon-damage-runtime-audit.md']
Siguiente paso: Resolver bonificaciones de equipo que bloquean snapshots y criterios pendientes; desplegar y probar armas en cliente.

### light_stasis

Estado: Luz1083 y Stasis917 integrados en motor común. Stasis usa mayor maestría y menor resistencia; Luz usa resistencia del elemento de mayor maestría. OriginalJava y9regresiones pasan; cargados boota1e61197. GUI y cicloSteamerator pendientes.. 
Evidencia: ['docs/protocol/native-light-damage-1083.md', 'docs/reports/combat-inventory/weapon-damage-runtime-audit.json']
Siguiente paso: Verificar hechizos completos Hipermago/Steamer en cliente y eventos de sus estados.

### Golpes críticos

Estado: Desplegado; pendiente verificar en cliente. Boot fe6b23ffc7bb401bbaa4c2756b94dee8 carga selección automática en hechizos y armas. Usa FEROCITY nativa9, indicador hasCriticalEffect original por nivel y una decisión por lanzamiento dentro del rollback. No se añade multiplicador universal; las ramas, maestrías y eventos son nativos. Pruebas de probabilidad y transacción pasan; GUI pendiente.
Evidencia: ['server/wakfu_server/combat/combat_critical.py', 'server/tests/test_combat_critical.py']
Siguiente paso: Verificar crítico y normal con notificaciones correlacionadas y efectos esperados en cliente.

### Tiempo de ejecución y geometría compartida

Estado: Puño y Atracción medidos en cliente, sin fallo de ejecución en estos casos. Puño: solicitud servidor 158 ms, paquetes 65 ms, resultado observado 1,38 s. Atracción: solicitud servidor 141 ms, paquetes 37 ms, resultado observado 1,33 s. Son tiempos distintos; la observación no mide sólo cálculo ni permite atribuir todo el resto a animación.
Evidencia: ['docs/reports/combat-inventory/immutable-terrain-optimization.txt', 'server/tests/test_combat_geometry_snapshot.py', 'server/tests/test_gui_combat_verdict.py']
Siguiente paso: Mantener presupuestos separados y medir otras familias; no extrapolar dos casos a todos los hechizos.

### Puño mediante confirmación común

Estado: Desplegado; prueba GUI de Puño pasa. Boot6ecf425a8ca646b8b2a881d32ffcca90. Puño: HP84→80, PA6→3. Animación13509 y daño12613 misma acción30/fight292704298. Solicitud servidor158ms, llegada65ms, observación cliente1,376s. No acredita crítico de Puño ni absorción de armadura en GUI.
Evidencia: ['server/wakfu_server/combat/combat_melee.py', 'server/tests/test_combat_melee.py', 'docs/reports/combat-inventory/unarmed-client-common-action-harness.json']
Siguiente paso: Ciclo hasta victoria y nueva pelea verificado por separado; crítico de Puño y absorción de armadura en GUI siguen pendientes.

### Ciclo completo de combate en el cliente

Estado: Verificado hasta victoria y entrada a un nuevo combate. 
Evidencia: ['docs/reports/combat-inventory/combat-cycle-client-evidence.json']
Siguiente paso: Verificar rendición y reutilizar este recorrido al comprobar cada familia de efectos.

### Condición de ataque por la espalda

Estado: Implementada; cinco escenarios antes bloqueados ya aplican efectos. Reglas originales de selección, orientación actual y propiedad 47 que anula el localizador. 112 posiciones comparadas con el cliente original, más ocho casos de firma/ausencia. Desplume, Cleptosram y Patada Azotada avanzan en cinco casos críticos, sin modificar el combate original. Fuente estable. Todavía no cargado en el servidor.
Evidencia: ['docs/reports/combat-inventory/active-critical-backstabbed-current.json', 'server/tests/test_combat_condition_facing.py', 'sniffer/java/ProbeNativeBackstabbed.java']
Siguiente paso: Cargar el checkpoint y comprobar giros y ataques en cliente.

### native_action_delivery

Estado: Corrección común cargada; ciclo completo pendiente de prueba. Identificadores únicos confirmados en cinco lanzamientos reales. No demuestra que todas las desconexiones estén resueltas. Rendirse y orientación también pasan por el asignador.
Evidencia: ['docs/reports/combat-inventory/state-client-native-action-evidence.json', 'docs/protocol/native-action-snapshot-order.md']
Siguiente paso: Pendiente

### general_first

Estado: Auditoría activa de contratos compartidos antes de mecánicas particulares. 
Evidencia: ['server/tests/test_combat_inventory_date_conditions.py', 'server/tests/test_combat_summon.py', 'docs/reports/progress.txt']
Siguiente paso: Revalidar objetivos/áreas y resistencias con fuentes actuales; corregir fronteras de eventos de turno contrastadas con cliente.

### inventory_date_conditions

Estado: GetDate/GetItemQuantity implementados y contraste original de fechas aprobado; delegación de inventario con roster de invocaciones aprobada en prueba. 
Evidencia: ['sniffer/java/ProbeNativeDateCriteria.java', 'server/tests/test_combat_inventory_date_conditions.py', 'server/tests/test_combat_summon.py']
Siguiente paso: Mantener límites explícitos para inventarios de invocaciones y calendarios fuera del contrato validado; verificar carga conjunta del servidor.

### current_fighter_condition

Estado: GetCurrentFighterId implementado con identidad del turno, independiente del caster; pruebas de autoridad y sintaxis aprobadas. 
Evidencia: ['server/wakfu_server/combat/combat_conditions.py', 'server/wakfu_server/combat/combat_runtime_adapter.py', 'server/tests/test_combat_inventory_date_conditions.py']
Siguiente paso: Validar criterios de pasivos mediante inicialización y ciclo de turnos comunes.

### general_area_footprints

Estado: Selector común corregido para radio físico del actor en áreas isotrópicas; 25 pruebas internas y probe original aprobados. 
Evidencia: ['docs/protocol/native-area-footprints.md']
Siguiente paso: Cuantificar definiciones alcanzables y validar integración sin afirmar razas completas.

## Prueba interna de inicialización por clase

Nivel 1 prueba las innatas. Nivel 200 añade las primeras seis pasivas válidas de la clase. Pasar significa que se instalaron sus efectos; no demuestra activación de eventos ni hechizos completos jugando.

| Clase | Nivel 1 | Nivel 200 |
|---|---|---|
| Feca | Instalación interna aprobada | Instalación interna aprobada |
| Osamodas | Instalación interna aprobada | Instalación interna aprobada |
| Anutrof | Instalación interna aprobada | Instalación interna aprobada |
| Sram | Instalación interna aprobada | Instalación interna aprobada |
| Xelor | Instalación interna aprobada | Instalación interna aprobada |
| Zurcarák | Instalación interna aprobada | Instalación interna aprobada |
| Aniripsa | Instalación interna aprobada | Instalación interna aprobada |
| Yopuka | Instalación interna aprobada | Instalación interna aprobada |
| Ocra | Instalación interna aprobada | Instalación interna aprobada |
| Sadida | Instalación interna aprobada | Instalación interna aprobada |
| Sacrógrito | Instalación interna aprobada | Instalación interna aprobada |
| Pandawa | Instalación interna aprobada | Instalación interna aprobada |
| Tymador | Instalación interna aprobada | Instalación interna aprobada |
| Zobal | Instalación interna aprobada | Instalación interna aprobada |
| Uginak | Instalación interna aprobada | Instalación interna aprobada |
| Steamer | Instalación interna aprobada | Instalación interna aprobada |
| Selotrop | Instalación interna aprobada | Instalación interna aprobada |
| Hipermago | Instalación interna aprobada | Instalación interna aprobada |

[Detalle de casos y errores](class-initialization-audit.csv). La tabla corresponde a la última ejecución guardada; las correcciones posteriores requieren repetir los casos.

