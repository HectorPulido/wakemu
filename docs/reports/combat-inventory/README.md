# Inventario de combate y seguimiento

Hay **722 hechizos de clase**: 383 activos y 339 pasivos. Incluye **6129 estados**, **55480 definiciones de efectos** y **227 familias** contando los estados.

**61 de 107 familias de los árboles de hechizos tienen ruta de ejecución registrada. Esto NO es el porcentaje de hechizos terminados.** La implementación tiene límites; las pasivas necesitan además sus eventos e instalación. Hechizos con prueba individual completa registrada: **0**. Las victorias previas no se convierten automáticamente en pruebas completas de cada hechizo.

El código nuevo no se marca como cargado ni probado jugando. El reinicio solicitado sigue pendiente de autorización.

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
| [Sacrógrito](clases/11.md) | 21 | 20 | 0 |
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
| 1013 | 101 | Sin manejador |
| 1093 | 101 | Sin manejador |
| 430 | 84 | Sin manejador |
| 315 | 78 | Sin manejador |
| 843 | 73 | Sin manejador |
| 1083 | 58 | Sin manejador |
| 48 | 54 | Sin manejador |
| 402 | 52 | Sin manejador |
| 447 | 46 | Sin manejador |
| 303 | 44 | Sin manejador |
| 345 | 42 | Sin manejador |
| 28 | 41 | Sin manejador |
| 16 | 33 | Sin manejador |
| 1084 | 33 | Sin manejador |
| 649 | 32 | Sin manejador |

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

Estado: Conectado en código; pendiente cargar y probar jugando. Ruta13260 prepara transacción, ejecuta raíces sin whitelist de raza y confirma paquetes. Costes y recursos se conservan ante fallo. El servicio activo no se ha reiniciado para cargar esta entrega.
Evidencia: ['server/wakfu_server/combat/combat_server_spell.py', 'server/wakfu_server/combat/combat_spell_transaction.py', 'server/wakfu_server/combat/combat_spell_commit.py', 'server/tests/test_combat_spell_transaction.py']
Siguiente paso: Cargar con autorización pendiente y comprobar daño, efectos propios y fallo sin gasto.

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

