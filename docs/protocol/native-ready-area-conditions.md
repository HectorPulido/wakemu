# Criterios comunes de áreas y relaciones de inicio

El gate785 registró39 bloqueos NbAreasWithBaseId,4
IsOnSpecificEffectArea y3 argumentos IsOwnSummon. Estos números pertenecen a
esa corrida; no prueban que cada caso pase tras la corrección. Se conservan
los rechazos restantes y se espera el gate posterior.

## Contrato original

- eQb/eQd: token362→ePj,272→eOv,280→eOG.
- ePj constructor toma un identificador long. Un argumento cuenta todos los
  Qq de Qs.bdm con bct igual; dos argumentos seleccionan el propietario mediante
  eII y exigen Qq.bch.Sn igual. La identidad no se trunca a int ni se compara
  con el UID. Un propietario seleccionado conocido nulo no cuenta áreas.
- eOv toma selector de actor, identificador long de prototipo y filtro opcional.
  false/default y string desconocido permiten todos; true/ownAreas exigen el
  dueño seleccionado; teamAreas compara bcM. Actor conocido nulo devuelve falso.
  Tras los filtros usa Qq.a(PV,x,y,z) para PV o Qq.d(position) para otro eHg.
- eOG acepta un selector string nativo, incluido triggeringTarget. No se limita
  a caster/target. La sobrecarga breed+selector convierte breed a short. Actor
  conocido nulo devuelve falso; los actores registrados usan dTE y fqK exactos.

El adaptador recibe la población explícita de native_effect_areas, propietario,
prototipo y geometría registrada. Los nuevos callbacks no usan una celda vacía
como sustituto de un actor nulo. Una relación triggeringTarget ausente dentro de
una fuente presente sigue siendo desconocida y rechazada. Source conocido
nulo produce la respuesta nativa vacía. La rama de geometría eOv se implementa
para radio0; radio diferente de0 se rechaza explícitamente hasta acreditar
Qq.a para esa huella. No se afirma soporte universal de geometrías o actores.

## Validación

39 pruebas ligeras pasan, incluyendo pruebas del adaptador real con
HasStateFromUser sobre ledger de triggeringTarget vacío y objetivo conocido
nulo. Se verifica que una identidad no registrada o una relación ausente no se
convierte en un false autorizado. El probe original comprueba long64 del
prototipo, selección global/propietario, los cinco filtros eOv y known-null de
eOv/eOG. No necesita GUI ni reinicio.

```sh
PYTHONPATH=server:server/tests python3 -m unittest test_combat_conditions test_combat_ready_area_conditions test_combat_effect_area_queries test_combat_area_type_conditions -q
javac -proc:none -cp 'client/lib/*:.runtime/local/classes' -d .runtime/local/classes sniffer/java/ProbeNativeLevelGroup.java sniffer/java/ProbeNativeOwnSummon.java sniffer/java/ProbeNativeEffectUIDs.java sniffer/java/ProbeNativeReadyAreaConditions.java
java -cp 'client/lib/*:.runtime/local/classes' ProbeNativeReadyAreaConditions
```

El probe demuestra firmas, filtros y resultados nulos originales; los conteos
y la geometría de poblaciones no vacías se verifican mediante los callbacks del
adaptador y el contrato bytecode ePi/ePj/eOv. No es una prueba del HUD.
