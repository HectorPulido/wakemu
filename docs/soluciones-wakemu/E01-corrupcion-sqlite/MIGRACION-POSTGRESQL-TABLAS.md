# Migración definitiva a PostgreSQL: tablas y operaciones

## Alcance y evidencia

Decisión del usuario, reiterada el 5 de octubre: **sin retrocompatibilidad con SQLite ni obligación de conservar su base**. PostgreSQL será el único backend del servidor y de sus tests de persistencia. La exportación puntual es opcional; se permite crear un esquema nuevo y una base vacía si simplifica el diseño. No implementar fallback, doble escritura ni traducción genérica de dialectos para mantener callers viejos.

**Actualización del plan de tipos:** las elecciones «inicialmente text/smallint/double para conservar callers» de la primera auditoría quedan sustituidas por tipos del contrato definitivo. Usar boolean para flags, jsonb para documentos estructurados (bytea para protobuf/binarios), bigint para IDs/contadores y timestamps UTC para instantes reales, preservando unidades/proyecciones que exige el wire mediante conversiones explícitas. Reescribir comparaciones de baseline y serializers; no mantener representaciones antiguas por compatibilidad. Constraints y claves deben expresar invariantes de dominio, aunque rechacen datos viejos. Normalización de nombres debe ser explícita y probada, no una emulación obligatoria de NOCASE.

El inventario27 de abajo es la evidencia original, no el esquema actual definitivo: recontar módulos y tablas antes de implementar, incluyendo rol administrativo y su auditoría añadidos por32. El esquema nuevo se diseña a partir del estado actual y sus invariantes.

Inventario por AST de todos los módulos: **27 tablas**. Inspección solo lectura de la instancia propia: **26 tablas**, incluyendo columnas incorporadas por ALTER; `fight_health_exits` está declarada pero ausente en esa instancia. No extrapolar su ausencia a otros boots. [DDL, columnas, FK, índices y archivos fuente](inventario-tablas-migracion.json). Este documento es especificación; no hay migración implementada ni ejecutada.

## Tipos y reglas comunes

- IDs de cuenta/personaje/objeto/grupo/recurso/instancia: **bigint**, porque INTEGER de SQLite no equivale a integer32 de PostgreSQL. Coordenadas x/y y referencias pueden usar integer cuando sus límites se verifican; z/nivel respetan además límites de wire. Revisiones/XP/kamas y tiempos enteros usan bigint con checks de rango adecuados.
- `accounts.id` y `characters.id`: bigint identity, importando IDs explícitos y reajustando secuencias. La identidad de objetos usa un asignador compartido, no una secuencia independiente por tabla.
- Hashes, salts y payloads binarios/protobuf: **bytea**. Flags de dominio: **boolean**; adaptar consultas y serializers al nuevo contrato.
- Instantes reales: **timestamptz** en UTC. Duraciones y contadores conservan unidades explícitas; convertir a segundos o milisegundos únicamente donde lo requiera el protocolo.
- Documentos estructurados: **jsonb**, con validación de su estructura. Reescribir comparaciones de baseline sobre valores de dominio; no depender de la representación textual anterior.
- Constraints, FK e índices expresan las invariantes del esquema nuevo. Definir una clave canónica para nombres y usernames, con pruebas de normalización y unicidad. Si se decide importar datos, detectar colisiones y rechazar registros inválidos; no condicionar el diseño a su aceptación.

## Revisión de las 27 tablas

| Tabla / clave | Qué conserva y qué cambia |
| --- | --- |
| `accounts` / id | Username único sin distinción de caja acreditada; salt/password_hash bytea; created_at segundos. Identity + RETURNING; no rehashear contraseñas. |
| `characters` / id | FK account; nombre único, aspecto/colors/appearance text, nivel/HP/mapa/instancia/posición. Importar `appearance`, añadido por ALTER. Checks HP y límites después de detectar datos inválidos; no cambiar estados HP0. |
| `sessions` / account_id | Una generación única por cuenta, expiración y personaje seleccionado. Bloquear fila al sustituir lease/seleccionar; comprobar personaje de la misma cuenta, algo que FK simple no garantiza. |
| `tokens` / digest | FK cuenta; kind, expires_at, generation, realm_id. Preservar digest y expiración, pero en cutover invalidar tokens/sesiones operativas de forma explícita; no publicar secretos. Índices expiry y cuenta/tipo según consultas. |
| `settings` / name | Valor text; convertir versionado ad hoc en tabla de migraciones y catálogo de parámetros. No guardar secretos de infraestructura aquí. |
| `character_builds` / (character_id,build_index) | Cuatro blobs bytea; FK personaje. Mantener índices existentes y distinguir cupo/permanentes. No restringir a0–2 en DDL ni alterar decks/hechizos dentro de esta migración. |
| `account_tutorials` / (account_id,tutorial_id) | FK cuenta, pending0/1. ON CONFLICT sobre clave explícita; conservar tutoriales ya otorgados. |
| `character_professions` / (character_id,profession_id) | FK cascade; nivel0–200 y oficio positivo. El alcance cuenta/personaje del issue8 no se arregla copiando tabla: dejar explícito como cambio de dominio separado. |
| `character_regeneration` / character_id | HP inicial, coeficiente y tiempos ms bigint; FK actual sin cascade. Preservar y reconciliar huérfanos; fijar eliminación junto al ciclo de personaje, no cascade genérico a ciegas. |
| `character_progression` / character_id | FK cascade, XP/kamas no negativos bigint. Reconciliar kamas legacy con wallet; **no sumar automáticamente ambos saldos**. |
| `account_wallets` / account_id | FK cascade, saldo bigint no negativo. UPDATE atómico/lock por wallet; trade bloquea dos wallets en orden estable. |
| `fight_rewards` / (generation,fight_id,character_id) | FK personaje/cuenta; premios, created_at y columnas start/end XP/nivel incorporadas por ALTER. Preservar recibos. La clave por generación tiene el riesgo de duplicación ya probado; identidad durable de combate es rediseño necesario antes de nuevos premios, no pérdida de recibos viejos. |
| `fight_health_exits` / (generation,fight_id,character_id) | FK cascade; reason y created_at. Incluir aunque no esté inicializada en la instancia propia; impide repetir aplicación de salud. No reutilizar como recibo de premios. |
| `fight_checkpoints` / fight_id | Cuenta/generación/revisión/status/snapshot/updated_at. Falta FK cuenta en DDL actual. Resolver conflicto si fight_id es local a proceso; persistir asignador global o identidad durable. Cierre/reinicio no debe reactivar snapshots antiguos. |
| `combat_groups` / (map_id,instance_id,group_id) | Members text, status, generación/fight/revisión y **defeated_at** añadido por ALTER. Conservar CAS y journals; índice por mapa/instancia/estado y derrotados según consultas. No FK a personaje para monstruos. |
| `inventory_containers` / (character_id,kind), uid UNIQUE | FK cascade personaje; reference/kind/capacity/flags. Mantener UNIQUE uid y tipos de bolsa. Verificar capacidad/kind; FK por container no garantiza que ítem y contenedor sean del mismo personaje. |
| `inventory_initialized` / character_id | Marcador FK cascade. No regenerar inventario por ausencia accidental del marcador; cotejar junto a containers/items. |
| `inventory_items` / uid | FK personaje cascade y container; UNIQUE(container,slot), qty1–32767, referencia>0, slot>=0. Quitar AUTOINCREMENT local y usar asignador común. Mantener propiedad cruzada mediante FK compuesto o transacción acreditada; rango slot<capacity requiere lógica/lock, no simple CHECK entre tablas. |
| `inventory_item_elements` / uid | FK ítem cascade; máscaras daño/resistencia0–30. Importar sin convertir máscaras a listas ni identificarlos automáticamente. |
| `inventory_uid_sequence` / singleton1 | **Sustituir por secuencia PostgreSQL** compartida y retirar tabla del modelo final. Inicializar desde high-water histórico, items, reservas y dominios del asignador. nextval puede dejar huecos tras rollback: aceptable, no reutilizar IDs. Comprobar límite i64; no repetir SELECT+UPDATE sin lock. |
| `inventory_reserved_uids` / uid | Cuenta/generación/personaje y used_request bytea; sin FK actuales. Preservar consumidas para replay según retención; invalidar reservas no usadas de leases terminados. UID reservado aún puede no existir en items: no FK directa a inventory_items. |
| `transport_discoveries` / (account_id,kind,transport_id) | kind1/2; falta FK cuenta en DDL actual. Reconciliar y agregar FK; mantener discoveries por cuenta, no por personaje. |
| `planted_resources` / resource_uid | Mapa/instancia/x/y/z/referencia/etapa/creation_time. UNIQUE(map_id,instance_id,x,y) **ignora z** actualmente: conservar o rediseñar deliberadamente tras cotejo de ocupación, no añadir z por intuición. |
| `planting_receipts` / operation_id | Personaje/item, request/resource/group_payload text, published0/1. Referencias de objetos son históricas y pueden haber sido consumidos; no FK restrictiva a ítem vivo. Conservar idempotencia y payload original. |
| `planting_growth_outbox` / resource_uid | Snapshot resource/group y published0/1. No borrar outbox al desaparecer recurso sin resolver entrega. FK/cascade al recurso podría perder evento pendiente; diseñar retención explícita. |
| `monster_harvest_receipts` / token | Personaje/monstruo/acción/completed_at/item_uid. Ítem puede ser consumido, monstruo tener ID negativo: no FK al inventario vivo/personajes para monstruo. Índice(monster_id,action_id,completed_at); identidad durable/alcance cooldown definidos en issue1. |
| `haven_bags` / character_id | FK cascade; appearance_id/layout/locked/furniture/access. Importar columnas añadidas por ALTER y JSON text íntegro, permisos incluidos; no resetear merkasaco para facilitar import. |

Son **26 tablas de dominio conservadas + secuencia de UIDs** en sustitución de la tabla27. Añadir tabla de migraciones; tablas nuevas de gremios, accesos rápidos, reglas o outbox general pertenecen a implementaciones posteriores, no se presentan como existentes.

## Cambios de código obligatorios, sin backend dual

Reemplazar sqlite3/Row/exceptions, placeholders, lastrowid y executescript por driver PostgreSQL, row factory y migraciones. `schema()` no ejecutará DDL en cada carga/concesión: convertir cada definición/ALTER a migración ordenada y retirar descubrimiento con PRAGMA. Un pool compartido entrega conexión por transacción; no compartir una conexión activa entre hilos ni retenerla durante interacción del jugador.

`BEGIN IMMEDIATE` protegía más que la escritura final: al quitarlo, revisar **todos los SELECT→UPDATE**. Casos concretos: consumo de token y reemplazo de lease; contar cupo/crear personaje; tomar UID; reservar slot/dividir/apilar; wallet; selección/build/HP; recompensa y recibo; recurso y outbox. Orden estable de locks y constraints evitan carreras; deadlocks/serialization failures necesitan rollback y reintento idempotente. No reintentar solo la última sentencia.

PostgreSQL aborto de transacción tras error exige rollback/savepoint: revisar handlers que capturan IntegrityError dentro de `with connection`. No asumir la continuación SQLite. Conversión de `INSERT OR IGNORE` debe nombrar conflicto tolerado; errores distintos deben propagarse.

Portar journals Redis manteniendo baseline, revisión y commit SQL antes de checkpoint. Su atomicidad no se amplía a Redis al cambiar motor. Determinar autoridad por dominio; no borrar journals durante import. Bloquear flush concurrentes del mismo agregado y recuperar commit confirmado/ACK perdido. El problema E09 de SQL repetido debe corregirse aparte.

## Exportación, importación y cutover

1. Congelar versión y enumerar schema de **la base elegida**, además de este inventario; un boot distinto puede tener tablas/columnas adicionales. Comprobar integridad y12 huérfanos del respaldo ya auditado; no importar ignorando FK.
2. Preparar PostgreSQL aislado y migraciones, luego export consistente privado. Orden: cuentas → personajes → tablas dependientes, containers antes de items y items antes de elements. Tablas históricas/outboxes según relaciones; comprobar PK/FK y propietarios, no únicamente conteos.
3. Copiar IDs/bytes/JSON sin pérdidas. Comparar hashes por fila o partición para blobs y payloads, saldos, XP, builds, reservas y recibos. Inicializar identities y UID sequence por encima del high-water; no solo MAX(items) si hubo reservas/deletions.
4. Antes del cutover final detener escrituras propias del servicio, drenar sesiones y resolver journals; no reiniciar sesiones caducadas en el destino. Export final y validación en PostgreSQL; activar solo al pasar invariantes y ensayos de restore.
5. Retirar configuración/driver/paths SQLite del servidor y tests; conservar respaldo histórico privado de solo lectura. Sin fallback SQLite. Rollback operativo anterior a aceptar escrituras o procedimiento de rescate posterior explícito; no arrancar una copia antigua en paralelo.

## Pruebas de aceptación de la migración

Tests actuales de Store y módulos deben usar PostgreSQL temporal, no MemoryRedis/SQLite como única evidencia. Dos conexiones/procesos: última plaza de personaje/inventario, UID simultáneo, token one-shot, lease reemplazado, wallet/trade, premio repetido, build/HP concurrentes. Fault injection antes/después de commit/checkpoint y restore completo; aislar hechizos reservados. Verificar bytea, nombres/caja, UID i64 y límites nativos. Medir latencias/pool/locks con misma carga, no prometer mejoras sin benchmark.

**Límite actual:** schema/operaciones cotejados; aún no existen DDL PostgreSQL ejecutados, import, benchmark ni pruebas contra ese motor. Ningún dato real se modificó.

## Ampliación E14

Migración005: character_world_shortcuts, FK characters con ON DELETE CASCADE, clave compuesta personaje/barra/slot. Checks WORLD4×8, tipos1/2, identidad/referencia positivas y normalización tipo1. No liga referencia a existencia de una pila: los accesos por referencia sobreviven al agotamiento. UID2 se filtra al restaurar si ya no es propio. Tras carga el esquema tiene cinco migraciones y33 tablas; no es una conversión adicional del SQLite.
