# Issue19 — Movimiento aleatorio

Implementación en fuente: migration006 agrega settings.monster_wander (interval_seconds=5, move_probability=0.25, min_steps=1, max_steps=3, radius=20). policy valida claves, tipos, rangos y valores finitos; el daemon consulta la política cada ciclo, sin usar WAKFU_MONSTER_WANDER_RADIUS. Los cambios de intervalo entran en el siguiente ciclo.

Cada grupo disponible tira su probabilidad independiente. plan_path elige pasos aleatorios, conserva únicamente aristas dirigidas y alturas válidas, frena si no hay movimiento legal y construye un solo paquete13852 por NPC con todos sus deltas. El CAS PostgreSQL confirma posiciones antes de emitir. Sin jugadores de mapa/instancia no hay intentos; grupos en combate/recolección permanecen excluidos.

Se indexan vecinos una vez por ubicación/ciclo, evitando escanear toda la geometría por grupo/paso. El roster/ocupación y envío todavía usan bloqueos globales existentes: la eliminación de esos bloqueos queda pendiente y no se atribuye a esta mejora. No se declara finalizada la optimización de0/19 ni la presencia regional fina de20.

Pruebas delegadas a Luna: azar determinista, recorridos nativos de varios pasos, altura/colisiones, pausa sin jugadores, exclusiones, CAS/reapertura y configuración DB inválida/recargada. Fuente sin desplegar.

## Índice fuera del bloqueo y caché acotada

El daemon compila la geometría antes de tomar los locks de grupos/recolección. Comparte índice entre instancias del mismo mapa y lo conserva mientras ese mapa tiene jugadores; lo retira cuando queda inactivo. wander_location acepta el índice preparado y no recorre las aristas de nuevo. La planificación de candidatos y el envío siguen bajo la sincronización anterior; retirar esa protección sin ordenar claim/recolección/publicación introduciría carreras, por lo que esta parte del issue permanece pendiente explícita.

## Pruebas y consulta por ubicación

Luna confirmó **8 pruebas pasan** sobre PostgreSQL aislado: umbral.249/.25 independiente por grupo, paths13852 de1/3 pasos con alturas, parada al terminar aristas, ausencia de jugadores sin consumir RNG, exclusiones, claim/CAS y reload de settings. También pasó reutilización del índice sin reconstrucción. No se ejecutó una suite completa ajena a este cambio.

Se añadió snapshot(map_id,instance_id) con filtro SQL por PK y validación de ambos argumentos juntos. El daemon consulta solo ubicaciones activas; no carga el roster de todas las zonas. La regresión de esta ampliación está delegada a Luna; imagen construida antes de esta última ampliación, por lo que necesita rebuild antes de carga.

## Regresión de consulta y carga

Luna confirmó **14 pruebas pasan** (wander y grupos), incluida consulta scoped, grupos fighting, default global y filtros incompletos rechazados. Se reconstruyó world y se recreó después del checkpoint visual de Audiluna; el entrypoint aplicó006. Pendiente comprobación health y reentrada del cliente. La política de movimiento ya es DB; bloqueo de planificación/envío e inspección visual de mobs siguen pendientes.

## Una lectura coherente del roster por ubicación

Se eliminó la segunda consulta SQL del ciclo: `wander_location` obtiene un único `snapshot(map_id, instance_id)` bajo el lock compartido, separa disponibles y calcula obstáculos de combate/recolección desde esa misma lectura. Los disponibles conservan orden por clave para mantener el orden de las tiradas. La confirmación CAS y la publicación siguen sincronizadas; no se debilitan las barreras frente a comenzar un combate o recolectar. Esta ampliación está en fuente, pendiente de regresión y despliegue; no se atribuye al contenedor actual.

La regresión de esta ampliación pasó: **9 tests PostgreSQL OK**. Verifica snapshot único y scoped, ausencia de llamadas a `available`, vecino en combate que bloquea el camino y cero consultas sin jugadores. Imagen preparada `84fdf3d6d1cf48473cdb6bd97e4d25a85600f4550fd75a0da22e39399f3fad10`, aún sin sustituir el contenedor durante la prueba visual.

## Carga comprobada

Imagen `9894e928a3b93f660ba2b44cc79004fc05ed3a6006e4e469346f55055a5b4187` cargada en Docker; contenedor healthy y `/health` devuelve PostgreSQL ok. Los pendientes gráficos y de recuperación indicados arriba se conservan.
