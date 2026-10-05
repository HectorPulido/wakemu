# XP acumulada y XP visible dentro del nivel

## Caso «Prueba Yopuka»

Consulta read-only de `.runtime/local/world.sqlite3`: personaje 20, nivel 200, `character_progression.xp = 59929868921`. No había WAL/SHM junto al archivo. Ese valor coincide exactamente con `level_xp(200)` del catálogo del servidor y con `MP.aXu.nT(200)` del cliente instalado.

La ventana muestra avance dentro del nivel, no XP histórica acumulada. El consumidor nativo `bkO.eH` obtiene el total mediante `biB.dpo()`, calcula el numerador mediante `MZ.cU(total)` y el denominador mediante `MZ.N(level)`. Ejecución offline contra el JAR instalado:

| Nivel | XP total | Numerador visible | Denominador |
|---|---:|---:|---:|
| 100 | 203111249 | 0 | 10806456 |
| 100 | 203111372 | 123 | 10806456 |
| 200 | 59929868921 | 0 | 3063832942 |
| 200 | 59929869044 | 123 | 3063832942 |

El resultado **0 / 3.063.832.942** coincide exactamente con la captura. Para este registro, tener XP en DB y ver cero es coherente: toda esa XP corresponde a niveles ya alcanzados.

## Recorrido del servidor

`storage/store.py::Store.character` incorpora `combat_rewards.load`, que lee `character_progression.xp`. `characters/progression.py::character_xp` valida el total acumulado. `wire.minimal_entity` escribe ese total como i64 en la sección `XP`; `wire.initial_progression` lo escribe en los formatos iniciales 5/10. Aunque `XP` figure entre las secciones genéricas vaciadas, su rama explícita tiene precedencia: no se serializa cero automáticamente.

`maps/test_console.py`, comando `!nivel`, fija `max(umbral_del_nivel, XP_anterior)`; al ascender desde un nivel inferior normalmente queda exactamente en el umbral. `combat_rewards.load` también inicializa una progresión ausente en ese umbral y eleva valores inferiores. Cambiar solamente el nivel no equivale a ganar XP adicional dentro de él.

## Solución y comprobaciones pendientes

No modificar el cliente ni enviar el avance parcial como si fuera XP acumulada. El issue de recompensas sigue vigente: una victoria debe generar un delta, persistir el nuevo total y actualizarlo por el protocolo nativo. Cotejar un caso con XP estrictamente entre dos umbrales: DB → personaje cargado → i64 enviado → barra → reconexión. Si ese caso muestra cero, investigar instancia/DB efectiva, sesión obsoleta y emisión/consumo del refresco; esta prueba no los descarta.

No se capturó el paquete de la sesión del usuario: la lectura del archivo y el cálculo nativo explican la captura, sin certificar la instancia activa. Además, el servidor restringe niveles a 200 mientras el constructor nativo declara 246; revisar conjuntamente límites, curva completa, desbloqueos y regla del máximo antes de ampliarlos. El denominador observado en nivel 200 no prueba que deba otorgarse nivel 201.

[Evidencia estructurada](probe-xp-cero-ventana.json). No se modificó código, DB ni cliente.
