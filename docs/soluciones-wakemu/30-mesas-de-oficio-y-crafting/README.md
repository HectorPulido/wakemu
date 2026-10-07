# 30. Mesas de oficio ausentes o inoperantes

Cargar mesas visibles y ejecutar recetas con consumo, producto y XP consistentes.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**🟡 Fabricación aceptada; carga de interactivos en corrección de fuente.** La fabricación desplegada en la imagen `3523a0a5` fue aceptada: 10 Pólvoras y 100 Bombas, con productos y XP confirmados. La fuente local ahora vuelve a publicar el estado estático del mapa después de entrar o cambiar de mapa, pero aún no está en una imagen candidata ni confirmada por el usuario.

La corrección aborda una omisión de sincronización: `14689` llega sin cuerpo y no se envía en todas las transiciones con mapa en caché; el servidor respondía `13984` solo cuando recibía ese request. El lector nativo de `13984` actualiza objetos existentes y omite IDs aún no registrados, por lo que el servidor reintenta el snapshot completo hasta tres veces, cada 750 ms, sin bloquear la sesión. La prueba completa de mesa, viaje por Zaap y reconexión está preparada en [PRUEBA-GENERAL.md](PRUEBA-GENERAL.md) y queda pendiente de imagen y aceptación. Las condiciones de recetas que requieren autoridad adicional también siguen pendientes.

## Dependencias

8, 22, 26, 29. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Ver mesa no acredita crafting; cada receta conserva materiales y concede resultado/XP una vez.

## Cotejo actualizado

[Contrato nativo, rutas y pruebas ejecutadas](REVISION-RESPUESTAS.md).

## Avance automático — 6 de octubre de 2026

`sniffer/java/ExportRecipes.java` exporta todo el catálogo mediante el lector nativo, ejecutado en Docker con Java21. `server/protocol/craft-recipes.json`:5449 recetas,34049 ingredientes,5449 productos, cero errores. IDs únicos, cantidades e IDs de ítems positivos; duración bruta1000–15000. Cada ingrediente conserva `extra_raw` (valores0–9), cuya semántica todavía debe cotejarse. El mapeo de definiciones de mesa está señalado explícitamente como no resuelto.

`items/craft_catalog.py` prepara carga validada y conserva campos nativos sin autorizar recetas por sí solo. `items/craft_wire.py`: seis pruebas Docker aprobadas para layout12231 y rechazo de paquetes malformados. No hay handler de crafting ni cambio de runtime todavía.

Consumidores nativos identificados: inicio13989, resultado13479 y XP12916. La duración ajustada utiliza efectos del personaje; no se sustituye automáticamente por el tiempo bruto del catálogo. Estos contratos y reglas se cierran antes de pedir una prueba manual completa.

Cotejo posterior:13479→`dag.db`→`eTe.u`→`eTa.dZ` incrementa el contador de creaciones (`rey`), sin modificar XP (`ban`).12916→`eTe.D`→`eTa.qJ` aplica la experiencia. Enviar resultado y delta de XP no duplica la experiencia. El segundo short del ingrediente llega a `boE.aHO` y su único consumidor identificado es `boR.compare`, usado para ordenar ingredientes; se conserva `extra_raw` sin atribuirle rareza ni cantidad.

### Ocupación, duración y límites actuales

`items/crafting.py` y la migración `040_crafting_occupations.sql` implementan la autoridad transaccional de receta ordinaria: lease, estación validada por el caller, materiales, producto, recibo de XP y replay/cancelación versionados. `eRJ.raJ` se identifica como `CRAFT_SPEED` (stat nativo2002, tipo8); el getter `eTx.av(eGj)` consulta `eGj.dpX().a(CRAFT_SPEED, recipe.profession_id, 8)` y calcula `Math.round(raw_duration / (1 + modifier / 100))`. El cuarto `i64` de 13989 llega al scheduler en milisegundos (`System.currentTimeMillis()`). El servicio recibe el porcentaje como `craft_speed_modifier` del contexto confiable del actor; cero es el valor neutral usado por las pruebas, no una lectura de personaje.

El cliente `13989` usa el cuarto `i64` como el único temporizador de ocupación. El handler lee el primer `i64` como identidad del actor, la receta, el tipo y el tiempo; no consume el quinto `i64`. El tiempo ajustado por receta está cotejado; la captura nativa no determina si el servidor multiplica el tiempo por cantidad. `native_craft_speed_sequential_batch_v1` conserva esa multiplicación como política local de lote secuencial, no como regla nativa demostrada. El handler/world todavía debe proveer el modificador del actor y resolver la estación.

Gate de catálogo y solicitudes: **11 pruebas Docker OK**. Incluye catálogo completo, receta nativa2047 y rechazo de extracciones parciales, IDs duplicados, cantidades inválidas y qualifiers ausentes. El codec de resultado13479 prepara el layout byte/i32/i16 y los23 estados nativos; sus regresiones están delegadas. La definición de cada mesa y sus restricciones siguen en extracción antes de habilitar recetas.

Gate posterior con resultado13479: **13 pruebas Docker OK** (1,730 segundos), incluyendo bytes exactos, extremos i32/i16 y rechazo de booleanos/rangos inválidos. Sustituye el total anterior; sin handler ni despliegue de crafting.

### Planner puro de materiales y productos

`items/craft_planner.py` calcula consumo y colocación de productos a partir del catálogo validado, sin escribir ni autorizar una receta. Consume determinísticamente solo contenedores tipo bolsa 0–3, excluye UIDs equipados en cualquier build y UIDs protegidos por transferencias, conserva los campos de las filas supervivientes y rechaza si faltan materiales o capacidad de salida. No interpreta criterios, secretos, tarifas, XP ni resultados; el handler transaccional aún debe aplicar las autorizaciones y mutaciones con recibo.

**Integración de dispatcher en revisión:** `local_game_server.py` ya enruta12231 y13382 a `crafting.begin`; 13429 tipo8 separa cancelación y finalización, resincroniza inventario y oficio en un retry completado, y cancela la ocupación al moverse o cambiar de mapa. El baseline local de velocidad de oficio es0 porque no existe un snapshot de stat2002 fuera de combate. La fórmula de duración usa el modificador nativo cuando se suministra; la multiplicación por cantidad de lote sigue siendo una política local secuencial. El quinto campo i64 de13989 permanece opaco, con cero como valor de emisión.

Gate puro posterior a la integración: `test_craft_station`, `test_craft_catalog`, `test_craft_wire`, `test_craft_planner` y `test_craft_dispatch`: **40 OK**; `py_compile` para dispatcher, adaptador y smoke pasó. El gate PostgreSQL está coordinado por separado.

La revisión nativa confirma `raw_cvc` como criterio base y `raw_clT` como segundo criterio condicional por `raw_cvd`; los predicados se evalúan en `eTx.at/as/au`. `raw_ckE` se transforma en flags `eTy`, incluido el flag que la UI expone como `isSecretRecipe`. `raw_cve` alimenta el cálculo de tarifa contextual `eTx.dCv()`; `raw_cvf` se presenta mediante localizaciones en la propiedad de máquinas; `raw_cvj` alimenta un filtro de vista como booleano positivo, sin semántica de dominio cerrada. `raw_cvg`, `raw_cvh`, `raw_cvi` y `raw_pf` siguen preservados sin regla autoritativa demostrada. El planner no convierte estos campos crudos en permiso de ejecución.

## Integración del sistema en curso

Gate de dominio/catalogo/wire/planner:42 pruebas Docker aisladas aprobadas. Consumo, producto y XP comparten transacción; falla de XP revierte todo y permite retry, cancelación repetida no consume, lease reemplazada cancela intento anterior. Se conecta el dispatcher con autoridad de mesa, posición nativa y adyacencia real.

El modificador de velocidad nativo es stat2002, tipo8, por oficio. Fórmula: round(duración bruta/(1+modificador/100)), con redondeo Java positivo. El campo extra del componente solo ordena ingredientes; no restringe autorización. El último i64 de13989 sigue opaco y sin consumidor identificado. Multiplicar duración por cantidad de lote continúa como política local explícita, no fórmula nativa acreditada. Sin despliegue de fabricación todavía.

## Dispatcher conectado en fuente

Los handlers12231 y13382 y el resultado13429 tipo8 están conectados en fuente. La exportación nativa resuelve la máscara/orientación de las 330 mesas y 457 celdas filtradas; cada celda coincide con el mapa estático local. Reintentos de finalización publican snapshots absolutos sin duplicar XP/contador. Movimiento/transiciones cancelan la ocupación. Velocidad0 es baseline local explícito mientras el snapshot no conserva el modificador2002. Se preservan ACKs3flora,2plantación y6recolección de monstruos. La prueba TLS en candidato aislado cubrió cancelación por mensaje y movimiento, inicio12231, completion/result/XP, retry sin doble recompensa, reconexión y 13382 lote2 con temporizador2000ms y XP400. No se ha desplegado.

## Revisión previa de geometría y XP

El consumidor nativo bEG.dST usa máscara de direcciones bbx/QV y orientación; aceptar ocho vecinos sin esa máscara puede autorizar casillas indebidas. `server/protocol/craft-table-interaction-candidates.json` contiene las 330 máscaras, orientaciones y 566 candidatas exportadas desde el cliente. La pasada nativa `VF.v` con el perfil estático `Sm(3,0,2,true)` resuelve 457 celdas en 330 mesas sin errores. `craft_station` usa esas celdas filtradas y exige coincidencia completa con la geometría estática local del mismo perfil.

La política aprobada del issue8 define XP por casillas de ingredientes distintas, multiplicada por creaciones; la revisión detectó que complete usaba el lote como recipe_slots. Corrección y regresiones en curso antes de congelar candidata.

## XP de fabricación corregida

La fórmula aprobada del issue8 ya usa casillas distintas de ingredientes × recipe_slot_xp SQL × número de creaciones. Las5449 recetas nativas tienen1–8 casillas, dentro del límite1–16 del lector de política. Regresión de dos casillas/lote2 acredita400XP con delta12916 y recibo durable; gate dirigido34/34. Se actualizó también el fixture histórico de migración de oficios para insertar por su esquema pre013, sin llamar al Store actual que requiere deleted_at de046; gate amplio en curso.

## Exportación general de interacción

330mesas,566candidatas por máscara/orientación,457casillas filtradas mediante VF.g/VF.v, cero errores y ninguna mesa sin acceso. Las457triples coinciden con las superficies exportadas de los33mapas. Fuentes reproducibles: sniffer/java/ExportCraftTableCells.java y FilterCraftTableCells.java. Perfil Sm(3,0,2,true), el mismo de ExportAllCombatMaps; no se afirma perfil variable por personaje ni ejecución del world-manager Wc.n. La autoridad de servidor valida mapa/instancia/objeto y esta topología estática. Integración/gate final y candidata por socket en curso.

## Protocolo automatizado

Los codecs y sus autoridades están cubiertos por [test_craft_wire.py](../../../server/tests/test_craft_wire.py), [test_craft_station.py](../../../server/tests/test_craft_station.py), [test_craft_catalog.py](../../../server/tests/test_craft_catalog.py), [test_craft_planner.py](../../../server/tests/test_craft_planner.py), [test_crafting.py](../../../server/tests/test_crafting.py) y [test_craft_dispatch.py](../../../server/tests/test_craft_dispatch.py). La implementación correspondiente está en [craft_wire.py](../../../server/wakfu_server/items/craft_wire.py), [craft_station.py](../../../server/wakfu_server/items/craft_station.py), [craft_catalog.py](../../../server/wakfu_server/items/craft_catalog.py), [craft_planner.py](../../../server/wakfu_server/items/craft_planner.py), [crafting.py](../../../server/wakfu_server/items/crafting.py) y el dispatcher [local_game_server.py](../../../server/local_game_server.py).

El gate prueba paquetes 12231/13382, inicio13989, cancelación y finalización13429, resultado13479, permiso de receta y estación, consumo/producto, XP12916, cancelación/retry, rollback, replay y persistencia. La prueba TLS de candidata añade recorrido de socket, temporizador y reconexión. El [borrador manual](PRUEBA-GENERAL.md) queda separado de estas pruebas automatizadas y pendiente del despliegue.

## Primera candidata por socket

wakemu-crafting-candidate:20261007 en DB aislada: bootstrap TLS, inicio12231/13989, cancelación sin consumo, fabricación con producto y200XP, reintento de finalización mediante snapshots absolutos sin duplicar, reconexión persistente aprobados. El recorrido detectó y corrigió imports de replay a los alias públicos del paquete. Se amplía con13382/lote2 y se espera gate final antes de desplegar; world activo continúa merge9af0658c.

## Candidata congelada3523a0a5

Imagen3523a0a5c7d5b7b2dd7945095c297fe251522be17cf8c515dfa10c97517d75f9. Dispatcher de imagen coincide por SHA256 con fuente;208módulos de combate idénticos a merge9af0658c. Socket ampliado aprobado:12231/13382, lote2 con2000ms y400XP, cancelación explícita/al caminar, replay sin duplicación y reconexión. Pendiente gate final de imagen y despliegue; no se atribuye aún al world activo.

## Gate final de imagen

Fuente181/181 e imagen3523a0a5 182/182 pruebas aprobadas. Incluye estaciones/celdas, oficio/XP, recolección de flora/monstruos y contexto de drops. Socket de fabricación completo aprobado; última regresión de combate/recompensas en curso antes de desplegar. Respaldo privado pre-crafting-20261007.dump verificado por pg_restore --list,3.35MB,permisos0600.

Configuración live verificada antes de desplegar: profession_action_rewards.recipe_slot_xp=100 y profession_xp.multiplier_basis_points=10000. Por eso la receta2227 de dos casillas concede200XP por creación (si no alcanza el cap de oficio). La prueba manual usa estos valores, sin ajustes temporales de balance.

## Despliegue confirmado

🧪 Cambio hecho no confirmado:3523a0a5 desplegada como wakfu-local-world:crafting-verified; world healthy y HTTPhealth200.182 pruebas de imagen y40 puras; socket completo de fabricación y combate/botín aprobado. Los208módulos de combate coinciden con la imagen anterior. Sin migraciones nuevas (001–048). [Prueba manual completa](PRUEBA-GENERAL.md) lista; pendiente aceptación del usuario.

## Confirmación de fabricación del usuario

Adael: receta2227 lote10 completed,2000XP; receta2475 lote100 completed,20000XP. Usuario confirma100Bombas y Minero nivel16; captura muestra producto100 y delta20000XP. Las mesas fabrican correctamente tras cargar. Se investiga por separado la carga dinámica de los interactivos al transportar/caminar: faltan objetos y reaparecen al recargar, patrón relacionado con35Zaap.

## Estado vigente — sincronización de interactivos, 7 de octubre de 2026

El cliente nativo `cDt` (opcode14689) no lleva cuerpo ni coordenadas de chunk. `13984` es un snapshot de estado para IDs que el cliente ya registró; no crea objetos ausentes. En fuente, cada `join_world` arma una publicación diferida del mapa entero. `idle()` la emite tras750ms y como máximo tres veces; un movimiento validado o una interacción válida la adelanta, y el request14689 la envía inmediatamente sin cancelar los reintentos. La sesión vuelve a validar `account_id/generation` antes de enviar y conserva la publicación pendiente mientras el combate está activo.

Gate Docker aislado: **114 pruebas aprobadas**, incluidas `test_world_static` 3/3 y `test_static_map_sync_dispatch` 9/9, más despacho crafting, estaciones, inventario, transportes y recompensas de combate. El costo máximo medido es60,078 bytes por mapa (mapa1134:21,155 bytes; mapa527:28,021 bytes). La fuente está probada; esta corrección aún no está incluida ni validada en una imagen nueva.

## Despliegue de sincronización — 7 de octubre

Imagen activa `63b4642d`, etiqueta `wakfu-local-world:static-sync-verified`; health HTTP200 y Docker healthy. Copia previa PostgreSQL comprobada (754 entradas). La corrección reenvía estados al entrar/cambiar de mapa, con hasta tres intentos separados por750ms, y difiere durante combate. Los208 módulos de combate son idénticos a la imagen anterior.

Gate fuente114/114; imagen99 pruebas aplicables aprobadas y contexto incluido8/8. El único test incompatible exige `encounter_kind`, una función de drops que aún no se despliega. La comprobación TLS ampliada pasó: mapa inicial359 objetos después de dos fragmentos históricos exactos; transición silenciosa492 objetos, reconexión con tres snapshots y petición14689 respondida en52ms. Smoke de combate y retorno aprobado. La carga visual queda **Cambio hecho no confirmado**, pendiente de la prueba conjunta del usuario; fabricación conserva su aceptación previa.
