# Orientación303: cálculo y entrega al cliente son contratos distintos

El manejador común calculaba eWF.C/c correctamente y cambiaba `Actor.direction` en el preview, pero enviaba13497/cvY. El consumidor original aTR.cbj registra/limpia el runner: no llama eWF.c. Eso permite un resultado servidor correcto con el actor cliente mirando en la dirección anterior.

La corrección específica de la familia nativa eWF303 envía12613/cvX, eIK=false, con el mismo iN evaluado. aVo.cbj termina la acción gráfica y aVo.cYg llama eZR.a(...,false) cuando el runner no está suscrito; eZR.a invoca eWF.c, que aplica `aAS.wL(value)` a PV. No se cambian otras familias de características ni la política de registro de suscriptores.

## Prueba original

`ProbeNativeOrientationDelivery` decodifica con eWF.ds un payload generado por el serializer servidor, usando la definición real326140 de Desplume7318 y value5. Compara ambos consumidores:

-13497/aTR: decodedDirection5, actorDirection0 permanece0.
-12613/aVo: al ejecutar el callback original de finalización cbj(), eWF.c recibe5 y actorDirection pasa a5.

El escenario usa PV/PN controlados y la cola aER original. La escena gráfica no se renderiza en este proceso offline: por eso invoca explícitamente el callback original de finalización. Acredita el consumidor y la mutación al completar; no acredita que una animación se renderice, su duración ni resultado GUI.

```sh
PYTHONPATH=server python3 - <<'PY'
from pathlib import Path
from wakfu_server.combat_stat_effects import owned_effect_payload
from wakfu_server.combat_native_timing_context import native_time_payload
Path('.runtime/local/orientation303-delivery-payload.bin').write_bytes(owned_effect_payload(
    uid=900,base_uid=None,generic_effect=326140,caster_id=7,target_id=-7,value=5,
    timing_payload=native_time_payload(),execution_status=0,executed=True))
PY
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/ProbeNativeOrientationDelivery.java
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java -cp 'client/lib/*:.runtime/local/classes' ProbeNativeOrientationDelivery .runtime/local/orientation303-delivery-payload.bin
PYTHONPATH=server:server/tests python3 -m unittest test_combat_orientation_effect test_combat_observation_delivery test_combat_target_life_selectors test_combat_diagonal_cross -q
```

Resultado: original PASS;20 pruebas Python PASS. La regresión verifica opcode12613, eIK=false y UID/baseUID/direction/target exactos; prueba inversión de actor en modo8, guard51, no cambio, retirada sin restaurar dirección y rollback del RNG ante fallo posterior de codec. Salida durable en docs/reports/combat-inventory/native-orientation303-delivery-probe.txt. Aún pendiente ejecución GUI tras despliegue coordinado.

## Entrada común Desplume

Focal normal7318 a niveles20/200: ambos ejecutan el efecto303 real326140 y emiten12613; daño10/12, rollback2/2 y hashes estables. Reporte orientation303-desplume-runtime-audit.json. La definición original326140 tiene modo6 (copiar orientación del lanzador): el fixture tiene caster.direction0 y el objetivo pasa3→0. Esto acredita aplicación del modo y entrega; no acredita que0 dé la espalda geométricamente al atacante. La alineación del lanzador durante el lanzamiento requiere auditoría separada antes afirmar el resultado visual solicitado por el usuario. El objetivo de nivel200 muere por el golpe después de la orientación; no se usa ese caso para afirmar postura de un actor vivo tras la animación.

## Casting alignment discovered after the delivery correction

The first runtime audit copied caster direction0 as mode6 requires. That did not
establish that Desplume turned its victim geometrically away from the caster.
The original spell7318 has bPK.cbH=1002410. Its installed Lua delegates to1040
with turnCasterTowardTargetCell=true and useDiags absent. Template1040 first
calls Mobile.setMobileLookAt(caster,targetX,targetY,false), then executes the
scheduled effects. aiL uses aBA.bXz and ignores NONE for identical XY;
beS.a updates the underlying big actor direction as well as its mobile.

The private common spell transaction now mirrors this accredited cardinal
alignment before creating the effect dispatcher. It never mutates the source
fight on a failed transaction. This is metadata driven, with no spell whitelist.
The compact export covers4143 spell identities:2090 literal1040 contracts and
2053 pending scripts. Nineteen literal contracts request diagonal alignment;
that branch remains unapplied pending aBz.bo verification. Pending scripts
preserve previous behavior and do not reject otherwise valid casts. These
limitations are explicit; this does not establish all casting scripts' facing.

Reproduce the metadata:

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/ExportNativeCastScripts.java
java -cp 'client/lib/*:.runtime/local/classes' ExportNativeCastScripts .runtime/local/native-cast-scripts.tsv
python3 server/tools/export_native_cast_facing.py .runtime/local/native-cast-scripts.tsv server/protocol/native-cast-facing.json
PYTHONPATH=server:server/tests python3 -m unittest test_combat_cast_facing test_native_cast_facing_export test_combat_orientation_effect -q
```

The focused pure suite passes13 tests. A refreshed common-runtime Desplume
geometry audit and GUI observation remain pending; no GUI success is claimed.

### Follow-up: real geometric matrix and diagonal paths

`audit_cast_facing_geometry.py` runs six common casts (levels20/200, three
cardinal target positions). Initial caster directions are changed through the
normal13655 orientation request, not by overriding Actor.direction. The shared
cast mirrors the original1040 alignment, then303 copies that facing to the
victim: west-facing caster turns east and victim ends east; north-facing caster
turns south and victim ends south; east-facing caster turns west and victim ends
west. All six preserve source snapshots. Runtime-module hashes are stable.
The native NPC starts with12 HP and dies in every case; this proves the geometry
and evaluated delivery, not a living victim's visible animation. Evidence is
`orientation303-desplume-geometry-runtime-audit.json`. No GUI claim is made.

The earlier nineteen diagonal pending entries are now implemented. Original
aiL selects aBA.bo(float32 dx, float32 dy), delegated to aBz.bo; its exact float
sector bounds are0.3926991,1.1780972,1.9634955,2.7488937. Java int subtraction
precedes conversion to float. SameXY still preserves the previous facing via
aiL's NONE guard. `ProbeNativeCastFacing.java` supplies121 original vectors,
including signed-int extremes, for both branches. Python matches242 outputs;
the fixed TSV is `native-cast-facing-probe.tsv`. All2090 literal1040 metadata
contracts can now mirror their declared cardinal/diagonal branch;2053 other
scripts remain explicitly pending and preserve previous behavior.

The focused export/alignment/orientation suite now passes16 tests, including a
late factory failure after facing and cost changes that leaves the source
unchanged. Reproduce the original matrix with:

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/ProbeNativeCastFacing.java
java -cp 'client/lib/*:.runtime/local/classes' ProbeNativeCastFacing
PYTHONPATH=server:server/tests python3 -m unittest test_combat_cast_facing test_native_cast_facing_export test_combat_orientation_effect -q
```
