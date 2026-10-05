# Flag15 en grupos nativos

`eVl.rwL` tiene ID15 y nombre CAN_BE_EXECUTED_ON_KO. La auditoría exacta de campos del JAR encuentra su único consumidor externo en `eZR.bcd`. Este método devuelve true con flag15, con el contenedor especial protegido2040, o con máscara1010. `eZR.bbH` e `eZR.i(Qe)` consultan bcd antes de rechazar PV.baG (KO).

Sin embargo `eYg.bcd` sobrescribe ese método y devuelve true incondicionalmente. Por tanto flag15 no agrega cálculo ni cambia elegibilidad KO propia del grupo eYg. `ProbeNativeGroupKoFlag` ejecuta ese override real con definiciones flagged/unflagged y ambas permiten KO. El guard común admite15 sin eliminarlo del catálogo ni de la retención.

Límite: el runtime ordinario sigue ofreciendo actores vivos; esta modificación no acredita selección, resurrección o efectos hijos sobre actores KO. No se cambia ese contrato por interpretar KO como HP0. Evidencia reproducible: FindNativeFieldConsumers(eVl,rwL), javap eVl/eZR/eYg y el probe Java. No hay branches por hechizo o raza.

Validación real: `audit_native_start_casts.py 1542 19 200` termina dos entradas comunes con daño12, muerte y curación0 al caster lleno. Ambas ejecutan8 referencias y emiten dos12613; rollback2/2 y fuentes estables. El reporte `native-group-flag15-real-casts.json` conserva criterios y otros outcomesfalse: no se fuerza éxito de todos los hijos ni se afirma resurrección.

El focal herido1542 (daño normal100HP, niveles19/200) conserva rollback y fuente estable, pero la curación efectiva activa una reacción que rechaza el predicado aún desconocido `IsTriggeredByZoneEffect` (367719/304). La transacción completa se revierte; no se afirma curación confirmada desde este caso. El reporte wounded separado mantiene esta diferencia frente al caster lleno.

Corrección posterior: IsTriggeredByZoneEffect ahora tiene contexto nativo de la fuente y el focal herido pasa ambos niveles con curación12/92 y las reacciones3894/3869, rollback y fuentesestables. Se conserva arriba el bloqueo histórico para mostrar qué cambió. Evidencia detallada en native-triggered-zone-effect.md.
