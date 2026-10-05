# Auditoría de daño de armas por la entrada común 12889

Se ejecutaron 1.549 definiciones candidatas en variante normal y crítica: 3.098 filas. Las fuentes de combate y protocolo permanecieron idénticas entre inicio y fin. Los 928 casos que llegaron a `prepare_server_weapon` conservaron el checkpoint original, incluidos recursos, orden y secuencia UID; los efectos sólo existieron en la vista privada. Los rechazos durante la creación de la fixture y los niveles no soportados se cuentan aparte y no acreditan rollback de un combate existente.

- 927 casos verifican pérdida de HP del enemigo, paquete 12613 de daño, entregas reales de eventos nativos y consumo exacto de recursos. Corresponden a 463 armas en ambas variantes y una arma de prueba sólo en normal.
- 1.754 casos rechazan la creación del snapshot por bonificaciones de equipo todavía no implementadas. El bloqueo principal es la familia de bonificación 1068; no constituye un fallo de la fórmula de Luz.
- 158 casos rechazan criterios EQUIP pendientes, como características FEROCITY/RANGE y medidores Wakfu/Stasis.
- 258 casos corresponden a 129 armas cuyo nivel mínimo supera200. Se enumeran; no se fabrica un personaje245 con un actor200 para eludir la arquitectura de salud actual.
- Un caso crítico de «Daga DMG de Test»18093 no selecciona ningún efecto; el root exportado sólo tiene la variante normal.

La fixture equipa un UID propio en slot15 y reconstruye las características completas a partir de los bonos reales de esa arma. Los recursos proceden de `combat_resources`; todos los costes de estas definiciones son como máximo6PA, sin aumentar PA artificialmente. El NPC5525 recibe HP/maxHP100.000 como recursos vivos explícitos antes de construir su snapshot nativo, evitando truncar el daño por muerte. Es una entidad de prueba, no una afirmación sobre la vida oficial de ese NPC. La arena es plana y sintética; el callback LOS devuelveTrue, así que esta auditoría no valida el terreno/LOS del cliente ni la respuesta visual de la GUI.

Reproducción: `PYTHONPATH=server:server/tests python3 server/tools/audit_weapon_damage_runtime.py`. Carga los catálogos mediante la caché común una sola vez. El archivo JSON contiene cada rechazo, delta HP, coste, paquete, entrega de evento y comprobación de rollback. `--references 2027 2037` permite una corrida focal.

El mismo informe registra un inventario conservador de Luz1083/Stasis917 en los grafos instalados de Hipermago y Steamer, incluidas innatas y estados304 alcanzables. Conserva criterios/flags/modos por ruta. La presencia de917 en la factoría o en un grafo no acredita por sí sola elegibilidad de ejecución; por ejemplo, Sobretensión6918 elige1083 sin estado7647 y917 con ese estado. No se añadió soporte de Stasis al motor en esta tarea.
