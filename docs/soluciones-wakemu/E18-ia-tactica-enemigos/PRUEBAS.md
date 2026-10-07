# Pruebas del motor de IA

Ejecutadas: 18 tests de la IA actual; tres fixtures de movimiento con metadata de ranged/support ignorada; cotejo de 3091 habilidades propias contra tablas nativas, sin ausencias. [Evidencia](probe-ia-actual-y-fuentes.json). Dofus solo leído; no ejecutado ni modificado localmente. Esta evidencia es de la línea base; el motor nuevo está implementado y su validación actual figura en el README y VALIDACION del servicio.

## Corpus requerido

| Escenario | Comportamiento a cotejar |
|---|---|
| Melee, enemigo alcanzable/inaccesible | Acerca/ataca sin atravesar ocupado ni gastar movimiento inútil |
| Ranged, alcance mínimo y enemigo adyacente | Usa posición de tiro legal, evita quedar en melee si tiene alternativa útil |
| Espalda accesible versus frente barato | Compara daño neto y coste real; no gira gratis ni expone espalda sin valorar amenaza |
| Dos niveles de altura, escalera y pared | Sigue aristas XYZ; distingue alturas y LOS; no inventa ventaja por Z |
| AoE con aliados y enemigo vulnerable | Valora todos los afectados, friendly fire y reacciones |
| Healer con aliado herido/full HP | Cura déficit real, no sobrecura y deja corredor/LOS al aliado |
| Dos melees, ranged y healer juntos | Foco razonable, reservas sin colisiones, no bloquean al soporte |
| Enemigo casi muerto y dos atacantes | El segundo replantea tras la baja; no desperdicia recursos en overkill |
| Daño resistido/inmunidad/reflect | Usa preview; no puntúa daño nominal como efectivo |
| Empuje/pull/teleport y zona reactiva | Nueva ocupación/reacciones invalidan y recalculan el plan |
| PA/PM/PW, límite por blanco/turno/cooldown | Uso autoritativo y múltiples casts cuando sean legales; sin límite arbitrario de uno |
| Habilidad desconocida o condición ambigua | No inventa efectos; fallback explicado y legal |
| Timeout, servicio caído, ACK pendiente | No bloquea el turno ni ejecuta respuesta tardía |
| Dos combates con mismo ID numérico | Memoria y respuestas separadas por UUID/instancia/revisión |
| Reinicio durante decisión/tras commit | No duplica acción ni conserva reserva no confirmada |

Cada fixture fija snapshot/catálogos/policy/semilla y expectativas de legalidad, consecuencias y motivos. Evaluar plan completo y acciones realmente ejecutadas, no un score autoconsistente. Registrar percentiles de latencia, nodos, CPU/memoria, tamaño de payload y rendimiento con varios combates simultáneos. Los parámetros iniciales deben ajustarse a esos datos; no extrapolar los tiempos de Dofus.
