# Límites comunes de lanzamiento

La exportación `ExportNativeSpellLimits.java` obtiene 4143 referencias del cliente instalado. `fyP.cwQ` limita usos por objetivo; `cwR + cwS * nivel` limita usos por turno con conversiones byte nativas; `cwP` define intervalo (negativo: una vez por combate). `fyS` registra por referencia, conserva el último turno de lanzamiento y reinicia los contadores personales de turno.

El consumidor `aVn.cby` registra objetivos de `fcb.b(x,y,z)`: actores cuya huella XY ocupa la casilla seleccionada, no todos los alcanzados por el área. La altura no participa en esa consulta. El servidor conserva los contadores en `Fight.native_spell_usage`, serializado por el checkpoint común. La validación no muta; sólo el preview que termina todos los efectos consume uso. Un rechazo o descarte del preview conserva recursos y contadores.

Juicio 4776: máximo 2 por objetivo, 4 por turno, intervalo 0. Las tablas condicionales idénticas no necesitan evaluar su criterio; tablas distintas requieren contexto autoritativo y se rechazan si su selección no está acreditada. No se deduce una huella desconocida como radio cero.

Pruebas: límites por objetivo/turno, cambio de turno, intervalo persistente, huella XY y descarte del preview; entrada común con Ready real y dos Juicios sobre monstruo nativo superviviente, seguida de tercer intento rechazado. Este trabajo no prueba visibilidad del estado Juicio en GUI ni resuelve su ciclo de efectos.
