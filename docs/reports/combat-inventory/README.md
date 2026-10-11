# Inventario de combate y seguimiento

## Current provisional acceptance — 12/18

The user provisionally accepts Cra, Iop, Sacrier, Aniripsa, Osamodas, Ouginak,
Zobal, Huppermage, Sram, Feca, Pandawa and Ecaflip. Manual validation is deferred until the end;
this does not close documented conditional branches or shared combat risks.
Current inventory-only refresh: **Enutrof, Steamer, Eliotrope, Sadida, Rogue and Xelor**. Historical counts
below describe their original workstream milestones.

## Pandawa and Ecaflip workstream — 2026-10-10

The [coordinated workstream](pandawa-ecaflip-workstream-20261010.md) records shared
corrections, regression gates and the distinction between deployed changes and
new local changes. [Pandawa inventory and manual battery](pandawa-implementation-inventory-20261010.md)
covers21 actives and17 passives. Ecaflip has a [current catalog inventory](ecaflip-catalog-audit-20261010.md),
[runtime qualification](ecaflip-runtime-qualification-20261010.md),
[twenty-passive semantic matrix](ecaflip-passive-semantic-matrix-20261010.md)
and [complete manual battery](ecaflip-manual-acceptance-20261010.md).
Neither catalog presence nor initialization alone raises the provisional class count.
The [final technical and manual acceptance procedure](pandawa-ecaflip-final-acceptance-20261010.md)
coordinates both complete batteries and the shared combat checks.
Both classes are now technically ready for manual acceptance:182/182 tests passed
on the active joint class/monster deployment, with no failures, errors or skips.
The user subsequently accepted both provisionally, bringing the register to12/18.

The [full regression review](validation/full-regression-20261010.md) records
complete discovery results, fresh class/shared-combat follow-ups, outstanding
failures and the validated but unactivated copied-book catalog correction.
NPC failures are excluded from this workstream at the user's request.

## Remaining class inventory and implementation priority

[Refreshed six-class inventory](remaining-six-refresh-20261010/README.md) records current estimates, per-class reports and remaining integration risks. [Current implementation priority](next-class-priority-20261010.md) ranks the six classes outside provisional acceptance. This is a risk-based scheduling estimate, not functional certification.

[Complete review register](remaining-classes-20261010/README.md) preserves the thirteen-class baseline and links all thirteen
class reviews and reproducible machine inventories: 521 primary active/passive
definitions, 65 extra/granted records, states and secondary dependencies,
summon books, areas, class resources, lifecycle risks and shared engine routes.
[Published PostgreSQL reconciliation](remaining-classes-20261010/published-catalog-reconciliation.json)
checks all class rosters and innates, extras and 29 unique fixed summon profiles.
Catalog presence and route registration are separate from functional acceptance;
this inventory does not raise the playable class count or implement mechanics.

## Huppermage, Sram and Feca workstream — 2026-10-10

The [coordinated local workstream](hupper-sram-feca-workstream-20261010.md) covers
Huppermage, Sram and Feca in parallel. Each class
requires a refreshed PostgreSQL-backed inventory, evidence for missing routes,
local runtime verification and a complete manual battery. Shared engine changes
remain coordinated and prior-class regressions must pass. No restart or
deployment is included; the user subsequently accepted these three provisionally in the **10/18** milestone.

## Zobal workstream — 2026-10-10

[Current implementation and validation](zobal-implementation-20261010.md) records the shared initiative correction, complete copied-book metadata, staged catalog revision and bounded active/passive/mask/copy validation. The [complete manual battery](zobal-manual-acceptance-20261010.md) covers masks, all owned actives/passives, copy control and multiplayer cleanup. Zobal was subsequently accepted provisionally in the **10/18** milestone; deferred branches remain documented. No deployment or restart by this workstream.

## Osamodas incident fixes — 2026-10-10

[Incident evidence and recovery](osamodas-incident-recovery-20261010.md) tracks
capture eligibility, missing NPC appearances on reconnect and the placement
socket EOF. Ordinary PvE reconnect now projects the claimed NPC appearances
before the combat bootstrap; nonactive recovery preserves pending delivery and
ACK state. [Native NPC property serialization](osamodas-capture-client-property-fix-20261010.md) now passes the shipped Java parser through
all format2 sections, including capturable and noncapturable controls. The final
offline regression matrix passed **116 tests without failures or skips**. The original EOF remains unexplained because the client log rotated.
These are local changes, without deployment or manual acceptance.

[Captured-creature deployment correction](captured-summon-copy-clone-20261010.md)
addresses the subsequent Invocation7348 rejection reported at 01:15 local time.
Family1001 event clones now receive the allocated execution identity and do not
become duplicate retained listeners. The actual saved capture continuation
restored, deployed and completed the summon-owned7359 attack offline; 17 focused
regressions passed. Deployment and live-client acceptance remain pending.

[Cross-class visual-state inventory](class-visual-state-recipient-inventory-20261010.md)
scans the published visual effects and distinguishes the two exact Dragon
empty-area state-child failures from other visual paths. The [general one-time native recipient binding correction](state-visual-recipient-fix-20261010.md)
is implemented locally; the final shared gate passed **174 tests without
failures or skips**. Both native sex branches deliver their visual effect,
retain it in the active snapshot and remove it by UID on return. Rendering and
real socket reconnection remain manual acceptance requirements.
Pesante7313 in Dragon correctly targets self or an owned summon as its area
center; direct hostile-player targeting is not permitted by native criteria.

[Dragon self-cast damage incident](osamodas-dragon-self-cast-incident-20261010.md)
records the fight 161 Látigo 7317 failure: a self-selected Dragon AoE center lost
its native cell criterion context before root 326119 ran. A shared resolver
correction now preserves that input while child actor selection resets it. The
new 7317/7312 production regressions and focused cross-class gate passed **2/2**
and **115/115** respectively. These changes remain local. The appearance
intermittency is still open; emitted state effects do not establish rendered
client behavior.

## Osamodas inventory — 2026-10-09

[Complete manual battery — 2026-10-10](osamodas-manual-acceptance-20261010.md) includes capture-to-reuse, all21 actives/17 passives, Jamajam, Dragon, multiplayer and the33 catalog-eligible spawn commands. This is a pending test plan, not a class pass.

The next class workstream is **inventory only**, before implementation.
[Complete inventory](osamodas-complete-inventory-20261009.md) consolidates the
owned/granted spell and state register, captured-creature dependencies,
current source support, proven gaps, risks and acceptance requirements.
[Summon lifecycle](osamodas-summons-inventory-20261009.md),
[spells and states](osamodas-spells-states-inventory-20261009.md), and
[current bounded runtime validation](osamodas-runtime-risk-inventory-20261009.md)
provide detailed evidence. No gameplay change, restart or deployment is part
of this inventory. Existing [capture-to-reuse manual sequence](manual-osamodas-system-20261008.md)
is historical setup guidance, not a current client acceptance result.

## Aniripsa inventory — 2026-10-09

[Current local implementation and acceptance](aniripsa-implementation-review-20261009.md)
supersedes the inventory-only baseline below. General resurrection, protected
summon replacement and transmitted healing-recipient corrections are implemented
locally. Real healing, marks, deferred healing, areas and summon/passive scenarios
are being validated with prior-class regressions. No restart/deployment by this
workstream. [Complete manual test](aniripsa-manual-acceptance-20261009.md).

[Complete current Aniripsa inventory](aniripsa-complete-review-20261009.md):
original inventory-only baseline, before implementation. Current native scope:
21 actives,20 passives,3 granted actions,4 dependent summon profiles;
974 effects,51 states and82 families. No missing definitions/factory bindings
in the expanded closure. Baseline32/35 ordinary spell-level pairs and60/60
prepared commits; remaining pairs require ally/KO contexts. Passive cycles20/20,
with only3 specific activations observed. Resurrection, allied healing,
Contra Natura, marks/death chains, Cunejo and conditional passive acceptance
remain explicitly open. See the report for priorities and exact evidence.


## Sacrier inventory — 2026-10-09

[Current local implementation and acceptance](sacro-implementation-review-20261009.md):
normal Cra/Iop/Sacrier regression105/105 spell-level pairs and195/195 commits;
Sacrier passive cycles20/20, transformation lifecycle and three attacks passed.
No restart or deployment performed. Graphical/manual acceptance remains pending;
class acceptance remains2/18. The figures below describe the historical baseline.

[Complete Sacrier review and readiness measurements](sacro-complete-review-20261009.md):
inventory/audit only; no implementation or deployment by this workstream.
The register includes 21 actives, 20 passives, five granted actions, three morph
actions and two innates. Current dynamic reconciliation covers 1029 effects,
52 states, 68 effect families, area1605 and profile5900. State759 is missing.
Fresh basic normal casting prepares62/64 attempts; the two rejected Columnata
self-centered variants remain visible rather than being hidden by other
successful variants. Passive cycles:19/20, with Immolation7224 blocked by native
dispel flag17. These are scoped audit measurements, not a class completion
percentage. Shared current implementation, risks, exact backlog and complete
manual acceptance are linked in the review. Acceptance remains Cra + Iop2/18.

## Provisional class acceptance — 2/18

On 2026-10-09 the user accepted Iop provisionally, matching the existing Cra
acceptance. Count: Cra + Iop = 2/18. This records user acceptance, not exhaustive
manual certification. The initial PvP combos were observed by the user and
correlated with server traces, including fight 100 additional-damage combo.
Higher-level spells/passives, remaining numerical cases, PvM and intermittent
presentation issues remain subject to validation. Shared combat resilience is a
separate cross-class workstream; a class acceptance does not close it.


## Parallel resilience and aptitude review — 2026-10-09

[Shared combat guardrails](shared-combat-guardrails-20261009.md): r54 deployed and healthy with the corrected serializable AI claim; eight current guard/idle regressions pass, including actual context serialization.

[All aptitude attributes](aptitude-all-attributes-audit-20261009.md): selected-build cap validation corrected and deployed; 39 focused catalog/persistence/build tests pass. General tackle/dodge movement and native Barrier activation-count scaling are deployed with the matching complete catalog. Movement has 32 focused tests plus one real initialized-fight regression passing; real Barrier hit/exhaustion and per-turn renewal acceptance now pass. Renewal is deployed in r55. Received healing now passes actual allied-heal acceptance after a source-backed general group target-transmission correction; that correction and periodic renewal are deployed in r55. Arithmetic consumers and manual acceptance remain separately tracked. Final renewal-source regression passes35/35 across aptitude initialization, actual Cra/Iop casting and retained group/area lifecycles. [Complete 31-attribute manual acceptance](aptitude-manual-acceptance-20261009.md) records allocation, persistence, caps and combat checks.

## Coordinated r55 verification update

The concurrent agent deployed `wakemu-world:chat-admin-20261009-r55`
(SHA256 `dfaaaf6afb3a7b60e3373b1f09d0c4aaf0aabddeea71c4120d12107398ac3346`).
Running production hashes match the current periodic-aptitude, group dispatcher,
retained runtime, turn-start and turn-guard files. World is healthy and HTTP
health succeeds. This includes periodic Barrier renewal and explicit target
transmission alongside the other agent's changes.

The post-transmission batch completed62/64. One failure was new armor-test
instrumentation (group children execute directly, not through activation); its
actual armor assertion is retained. The reproducible Iop Preparation failure
is real: its damage modifier applies but its consumption criterion skips.
The final source correction now passes 16/16 focused tests (49.189 seconds),
including actual Preparation consumption, five policy cases, allied healing,
Cra casting and aptitude initialization/armor. The original 64-test batch has
not been rerun in full. This final correction is not deployed.
See the [deployment handoff](deployment-handoff-20261009.md).

## Environmental retained-effect lifecycle — 2026-10-09

[Preparation and native null-Qf lifecycle](preparation-null-qf-lifecycle-20261009.md): general environmental subscription release and final-modifier PV correction; actual Jabs/Bofetada environmental regressions and Cra regression pass.

## Multiplayer lifecycle — 2026-10-09

[Shared fight 97 recovery](shared-recovery-fight97-20261009.md): r51 deployed and healthy; map context, NPC retry, disconnected ACK membership and departed-player reconnect corrections. Dungeon recovery verified at room 2 with the original group available. Manual acceptance remains pending.

[Consolidated errors and acceptance](multiplayer-errors-20261009.md): joining, first-turn timeline, reconnect fencing, completion disconnects and friendly-duel QI registration. Automatic validation is recorded separately from manual acceptance.

## Multiple-death timeline delivery

Delivered and healthy: `timeline-death-complete-20261008-r35`. The next turn restores native12053/12514 after roster deaths, preserving normal later turns.14/14 focused tests pass. See [fight80 evidence and manual steps](fight80-multiple-death-timeline-20261008.md). The wrong-actor death-animation report remains separate and unverified.

## Shared summon and finisher delivery — 2026-10-08

The shared recognition correction covers class summon creation307/324/1002, current snapshots, controlled movement, retirement and reconnect. See the [general route inventory](class-summon-recognition-lifecycle-20261009.md). Shared1099 now includes owned account selection, client cosmetic updates, the original4464 tree, immediate/retained reconnection and cleanup after the actual12727 death action. It uses the explicit `wakemu.owned-finisher-boundaries-v1` policy; original external server producers are not claimed.

The final integration regression passed35/35 and the complementary suite passed24/24, including an actual initialized round4 lethal cast reaching native leaf185395 on the defeated enemy. Additional summon and cosmetic checks are recorded in the linked reports. Delivered and healthy: `wakemu-world:shared-finisher-complete-20261008-r34`, migration078 applied, all21 delivery-file hashes verified. Visible finisher acceptance remains pending; [exact whole-system manual steps](shared-finisher-manual-acceptance-20261008.md) include the one-item test command and the native unequip/relogin limitation. These results are not a certification of18 complete classes.

## Foco actual: inventario de código del ocra

Consultar el [inventario exacto del ocra](cra-code-inventory-20261008.md): 21 activos, 19 pasivas, 6 concedidos y 2 innatas, con dependencias y faltantes concretos de implementación. La ausencia de prueba manual no se clasifica como código faltante. Consultar la actualización de entrega siguiente para la versión actual; los porcentajes históricos siguientes no representan clases completas.

## Estado actual: 2026-10-08

Consultar primero el [estado actual consolidado](current-status-20261008.md): contiene el resultado del lote completo de las 18 clases, los huecos por mecanismo y las verificaciones pendientes. El último lote completo prepara y confirma **557/635 pares de hechizo/nivel (87,717%)**. Quedan 43 búsquedas sin contexto elegible, 32 rechazos compartidos y 3 predicados de objetivo sin resolver en esa captura; una repetición dirigida posterior resuelve esos 3 predicados. Este porcentaje corresponde exclusivamente al lote básico, no a hechizos completamente funcionales ni al sistema completo. Estados, pasivas, condiciones, invocaciones y cliente tienen requisitos separados. Las cifras de las secciones siguientes son checkpoints anteriores.

Los **32 rechazos** de aquella captura ya tienen repetición dirigida exitosa: 31/31 en un lote conjunto y el caso de disipación aparte. Falta repetir el lote completo con las correcciones; no se suma esa evidencia parcial para inventar un porcentaje global.

El [siguiente lote semántico](class-semantic-priority-next-20261008.md) enumera los casos ejecutables y sus requisitos. El [plan manual representativo](manual-representative-acceptance-20261008.md) concentra la aceptación del cliente en mecanismos compartidos; sus resultados siguen pendientes.

## Revisión actual: 2026-10-07

Consultar [la auditoría actual de las 18 clases](current-review-20261007.md) antes de usar las cifras y prioridades históricas de este documento. Las matrices generales guardadas no corresponden a las fuentes actuales; tener un manejador, instalar una pasiva o completar un ciclo interno no acredita un hechizo completo. Ninguna clase tiene comprobación completa registrada. Los resultados antiguos se conservan como evidencia, no como certificación del servidor actual.

La revisión inicial incluye los **383 activos** (1.714 escenarios, 161 rechazos) y las **339 pasivas** (319 ciclos observados, 20 bloqueos). La [repetición completa de pasivas](passive-foundations-activation-review-20261007.md) observa ahora **336 ciclos y 3 bloqueos**, con fuentes estables; 28 casos muestran activación, sin acreditar semántica completa. El [registro completo de verificación](verification-ledger-20261007.csv) cubre **722 hechizos de clase y 91 extras**, agrupando bloqueos por mecanismos comunes. La [extracción masiva](bulk-import-review-20261007.md) obtuvo en staging 4.143 hechizos nativos, 6.129 estados, 1.436 zonas y 81.965 efectos.

La [integración del motor de clases](class-engine-integration-20261007.md) registra los cambios locales posteriores: alcance condicional, modificadores, propiedad de efectos, áreas, relaciones de invocaciones y condiciones. La [última auditoría completa](class-engine-general-review-20261007.md) cubre los 383 activos en 1.704 escenarios: 57 rechazos, incluidos 30 candidatos rechazados correctamente por alcance. Entre los casos compartidos, 46 rechazos anteriores avanzan y no aparecen rechazos nuevos. Los 379 archivos de fuentes y datos observados permanecieron estables durante la ejecución; esto no acredita semántica completa ni entrega al cliente. La [clausura de datos de clase](class-only-bulk-closure-20261007.md) no encuentra árboles ni efectos faltantes en las 813 referencias clasificadas. La [prueba completa de inicio y dos turnos](ready-basics-boolean-border-review-20261007.md) pasó 54/54 casos: las 18 clases en niveles 1, 20 y 200, sin pasivas seleccionadas. No se reiniciaron ni desplegaron servicios. El alcance actual excluye hechizos de monstruos; la IA se revisó solo para comprender la integración.

El [mapa de dependencias por hechizo](class-dependency-coverage-20261007.md) separa los 813 hechizos de sus familias, estados, condiciones, zonas, innatas e invocaciones. El [registro de evidencia por mecanismo](class-mechanism-evidence-20261007.md) distingue datos exportados/publicados, implementación, pruebas unitarias, auditoría interna y prueba manual de cliente. La [publicación de dependencias de invocaciones de clase](class-summon-dependency-import-20261007.md) añade 38 árboles y 297 efectos: las 43 habilidades nativas tienen una clausura de 623 efectos. No equivale a 43 nuevos hechizos de clase ni a invocaciones totalmente comprobadas. La tanda dirigida posterior pasa 51 pruebas de invocaciones, compilación restringida y superficies; no acredita todo el mapa de mecánicas.

El [índice completo de mecánicas y huecos](class-mechanic-gap-index-20261007.md) añade el grafo nativo tipado final: **764 estados**, **90 áreas**, **21.207 efectos** y **58.729 aristas**, con matrices para las 18 clases separando innatas comunes de dependencias de sus hechizos. Los estados se clasifican como 79 parciales, 682 pendientes de verificación y 3 ausentes; las 116 funciones condicionales incluyen 89 parciales y 27 sin ruta explícita. Los 130 objetos estructurales del parser incluyen operadores y literales, no 130 predicados. Las rutas de familias sin creación/control de criaturas siguen en **145/177 (81,9%)** con el grafo nuevo: es registro de implementación, nunca porcentaje funcional. Depósitos de Anutrof, WALL y bits de objetivo 44/46 quedan como huecos concretos. La comparación contra datos persistidos y sus uniones de metadatos no encuentra definiciones faltantes ni divergencias en los campos nativos comparados de los 21.207 efectos; eso no acredita su ejecución.

## Inventario generado histórico

Las cifras, estados y notas siguientes proceden del inventario anterior. No describen automáticamente el código actual; en particular, las etiquetas «Sin manejador» de familias como 305, 430 y 345 requieren contraste con los checkpoints posteriores. Usar los informes nuevos para decidir trabajo actual, sin borrar la evidencia histórica.

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

## Prioridades comunes históricas

Fotografía histórica de familias sin ruta de entrada; no es una lista actual de bloqueos. Ordenadas por número de hechizos relacionados. Dependencias conservadoras; el orden no demuestra que implementar una familia baste para completar esos hechizos.

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

[Lista histórica completa de prioridades](prioridades.csv)

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
Evidencia: ['server/protocol/weapon-combat-rules.json', 'server/protocol/weapon-combat-effects.json', 'docs/reports/combat-inventory/weapon-damage-runtime-audit.md']
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


Casting denominator checkpoint (2026-10-07): [complete casting-table inventory](class-casting-gap-inventory-20261007.md) records851 scoped spells,968 raw expressions,672 conditional rows,62 function names (5 casting-only), and2152 root selector/geometry definitions. Effect-only116 predicate names are a separate denominator. [Current combined gap index](class-mechanic-gap-index-20261007.md) supersedes historical selector44/46 gap rows;108 masks are now recognized. Overall functional/client completion remains unknown.

Current flow evidence: [class access, initial summon states, and reaction checkpoint](class-flow-checkpoint-20261007.md). Ready reaches 34/36 class-level cases; 116 granted UIDs resolve and expire correctly. These are access results, not completed spell gameplay. The latest production-Ready summon probe creates all six initial-state profiles and observes 1,341 native events with nine successful retained activation calls; Cra beacon reactions remain unproved. This probe does not validate normal cast permissions or resource commitment. No deployment or manual acceptance is included.

Current manual plan: [eight representative acceptance cards](manual-representative-acceptance-20261008.md). Start with range, beacons, captured summons and carrying; the implementer prepares exact fixtures and expectations before Hector tests. Exhaustive manual spell/enemy combinations are not required.

## Fight82 shared corrections deployed

See [corpse LOS and summon refresh](fight82-corpse-los-and-summon-refresh-20261008.md). r39 preserves concurrent dungeon breeding changes, retires completed NPC death obstacles, preserves summon recognition on tactical bulk refreshes, and uses Lua-exact NPC identities. Offline repair remapped166 available groups;33 unavailable groups were intentionally preserved. Fresh-fight manual acceptance remains pending.

Latest deployment: r40 corrects the retired NPC snapshot NameError that disconnected Fight83 after a lethal attack. See the Fight82 report above for the actual regression and targeted validation.

Latest r41: native parser-verified inventory shard initialization fix; preserves r40 death snapshot fix. Login/entry acceptance passed41 pure+14 isolated database tests. Initial invisible-player symptom and cold entry delay remain under investigation.


## Current Iop source and semantic inventory

The [current Iop/Yopuka inventory](iop-current-code-inventory-20261008.md) covers21 active spells,20 passives, four granted abilities, two innates,59 states and74 effect families. Current published definitions and handler bindings have no missing entries. Separate source review identifies **three incomplete semantic paths and one partial event gap**; these now have shared repairs and actual-route automated validation; client acceptance remains pending. See [exact producer/context evidence](iop-semantic-producer-current-audit-20261008.md) and [machine-readable inventory](iop-current-code-inventory-20261008.json). Whole-system manual acceptance is prepared in the inventory for after repairs and automatic validation; routing coverage is not class completion.

Sacudido8913/event2236 correction: the shared current-stat consumer receives native ARMOR97 reduction notifications2236, including family1011 produced events. Damage2 is also present. An Iop-local publication-mask census cannot exclude incoming general/cross-class events;2236 is **not** classified as an absent producer.


## Iop repair delivery update

The shared Iop context, Preparation and voluntary-movement repairs are delivered in the complete r47 image. Current code and catalogs were verified before restart; actual Iop/Cra regressions and summon retirement checks passed. See the [delivery and validation record](iop-shared-repair-delivery-20261009.md). Manual whole-class acceptance remains pending.

## Iop level 60 manual acceptance

[Complete level-60 test plan](manual-iop-level60-acceptance-20261009.md): decks, five combos, Preparation/environment regression, banner variants, available passives, movement, LOS and multiplayer/dungeon lifecycle. Higher-level abilities remain explicitly pending.

## Aniripsa / Cunejo integration follow-up

[Current review and remaining inventory (2026-10-10)](aniripsa-cunejo-integration-review-20261010.md) records the native explicit-recipient correction, fresh regression results and ordinary-monster activation boundaries.
