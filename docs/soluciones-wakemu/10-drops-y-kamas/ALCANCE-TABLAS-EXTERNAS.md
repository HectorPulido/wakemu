# Alcance de las tablas externas de loot

## Resultado

El catálogo instalado contiene 2.204 registros `fFc` de tablas externas y 16.138 filas `aMf` asociadas a los 2.874 monstruos exportados. Ninguna de esas filas tiene `aMf.cqA` (`is_loot_table`) activado. Por tanto, el catálogo no proporciona actualmente un enlace desde un drop de combate de monstruo a una de esas tablas. La presencia de `fFc/fFe` por sí sola no demuestra que esas 2.204 tablas sean recompensas de combate, ni permite asignarlas a monstruos por ID o parecido.

La evidencia sí demuestra un cargador y consumidor del cliente para el catálogo de tablas y su representación en la enciclopedia. No demuestra si algún otro sistema de recompensas del juego usa esas tablas. La clasificación correcta por ahora es **uso de combate no acreditado; otro uso también pendiente de identificar**.

## Evidencia del cliente

- `bat.a(VQ)` registra un cargador para `fFc`; su nombre de interfaz es `contentLoader.externalLootLists`. En `bat.a(fFc)`, el cliente lee el ID de la tabla (`fFc.d`), sus entradas (`fFc.gBN`, elementos `fFe`), construye una lista `fqJ/fpv` y la registra en `fqE`.
- `brq.d(double,int)` consulta `fqE.Xc(id)`, recorre sus entradas `fpu` y calcula las probabilidades que presenta. Si la entrada tiene `cqA=true`, vuelve a resolver el ID anidado; de lo contrario crea una entrada de loot visible. Esta ruta es de presentación de probabilidades; no acredita una tirada de servidor ni el sistema de recompensa que consume el resultado.
- El cargador de monstruos `bbo` recorre por separado `aMb.csr()` (`aMf`) para construir las filas de drops del monstruo. La marca `aMf.cqA` se copia a la estructura visual del drop y `brq` sabe cómo resolverla. En el catálogo cargado no hay ninguna fila que active esa marca.
- El exportador conserva los dos conjuntos separadamente: `aMb/aMf` como `monsters[].combat_drops` y `fFc` como `external_loot_tables`. El exportador registra que `fFe.czk` y `gBO` se conservan aunque el constructor visual de entradas los ignore. No se halló en los artefactos de bytecode revisados un productor de combate que recorra `fqE` para conceder objetos.

Artefactos inspeccionados:

- `server/protocol/monster-encyclopedia.json.gz`, SHA-256 `38ad16ed614537e4f54540b6988cbddee55e668d458b76110abcabddcce1dc21`.
- `.runtime/local/review-continuacion-20261004/loot/loot-loader-bat.txt`, SHA-256 `8fb4db5bbbad4830f80dae95d92aae61e5d3913e73fb87dd7fb75b98e79bc132`.
- `.runtime/local/review-continuacion-20261004/loot/loot-formula-brq.txt`, SHA-256 `367f2f3eee2f58cbf3388b583681bb6c16c04dd780e0790999d636ef7d23c71f`.
- `.runtime/local/monster-content-loader.txt`, SHA-256 `96f4d8db870b0f1a5ee72a999297cfdd8fb5d5d503b16724d74aacb87579e38f`.

## Recomendación

Mantener `external_loot_tables` como catálogo de referencia y no conectarlo a `combat_drops` ni al resolver de recompensas por conjetura. La ruta de combate puede seguir usando filas directas `aMf` que estén habilitadas y cuyas condiciones y límites estén soportados. Para ampliar el alcance se necesita evidencia de una fila `aMf.cqA=true` enlazada a `fFc`, o una ruta autoritativa de combate que consuma `fqE`, además de resolver las expresiones `fFe.czk`, entradas anidadas, referencias faltantes y ciclos. Hasta entonces tampoco se debe etiquetar el catálogo como parte de otra recompensa concreta.
