# 20. Pocos mobs iniciales, reproducción y pausa sin jugadores

Sembrar población inicial pequeña una sola vez y pausar simulación sin jugadores.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Solucionado totalmente.** Movimiento, maduración y reproducción filtran presencia por mapa/instancia desde `WORLD.snapshot()`. Los relojes activos conservan el tiempo restante sin acumular tiempo de ausencia. La población inicial ya se ejecuta al arrancar, una sola vez por región, con nueve planes verificados en Astrub527/Tierras Salvajes711 y18 miembros originales. Los marcadores durables impiden reponer grupos derrotados o borrados.

El arranque4aae53dd de la imagen3540c61b confirmó los nueve marcadores como duplicados, sin nueva siembra. Falta extender los planes al resto de mapas públicos y completar aceptación visual. Un inventario de53 mapas/93 regiones con capacidad positiva no permite excluir mapas por nombres de archivo; separa39 candidatos con Zaap/Drago y14 ambiguos. Se está buscando el metadato nativo de tipo de mapa: esos indicios de transporte todavía no acreditan scope público.

## Dependencias

2, 3, 19, 0. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Seeding una vez por zona/version; estado vacío no se rellena implícitamente al entrar.

## Fuente regional existente

`server/protocol/monster-encyclopedia.json` contiene territorios y `family_entries` nativos, además de referencias/familias de monstruos. No se deben tratar IDs de territorio como IDs de mapa: hay que resolver región geométrica y celdas válidas antes de sembrar. La decisión del usuario ya está tomada: un par de mobs al iniciar, sin política de refresco. El marcador durable debe impedir que reiniciar o entrar rellene una zona exterminada; no volver a solicitar esa decisión.

## Implementación en fuente — 6 de octubre

Migración031 y `maps/monster_initial_population.py`: siembra transaccional por mapa/instancia/región, marcador durable independiente del grupo y serialización con nacimientos. Exterminar un grupo no borra el marcador ni provoca reposición. Valida familia nativa, nivel, coordenadas, cupo y celdas ocupadas por monstruos o plantas. Gate PostgreSQL aislado:13 pruebas aprobadas, incluyendo concurrencia, rollback y recuperación sin reposición.

La conexión al arranque y los nueve pilotos están desplegados. Falta generar planes completos sobre geometría segura y conectada para el resto de mapas públicos, excluyendo zonas especiales. Las pruebas del helper no acreditan población visible en todas las zonas.


Cupo regional corregido en fuente: la siembra comprueba población viva existente + plan, bajo el mismo lock que nacimientos; no basta comparar el tamaño del plan con el cap. Superficies no resueltas rechazan antes de reservar IDs. Gate ampliado22 PostgreSQL aislado OK, incluidos miembros de otra región y derrotados. Planes piloto Astrub527/TierrasSalvajes711 localizados; se está corrigiendo la proximidad entre los dos miembros del mismo grupo antes de conectarlos al arranque. No se considera completa la población inicial de todas las zonas por estos pilotos.


Pilotos desplegados: catálogo `initial-monster-population.json`, arranque antes de listeners y marcadores durables por región. Imagen3540c61b/schema034, boot4aae53dd:9 regiones listas,9 marcadores/18 miembros confirmados en DB. Astrub527 y Tierras Salvajes711; todas las parejas tienen arista nativa bidireccional, misma altura y familia. Gate final de imagen246 incluye configuración/siembra, rollback y no relleno tras derrotar. No se invoca al entrar jugadores ni al derrotar grupos. Pendiente aceptación visual y clasificación/extensión del resto de mapas públicos; no afirmar población inicial global completa.

## Optimización del siguiente arranque

Fuente preparada e imagen candidata7556e218: consulta los marcadores antes de construir geometría. Un hábitat ya sembrado conserva validación de estructura e identidades, pero no recalcula terreno ni recrea grupos. Hábitats nuevos mantienen validación nativa completa. Gate de imagen105 pruebas OK; medición de validación de los9 habitats marcados3,22ms en proceso Docker separado. No cargada en el proceso world y no se reinició durante la prueba del usuario.

## Generación reproducible de candidatos

`server/tools/plan_initial_monster_habitat.py` produce un plan offline a partir de mapa/región/referencia/nivel explícitos. Valida familia nativa, estadísticas vivas, cupo mínimo2, superficie exacta, altura común, casillas distintas y aristas cardinales bidireccionales. La CLI exige además una componente conectada de al menos24 celdas para evitar islotes; umbral explícito configurable. Acepta una lista JSON de celdas excluidas para entradas/transporte u otros puntos reservados. El resultado es candidato: no clasifica mapas públicos, no escribe en DB y no sustituye automáticamente el catálogo desplegado.

Ejemplo probado en Docker, sin servicios ni DB:

```sh
PYTHONPATH=server python3 server/tools/plan_initial_monster_habitat.py --map 527 --region 75701 --reference 6 --level 4
```

Generó la pareja(-162,-126,-4)↔(-162,-125,-4) de la región75701. No se publicó ni sustituyó la pareja del piloto existente. Pruebas dirigidas acreditan exclusión de aristas de un sentido, alturas/regiones distintas, casillas reservadas y familias incompatibles; validación adicional de rangos/tipos de coordenadas acreditada:10 pruebas Docker OK, incluido mínimo de componente conectada.

Cotejo corregido de scope:1134 y1385 se mantienen candidatos; el nombre de los exports test-arena no acredita tipo de zona. Hay39 candidatos con Zaap/Drago y14 ambiguos. Se preparan planes adicionales para1134 con recorrido del usuario acreditado, exclusión de nodos reservados y componente nativa suficiente; todavía no se publican.

## Ampliación preparada a12 regiones

Catálogo en fuente incorpora79001/79201/79101 del mapa1134: Maltrahzero1166/nivel97, Crujibola4512/nivel38 y Mala semilla de girasol135/nivel38, respectivamente. Familias regulares nativas, MP positivo, niveles válidos y parejas con aristas bidireccionales. Componentes disponibles3269/27/7863 celdas, mínimo24; margen de4 celdas alrededor de279 nodos de entradas/transporte y exclusión de ocupación/plantas del snapshot de solo lectura. La verificación transaccional vuelve a comprobar ocupación/cap al arrancar: el snapshot no autoriza sobrescribir cambios posteriores.

19 pruebas PostgreSQL aisladas OK:12 marcadores/24 miembros; recuperación con uno derrotado conserva todos los marcadores y no repone ni reconstruye geometría. Fuente preparada, aún no cargada en world; vivo conserva9 marcadores. Resto de mapas continúa pendiente de cotejo de scope/acceso.

Despliegue confirmado:imagen4166845e, boota0da568a, Docker healthy, listeners abiertos. DB12 marcadores/24 miembros; logs acreditan9 duplicados sin reposición y3 siembras nuevas1134. Gateimagen296 OK sin fuentes/protocolos/migraciones montados. La validación de población y apertura de listeners tras catálogos tardó318ms; la carga de catálogos continúa26,38s. Evidencia privada `.runtime/local/population-12-deployment-20261006.json`. La expansión global y aceptación visual siguen pendientes.

## Generación automática autorizada por el usuario

El usuario prefiere generar automáticamente y después revisar manualmente. Política de selección: todos los hábitats ecológicos nativos con capacidad mínima2, excluyendo mapas privados explícitos; el nombre de un archivo o la ausencia de Zaap no se usa para descartarlos. Se conservan los planes anteriores. La herramienta `generate_initial_monster_population.py` filtra referencia regular, familia nativa, ausencia de propiedades especiales, HP/MP positivos y mínimo de nivel nativo; el planificador valida superficies, adyacencias recíprocas, componente mínima24 y margen Manhattan4 alrededor de nodos de entrada/transporte. El servidor vuelve a comprobar ocupación/capacidad en la transacción de siembra.

Resultado completo preparado:93 planes/53 mapas/186 miembros;12 conservados y81 nuevos. Excepción explícita:mapa455/región59601 sin referencia móvil regular sin propiedades especiales. No se sustituye por jefe/archimonstruo ni se inventa referencia. Los resultados están en `.runtime/reports/issue20-automatic-catalog.json` y `issue20-automatic-exceptions.json`. Gate de siembra y recuperación completo en curso; proceso vivo aún con12 marcadores. La revisión manual comprobará distribución/especies/acceso y se ajustará el catálogo por lote.

### Comando reproducible de generación

```sh
PYTHONPATH=server:server/tools python3 server/tools/generate_initial_monster_population.py --output .runtime/reports/issue20-automatic-catalog.json --report .runtime/reports/issue20-automatic-exceptions.json
```

La herramienta conserva los planes ya elegidos, emite excepciones y no toca PostgreSQL. Para excluir interiores conocidos admite `--excluded-maps archivo.json`; para reservar ocupaciones observadas admite `--occupied-cells archivo.json` (map ID a coordenadas). La siembra autoritativa siempre comprueba nuevamente ocupación y capacidad. Docker incluye las dos herramientas para repetir el proceso sin dependencias locales.

Despliegue automático confirmado:imagena6594f58 healthy, DB93 marcadores/186 miembros iniciales, gate308 OK. [Una sola prueba manual general y catálogo de consulta](REVISION-AUTOMATICA.md); no se pide probar93 regiones por separado. EnAGENTS.md queda guardada preferencia:solución automática→pruebas automatizadas→una prueba manual general→revisión del usuario.

## Aceptación general del usuario

Usuario confirma con capturas el recorrido completo:grupo de Miaumiaus en Astrub, dos larvas en alcantarillas y dos Crujibolas nivel38; al recargar no aparecen monstruos duplicados. Junto al gate308, DB93 marcadores/186 miembros y recuperación sin reposición, acredita el sistema de población inicial automática. Excepción455/59601 documentada:ninguna referencia regular móvil elegible. Los pendientes históricos de pilotos quedan superados por la generación automática autorizada; la revisión adicional de distribución puede hacerse con la tabla de referencia.
