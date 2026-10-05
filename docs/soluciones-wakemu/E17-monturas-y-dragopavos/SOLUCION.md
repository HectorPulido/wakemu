# Solución propuesta del servidor

## Autoridad y desbloqueo por defecto

Añadir configuración versionada en DB: `mounts.enabled=true`, `mounts.require_unlock_quest=false`, cooldown de montar/desmontar y restricciones por mapa/instancia. Aplicarla también a personajes existentes al cargar. No falsificar logros ni completar todas las misiones. Mantener propiedad, cantidad 1, nivel efectivo y estado válido; misión desactivada no equivale a omitir estas validaciones.

Persistir estado por unidad: `inventory_mounts(item_uid PK/FK, model_id, xp BIGINT, health, color_item_ref, equipped_cosmetic_ref, sleep_item_ref, last_meal_at, last_hungry_at, sleep_at, name, revision)`. Validar modelo/referencia con catálogo exportado. Añadir checks de rangos y semántica de fechas conforme a consumidores nativos; no inventar fechas cuando no hay comida/reposo. Las columnas son propuesta, no DDL implementado.

Persistir por personaje `character_mount_state(character_id PK/FK, mounted, last_toggle_at, revision)`. Derivar el UID equipado de la build activa, evitando un segundo puntero divergente. Montura nueva legítima: vida máxima del catálogo y XP inicial explícita; no reinicializar vida/XP al reconectar o reequipar. No permitir stacks de monturas mediante grants, división, equipamiento o transferencias.

## Equipar, entrar al mundo y montar

1. Tras equipar/cambiar build, resolver la unidad slot 24 y su estado. Serializar tanto estado nativo del item como PET del actor. Usar model_id, no referencia de item. Conservar mascota independiente en Xk. Determinar y probar el carrier de actualización de PET en caliente; el layout del bootstrap no acredita ese opcode.
2. En bootstrap/restauración, emitir PET antes de cualquier notificación de montar. Restaurar estado montado solo si el contexto actual lo permite. Acreditar carrier de estado inicial montado o notificación posterior al alta del actor; no rellenar offsets de fixture sin contrato.
3. Implementar 12634/13928: validar sesión/lease, cuerpo vacío, fase WORLD, unidad equipada propia, vida/reposo, prohibición de zona, ocupación y cooldown en DB. La petición no contiene UID: resolverlo en servidor. Commit con revisión antes de emitir; repetir montar ya montado/desmontar ya desmontado debe ser idempotente.
4. Emitir respuesta nativa al dueño y observadores del mismo mapa/instancia. Un error 12634 usa el enum acreditado; verificar contrato de error de desmontar antes de inventar una respuesta. Reconciliar notificaciones perdidas mediante snapshot/estado autoritativo, sin deshacer commits porque falle una conexión.

## Ciclo completo y movimiento

Desequipar, borrar/transferir la unidad, cambiar a build sin montura o entrar en contexto incompatible debe desmontar y refrescar PET/estadísticas en orden. Combate conserva bonuses de equipo válidos y elimina solo el estado visual/velocidad del mundo; definir restauración tras victoria, derrota, rendición y espectador con el ciclo de combate existente. Revalidar al teleportar y reconectar. No propagar el estado a otra instancia ni a otro héroe.

Exportar reglas de montura y velocidades a un catálogo del servidor en DB. Implementar duración/rate limits de rutas con reloj autoritativo, tolerancia de red y cancelación/cambio de modo; no inferir velocidad del modo declarado por el cliente. Verificar animación y tiempo observado con 200 ms/celda para este modelo. No convertir +50% velocidad en PM ni aplicar dos veces bonus de equipo.

Alimentación/curación/reposo/cosméticos: extraer opcodes y reglas del cliente instalado; validar consumo propio y cambios de estado en una transacción por UID. Persistir cooldown/fechas, supervivencia tras reinicio y transferencia. No cerrar este subsistema solo porque sea posible montar. Coordinar tablas nuevas con migración PostgreSQL y validación de UID de E01.
