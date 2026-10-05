# Armas equipadas: entrada común 12889

`combat_weapon.prepare_server_weapon` valida actor activo propio, UID real de una unidad en el inventario, hoja seleccionada y slot15 equipado. No crea unidades ni acepta UID de otra cuenta. El byte de 12889 proviene del slot nativo fnO: cMT→dhR.j→dbl→dbd.h→cpe. Un UID−1 conserva la ruta de puños previa, comprobando ahora que el slot de arma esté realmente vacío.

Costes acreditados por `fcH.a(eGj,fnR,aBn,boolean)`: fpC.gjf=PA, gji=PM, gjh=PW. Rango cpF/cpG por distancia Manhattan; gjn exige alineación, gjk solicita LOS, gjj celda vacía. El booleano de bonificación de alcance es false para armas. RANGE_REDUCED_TO_CAC reduce el máximo a1. También se respetan eGj.frA/carry, CANNOT_USE_ITEM_CAST41 y AP_AS_MP50 cuando el coste PA es positivo. El gate gjl/QI.P todavía rechaza expresamente porque no se acredita su semántica de terreno.

El evaluador usa nivel de plantilla fpC.cmZ y contenedor fnR de tipo12, ID de referencia del objeto. `weapon-combat-rules.json` y `weapon-combat-effects.json.gz` proceden de assets instalados, no de capturas. Variant0/1 escoge normal/crítico; execution_mode2 identifica acción activa. Se admite sólo árbol directo de daño (1..5/1083). Criterios USE no vacíos y otros efectos rechazan la transacción completa.

La factoría, condiciones, áreas, fórmulas, resistencias, reacciones, RNG y efectos son el motor común de hechizos. Los nuevos efectos de armas se combinan validando identidad con `_merge_effects`, y se precargan antes de abrir listeners. No hay fórmula por nombre de arma. Los costes siguen la misma actualización de recursos del camino de hechizos; no se inventan eventos de gasto no acreditados.

La función devuelve SpellTransaction con preview privado, source checkpoint y paquete13509. La integración 12889 usa `commit_spell_transaction`, serializa todos los actores, conserva flush/ACK y maneja muerte/fin comunes. Un rechazo no emite paquetes ni consume recursos del original. Logs incluyen UID/slot/destino, referencia/nivel/costes y tiempos de preparación/commit/envío.

Verificación focal: 5 tests tras integrar gates. Jalamartillo2027 (PA5,nivel7) y Espada de tofu2037(PA6,nivel17), normal y crítico, dañan vía factoría común; costes, checkpoint original, slot/UID y commit de RuntimeMessages/12873 comprobados. El cliente Java original cvO decodifica el13509 propio con actor7, item2027, nivel7, sin spell, destino1,0,0. No demuestra todavía comportamiento GUI. Selección de críticos sigue siendo una rama explícita del entorno de prueba, no un sorteo de crítico reconstruido.

Auditoría exhaustiva adicional en curso por herramienta separada: no convertir candidatos de catálogo en soporte completo antes de resultados.

Auditoría exhaustiva final:3098 casos (1549 candidatos×2 ramas);927 completan,1912 rechazan,258 limitados por nivel plantilla>200 y1 crítico sin variante nativa.463 referencias completan ambas ramas. Fuentes estables y3098 originales conservados. De los rechazos,1754 proceden de bonos de equipo todavía no soportados al crear snapshot y158 de criterios EQUIP desconocidos; no se omiten esos bonos/criterios para forzar aceptación. Informe `docs/reports/combat-inventory/weapon-damage-runtime-audit.json`.

Después de la auditoría se añadió guard para crítico solicitado cuando no existe ninguna raíz variant1: rechaza antes de ejecutar/consumir. Prueba ligera adicional PASS (total seis tests, cinco de integración ejecutados juntos más este guard aislado). No se afirma que ese guard haya sido incluido en los hashes de la corrida anterior.


## Nueva auditoría completa tras selección elemental persistida

Se ejecutaron 3.098 variantes de 1.549 armas de daño sobre una única carga del catálogo: 2.473 PASS, 367 rechazos y 258 límites por nivel de equipo superior a 200. Pasan ambas variantes 1.236 referencias; 1.237 tienen al menos una variante comprobada. Las fuentes permanecieron estables durante toda la corrida.

El informe anterior se conserva en `docs/reports/combat-inventory/weapon-damage-runtime-before-elements-audit.json`; el actual está en `weapon-damage-runtime-audit.json`. La corrección aumenta los casos PASS de 927 a 2.473 (+1.546) y reduce los rechazos de snapshot de equipo de 1.754 a 208. No quedan rechazos identificados por las familias 1068/1069.

Los 367 rechazos restantes son 208 snapshots con otros bonos de equipo aún no soportados, 158 criterios de equipo sin autoridad implementada y una variante crítica inexistente en el catálogo nativo. Entre los bonos pendientes destacan 80/120: sus referencias actuales no quedan justificadas sólo por interpretar el sentinel −1, por lo que se mantienen rechazadas. El contador de ocurrencias de familias puede superar el número de casos porque un arma contiene varios efectos.

Los 2.473 PASS comprobaron preservación del Fight original, daño efectivo, paquetes, eventos y gasto exacto. Los 366 fallos de preparación y 258 límites de nivel no llegaron a crear una transacción; su bandera de ausencia de mutación no constituye prueba de rollback. La única variante sin rama crítica fue rechazada conservando el origen. Esta es una auditoría offline con terreno y LOS de fixture explícitos, NPC de HP elevado y un objetivo axial; no acredita animación del cliente, otros objetivos, GUI ni todas las reglas de LOS. No se reinició el servidor ni se modificaron datos del usuario.
