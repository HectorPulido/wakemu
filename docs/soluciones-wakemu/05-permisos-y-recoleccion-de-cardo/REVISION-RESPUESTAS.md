# Revisión profunda: propiedad de todos los recursos vegetales

## Catálogo nativo de acciones de flora

Se amplió `sniffer/java/ExportPlantResources.java` para recorrer `aNl → aNm → aNn[]` y conservar los campos del catálogo anterior junto a `stage_definitions`. Cada acción incluye `action_id`, `profession_id`, `minimum_level`, `duration_ms`, `item_reference`, `product_references` y `criteria`. Los getters cuyo significado no está acreditado quedan bajo `raw_getters`, sin asignarles reglas de cantidad, azar o experiencia. `boq.csP`/`boq.dBl` son las referencias de producto que usa el consumidor nativo de enciclopedia; eso no demuestra cantidades ni que cada referencia sea una recompensa garantizada.

La exportación local actual contiene **533 referencias únicas, 1.800 etapas y 1.141 acciones**, con 1.141 IDs distintos. Se preservaron exactamente los campos y listas `stages` previos. Reproducción desde la raíz: compilar `sniffer/java/ExportPlantResources.java` con `client/lib/*` y ejecutar `ExportPlantResources server/protocol/plant-resources.json`; la carga lee `client/contents/bdata` y escribe solo el catálogo indicado.

Procedencia para esta ejecución: `client/lib/wakfu-client.jar` SHA-256 `e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd`; agregado determinista de 113 shards bdata (nombre de shard + SHA-256 de cada archivo) `9ef3bcfa2589db304c3f703ea8a99e00b864d54a01961422e7960157bdcead18`; `client/contents/bdata/indexes.bdat` SHA-256 `e64de278a22979552cd3d58ffb62e792d396acac0d9b7eb175f6dadf3133140d`; exportador SHA-256 `4c1b4b15687e87c8fc168a511b1b06caf9e7801d3654f314116cceddd3976d08`; catálogo resultante SHA-256 `2397948397dbd0ed9b30d3d7905f4b3e726bf384dd0766436f0fa02f5637a4e2`.

El probe de recursos 60 y 139 confirma acciones distintas por etapa, incluidas varias acciones posibles en etapa 3 y ninguna acción en etapa 16. Sus IDs, oficios, niveles mínimos, duraciones y referencias están en el catálogo. Aún no hay prueba que determine cantidad/probabilidad de recompensa, XP de cosecha, transición/regeneración vegetal ni el resultado de ocupación específico de flora. La ausencia de esos datos no se sustituye con valores de las acciones de recolección de monstruos.

## Causa comprobada en el servidor

`planting.resource_packet` escribe `creation_time` en el campo protobuf 7 (tag 56). El descriptor nativo `zk.axp()` identifica ese campo como **ownerAccount**, no fecha. Ejecutando el serializador actual y decodificando sus bytes con `zk.cy`, una fecha `1791072000000` aparece literalmente como dueño de cuenta. Evidencia reproducida: [probe-propiedad-recursos.json](probe-propiedad-recursos.json).

`cFL` transmite el valor a `bOm`; `bOm.axu()` considera que existe propietario cuando es positivo. `cWn` compara `bOm.axv()` con `biB.cBt()` y, si difieren, evalúa restricciones que pueden devolver `bOd.kEa` (`RESOURCE_RESERVED`). Esto explica un rechazo local anterior a la solicitud de cosecha; no exige que el servidor haya enviado un error de permiso.

## Alcance general

El usuario confirma también fresnos y otros recursos. El serializador no contiene una condición específica de Cardo: lo llaman tanto la publicación de una plantación (`planting.py`) como la reconstrucción de recursos del mapa (`planting_runtime.py`). El catálogo contiene 533 recursos. La incompatibilidad del campo es común a todos los que pasan por esas rutas; no se afirma haber reproducido gráficamente cada especie ni que sea la única causa de sus acciones fallidas.

## Corrección propuesta exclusivamente en el servidor

Conservar la fecha en persistencia para crecimiento y temporizadores, sin reutilizarla como cuenta. Para recursos públicos enviar propietario 0 y nación 0; una futura propiedad privada debe tener campos separados con identificadores reales. No transformar las fechas antiguas en supuestos propietarios ni modificar el cliente. Revisar todas las emisiones y reconexiones porque corregir solo la primera publicación dejaría el fallo al volver al mapa.

La recolección vegetal sigue necesitando una ruta autoritativa para validar acción, etapa, alcance, profesión y recompensas; corregir estos bytes por sí solo no implementa la cosecha.

## Verificación pendiente y casos concretos

Probar Cardo, fresno y otra especie con personaje nuevo: plantación, crecimiento, recolección propia y de otro personaje, cambio de mapa y reconexión. Decodificar 13135 y comprobar ownerAccount=0 para recursos públicos. Diferenciar un bloqueo local sin solicitud de un rechazo real recibido del servidor. Incluir etapas sin acciones y ocupación simultánea como controles negativos. No se ha aplicado ninguna corrección al código.

## Intento gráfico y recuperación del entorno

El primer intento no pudo observar el cliente: el inspector rechazó conexión a las 20:21:19 UTC, y también rechazó conexión la API aislada 18091. No hubo clics ni captura nueva y no se cuenta como reproducción. Con autorización explícita del usuario se levantó otra instancia exclusiva, con copia de la base de auditoría y puertos world15566/dispatcher15568/API18091. Su health respondió 200 y el inspector del cliente relanzado volvió a responder. El personaje exclusivo se verificó como Audit Builds, nivel 100. La prueba de recolección gráfica está en curso; no se certifica todavía.
