# 22. Objetos sin identificar

## Identified sword rejected by equipment UI — source correction

Read-only inspection of actor13's Espada Mento UID1099511635222 confirmed both
identification receipts and selected damage mask26/resistance mask0. This was
not an unconfirmed elemental choice. Native13766 resolves the physical item;
the equipment/build registry13078 maintains a separate item representation.
Identification previously refreshed only the first representation, leaving a
previously published equipment item with its pending elemental state.

The three identification/element-selection/enchantment dispatcher paths now
publish the refreshed equipment registry after their native responses, with
explicit branch-local serializer imports. Six focused PostgreSQL/dispatch tests
passed; after correcting those imports, five dispatch tests passed again.
The installed Java client parser also verified physical, equipment and13766
carriers for that existing UID agree and report no pending elemental selection.
No live item repair or repeated identification was performed. Deployment and
graphical acceptance remain with the coordinated full-server build.

## Additional transactional review — source only

Ordinary bonus installation now constructs and validates its native BAGS13713
and item-state13766 responses before committing. A PostgreSQL regression forces
response rejection and verifies rollback of common shards, socket state, local
fee and installation receipt. The incremental-cost regression also reloads a
fresh character snapshot and verifies a nonzero passive bonus against an
otherwise identical unenhanced item. Both targeted tests passed; the broader
gate and graphical acceptance remain separate.

Native `bqI.dGz` counts only inventory reference27083 for the reserve. Request13269
contains the target UID and changed bonus references/cumulative shard amounts;
the separate request12365 carries a sacrificed equipment UID. Bonus definitions
are therefore not newly treated as consumable materials. The user's proposed
object-once rule still requires distinguishing equipment sacrifice from ordinary
effect installation. No consumption policy, migration or live state was changed
by this review.

## Socket bonus source correction — verified, not deployed

The user authorized the socket correction and explicitly prohibited restart.
The source now consumes common native Esquirlas27083, not bonus definitions;
uses the target item's level for bonus eligibility; treats unchanged late
confirmations as an authoritative refresh without another charge; and sends
BAGS13713 followed by native item-state13766 to refresh the open workshop while
preserving elemental selections. No gameplay state repair/refund was performed.

Luna's final targeted run passed28 tests with zero failures/errors/skips in
22.489seconds: test_socket_enchantment, test_socket_enchantment_concurrency,
test_socket_enchantment_wire and test_socket_enchantment_dispatch. SQL cases
used temporary schemas in wakemu_migration_test; the published runtime catalog
was read only. The initial run had two invalid concurrency fixtures missing a
required slot position; fixtures were corrected, preserving the production
validation, and the full targeted set was rerun successfully. The generated
13766 packet also passed the installed native Java decoder with sockets and
elemental state present. This is not a full-suite or visual acceptance claim.

The live server was independently observed as r61; these socket modules differ
from the corrected source. This review did not restart or deploy world. Retest
only after a separately coordinated full shared build/deployment. Previous
failed manual acceptance remains open until that acceptance passes.

## Failed socket bonus acceptance — Capa Jalosa

Hector reports ordinary socket installation fails manual acceptance. Before
reconnect the client repeatedly displays `Native socket bonus request contains
no changes`; after reconnect Capa Jalosa shows a blue elemental-mastery bonus,
but the native Esquirla reserve is unchanged and a comparison with another
unenhanced Jalosa shows no apparent stat difference. Do not mark socket bonuses
accepted from the persisted attachment alone.

Read-only request logs confirm one successful13269 request at2026-10-10
00:57:13UTC: actor6 inventory reference27094 decreased7→6, while reference27083
(Esquirlas) remained1. Subsequent requests were rejected without further
consumption. The prior manual command `!item 27094 7` incorrectly treated the
bonus definition as native currency. The server likewise aggregates consumption
by bonus reference. Currency mapping, immediate native UI refresh/no-op response,
bonus level eligibility and actual equipped-stat contribution require review.
No runtime correction or restart was performed for this report.

## Latest manual feedback

Hector confirms identification works. Socket/enchantment operations have not
been tested and remain pending; identification acceptance does not cover them.

## Estado actual — 2026-10-09

**Identificación aceptada en r55:** Hector confirmó en un objeto nuevo que el
interrogante desapareció, aparecieron tres engastes y se mostró la elección
elemental (aire23). Esta prueba reemplaza el fallo gráfico de r54 descrito
abajo. Persistencia tras reconexión todavía no confirmada en esta aceptación.
Sublimaciones se revisan por separado: instalar un pergamino y ejecutar su
estado de combate son capacidades distintas; no se consideran aceptadas aquí.
La revisión de instalación, comandos compatibles y pendientes del motor está en
[Sublimaciones](SUBLIMATION-REVIEW-20261009.md). Corrección de wire y consumo
de stacks verificada con 10 pruebas dirigidas y respuesta SQL aceptada por el
parser nativo; todavía sin desplegar por este agente. El mapeador general de
fuentes nativas se entrega sin hook automático para preservar combate.

**Última prueba gráfica:** La Cola25069 sí abrió el modal y permitió elegir fuego;
el tooltip cambió de agua a fuego. Se acepta selección elemental y su refresco.
El interrogante permaneció y no aparecieron engastes: identificación completa
sigue fallando en r54. El evento12487 de Audiluna a18:46:28UTC y su UID
1099511633590 tienen máscara fuego2, sin engastes ni recibo de engastes.

**Abierto por aceptación gráfica fallida de Hector; corrección general nueva en
fuente, todavía sin desplegar:** el reporte inicial describía identificación sin
resultado visible hasta reabrir; la prueba reciente precisa que selección
elemental funciona y lo que sigue incompleto son los engastes y el interrogante.
Se reprodujo con el lector del cliente la causa del recibo histórico de Npers:
engastes sin el campo requerido de referencia del objeto vacío. La imagen
activa r54 ya adapta ese recibo y el cliente nativo decodifica sus dos engastes
correctamente, pero eso no resolvía todo el recorrido. Se encontró además que
grants/drops/crafting preasignaban elementos aleatorios antes de identificar.
Ahora su función compartida crea máscaras pendientes cero y la selección12487
identifica elementos y engastes dentro de una sola transacción, sin cobrar ni
sortear otra vez al reintentar. Falta desplegar esta corrección y aceptar el
recorrido gráfico. No se cerró el issue ni se reinició world en esta revisión.
Validación: 10/10 pruebas de codec/dispatcher/estado pendiente, 14/14 de SQL
aislado y respuesta SQL real13766 aceptada por las clases del cliente con
elementos elegidos y engastes presentes. No equivale a aceptación gráfica.
También pasaron tres regresiones SQL dirigidas de crafting, drops e intercambio
parcial, que usan la creación y conservación compartidas de metadata.

El modal de selección elemental y el aviso breve de engastes son rutas distintas
del cliente; no todos los objetos abren un modal. El estado debe refrescarse sin
cerrar inventario en ambos casos. Evidencia y prueba exacta:
[revisión UI](UI-IDENTIFICATION-REVIEW-20261009.md).

Completar propiedades por unidad, identificación, selección elemental, engastes, reciclaje y sublimaciones con efectos reales.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Solucionado parcialmente.** La selección elemental12487, su respuesta13766 y la conservación de engastes por UID están desplegadas en la imagen78e8ae29. Gate imagen80/80 y recorrido TLS de elementos, inventario, merkagemas y combate aprobados. Falta aceptación visual del sistema.

La identificación inicial13787 se desarrolla por separado: política local parametrizada en SQL y premios persistentes. No está desplegada; su sorteo se basa en una utilidad nativa y no se presenta como fórmula original del servidor. Reciclaje/sublimaciones y efectos de encantamiento conservan sus tareas pendientes.

## Dependencias

0, 10, 11, 17, 23, 26, 30, 34. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Propiedades pertenecen a una unidad; reintento no vuelve a sortear; consumo/reembolso y modificación se confirman juntos.

## Contratos nativos resueltos tras las respuestas

[13787, 12487, 13766 y la condición de engastes sin identificar](REVISION-RESPUESTAS.md).

## Selección elemental automatizada

`server/wakfu_server/items/element_selection.py` (import público `wakfu_server.element_selection`) valida el UID poseído, una máscara acorde con los efectos elementales nativos de la plantilla, bloquea objetos equipados o en intercambio, persiste la selección por UID y responde con el frame 13766. La misma selección reintentada no vuelve a mutar; una nueva elección válida actualiza el estado existente. No divide stacks porque el protocolo acreditado solo identifica un UID y no hay contrato probado para crear otra identidad. El ledger está en `server/migrations/049_inventory_element_selection.sql`.

La migración 050 y `inventory_shards.py` conservan por UID el protobuf nativo `lD/ProtoShard`. La carga lo hidrata; `item_proto` lo transmite en campo 52 y `item_form` reconstruye la opción `vA` del inventario. La respuesta 13766 de 12487 incluye esos bytes si ya existen. Un fixture pasado por el cliente instalado recuperó un slot, un adicional, ambas sublimaciones y las cargas desde ambos carriers, sin cambiar el blob. El estado ausente sigue ausente: no se inventan slots ni se vuelve a sortear al reconectar. La copia por intercambio conserva el blob y las unidades socketed no se apilan ni se dividen.

El export offline encontró 9.163 de 20.230 plantillas con `fpC.gjv()` verdadero (`cpR` y `cpS` ambos distintos de cero). Esos bytes no acreditan por sí solos la regla oficial de generación, tasas ni costo del servidor original.

Se añadió en fuente una autoridad separada `shard_identification.py` con política **local y explícita**, aún no conectada al dispatcher ni desplegada. Usa el catálogo nativo de plantillas (incluye nivel y límites cpR/cpS) y los pesos observados en la utilidad `fpK` (cantidad 0/1/2/3: 30/67/38/15; colores rojo/verde/azul/blanco: 100/100/100/32), aplicando el clamp nativo de límites. Esta es una política configurable derivada de una utilidad del cliente; no está probado que el servidor original la invoque para 13787. El costo local configurado es 0 kamas, por autorización explícita del proyecto, no por evidencia de gratuidad oficial. El nivel mínimo local se compara con el nivel del objeto y devuelve el status 2 `TOO_HIGH_LEVEL`, nombre confirmado por el cliente, pero la correspondencia con `item_level` es una decisión local.

La generación conserva `ProtoShard` y un recibo único por personaje/UID dentro de la misma transacción; los reintentos devuelven los mismos bytes sin volver a sortear ni cobrar. Se opera sobre un UID unitario existente, sin consumir un slot nuevo. Los stacks se rechazan porque no se acreditó el split nativo ni cómo se asigna/retorna su UID. Por la misma razón no se emite el status 1 `NO_ENOUGH_SPACE`: no hay una separación soportada que necesite espacio y no se debe reutilizar ese status para errores económicos. Pruebas PostgreSQL aisladas de esta autoridad más el roundtrip de estado: 7/7 OK. Esto no equivale a validar un recorrido visual o integración 13787 completa.

Validación aislada: 56/56 pruebas de shards, elementos, movimiento, intercambios y migraciones; además, el probe Java nativo pasó el roundtrip de campo 52 y `vA`. La ruta12487 está conectada en fuente: rechaza combate antes de mutar, actualiza el inventario del servidor y responde13766. Tres pruebas ejecutan la rama real con fronteras aisladas (éxito, combate y petición inválida). El gate combinado de rutas16/16 pasó. No está desplegada.

## Engastes persistentes en desarrollo

Migración050 conserva `ProtoShard` por UID. La validación aislada56/56 incluye persistencia, elementos, movimientos, intercambios y migraciones; un lector Java nativo confirmó el recorrido campo52 y opciónvA. Esto conserva un estado conocido; aún no acredita sorteo, costos ni identificación13787.

## Versión desplegada — 7 de octubre

Imagen78e8ae29 (`wakfu-local-world:item-options-verified`), world healthy y HTTP200, migraciones049–051 aplicadas. Gate imagen80/80 y TLS elementos12487/13766, inserción/retirada de gemas con pilas, reintentos y reconexión aprobados. Smoke combate y recompensas aprobado;208 módulos de combate idénticos a la versión anterior. Backup previo comprobado754 entradas.

Aceptación visual pendiente. La identificación/sorteo13787 y la autoridad de combate compartido052 siguen fuera de la imagen activa. Los apartados anteriores reflejan etapas históricas.

## Integración de identificación inicial en fuente

La ruta13787 está conectada en fuente a la política local053 y al carrier13766. Valida posesión actual antes del recibo; reintentos devuelven los engastes actuales, sin segundo sorteo ni cobro. Un propietario nuevo conserva el estado existente. Auditoría PostgreSQL28/28; rutas/codec9/9. La imagen activa78e8ae29 todavía no incluye esta ruta.

La siguiente candidata requiere el DDL052 nullable para mantener la secuencia de migraciones antes de053, pero excluye los cambios de módulos de combate compartido. No se certifica TLS de identificación hasta ejecutar esa candidata.

## Candidata de identificación — 7 de octubre

La candidata aislada `wakemu-identification-candidate:20261007` (SHA `130ec9fd`) incluye 052 nullable y 053, sin cambios de módulos de combate. Gate dirigido53/53 y TLS 13787→13766 aprobados: status2 por nivel bajo, éxito con política local de costo7, retry idéntico sin segundo cobro, y reconexión con ProtoShard en campo52 y opción vA. Smoke de combate/inventario también aprobado. No está desplegada; la prueba gráfica continúa pendiente. El smoke fijó costo7 solo para comprobar el cargo atómico; el costo local normal configurado sigue siendo0 y ninguna de estas cifras se presenta como regla oficial del servidor original.

## Identificación inicial desplegada

Imagen130ec9fd (`wakfu-local-world:identification-verified`), healthHTTP200 y Docker healthy. Migraciones052–053 aplicadas;052 añade únicamente autoridad nullable, sin cargar nuevos módulos de combate compartido. Gate imagen53/53 y TLS identificación/nivel/cobro único/reintento/reconexión, más smoke de combate aprobados. Los208 módulos de combate son idénticos a78e8ae29. Copia previa PostgreSQL comprobada773 entradas.

Política SQL local activa: coste0 kamas, pesos del helper nativo fpK y requisito de nivel del objeto. Con pesos iniciales0–3 y mínimo1, Espada Mento recibe1–3 engastes; no se promete4. Falta aceptación visual, división de stacks y encantamiento avanzado. Las menciones de fuente/candidata en apartados anteriores son históricas.

## Encantamiento avanzado en fuente

Migración 054 y API transaccional para sacrificio, cargas, colores/orden y sublimación con política local SQL. Sacrificio requiere UID propio unitario y misma referencia por defecto; sublimación consume su objeto propio y exige regla de compatibilidad explícita. Reintentos sin nonce usan ventana configurable de 3 segundos: fuera de esa ventana una petición idéntica se trata como nueva acción, no se promete deduplicación perfecta. Revisión independiente en Docker: 27 pruebas PostgreSQL/puras aprobadas para mutaciones, equipo y dispatch de clima. Falta integrar/verificar respuestas nativas y edición 13269; estos cambios no están desplegados.

Revisión adicional PostgreSQL: dos regresiones de concurrencia/reconexión aprobadas. Solicitudes simultáneas idénticas de sacrificio consumen un UID, cobran 7 kamas una sola vez y producen un recibo; una sesión nueva recupera el resultado sin consumo adicional y la generación antigua queda rechazada. Coste 7 usado solo en fixture aislado.

Tres regresiones PostgreSQL de revisión independiente aprobadas: carrera de solicitudes, reconexión/lease antigua y rollback ante ProtoShard válido pero mayor que el carrier nativo signed-short. El encoder se ejecuta dentro de la transacción antes del commit. El smoke TLS encontró y corrigió imports de módulos de área: el dispatcher usa los alias públicos `wakfu_server.*`; nueva candidata en validación.

Gate de revisión ampliado: **41/41 pruebas Docker/PostgreSQL** de encantamiento, codecs, concurrencia/reconexión/rollback, engastes, elementos, movimiento de inventario y estadísticas de equipo. Prueba ejecutada contra fuente montada, no acredita todavía la candidata TLS ni el despliegue.

## Smoke de mutación en candidata

Candidata aislada `c7eaf390` verificó por TLS sacrificio12365→13703, BAGS13713, un recibo/consumo y retry tras reconexión. Esto acredita el recorrido de esa mutación, no todas las operaciones. El verificador Java de la respuesta completa falló por método protobuf obfuscado; no se cuenta como aprobación del consumidor nativo. Esta imagen no contiene todavía los overlays de bonificaciones pasivas de equipo; nueva candidata requerida para el sistema completo.


### Despliegue integrado verificado

Imagen `e839fd35a2c123b8c83006528cfabc8f7bb5c8e5c3d0973f347ffcadc5321742` desplegada en world; Docker healthy y `/health` PostgreSQL correcto. Migraciones057–059 aplicadas;388 patrones de sublimación en SQL. Gate de la imagen198/198 aprobado y TLS de combate individual/compartido, sublimaciones y clima acreditados. Respaldo previo privado `.runtime/backups/pre-integrated-20261007.dump`, archivo CUSTOM con793 entradas TOC. Aceptación visual pendiente; no implica cierre completo del issue.

## Contexto oficial — 8 de octubre de 2026

El usuario anunció una identificación de objeto en el oficial para aportar referencia. La captura acumulada incluye ese intervalo; hay que localizar solicitud, propiedades por UID y respuesta antes de afirmar que el flujo quedó reproducido. No confundir apertura de interfaz con identificación completada. Referencia privada: `.runtime/official-dungeon-capture/`, con manifiestos y contratos de versión registrados. No se declara aceptación ni cambio desplegado por esta captura.
