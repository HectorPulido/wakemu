# Transmisión de nivel de grupos: flag16

`eVl.rwM` es el ID16 `TRANSMIT_LEVEL_TO_CHILDREN`; no es un ordinal ni una autorización general de ejecución.

En `eYg.a(Iterator,Qe,boolean)` (bytecode 11–36) y ambos caminos de `eZM` (76–99 y74–99), el grupo obtiene primero su contexto `eVt` mediante `d(source,relative)`. Sólo cuando contiene flag16 **y** `eVt.Oh()==-1`, asigna `SP(fRR())`. Un override calculado por la familia tiene prioridad.

`eZR.fRR()` consulta el PS heredado: si existe y su `Oh()!=-1`, devuelve su valor convertido a `short` de Java. De lo contrario devuelve `eVo.cmZ()` del contenedor PL; si PL es null, devuelve0. No equivale en general a `invocation.level`.

`sniffer/java/ProbeNativeGroupLevelTransmission.java` ejecuta el método real del JAR. Verifica contenedor200, parentSP65538→2, parentSP-1→200 y contenedor ausente→0. El helper `combat_group_level_transmission.transmitted_child_override` conserva esta prioridad y exige presencia/nivel explícitos cuando necesita consultar el contenedor. Tres pruebas unitarias pasan.

La conexión común está implementada: `NativeRetainedRuntime.child_level_context` devuelve juntos el nivel de evaluación y el contexto eVt serializado. `child_context` calcula primero el override de cada familia y después aplica el gate16. `EffectDispatcher` consume ambos resultados y rechaza16 si no dispone de autoridad de contexto.

El nivel de contenedor de estado procede de `resolve_state_container`, incluyendo el scope síncrono de un carrier reemplazado. Para hechizos, procede del `evaluation_level` explícito del plan que construye la instancia fyF; un contenedor directo presente debe aportar `level` explícito. No se deriva de `invocation.level` ni de los bits bajos de la identidad de contenedor. Un override padre no-sentinel retorna sin consultar PL, como fRR nativo.

Las pruebas distinguen un hijo evaluado a200 de su contenedor23: tanto el nivel efectivo como campo4 son23; parentSP65538 los cambia a2. Un contenedor directo sin nivel falla, y nullPL da0. La suite focal de transmisión, dispatcher y eventos suma19 pruebas PASS.

`docs/reports/combat-inventory/ready-group-level-transmission-focal.json` repite los27 casos reales de Eniripsa bloqueados antes por16: todos `ready_started`, hashes estables, rollback conservado, sin forzar criterios/estados. No implica verificación GUI ni cobertura de todo el combate. La función queda compartida para eYg y eZM/949; la ejecución repetida/PT de949 se implementa por separado.
