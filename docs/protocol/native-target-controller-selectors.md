# Relaciones fcE42/45 y cruz diagonal anx

## Selector por dueño/controlador

El fcE original compara identidades de objeto, sin introducir una condición de equipo:

- bit42: objetivo idéntico a `caster.dpu()`.
- bit45: objetivo idéntico a `caster.dpr()`.
- Ambos exigen que el lanzador sea `eGj`.

`big.dpu → dnG → eGj.b(fcb, actor)` y `big.dpr → dnH → eGj.c(fcb, actor)` resuelven al propio actor si no hay manager o relación registrada. El probe usa fcE original con relaciones controladas y, por separado, ejecuta ambos métodos originales heredados por bje con manager nulo. Seis comparaciones PASS; fallback self PASS.

La autoridad ordinaria acredita el roster exacto PC/NPC y rechaza cambios de master/carrier. Esa creación sin relaciones expone `dpu_id=dpr_id=actor.id`. Los summons conservan su autoridad independiente; un controlador desconocido sigue rechazado, sin aplicar el fallback self de forma universal. El selector compara IDs porque la autoridad garantiza una única instancia por ID dentro del preview.

## Cruz diagonal

`anx.p` acepta1/2/4 parámetros y serializa `crossDiag-hH bB-gG dD` sin espacios. Sus puntos son el centro y los cuatro brazos:

| Campo | Punto de cada paso n |
|---|---|
| h | (-n,-n) |
| b | (n,n) |
| g | (-n,n) |
| d | (n,-n) |

Longitudes no positivas no añaden brazo. `anx.bEj()` devuelve true: no rota, incluso con longitudes distintas. El probe comprueba listas originales para1/2/4 parámetros, cero/negativos, las8 orientaciones y alturas distintas. La selección de actores reutiliza el footprint cuadrado nativo acreditado, sin cambiar afiliación ni permitir celdas ajenas.

## Reproducción

```sh
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/javac -proc:none -cp 'client/lib/*:.runtime/local/classes' -d .runtime/local/classes sniffer/java/ProbeNativeTargetControllerSelectors.java sniffer/java/ProbeNativeDiagonalCross.java
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java -cp 'client/lib/*:.runtime/local/classes' ProbeNativeTargetControllerSelectors
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java -cp 'client/lib/*:.runtime/local/classes' ProbeNativeDiagonalCross
PYTHONPATH=server:server/tests python3 -m unittest test_combat_target_life_selectors test_combat_diagonal_cross test_combat_area_footprints test_combat_effect_targets test_combat_effect_resolver -q
```

Los probes requieren previamente las clases auxiliares ProbeNativeLevelGroup y ProbeNativeTargetLifeSelectors indicadas en native-target-life-selectors.md. Resultado32 pruebas Python PASS. Evidencia durable: native-target-controller-selector-probe.txt y native-diagonal-cross-probe.txt en docs/reports/combat-inventory.

La cobertura de grafos posibles afecta bit42 a3 hechizos/3razas, bit45 a2 hechizos Ouginak y anx a2 hechizos/2razas en el inventario previo a esta corrección. Estos conteos no afirman que todas las condiciones permitan ejecutar cada rama, ni resultado GUI. Se reaudita la estructura actual tras integrar, conservando los contratos desconocidos como pendientes.

## Contratos restantes acreditados pero todavía no integrados

El mismo probe se amplió con los dos filtros restantes: bit34 excluye exactamente `target instanceof eGj && target.dTE() && target.dpu()==caster`, y exige caster eGj. Bit14 exige target eGj y baG. Matrices originales PASS. La cadena de vida es precisa: eGj.baG→fcb.ba→fdt.ba→fdy.baG equivale a OFF_PLAY(say), mientras baK equivale a OUT_OF_PLAY(saz). No son estados intercambiables ni puede inferirse ese enum de un HP0 aislado. El selector14 requiere auditar las exclusiones previas de candidatos y la autoridad del registro OFF_PLAY antes habilitarlo.

## Follow-up: selector34 integrated

The earlier pending34 entry is historical. Current common selection implements
fcE bit34: for eGj sources it excludes an eGj candidate only when native dTE is
true and dpu_id equals the caster UID. Ordinary actors remain eligible, and
foreign controlled actors remain eligible. Missing applicable relationship
metadata rejects selection. The combined targeting/areas/orientation suite
passes41 tests. Bit14 remains pending because OFF_PLAY population cannot be
inferred from current HP or silently filtered into an empty successful cast.
