# Línea de visión nativa y cobertura de mapas

El motor ejecuta una traducción acotada del bytecode original `Sf.bfZ` y sus callbacks `m`/`bfX`. Conserva aritmética Java int32/short, orden de columnas, empates de la rasterización tridimensional y dos rayos de altura de `fcr.a`. No sustituye el cálculo por una respuesta positiva ni por un Bresenham aproximado.

`native-los-ray-program.json` se reproduce con `server/tools/export_native_los_program.py`. `ExportNativeLOSTopology.java` extrae las columnas originales `VB.a(..., Vz[], ...)`, incluyendo altura y transparencia, en `native-los-topology/<mapa>.json`. Actualmente sólo **1134** tiene esta topología completa (196.020 columnas). Otros mapas conservan el catálogo previo y rechazan pares sin evidencia; no se declara cobertura completa de todos los mapas.

Las alturas proceden de `eGE.bcK()` para jugadores (6) y de `aMb.css()` estrechado a byte por `bbo`/`blj` para monstruos. Por ejemplo, 5525 usa 4 y 3646 usa 3. Un actor sin altura acreditada se rechaza. Los bloqueadores vivos se evalúan en cada llamada; las columnas y los resultados estáticos se cachean. El arranque precarga programa y topología1134 para evitar una primera carga en el ataque.

Validación offline: `ProbeNativeGenericLOS.java` compara 500 rayos originales con posiciones/alturas variadas, 27 casos `fcr` de los extremos reportados por GUI y 3 casos de bloqueadores dinámicos. Los **530 casos** coincidieron en resultado y, cuando aplica, celdas examinadas. Las pruebas `test_combat_actor_snapshot`, `test_combat_los`, `test_combat_native_los_ray` suman **16 PASS**.

La reproducción común de Atracción5030 desde (-15,-3,0) hacia (-15,-5,-1), niveles20/200, supera ahora LOS y conserva rollback. Su siguiente rechazo es la transición forzada de altura: el desplazamiento anterior exigía z constante y carece todavía de la selección nativa `faz.B`/`Sm.a` para esa ruta. El informe `attraction-5030-gui-endpoints-audit.json` documenta este límite; no acredita un movimiento exitoso ni una prueba GUI posterior.
