# 34. Builds personalizadas: desbloqueo tardío y hojas no seleccionables — prioridad alta

Completar desbloqueo, hojas, guardado, activación autoritativa, estadísticas/deck y persistencia de builds.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Solucionado parcialmente.** El usuario verificó creación, apertura, activación, alternancia, edición y borrado de builds, con cambio de personaje y reinicio. E10 también quedó confirmado: equipo propio de cada build, persistencia y borrado sin pérdida ni duplicación. Issue17 acredita aptitudes +5/+10, alternancia sin acumulación y reset persistente.

Pendientes de aceptación gráfica: cruce del umbral49/50/51, capacidad completa24 y actualización visual del equipo. La modulación/salud ya pasó49/49 pruebas sobre el código actual, con paridad mundo/combate, reconexión de héroes, restauración de selección/heridas y build temporal protegida; esto no sustituye la prueba gráfica completa. El consumo del deck seleccionado en combate está cubierto por el cierre automatizado de E05; no se modifica la semántica de hechizos para cerrar este issue.

## Dependencias

9, 17, 22 y E04–E08. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Metadata, equipo, aptitudes, deck y selección comparten índice y revisión; el check visual Activa no prueba autoridad del servidor.

## Revisión posterior a tus respuestas

[Desbloqueo 51, cupo no permanente 24 y respuesta 13811 verificados](REVISION-RESPUESTAS.md). Esta revisión sustituye las dudas anteriores sobre esos contratos. Las referencias a casts son históricas o trabajo de otra sesión; no se continúan aquí.


## Current source qualification — 2026-10-11

The level command now publishes the existing owned actor's format10 spellbook
and deck through15548, followed by the real-level roster23548. Missing default
decks are generated at each sheet's effective level, independently of the real
level used for ownership and build availability. Earlier documents describing
only a format3 progression update are historical. This source correction does
not replace graphical49/50/51 acceptance or certify every combat consumer.
See the [bounded build/stat audit](../../reports/BUILD-STAT-SOURCE-AUDIT-20261011.md)
for authoritative paths and the separate mount identity limitations.


Offline follow-up: the [original-JAR two-UID mount registry audit](../../reports/NATIVE-MOUNT-TWO-UID-REGISTRY-20261011.md)
separates independent native UID state and refreshed authoritative snapshots
from selected-panel GUI rebinding. It does not change accepted XP arithmetic or
close the remaining graphical acceptance boundary.

Current-source modulation qualification:49/49 tests passed in45.670s, with
unchanged production hashes. The count includes the four requested modulation
modules and imported instance lifecycle cases. Evidence:
`.runtime/local/verification-dungeon-modulation-current-20261011/evidence.json`.
The separate canonical world-stat zero reset remains source-qualified and
pending publication; physical selected equipment-panel refresh is under audit.
