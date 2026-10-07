# 3. Los monstruos no se reproducen ni amplían grupos

Crear descendencia y ampliar grupos por reproducción o siembra, sin respawn automático independiente.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

**Cambio hecho no confirmado.** Motor de reproducción desplegado con PostgreSQL/Redis y gate105 aprobado. Cliente confirma creación de otro grupo y ampliación del existente, además de reentrada sin duplicación. Falta confirmar recuperación de estos hijos tras reiniciar el servidor. Las secciones siguientes conservan la cronología de implementación; sus notas de «no desplegado» describen etapas anteriores.

## Dependencias

2, 19, 20 y 0. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

Cada nueva unidad tiene origen durable de siembra o reproducción; matar y esperar no genera unidades.

## Revisión de catálogo y política solicitada

[Familia 68, ausencia de is_boss, ruta de respawn y límites del crecimiento](REVISION-RESPUESTAS.md).

## Cotejo de implementación — 6 de octubre

`spawn_group` valida roster nativo hasta127 miembros; ese límite de serialización no implementa el máximo8 solicitado. `combat_group_members` impone unicidad por mapa/instancia/UID y FK al grupo. Agregar una cría requiere bloquear el grupo, validar disponibilidad/capacidad, actualizar roster y revisión, insertar membresía y confirmar recibo/outbox en la misma transacción. `move_members` solo permite posiciones y no sirve para agregar miembros.

El nacimiento desde flora ya usa `monster_growth_member` para escoger la referencia de menor nivel de la familia y construir estadísticas nativas. Los IDs actuales son aleatorios de62 bits; no hay secuencia de monstruos. Una secuencia dedicada por encima de2^62 evitaría colisión con ese espacio actual, usando su negativo para actor y positivo para grupo. No reutilizar `inventory_uid`. El camino de grupo nuevo necesita outbox propio además de la actualización del grupo padre.

La reproducción debe mantener dos resultados explícitos: añadir miembro cuando quede capacidad y crear otro grupo cuando corresponda, con sus respectivas publicaciones. El máximo8 y la probabilidad local0.05 deben residir en PostgreSQL. No debe invocar `respawn` ni revivir grupos derrotados. Sexo se ignora por decisión del usuario; madurez/referencia se derivan de los rangos de la familia. Esta sección es cotejo para implementar; todavía no hay motor de reproducción desplegado.

Base de implementación en fuente: DB024 define política local60000ms/chance0.05/nuevo grupo0.5/max8 y secuencia `monster_entity_uid` que comienza en2^62+1 (fuera del namespace aleatorio actual, que puede incluir2^62). `monster_reproduction.policy` rechaza configuraciones inválidas y `allocate_identity` asigna grupo positivo/actor negativo sin reutilización. **6 pruebas PostgreSQL aisladas OK**, incluidos rollback y32 asignaciones concurrentes únicas. DB024 no está desplegada y todavía falta la transacción de nacimiento/ocupación/publicación; no se afirma que exista reproducción efectiva. Chance de nuevo grupo0.5 es un default local configurable, no una regla oficial.

Nacimiento en fuente: `attempt` revalida padre adulto/disponible, ciclo pendiente y referencia; escoge únicamente una superficie adyacente de los edges nativos, excluye jugadores/monstruos/plantas y comparte el advisory lock de celda con plantación. Un intento fallido guarda recibo sin cría; un éxito añade una cría de rango mínimo a un grupo con capacidad o crea un grupo nuevo. Roster, membresía, recibo, outbox y siguiente intervalo se confirman juntos. El replay devuelve el recibo sin otra tirada. Gate en curso.

El reloj por lotes se extrajo a `monster_active_clocks` con whitelist de tablas; maduración y reproducción lo comparten para conservar pausa, generación de reinicio y ciclo único. Reproducción observa solo referencias adultas (rango mayor que0). Esta refactorización está en fuente, no recargada; requiere repetir el gate de maduración antes de desplegar.

Gate inicial de nacimiento/observación:22 pruebas PostgreSQL OK, incluido rollback del outbox y concurrencia de un mismo ciclo. Recuperación de pendientes y publicación por roster actual están conectadas en `tick`, pendientes del gate ampliado. Cotejo nativo12304: cgN busca la entidad por UID y retorna si es nula; retirar un UID todavía ausente es no-op, permitiendo replay de crías/grupos nuevos antes de12608. Esto no sustituye la aceptación visual.

Gate ampliado:44 pruebas PostgreSQL OK en reproducción, intentos/tick de maduración; pausa, replay y publicaciones coalescidas verificados. El recibo de nacimiento ahora conserva el snapshot completo de la cría. `expanded_seeds` autoriza anexiones al grupo inicial solo si hay recibo, familia/rango mínimo y estadísticas nativas coinciden; después `reconcile_seed` valida maduraciones posteriores. Gate de este añadido en curso. Faltan control de población por zona, balance por nivel, daemon y retirada del respawn; no está desplegado.

Control de población en fuente: límites localesSQL de128 miembros y32 grupos vivos por mapa/instancia, además del máximo8 por grupo. Son defaults configurables, no valores oficiales. Un advisory lock por zona serializa nacimientos entre padres distintos; los grupos en combate cuentan como vivos y los derrotados no se reviven. Al alcanzar el límite de grupos, solo se permite anexión si queda capacidad; al alcanzar el límite de miembros no se tira ni se crea cría. Gate de fronteras/concurrencia en curso.

## Balance por nivel y retirada de respawn

Probabilidad local de nacimiento: `base × decay^(rango_adulto−1) × nivel_primer_adulto / nivel_siguiente_rango`. En rango terminal se usa su propio nivel. DefaultsSQL: base0.05 y decay0.5; Tofu adulto8→siguiente10 da0.04 por intento. Bebés y referencias desconocidas no se reproducen. La chance disminuye con rango/nivel siguiente; el recibo conserva la probabilidad efectiva junto a la política. Esta regla es balance local explícito, no fórmula oficial. Gate de fronteras en curso.

Respawn artificial retirado de fuente: worker, variable de entorno y método `respawn_due`. La recuperación mantiene derrotados, sin disponibles ni nuevo claim. Gate anterior a la última fórmula:86 pruebas PostgreSQL/Redis OK, incluyendo avance24h y tick de reproducción sin revivir ni publicar grupos derrotados. El daemon de reproducción está conectado en fuente; todavía sin despliegue.

Cotejo de instancia: `owned_instance` asumía0 y `world_actor` rechazaba rosters con otra instancia. Se añadió parámetro validado de instancia al constructor y a ambos cotejos del roster; `Groups.register` rechaza miembros de otra instancia. Maduración, crías y nacimiento desde flora pasan ahora la instancia real. Tests específicos con instancia17 y gates de grupos/flora en curso. No se cambian estadísticas ni hechizos. La imagen previa de preparación se reconstruirá tras este gate.

## Despliegue — 6 de octubre

Gate final **105 pruebas PostgreSQL/Redis OK**. Imagen `f75997653aa1a9ce57d358f460071a70e33c7084f7c7b9775f75635c0ce85541` recargada tras backup privado y cero combates/ocupaciones. Startup aplicó DB024–025; `/health` responde OK. El grupo inicial200 ya estaba madurado a5456 antes de la recarga, por lo que el arranque también recorre reconciliación de su cadena. Prueba visual de nacimientos y continuidad tras reinicio en curso. Estado: **Cambio hecho no confirmado**. Las notas previas de no despliegue quedan históricas.


## Ambos resultados de nacimiento confirmados en cliente

Con la política real intacta (intervalo60000ms, probabilidad base0,05, decaimiento0,5), Luna adelantó únicamente el temporizador del padre de auditoría−88006001. Los recibos conservaron tirada y probabilidad efectiva0,00555556 para Gorditofu704. El ciclo102 creó un grupo nuevo con bebé−4611686018427387906; el137 añadió bebé−4611686018427387907 al grupo88006001. Ambos outboxes quedaron publicados y el cliente recibió12304 seguido de12608 para los rosters correspondientes; el inspector acreditó ambas identidades exactas. No se modificó RNG ni política global.

Evidencia privada0600: `.runtime/local/instances/audit-profession-013/e2e-tofu-reproduction.json` y captura `e2e-tofu-reproduction-success.png`. La aceleración comprueba las dos ramas de publicación, no la frecuencia natural de nacimientos. La reentrada posterior confirma ambos hijos únicos: grupos de2+1 miembros, referencias evolucionadas coherentes y un recibo/outbox por nacimiento. Evidencia privada adicional: `e2e-tofu-reproduction-post-reentry.json`. Queda verificar recuperación de estos hijos después de reiniciar el servidor antes del cierre completo.
