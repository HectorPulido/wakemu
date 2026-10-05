# Invocaciones307: contrato nativo y límites

`eVi307` crea `eZl` (Summon: Invoque une créature), no un estado ni un spawn de mundo. `eZl.C` reserva identidad mediante `PN.bae().baj()`. Parámetro0 es referencia short;1 es nivel: positivo explícito,−1 fRR con contenedor existente,−2 nivel caster,−3 mínimo eGC.cqN. Parámetro2>=1 elige como controlador la criatura; en otro caso lo es el caster.3 pasa por aAS.wL (orientación0..7/NONE);4 es equipo byte con fallback caster;5 pasa por SR.pv y6 es offset SQ. SQ por defecto usa EFFECT_CASTER y offset1.

`eZl.c` llama `eGj.b`→`bjo.a`→`big.a`. El cliente construye/reutiliza bje por UID, configura eHD y SQ, marca invocación, aplica descriptor y propiedades nativas, registra propietario/controlador/equipo con buH y bio, y agrega a la pelea. `eHD.b` puede añadir DMG_IN_PERCENT20 del invocador mediante fff.nG (suma, no sustitución) si ffe81 y característica presente. La criatura3251 tiene una rama nativa adicional de copia cosmética/equipo dsK; propiedad101 implica copia visual mediante bPi. Estas ramas no deben eliminarse de un ejecutor genérico.

## Implementado

`combat_summon.summon_specification` interpreta parámetros sin convertir límites de monstruos de mundo en límites de invocación. `summon_additional_payload` serializa field12/iR.field4 UID. ProbeNativeSummonDescriptor ejecuta C real de eZl con proveedor explícito de parámetros/PN y verifica eHD/SQ: payload UID901 exacto `6203208507`. No ejecuta OpenGL ni conecta red.

`fresh_summon_insertion` reproduce Tc.a para identidad nueva: ancla current/start/caster, suma int32 y Math.floorMod por tamaño+1. Conserva el actor que estaba jugando. ProbeNativeSummonTimeline ejecuta Tc/SQ/SX y feq reales y acredita cuatro casos, incluyendo negativos y overflow. Reinsertar una identidad existente usa la rama bsy/Td adicional y permanece rechazado.

`RegisteredSummonAuthority` compone el proveedor ordinary estricto con registros propios en el preview. Exige snapshot completo, propiedad/controlador y orden explícitos antes de mutar. Cualquier actor añadido sin registro sigue rechazado. No inventa conteos dTB/GF: quedan desconocidos hasta acreditar filtros de elegibilidad. La retirada sólo acepta criatura ya muerta y orden postmuerte explícito; conserva identidad para efectos pendientes. eZl.bbF limpia descriptores del runner: NO acredita matar/eliminar una criatura viva.

Ocho pruebas pasan: parámetros/niveles, bytes nativos, inserción, rechazo sin mutación, guardas ordinary retiro de cadáver, permisos de turno y preparación transaccional privada. `prepare_summon` devuelve `(preview, packets)` sin modificar el original; exige proveedor nativo de construcción postdescriptor, allocador de identidad y encoder de alta. La prueba de esta API usa un encoder explícito de fixture y NO acredita bytes307 completos. No hay binding307 en factory ni validación GUI.

## Integración pendiente concreta

Crear snapshot bje/eHD después de aQc y descriptor, incluyendo herencia20, propiedades/copias y estado inicial; ligar creación307 a esa autoridad y a paquetes13497/cronología acreditados. Conservar caster y controlador separados (controlador puede ser la criatura), cuenta de control explícita y root fqK. Ampliar condiciones de conteo únicamente con filtros nativos dTB/GF. La rama de invocación viva/retirada y la IA/control cliente necesitan su lifecycle propio; no se sustituyen por NPC de mundo o broadcast12873 ordinario.

Evidencia bytecode: `.runtime/local/native-summon-{eZl,eGj,bjo,big,bje,eGz,descriptors,SX}.txt`, `.runtime/local/combat-timeline-Tc.txt` y `.runtime/local/combat-order-java.txt`.

## Avance de snapshot y alta nativa

`combat_summon_creation.NativeSummonBuilder` construye características completas desde curvas ffC/ffx sin imponer mínimos/máximos de monstruos de mundo. `native_npc_creation_values` comparte ese cálculo con el snapshot ordinario. ProbeNativeSummonSnapshot ejecutó bje.drd/dpQ y eHD reales para referencia3791 nivel20: HP1 y PA/PM/PW0. La propiedad114 conserva la invocación en el roster y excluye su entrada de la cronología. No se ejecutó aQc gráfico.

`combat_summon_codec` serializa el descriptor completo eZm(vJ,wU,SQ), UID adicional y TimeDatas. ProbeNativeSummonDescriptor acredita bytes completos del descriptor y lee un paquete Python13497 con cvY y eZl.ds reales: identidad de efecto902/base902, criatura901, referencia/nivel/controlador lógico y datos temporales conservados. El ensayo usa un descriptor3251 para verificar bytes, **no habilita** su rama cosmética.

Dieciocho pruebas focales de invocación y snapshots pasan, incluyendo creación privada3791 con snapshot completo, packet13497, propiedad114 y original intacto. La propagación nativa eHQ.pSW (categoría0, propiedad47) utiliza autoridad explícita world_properties del caster y tiene prueba. Continúan pendientes wiring factory/entrada común, inicializadores bPD y ramas de copia cosmética. El builder rechaza3251/propiedad101; no se declara cobertura de todas las invocaciones ni validación visual.

## Wiring común y siguiente bloqueo

El factory registra307 cuando se aporta `RegisteredSummonAuthority`; `server_runtime` envuelve el proveedor ordinary con ella y reconstruye registros desde el Fight. Actor desconocido sigue rechazado. El adaptador conserva eventos de los actores originales; la propagación de eventos cuya fuente/objetivo es una invocación sigue rechazada explícitamente. Conteos no acreditados pueden ser None, y el predicado correspondiente rechaza sin inventar cero.

La raíz nativa313167 (307 de hechizo5345) pasa por dispatcher/resolver/factory de producción, crea3791 con packet13497 y permite que un runtime nuevo reconozca el registro. El cast completo5345 llega a315 y hace rollback del snapshot: **todavía no funciona íntegramente**.315 es eYQ creación de zona de efecto, no retirada de estado. No se omite.

Cronología permite excluir únicamente registros propios con ffe114. El clock de uno de esos actores usa índice−1, ya previsto por SU/Tb y schedule_state_timer; un actor desconocido fuera de cronología sigue rechazado. Focal de entrada PASS; regresión de36 pruebas anterior tuvo35PASS y fallo de referencia equivocada en la prueba nueva, corregido y vuelto a comprobar individualmente. Sin GUI/reinicio.
