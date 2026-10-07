# E17 — Monturas equipadas que no permiten montarse

**Solucionado totalmente.** Confirmado por el usuario; las notas de implementación siguientes son históricas.

La captura muestra un dragopavo equipado, el bonus de 28 de dominio y el botón de montar deshabilitado. **Equipar y montarse son recorridos distintos.** El servidor admite la referencia en equipo, pero carece del estado y operaciones de montura.

Preferencia explícita: **desbloquear monturas por defecto, sin exigir la misión**. Esto no implica regalar un dragopavo ni eliminar automáticamente su requisito de nivel.

[Diagnóstico y cotejo](COTEJO.md) · [Solución concreta del servidor](SOLUCION.md) · [Pruebas ejecutadas y aceptación](PRUEBAS.md) · [Evidencia](probe-monturas-nativo-y-servidor.json).

Implementación en curso. `items/mount_codec.py` añade carriers PET, ProtoItem.pet50, refresco15548 y respuestas12634/13928 con validación explícita de rangos. No inicializa fechas ni inventa estado: exige datos autoritativos. Compilación comprobada; roundtrip nativo, tablas, carga/guardado por UID y handlers siguen pendientes. Todavía no habilita montar en el servidor activo. Dependencias:34/E05 (equipo activo), E01 (persistencia),0 (movimiento) y E14 (accesos rápidos, si se añade allí el control). No incluye cambios de hechizos.

Migración010 añadida en fuente: catálogo `mount_models`, estado `inventory_mounts`, estado de personaje y políticas PostgreSQL. Aún no aplicada al servidor activo. `mount_inventory.initialize` exige transacción, dueño y unidad no apilada; inserta solo si falta el estado y conserva vida/XP/fechas en repeticiones. `hydrate` obtiene todos los estados con una consulta. La fábrica nativa inicializa comida/hambre con reloj actual; `TP` serializa epoch milisegundos truncados al segundo y0 significa fecha nula. El cooldown configurado de1000ms es una política propuesta, no una fórmula nativa acreditada. Catálogo completo, regresiones PostgreSQL, integración y handlers siguen pendientes.

Catálogo completo40/40 exportado en `server/protocol/mount-models.json`, con hashes de procedencia, salud, progresión, velocidad y reglas de comida. Migración010 contiene las40 filas para que la autoridad sea PostgreSQL. `inventory_items.grant` ahora crea estado en la misma transacción y rechaza stacks de monturas antes de asignar UID; carga de inventario hidrata estados y el protobuf publica campo50. Esta integración está en fuente y su gate de regresión sigue en curso; no desplegada todavía. Los lectores nativos `rw/rz`, `kX.Ht.parsePartialFrom` y `cyo.dp` corroboraron layout/valores del codec, presencia de los10 campos requeridos y límite32767 del refresco. Usar parser parcial evita el chequeo de inicialización de getters ofuscados del item completo; no acredita bootstrap ni montar en GUI.

La resolución equipada usa `active_build_index`, nivel efectivo y `validate_sheet`; obtiene slot24 y exige estado del UID seleccionado. `wire.minimal_entity` publica PET propio, y `refresh_player` construye15548 desde el mismo serializador de entidad completa. Todavía falta conectar ese refresco a los handlers. Migración010 protege también cambios SQL: salud no supera el máximo del modelo, unidad/referencia coinciden y una montura con estado no puede apilarse ni redefinirse. Estas nuevas rutas y triggers están pendientes del gate actual; no se atribuyen al contenedor activo.

`mount_state.toggle` añade lease, dueño, fase durable, política PostgreSQL, salud/reposo y cooldown persistido. Aún requiere guardas autoritativas de ubicación/ocupación suministradas por el mundo y no está conectado al dispatcher. Cambiar de UID equipado desmonta en la misma transacción de guardar/activar/borrar build. La regresión encontró y se corrigieron dos defectos: importación errónea del protobuf de elementos y validación de nivel modulado que conservaba un `effective_level` anterior. El gate ampliado sigue en ejecución; no dar estos cambios por aceptados solo por compilar.

## Publicación tras cambios de build

**Cambio hecho no confirmado:** `mount_publication.equipment_changes` compara PET y estado montado de snapshots propios antes/después del commit. Guardar, activar y borrar builds publican15548 solo cuando cambia PET, seguido de12634/13928 para conservar la apariencia montada o desmontada. Cambios sin diferencias de montura no generan paquetes. La publicación se omite durante combate. Usa `WORLD.update` para actualizar también el snapshot del actor que recibirán los observadores posteriores, con validación de sesión y mapa/instancia; un broadcast sin actualizar ese estado dejaría PET obsoleto. Gate de monturas/builds/publicación: **65 pruebas OK** en Docker con PostgreSQL aislado; sin recarga todavía. Esto no habilita aún los handlers de montar/desmontar ni acredita restauración al reconectar.

## Estado nativo del actor pendiente de cotejo

12447 usa un cuerpo de11 bytes (i64 actor + tres bytes familia/propiedad/operación). `DISABLE_MOUNT=125` es una propiedad del actor, no una tabla territorial acreditada. Además `minimal_entity` conserva todavía `WORLD_PROPERTIES` de la plantilla porque esa sección no está en `EMPTY_SECTIONS`; la plantilla contiene `01 00 01 55 01`. El default00 existe, pero aún se coteja el parser/hidratación antes de sustituir propiedades sin conocer su efecto. PET no incluye el booleano de ir montado.

## Guarda transaccional de ocupación

`mount_state.toggle` ahora comprueba también la reserva de cosecha en PostgreSQL, bajo el lease del personaje. Si existe una ocupación no vencida devuelve código nativo5 y no cambia el estado montado, aunque el contexto del caller indique que puede cancelarse. El mundo debe cancelar primero la reserva. Desmontar conserva su flujo anterior. Regresión aprobada: **66 pruebas OK** en PostgreSQL aislado; incluye reserva real, rechazo sin mutación, cancelación, vencimiento y desmontaje. Cambio sin recargar.

Cotejo posterior: los bytes heredados son `RELIC_SPECIAL_JUMP=1`, no `DISABLE_MOUNT`. La hidratación `rK→eGv→pGI` está acreditada; no se quitará el permiso de salto al implementar monturas. Ver [cotejo](COTEJO.md).

## Dispatcher y reconexión implementados en fuente

**Cambio hecho no confirmado:**12634/13928 aceptan solo cuerpo vacío y personaje de la sesión cargada. Combate/merkasaco rechazan sin ejecutar toggle. Montar cancela las ocupaciones implementadas antes de la transacción. Natación se evalúa con la posición SQL bajo lease; superficies no verificadas o desconocidas devuelven código4. El resultado exitoso actualiza el actor de World y se publica en su mapa/instancia. Se conserva la política DB010 de desbloqueo por defecto sin misión.

`mount_publication.snapshot` restaura12634 OK tras instalar el actor/PET al reconectar y para observadores que entran en la zona; actores desmontados no generan paquetes adicionales. Docker empaqueta el catálogo de natación. Gate ampliado en curso; sin recarga ni aceptación visual. Alimentación, reposo, cosméticos y temporización del movimiento siguen pendientes del alcance completo.

La revisión del dispatcher corrigió la desconexión potencial por cuerpo no vacío o `ValueError` de política/equipamiento: responde12634/código7 y conserva la sesión, sin publicar éxito ni ocultar errores de lease. La regresión ampliada está en ejecución; no se atribuye este cambio al contenedor aún.

## Recarga del flujo de montar y desmontar

Gate final: **102 pruebas OK** (`test_builds test_build_capacity test_mount_codec test_mount_inventory test_mount_publication test_swimming test_world`) en Docker con PostgreSQL aislado y Redis DB15. Incluye agua/seco/mapa desconocido, ocupación vigente/cancelada/vencida, errores sin desconexión, rechazo durante combate/merkasaco, persistencia y orden actor/PET→estado montado para propio personaje y observadores.

Imagen `ca76e0f142d367da6bff101aa213a9feb111d29f0593e30aa6d6c3f8e9e6e42d` construida y contenedor recargado, sin combates/cosechas activos y con backup previo. No se atribuye validación visual a estas pruebas. Estado general **En revision**: alimentación, cosméticos, reposo completo y velocidad siguen pendientes. Las notas anteriores de “sin recarga” describen el estado previo.

Verificación posterior: contenedor `healthy`, `/health` devuelve `ok=true, storage=postgresql`; arranque sin migraciones nuevas ni errores en logs. Se solicitó comprobación visual a Luna; aún no existe resultado de aceptación.

## Aceptación visual del ciclo básico

El usuario confirma los ocho pasos con Audiluna: equipar, montar sin misión, caminar, cambiar de personaje y volver, desmontar/remontar, quitar montura con desmontaje y reequipar sin pérdidas ni duplicaciones. Otro jugador también ve montar y la apariencia montada. Estado actual: **Solucionado totalmente**, confirmado por el usuario. E17 resuelve equipamiento y montaje desbloqueado por defecto, persistencia y publicación a observadores. Alimentación, cosméticos y otros sistemas de progresión son ampliaciones posteriores; no mantienen abierto este error de montaje. E23 trata exclusivamente la orientación invisible para otros jugadores.
