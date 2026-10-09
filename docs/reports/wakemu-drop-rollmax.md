# Auditoría de `rollMax` en drops de combate Wakfu

Fecha: 2026-10-07. Alcance: lectura de catálogo/exportaciones y bytecode local. No se cambió el motor de combate, la política de drops, los datos del cliente ni los servicios.

## Resultado

El cliente instalado transporta `m_rollMax`, pero las fuentes examinadas no acreditan cómo lo consume el resolvedor autoritativo de recompensas. No hay base suficiente para imponer un cap ni para escoger su unidad (fila, enemigo, jugador o pelea), ni cuándo se reinicia. `native_csE` permanece preservado en el catálogo y en los recibos, y no gobierna el número de intentos implementado.

## Evidencia del cliente y el catálogo

- `client/lib/wakfu-client.jar`: el cargador `bbo.a(aMb, short)` toma `aMf.csE()` y lo copia a byte mediante `fqH.gF(byte)`; `fqG.csE()` devuelve el valor almacenado. La representación `fqG.toString()` conserva el nombre nativo `m_rollMax`.
- La ruta de presentación `brq` agrupa/muestra filas con referencia, probabilidad, tabla y `roll_count`; no consulta `fpu.csE()` para limitar sorteos. Las búsquedas de consumidores del getter en el JAR dieron construcción, getter y representación, no un ejecutor de tiradas. Esto caracteriza el modelo/UI, no demuestra la semántica del servidor oficial.
- `server/protocol/monster-encyclopedia.json`: hay 16.138 filas; 14.795 tienen `native_csE=-1` y 1.343 tienen `native_csE=1`. El valor no es un alias de `roll_count`: se observan combinaciones diferentes. El exportador es `sniffer/java/ExportMonsterEncyclopedia.java` y el normalizador `server/tools/export-monster-encyclopedia.py`.
- `server/wakfu_server/storage/combat_drops.py` conserva las filas e índices. Para `roll_count>0` genera esa cantidad de intentos; para el sentinel `roll_count<=0`, genera un intento por fila, enemigo derrotado y propietario elegible. `native_roll_max` se guarda, pero no reduce esa cuenta.
- `server/tests/test_combat_drops.py::test_native_roll_max_is_preserved_but_does_not_override_displayed_roll_count` usa `roll_count=2, native_csE=1` y comprueba dos intentos. Es una regresión de la política local actual; no acredita equivalencia con el servidor oficial.
- Las cuatro filas repetidas de Esquirlas de Kralaman (`monster ref 2709`, `item ref 27083`) tienen `roll_count=-1` y `native_csE=1`. La UI las agrupa, pero esa agrupación no determina la unidad del máximo ni autoriza deduplicarlas.

## Contraste Dofus: no resuelve Wakfu

El código local de Dofus usa `drops.ceil` como requisito de prospección al formar un pool compartido (`Fight.java`, `World.Drop.getCeil()` y `DropData.java`). El esquema `game.sql` lo comenta como `Prospection ceil`. No es el campo Wakfu `m_rollMax`; no se traslada esa regla a `native_csE`.

## Candidato de prueba y limitación de acceso

El catálogo localizado permite identificar un buen candidato semántico:

| Campo | Valor verificado |
| --- | --- |
| Monstruo | `Mekarbok perturbado`, ref. 5767 |
| Nivel | 10–10 (`server/protocol/monsters.json`) |
| Familia | 1153 |
| Botín | `Fragmento de temporalidad`, item ref. 32426 (`i18n_es.jar`, clave `content.15.32426`) |
| Fila | probabilidad 1.0, `roll_count=-1`, cantidad 1–1, `csE=1`, `csF=0`, criterios simples vacíos, `csH=false` |
| Habilidades/acciones exportadas | habilidades nativas 3472 y 3477; acciones de recolección/objetos de recolección y acciones de mundo exportadas vacías |

La familia 1153 no aparece en los 105 territorios de `monster-encyclopedia.json`, en las regiones de `server/protocol/ecology-regions.json` ni en los hábitats de `server/protocol/initial-monster-population.json`. Eso solo demuestra ausencia en esas exportaciones consultadas; no prueba que el monstruo sea exclusivamente invocable ni que no tenga una ubicación nativa en otra tabla.

Por ello, todavía no hay una secuencia oficial reproducible que pueda darse al usuario: faltan el mapa/lugar de aparición y una comprobación nativa de si ref. 5767 puede aparecer como enemigo ordinario o solo como invocación. No se debe inventar un `!mob`, teletransporte ni ubicación. Las habilidades 3472/3477 y la falta de hábitat en las listas consultadas no bastan para clasificarlo como invocación.

Cuando se identifique su ruta de aparición, este candidato sirve para aislar el ámbito del límite porque su fila es 100 %, no tiene condiciones exportadas y deja la variable `csE=1`. Una prueba útil necesita capturar la cantidad concedida por personaje para (1) dos propietarios elegibles en una victoria contra un Mekarbok y (2) un propietario elegible en la misma pelea contra dos Mekarboks de referencia 5767. Si el acceso nativo permite repetir la pelea, añadir una tercera victoria separada discrimina un reset por pelea de uno persistente. Los resultados deben compararse con los recibos por personaje/fila/enemigo; el resumen visual por sí solo no identifica la unidad del máximo. No solicitar esta prueba hasta verificar aparición ordinaria, mapa y contexto.

## Fuentes siguientes necesarias

Hace falta la ruta nativa que crea encuentros regulares a partir de la referencia 5767 (definición de aparición/mapa o el sistema que lo invoca) y el servidor/resolvedor de drops que lee `m_rollMax`. Un bytecode del cliente que solo copia el campo, una fila garantizada y el contraste Dofus no reemplazan esas fuentes. Hasta entonces se conserva el dato sin aplicar cap.
