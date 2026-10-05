# E12 — Curación al alternar aptitudes

## Causa actual y reproducción

Las rutas SQL (`Store.save_build`) y journal (`BuildJournal.save`) calculan el máximo nuevo. Si antes HP==máximo consideran al personaje sano y lo llevan al máximo nuevo; en otro caso hacen `min(hp,nuevo_maximo)`. Al bajar el máximo de un herido por debajo de su HP, el clamp lo deja exactamente sano para la siguiente operación. Restaurar las aptitudes entonces rellena completamente su salud y pierde el daño anterior.

[Revalidación actual SQLite](probe-revalidacion-sqlite.json): personaje nuevo nivel100, 10 puntos de HP, **1470/1470**. Daño directo fixture100→**1370/1470**; quitar puntos→**1050/1050**; volver a asignarlos→**1470/1470**. Recuperó100 HP sin tiempo transcurrido ni regeneración. No se ejecutaron hechizos, decks o GUI. El [probe previo de diez casos](../17-aptitudes-y-calculo-de-estadisticas/probe-reversibilidad.json) cubre SQLite y MemoryRedis; sus hashes históricos no se confunden con esta revalidación SQL actual.

La ruta journal conserva actualmente el mismo cálculo; añade guardia hp>0 para la rama sano. No se volvió a ejecutar Redis real en este probe. Guardar una hoja no equivale a activar otra build: ambos flujos deben aplicar una política compartida cuando alteran el máximo efectivo.

## Solución concreta del servidor

Representar el daño o salud canónica independientemente del clamp de presentación. Si la política conserva déficit absoluto, mantener `damage_deficit = canonical_max - canonical_hp` y derivar HP visible del máximo efectivo sin sobrescribir ese déficit al reducir temporalmente el máximo. Un simple `new_hp = min(old_hp,new_max)` seguido de inferir sano desde igualdad repite el bug. Documentar tratamiento de cero/muerte y límite de déficit, sin revivir por cambios de hojas.

Diferenciar cambios de configuración de curación/regeneración/daño reales. Solo estas últimas operaciones alteran el déficit; guardar, activar o retirar equipo no otorga salud por sí mismo. Si se adopta otra regla nativa acreditada (porcentaje, puntos absolutos), conservar una representación reversible y probar los bordes. No atribuir una fórmula oficial a la propuesta de déficit.

Aplicar cálculo, selección/hojas y registro de regeneración en la misma transición versionada. Mantener una autoridad consistente SQL/Redis; no confirmar hoja y salud en estados independientes que un retry mezcle. Los puntos y UIDs no deben perderse al corregir salud. Integrar E06 y el modelo de selección activa de34.

## Validación pendiente

Ampliar la revalidación journal de abajo a la matriz completa, caída entre CAS Redis y commit SQL, concurrentes y personaje muerto. Probar ciclos alta→baja→alta con daños1/100/cerca del máximo, cambios de equipo, build inactiva sin efecto y regeneración real entre cambios. GUI sigue pendiente. El caso SQL está confirmado; no se implementó ninguna solución.

## Journal actual y persistencia tras flush

[Revalidación con MemoryRedis](probe-revalidacion-journal.json): el mismo ciclo **1370/1470 → 1050/1050 → 1470/1470** recuperó100 HP con `BuildJournal.save` actual. Tras `flush`, reabrir SQLite sin journal conservó **1470/1470**: no fue únicamente una lectura de caché. El reloj permaneció fijo y no hubo regeneración ni ejecución de hechizos.

Esto confirma el fallo en ambas rutas actuales, SQL y journal. MemoryRedis no acredita caídas de red, AOF ni rendimiento de Redis real; las pruebas de fallos concurrentes siguen pendientes. La solución necesita una política de salud reversible compartida, no dos parches independientes con resultados distintos.

## Borde de cero HP: no revivió en las fixtures válidas

[Probe cero HP](probe-cero-hp.json): se repitió asignar10→quitar→asignar10 puntos con personaje en **0/1050**, para SQL y journal/MemoryRedis actuales. Ambos conservaron HP **0** durante máximos1470→1050→1470. No hubo resurrección en estos seis cambios. No extender la curación de un herido a una afirmación de revivir muertos sin evidencia: el defecto confirmado afecta al daño que el clamp convierte en igualdad con el máximo.

La fixture tiene máximo positivo y no ejecuta el lifecycle completo de muerte/retorno de combate. Estados corruptos con máximo0 y diferencias entre guards SQL/journal deben diagnosticarse separadamente, sin presentarlos como personajes válidos. Se mantienen pendientes concurrencia y fallos entre autoridades.
