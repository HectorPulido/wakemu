# 39. Alimentación de monturas y mascotas

**Cambio hecho no confirmado — r12 hereda la implementación desplegada en r9.** Migración064 aplicada en el mundo activo. Gates integrados aprobados; TLS verifica XP50, curas1/20, replay y reconexión con ProtoPet persistido. Pendiente aceptación visual. La guía [PRUEBA-GENERAL](PRUEBA-GENERAL.md) prepara un Dragopavo modelo76 antes de medianoche UTC y lo alimenta tras el cambio de fecha, sin editar estado SQL. Las secciones siguientes conservan el historial de investigación y candidatas.

Mantener separado de E17: equipar, montar y visibilidad del dragopavo ya fueron confirmados.

La inspección del cliente instalado confirma que `cMD.togglePetFeedingDialog` y los botones del diálogo usan eventos locales `18423` y `19558`; no son peticiones de red. Al soltar comida sobre la mascota, `cMD.feedPet` distingue primero la comida curativa. Para una comida curativa con salud faltante y pila mayor que uno, envía el evento local `16923` a un selector de cantidad cuyo máximo es `min(cantidad de la pila, salud máxima - salud actual)`. Para las otras comidas crea `diP` (subclase de `diq`) con cantidad inicial 1. `diP.d()` también devuelve `16923`. El listener `ddX` consume ese evento y comprueba flags/tipo del item, propiedad en el inventario, combate, compatibilidad con el modelo, hambre y nivel máximo antes de pedir confirmación.

Tras confirmar, `ddX.a(bLK,fnR,short)` crea `crX` opcode `12767`. `crX.aWH()` escribe dos `long` y un `int` big-endian: UID del item mascota, UID de comida y cantidad, 20 bytes dentro del wrapper de tipo 3. `mount_feeding_wire.py` implementa ese cuerpo. El cliente comprueba que la comida pertenece al inventario local y que no hay combate; el servidor debe repetir esas comprobaciones sobre su estado autoritativo.

El catálogo nativo `server/protocol/mount-models.json` contiene los 40 modelos y se cotejó con `sniffer/java/ExportMountFoodSemantics.java` (40 registros, cero errores). Las referencias `12284`, `13358` y `18377` son alimentos curativos por modelo: `YH=true`, con valor `YJ=1`, `YJ=1` y `YJ=20`, respectivamente, para los modelos que las ofrecen. No son alimentos de XP. `YI=true` identifica comida de XP: por ejemplo, `18378` es XP válido en los 40 modelos, incluso en los tres modelos cuya lista `gqr()` de dieta está vacía. La lista `gqr()` no basta para filtrar alimentos de XP. La migración 064 carga la matriz exacta por `(model_id,item_reference)` desde `aMo.ctc()` (curación `YH/YJ`) y `aMo.ctd()` (XP `YI`).

El lector nativo separa la mascota del item del actor montado. `ProtoItem` field 50 contiene `ProtoPet`; sus fields 6/7/8 son XP, `lastMealDate` y `lastHungryDate`. El `PET/rw` del actor contiene solo seis enteros (definición, color, equipo, sueño, salud y reskin), sin XP ni relojes; el carrier nativo para refrescar una entidad de actor es 15548. En el servidor actual, `mount_inventory` persiste XP, salud y fechas por UID, y `mount_codec.item_pet` serializa el ProtoPet.

**Elegibilidad temporal cotejada.** El envío XP se bloquea si `lastMealDate` cae en la misma fecha UTC actual: `ddX.a(fnR,bLK)` comprueba la bandera `YI`, llama a `fvL.a(fvH,now)` y rechaza si esa comparación de año/mes/día coincide. `TP` fija explícitamente `TimeZone.UTC` en su inicializador estático y `TP.bjy()` pone hora/minuto/segundo en cero. La ruta de envío no compara `gqs()`; ese mínimo solo se presenta en la descripción de dieta (`bLE.eH`). Por tanto, el gate del servidor usa el día UTC, no `meal_min_interval_seconds`. La rama de mascota dormida calcula y descarta un ajuste de elapsed antes de comparar las fechas originales, así que no hay evidencia de que sueño desplace el gate. Para hambre, `ddX.d(fvH)` calcula elapsed desde `gpK`; `TS.f(gqt)` hace división entera por la duración máxima y la tarea `ddX.f` sigue su aviso solo cuando el cociente es mayor que cero. Esta ruta de hambre es distinta de la elegibilidad de comida XP.

**Modelo local de estado y límites verificados.** `fvN` hidrata los campos del modelo `wS`: `aiE`→XP, `aiF`→última comida, `aiG`→última fecha de hambre, `aiH`→marca de sueño; `d(wS)` repuebla el modelo desde esos campos. Sus mutadores son locales: `mb(int)` limita XP a `[0, xpPerLevel × maxLevel]`, `Yz(int)` limita salud a `[0, saludMáxima]`, `ad(TQ)` fija la última comida, `ae(TQ)` la fecha de hambre, `ag(TQ)` el inicio/fecha de sueño y `Yy(int)` el entero de sueño. Cada mutador notifica observadores del objeto (`fvO`); ninguno es llamado por el camino de envío `crX/12767` en el cliente inspeccionado. `ddX.b(bLK,fnR,short)` calcula texto/animación local: para comida curativa muestra la curación calculada y para un item con efecto XP muestra `dYU × csW`; eso es presentación local, no evidencia de una mutación persistida ni de la regla del servidor. No se deduce del cliente cuánto XP/vida/tiempo debe otorgar un handler.

La búsqueda de referencias de mutadores en todo el JAR apunta a `fvJ` (construcción/copia desde `wS` o `lz`), `fvI` (fachada de cambios locales a XP, salud, nombre y sueño), `fvN` (hidrata estado), y `brA.getItem` (normaliza XP del item mascota al máximo). `fnR.a(wS)` asigna el modelo `fvJ.b(wS)` al item; el constructor de item `bJk.a(eGj,long,fqd,boolean)` crea un `fnR` nuevo y le asigna `fqd.gkv()` (`wS`). Esto prueba la ruta de carga de un ProtoPet al crear/hidratar un item, no que el consumer permita reemplazar el ProtoPet de un UID ya presente. `crX` es la única clase del catálogo de mensajes que emite opcode 12767; no aparece una respuesta específica de comida en el catálogo extraído. Esto no demuestra que el servidor carezca de una respuesta genérica de inventario, pero tampoco ofrece un contrato de actualización de `ProtoPet` ya insertado.

El item existente no tiene un opcode dedicado de refresh confirmado. El consumer nativo `chK` procesa `cxa/12471` como inserción: si el UID ya está en ese inventario, `Rj.a(C,short)` lanza `RV` antes de escribir el slot. `cwZ/12470` aplica un delta de cantidad con signo; `Rj.b(long,short)` llama a la eliminación normal si el resultado llega a cero. Ejecuté un probe offline contra `Rj` del JAR instalado: insertar UID, rechazar inserción duplicada, delta `-1` que elimina una pila de cantidad 1 y reinsertar el mismo UID en el mismo slot sí funciona. Esto acredita el comportamiento del modelo local de inventario, no que el flujo completo de mensajes muestre correctamente la mascota o que exista un ACK/retry de refresh. El único candidato basado en mensajes observados es publicar, en orden, la eliminación de cantidad `-1` y después `12471` con el mismo UID/slot y el ProtoPet nuevo; debe verificarse con el cliente antes de habilitar consumo.

El `12471` de inserción y su payload completo hidratan mascotas: `bJk.a(eGj,long,fqd,boolean)` crea el item y carga `fqd.gkv()` (`wS`), y `fnR.a(wS)` crea el modelo pet. No encontramos un mensaje genérico alternativo que actualice `ProtoPet` en un UID ya existente. `12691` es la bandeja de drops temporales y `13078` actualiza el registro de equipo, no el inventario normal. La ruta implementada usa retirada y reinserción con el mismo UID, sujetas al gate de imagen y TLS. Un fallo entre ambos mensajes de la secuencia candidata deja al cliente temporalmente sin item; como no hay ACK de aplicación ni idempotency key, el servidor no debe reemitirla ciegamente en la sesión actual. La comida, cambios ProtoPet y recibo se confirman en una sola transacción; un envío parcial requiere cerrar la sesión y recuperar con el snapshot autoritativo de reconexión, sujeto a prueba real. No confundir `16923`/`18423`/`19558` —eventos UI locales— con el opcode de red `12767`.

La capa de dominio está en `server/wakfu_server/items/mount_feeding.py`; usa lease/account/character, bloquea el pet y luego el alimento bajo el lock del character, comprueba participación durable en combate, cantidad, modelo/dieta y persiste estado, consumo y recibo en una transacción. El tope de XP sí está verificado exactamente: `fvN.mb` calcula `min(max(0,xp), fwr.csW() * fwr.aWa())`, equivalente al catálogo `xp_per_level × maximum_level`. El delta configurado de XP usa `xp_per_meal × cantidad`; la curación solo se permite con un mapping SQL explícito por referencia y limita cantidad a la necesaria para la salud faltante. No se infiere efecto por nombre. La migración 064 contiene las filas nativas de comida para cada modelo; cualquier referencia sin una fila correspondiente falla cerrada. La comida actualiza `last_meal_date`; `last_hungry_date` solo cambia si la fila SQL habilita explícitamente `reset_hungry_clock`. La comida XP se limita a una vez por fecha UTC, conforme al predicado nativo; `meal_min_interval_seconds` se conserva como dato descriptivo, pero no bloquea el opcode. La comida curativa puede repetirse si falta salud. El cliente establece UTC explícitamente en `TP.<clinit>`; el servicio usa esa misma zona para el predicado de fecha. La petición 12767 no tiene nonce, así que no puede garantizarse exactamente-una-vez para dos acciones idénticas. La migración 064 configura un debounce local (`replay_window_ms`, default 3000, rango 0–10000); no es una regla nativa. Para detectar una repetición incluso si la primera petición consumió toda la pila, el servicio consulta el recibo bajo el lock de mascota antes de comprobar la comida. Dentro de la ventana y con la revisión intacta no reemite paquetes; vencida la ventana, la petición idéntica puede ser una nueva acción si queda comida.

El adaptador `mount_feeding_dispatch.py` publica el lote solo después del commit, no reenvía paquetes de replay y propaga fallos de socket; la integración del dispatcher debe cerrar esa sesión para recuperar el snapshot al reconectar. Ya está conectado al dispatcher en fuente: los errores del dominio se manejan antes de publicar; los errores posteriores al commit se propagan para cerrar la sesión y recuperar el snapshot al reconectar. `test_mount_feeding.py` cubre recibo/replay (incluida pila consumida), XP y tope, curación repetida con salud faltante, política SQL para los 40 modelos, combate/lease, ownership, cantidad y rollback. `test_mount_feeding_wire.py` verifica eliminación de cantidades consumidas y reinserción de la mascota con el mismo UID/slot y ProtoPet; `test_mount_feeding_dispatch.py` cubre publicación, replay y fallo de socket. El gate fuente/PostgreSQL aislado ejecutó 36/36 pruebas (incluidas migraciones y enrutamiento) y aplicó 064 en esquemas UUID temporales. Falta probar el intercambio completo de paquetes con cliente; el handler no debe considerarse validado hasta esa prueba.

**Trazas locales reproducibles (JAR instalado, sin modificarlo):** `ddX` está en `.runtime/local/mount-feeding-ddX.javap.txt`: `d(fvH)` (línea 54, bytecode 0–33) calcula elapsed desde `gpK` y compara con `gqt`; `b(aAa)` (línea 74) despacha el evento local; los chequeos de comida/ownership/combate/modelo están en `a(bLK,fnR,short,boolean)` (línea 489; ramas relevantes bytecode 54–294); el request se crea en `a(bLK,fnR,short)` (línea 702; `crX` serializa UID mascota, UID comida y cantidad). `fvL.a(fvH,TQ)` está en `.runtime/local/mount-feeding-fvL.javap.txt`, línea 84, bytecode 0–97; la rama de sueño ocupa 24–52 y la comparación final de fecha 53–97. `TP.bjy()` (normalización a medianoche) está en `.runtime/local/mount-feeding-TP2.javap.txt`, línea 1090; `TP.l(TQ)` resta timestamp base de `now`, y `TS.f(TT)` hace división entera (dumps `.runtime/local/mount-feeding-TP2.javap.txt` y `.runtime/local/mount-feeding-TS.javap.txt`). `fvN` getters/mutadores e hidratación están en `.runtime/local/mount-feeding-fvN.javap.txt`: `a(fwr,TQ)` línea 56, `Yz` línea 275, `mb` línea 317, fechas `ad/ae/ag` líneas 336–366, `Yy` línea 366 y `d(wS)` línea 530; `ddX.b(bLK,fnR,short)` (presentación local) inicia línea 830. El enlace de ProtoPet al item aparece en `.runtime/local/mount-feeding-fnR-full.javap.txt` (`a(wS)`/`efH`), y su constructor de item está en `.runtime/local/mount-feeding-bJk.javap.txt` (`a(eGj,long,fqd,boolean)`). Referencias de mutadores escaneadas por ASM en `.runtime/local/mount-feeding-mutator-callers.txt` con fuente `.runtime/local/ScanPetCalls.java`; llamadas a la fábrica `fvJ` y al setter de ProtoPet están en `.runtime/local/mount-feeding-factory-callers.txt` y `.runtime/local/mount-feeding-protopet-setter-callers.txt`. `fvJ`, `fvI`, `wS` y `crX` inspeccionados con `javap -c -p` en los dumps `.runtime/local/mount-feeding-{fvJ-full,fvI,wS,crX}.javap.txt`. `cMD.feedPet` y selector de cantidad están en `.runtime/local/mount-feeding-cMD.javap.txt`; modelo/dialog `bLE` en `.runtime/local/mount-feeding-bLE.javap.txt`. Los consumers 12471/12470 están en `.runtime/local/review-continuacion-20261004/trade-chK.javap.txt`, `.runtime/local/review-continuacion-20261004/trade-cxa.javap.txt`, `.runtime/local/review-continuacion-20261004/trade-cwZ.javap.txt` y `.runtime/local/mount-feeding-Rj.javap.txt`; el probe reproducible contra el modelo nativo está en `.runtime/local/InventoryPetRefreshProbe.java`.

## Validación de imagen y reconexión — 7 de octubre

La candidata aislada `23c96da` pasó 332/332 pruebas con aplicación congelada. La primera ejecución del runner falló en cuatro importaciones por la ubicación del paquete de tests; se corrigió el runner, sin cambiar la aplicación. El smoke TLS verificó alimentación XP, curación, repetición y límite diario, pero detectó ausencia de registro rico `13078` al seleccionar de nuevo el personaje: SQL conservaba el ProtoPet, mientras `13713` BAGS omite esos campos. La dependencia está corregida en fuente, con 38/38 pruebas PostgreSQL y 14/14 puras; una imagen derivada debe pasar TLS antes de desplegar.

Los objetos nuevos de mascota tienen `last_meal_date` del día actual: no son elegibles para otra comida XP ese mismo día UTC. El harness limpia ese campo únicamente en su DB aislada para preparar una mascota elegible; no modifica la regla nativa. La prueba manual puede usar una mascota ya existente cuya última comida sea de una fecha anterior o preparar una mascota nueva antes de medianoche UTC y alimentarla después. `!item` requiere cuenta autorizada; curación manual requiere además una mascota propia con salud faltante.

## Smoke TLS corregido — candidata r3

Imagen aislada `3b159da95f28f9e0b26a3061504cbcad1ab3946211bae78f611238f4d894841b`: smoke TLS aprobado. Verifica XP+50, repetición sin mutación, rechazo diario sin consumir, curación1 y20 limitada a salud faltante, retiro/reinserción del mismo UID y reconexión `13713 → 13078` con ProtoPet actualizado `→ 13778`. Artefacto privado `.runtime/local/candidate-mount-feeding-20261007/tls-output-r3.txt`. El gate completo de esta imagen está en curso; no está desplegada ni habilitada la prueba manual.

El gate posterior de r3 ejecutó338 casos:8 fallos y113 omitidos. Seis fallos correspondían a pruebas nuevas de carga estática35 que esa imagen no incluía; dos exigían el helper de hidratación de la fuente mientras el overlay usaba el serializador directo. Los113 tests PostgreSQL se omitieron por faltar `WAKFU_POSTGRES_TEST_URL`. Esta corrida no acredita un gate PostgreSQL ni una imagen integrada aprobada. El overlay siguiente incorpora helper y fix35; el gate final deberá usar DSN aislado explícito y un set congelado de pruebas, junto con las correcciones de duelos. El smoke TLS r3 aprobado conserva su evidencia independiente.

## Alimentación TLS en candidata integrada r5

Imagen8e019af2: prueba con cuenta nueva aprobada para XP50, curas1/20, actualización12470→12470→12471, replay y reconexión13078 con ProtoPet persistido. Artefacto `.runtime/local/r5-spectator-marker-smoke/mount-feeding-r5-20261007.txt`. No desplegada: la promoción integrada espera correcciones del retorno de duelos y los gates restantes.


## Despliegue integrado actual

Imagen `1c3bbea5` (r9), único contenedor `wakfu-local-world-1`, saludable. La alimentación ya no espera promoción; conserva el TLS r5 aprobado y el gate integrado posterior. No se declara aceptación visual ni se altera el límite diario para facilitar la prueba.
# Failed manual acceptance — 2026-10-09

Hector's Dragopavo feeding test failed. The client announces food XP, but the
pet panel remains level0, food quantity does not decrease, and the server
rejects with `Pet item must be an unstacked unit` although the mount is a
single visible item. Splitting the food does not resolve it. Feeding while
unequipped is unavailable. Unequipping also prevents mounting again until
reconnecting; reconnect restores mounting but not the reported XP/level.
The tooltip lists elemental mastery and movement speed, but the user reports
that the expected characteristics are not applied.

Server logs confirm character1 opcode12767 rejections at18:38:32,
18:39:32,18:39:51 and18:43:32UTC on2026-10-09. Client XP text is not proof of
a committed reward. Investigate request identity, stack validation,
transactional food consumption, pet hydration, equipment characteristics and
mount state together. This issue is open; earlier automated gates do not
override this failed live acceptance. Do not request another identical manual
probe until the failure has been reproduced and corrected.

## Confirmed protocol regression — 2026-10-09

The four native requests captured at 18:38–18:43 UTC serialize mount UID
`1099511628620` first (reference18704, quantity1), food UID `1099511627907`
second (wheat reference1752, quantity3), then quantity1. The decoder had these
UIDs reversed, so it validated the food stack as the pet and rejected all four
requests. The native client prints its XP message optimistically; there was no
successful durable feeding in these requests. Splitting food cannot fix this.

Source now decodes pet UID first and food UID second, matching `ddX` setters
`oa(pet UID)` / `nx(food UID)` and `crX.aWH`. Socket smoke fixtures previously
reproduced the server's mistaken order; those fixtures are corrected too.
A rejection now restores the rich ProtoItem registry after BAGS because BAGS
alone omits ProtoPet; this addresses lost local pet metadata after rejection.
These changes are source only until the complete world image is validated and
deployed. Feeding, mount re-equipping and actual mount statistics remain open
for acceptance. No XP/food state was manually changed for this investigation.

Successful feeding also publishes the updated `13078` rich registry after
`12470 → 12470 → 12471`. The equipped pet panel resolves that independent
registry; updating physical bags alone is insufficient. The socket harness
now requires the fourth packet instead of accepting only the physical refresh.

## Repeat feeding policy and native XP scaling — 2026-10-09

The live r55 test committed XP50 at 19:21:10 UTC; reconnect displayed pet
level1, proving durable XP while the open UI remained stale. The next request
at 19:23:17 UTC hit the daily gate. That is a failed immediate-refresh test.

Migration084 introduces boolean setting `pet_feeding_daily_limit_enabled`,
default true. Hector explicitly requested repeat feeding, so the current DEV
database setting was changed to false. This requires the new server source to
be deployed. No stored meal timestamps were changed. When false, both feeding
validation and the unmodified client's independent date gate are disabled: the
wire-only ProtoPet last-meal field is zero while storage and receipts retain the
real successful timestamp. The setting can be restored to true without losing
meal history. Receipt retry debounce remains in place to avoid transport repeats.

Equipped mount effects now evaluate native parameter pairs at the actual pet
XP level using the existing float32 native evaluator, rather than catalog values
precomputed at base item level35. For the Dragopavo coefficient0.8, pet levels
0/1/2/35/50 yield elemental mastery0/0/1/28/40. Level1 granting zero mastery is
native rounding, not missing XP; the item's static level35 tooltip is not proof
of the currently applied bonus. Successful feeding also refreshes the actor PET
observer, effective characteristics and current riding state after the rich item
registry. An additional client reconciliation fix is being integrated for open
pet panels, which otherwise retain an old item model after registry replacement.

Validation for this source change: **62 tests passed, zero skips**, using the
existing Compose `world` image only as an ephemeral test runner with the
current checkout mounted read-only. PostgreSQL tests used UUID schemas in
`wakemu_migration_test`, never runtime tables. Command modules:
`test_mount_feeding test_mount_feeding_wire test_mount_feeding_catalog
test_mount_feeding_dispatch test_mount_feeding_routing test_mount_inventory
test_mount_codec test_equipment_stats`. This verifies policy, durable meal
history versus UI projection, fresh grants, registry publication, actor refresh
ordering, and native XP-level scaling. Full integrated build/deployment and
manual open-panel acceptance remain required.

## r56 acceptance update — 2026-10-09

Repeat feeding now works manually, but immediate UI refresh is only partial:
Hector reports that touching another control updates the visible result.
Equipment statistics failed acceptance: large bonuses appear when equipping
and removing a mount, while feeding level increases do not update the bonus.
This remains open and must not be marked accepted.

The latest successful requests at 19:48–19:50 UTC belong to character6, not
character1. Its fed mount is UID1099511633734/reference18682/model76 and stores
XP400 (pet level8); its other mount UID1099511633735/reference18704 stores XP0.
The durable active build24 contains slots7 and13 only, no mount, and no build
save or activation requests were observed during that feeding window. A mount
in an unsaved local equipment preview does not prove durable equipment. This
difference is under investigation alongside deferred native item-effect reloads;
it is evidence to isolate the failure, not a claimed explanation of all UI issues.
No deployment or restart is authorized during the user's other manual tests.

### Confirmed captured-stat overwrite in full world refresh

The format11 world serializer copied the captured template's entire
`PUBLIC_CHARACTERISTICS` section (597 bytes) unchanged. Equipping or removing
a mount publishes a full PET/entity refresh after the authoritative build
stat snapshot, so that refresh could restore captured high characteristics.
This is a concrete serialization defect independent of the unsaved-preview
question. Source now serializes owned effective public characteristics with the
existing authoritative actor-stat codec for every format11 spawn/full refresh.
Combat arithmetic and spell behavior were not changed. Automated full-wire
transition regression is in progress; deployment and manual acceptance remain
pending. Native deferred item-effect recalculation is still being reviewed,
so this finding does not claim every reported preview problem is resolved.

The native client JAR now decodes the corrected full world snapshot completely:
92 public-characteristic rows and zero trailing bytes. The read-only character6
snapshot verifies HP860, owned total damage123, and elemental rows21–24 equal
zero, replacing captured elemental values71/435/435/184 and HP3084. The
serializer publishes all fresh native characteristic defaults before applying
owned values, so missing rows cannot retain old captured bonuses. Offline
oracle: `sniffer/java/ProbeWorldPublicCharacteristics.java`; private artifacts
are under `.runtime/local/pet-stats-world-refresh-20261009/`. This native decode
is not a manual acceptance of the live client or unsaved build previews.

Final regression for the captured-stat overwrite: **111 tests passed, zero
skips** across wire, mount publication, feeding, inventory, codec and equipment.
The real captured format11 template is refreshed through persisted equip →
eight meals (XP400) → unequip → re-equip, verifying owned total damage6/0/6
and explicit native defaults for capture-only characteristics. Native JAR oracle
`ProbeWorldPublicCharacteristics` confirms92 rows, damage6, elemental rows21–24
zero and complete decoding of `.runtime/local/dragopavo-owned-fmt11-xp400.bin`
(SHA256 `4b51ccbfb5e98cc0727289aa8459c4a054de397e31bbb0588d9fbabf90c32e8d`).
These source changes remain undeployed while Hector performs other tests.
