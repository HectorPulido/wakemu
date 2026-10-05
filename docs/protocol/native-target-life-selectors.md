# Selectores compartidos fcE: identidad y pertenencia IN_PLAY

El cliente instalado distingue dos contratos independientes:

- bit16: el objetivo debe ser `eGj` y `Sn()>0`. No equivale a personaje jugador: una invocación con ID positivo también cumple la identidad.
- bit40: el objetivo debe ser `eGj` y `baF()==true`. `eGj.baF` consulta `fcb.aZ → fdt.aZ → fdy.baF`; sólo el estado `fdx.sax` (`IN_PLAY`) devuelve true. NONE, OFF_PLAY y OUT_OF_PLAY devuelven false.

`ProbeNativeTargetLifeSelectors` ejecuta fcE original con una subclase eGj que proporciona identidad/baF controlados y, por separado, ejecuta el fdy original para los cuatro estados. No afirma reproducir toda la fábrica de actores con esa subclase. La matriz consta de18 casos, incluidos ID negativo/cero/positivo y ambas pertenencias.

```sh
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/javac -cp 'client/lib/*:.runtime/local/classes' -d .runtime/local/classes sniffer/java/ProbeNativeLevelGroup.java sniffer/java/ProbeNativeTargetLifeSelectors.java
/Library/Java/JavaVirtualMachines/jdk-22.jdk/Contents/Home/bin/java -cp 'client/lib/*:.runtime/local/classes' ProbeNativeTargetLifeSelectors
PYTHONPATH=server:server/tests python3 -m unittest test_combat_target_life_selectors test_combat_area_footprints test_combat_effect_targets test_combat_effect_resolver -q
```

Resultado: original PASS;28 pruebas Python PASS. Salida durable en `docs/reports/combat-inventory/native-target-life-selector-probe.txt`.

La autoridad ordinaria ya acredita la ruta exacta de creación del roster PC/NPC y expone `native_in_play` mediante `creation_in_play`. Ahora usa esa misma pertenencia para el contexto baF. La creación registrada comienza IN_PLAY; la muerte owned registra su salida. HP0 sin registro, o HP positivo tras salida sin transición de resurrección acreditada, produce contexto desconocido y el selector rechaza la evaluación. No se introduce `HP>0` como regla universal. Autoridades ajenas y summons deben aportar su baF acreditado; no reciben un valor por defecto.

La auditoría estructural actual encuentra16/40 en grafos posibles de15 ataques Yopuka, bit16 también en una ruta Pandawa y bit40 en una ruta Hipermago. Esto acredita cobertura de contrato y no ejecución de cada hechizo, condiciones satisfechas ni resultado GUI. Quedan pendientes bit42/45/34/14 y geometría anx de la auditoría actual.

## Checkpoint actual de cobertura

La prueba de autoridad `test_combat_ordinary_authority` pasó7 casos con catálogo real (9.587s), incluyendo baF desconocido ante HP0 sin salida y false tras salida registrada. Los filtros42/45 y anx posteriores también están implementados y probados según native-target-controller-selectors.md.

Reauditoría estructural posterior:383 activos,13164 efectos potenciales, hashes de catálogo/selector/autoridad/geometría estables. Desaparecen los bloqueos16/40/42/45/anx. Quedan bit34 (exclusión de invocaciones propias; Sadida927, cuatro definiciones) y bit14 (cadáver registrado; Hipermago5595, cuatro definiciones). Este último requiere además revisar los filtros previos de candidatos vivos, no basta admitir el bit y devolver una selección vacía. Se conserva el inventario previo en native-targeting-contract-audit-before-life-controller-fix.json. Ningún conteo estructural es un PASS de gameplay o GUI.
