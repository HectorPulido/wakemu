# E22 — El personaje gira al golpear

**Estado: En revision.** El usuario confirma que el puño vuelve a funcionar y que puede orientar al personaje en colocación, pero observa un giro molesto al atacar. Esta observación se investiga por separado de18: no invalida la orientación manual ya confirmada.

## Evidencia actual

`combat_cast_facing.mirror_cast_facing` cambia la dirección del caster cuando el contrato nativo del hechizo acredita `turnCasterTowardTargetCell`. `combat_spell_transaction` lo ejecuta en el preview. Esto refleja código Lua/cliente; no demuestra todavía que esa sea la causa del giro del puño2145 ni que el giro persista después de la animación. Se está siguiendo además el consumidor nativo de13509 y el camino de arma/puño.

## Verificación necesaria

Comparar dirección inicial, dirección durante animación y dirección final para puño y ataque elemental; correlacionar paquetes de orientación y acción. Distinguir giro visual de una mutación del facing autoritativo, que interviene en espalda, bloqueo y condiciones. Una modificación solo en servidor no debe dejar al cliente mirando en otra dirección ni recalcular daños con un facing distinto.

## Alcance

Investigación de solo lectura. Los hechizos, sus efectos y su ejecución están reservados a otra sesión; no se modificaron. Cualquier corrección debe preservar puño, giro manual de colocación, continuidad de acciones y estado al terminar combate. No se atribuye automáticamente esta observación a una regresión ni se promete desactivar una animación nativa sin cotejar su contrato.


## Cotejo de puño y arma

El camino12889 de puño (item2145, slot15) publica13509 con actor y celda objetivo; `combat_melee.animation` no incluye dirección. La ruta de arma equipada también publica13509 con objetivo. El decoder nativo`cvO` y su handler`cjz` crean la acción`aVE/aTM`; los dumps inspeccionados no acreditan una escritura de facing. En los caminos revisados de puño/arma no se encontró un13494 de orientación enviado como parte del ataque. Esto no demuestra todavía si la animación gira solo temporalmente ni si conserva la dirección después.

Los hechizos tienen un contrato separado de Lua1040: la ruta acreditada puede orientar el caster hacia el objetivo. No se modificó. No hay aún una opción de presentación exclusivamente en servidor cotejada para evitar el giro: quitar el objetivo de13509 o enviar un13494 de retorno sin sincronización probada arriesga animación y consistencia. La siguiente evidencia necesaria es dirección antes/durante/después del puño, con paquete propio correlacionado.
