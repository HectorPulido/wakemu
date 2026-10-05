# Auditoría de problemas de Wakemu

Fecha: 4 de octubre de 2026. Revisión estática, lectura de registros y pruebas autorizadas posteriores; ninguna solución aplicada.

## Alcance y conclusión

La revisión inicial inspeccionó los archivos de `/Users/hectorpulido/Documents/wakfu-experiment`, configuración Compose, herramientas locales del cliente y el último tramo de 8 MB de `.runtime/local/logs/game-server.jsonl`, sin ejecutar ni modificar el proyecto. Posteriormente, el usuario autorizó cliente, pruebas y cambios de datos, exclusivamente con un personaje nuevo. La sección final registra esas comprobaciones y distingue evidencia dinámica de conclusiones estáticas. No se corrigió código, no se reiniciaron servicios y no se hizo commit ni push.

La copia de trabajo tiene cambios de otro agente. Las referencias corresponden al contenido observado durante la revisión, no necesariamente al commit de GitHub ni al código cargado en el proceso. No se verificó el entorno remoto. Se incorporó la captura de pantalla del bolso Sadida enviada por el usuario durante la revisión; no se copió al repositorio.

Los síntomas combinan cuatro situaciones: funciones pendientes, políticas de prueba que alteran el comportamiento esperado, restricciones explícitas del código y posibles desincronizaciones del cliente. Además, hay evidencia histórica de errores de corrupción de SQLite que afectan al crecimiento.

**Clasificación:** “Confirmado” significa demostrado por el código o registro indicado; no implica reproducción gráfica. “Hipótesis” identifica una causa plausible pendiente de comprobar. “Pendiente” significa que la ruta completa necesaria no apareció en la revisión; no demuestra ausencia absoluta en todo el proyecto.

## Hallazgo prioritario de almacenamiento

En el tramo leído aparecen **8.245 eventos `plant_growth_error`** con `database disk image is malformed`, desde `2026-10-04T03:13:05Z` hasta `05:33:54Z`. Son registros históricos, no una comprobación de integridad actual. Antes de esa ventana hay 18 eventos `planted_resource_grown`; el último observado es del 3 de octubre a las `22:30:01Z`. El crecimiento funcionó al menos para algunos recursos y posteriormente encontró errores de almacenamiento.

**Posible solución:** antes de desarrollar más crecimiento, preservar una copia consistente de SQLite y sus archivos WAL/SHM, comprobar integridad sobre una copia y determinar si corresponde restaurar un respaldo o recuperar datos. Investigar el origen del daño sin atribuirlo automáticamente al bolso ni al otro agente. Ninguna de esas operaciones se hizo aquí.

## Requisito transversal: parámetros del servidor en DB

El usuario confirma que cooldowns, flags, tiempos, probabilidades, límites y multiplicadores deben parametrizarse en la base de datos, incluyendo los ajustes de juego mostrados en Compose. La auditoría debe proponer claves, ámbitos, validación, caché y revisión efectiva, no limitarse a recomendar variables de entorno. [Correspondencia de variables y diseño concreto](../soluciones-wakemu/PARAMETROS-SERVIDOR-EN-DB.md). Endpoints y credenciales de infraestructura mantienen su configuración de arranque. No se implementó esta migración.

## Plantación y ecosistema

### 0. Retrasos al iniciar combates y lanzar hechizos

**Alcance actualizado:** las mejoras solicitadas son exclusivamente del servidor. El cliente sirve como instrumento de reproducción; no se proponen modificaciones de cliente, interfaz ni herramientas. Las propuestas anteriores de cliente quedan fuera del alcance de implementación.

**Confirmado por mediciones aisladas:** el movimiento recalcula y recorre las 125.989 aristas del mapa 1134 para cada grupo cercano. Simular 16 grupos costó 1,94 s y 32 grupos 3,83 s, sin Redis ni red. El worker conserva bloqueos compartidos de grupos y recolección mientras calcula y publica; comenzar un combate puede esperar esos bloqueos. El coste CPU también puede competir con otros hilos del servidor.

**Confirmado en combate:** las transacciones copian y serializan la geometría completa repetidamente. En una prueba controlada de dos actores, el terreno de radio 89 produjo un estado de 844.397 bytes. Preparar y confirmar un hechizo caliente costó unos 299 ms, frente a 21 ms con radio 12. Es una comparación diagnóstica, no una recomendación de reducir arbitrariamente el terreno: el serializador de estadísticas fue sustituido por uno vacío y se excluyeron persistencia y red. También hay checkpoints síncronos completos en el camino de solicitudes.

**Límite de evidencia:** diez lanzamientos recientes en los registros tardaron aproximadamente 374–4.037 ms entre recepción y publicación; la entrada al mundo alcanzó 7,77 s. No se reprodujo todavía el retraso completo de 20 s. La traza actual empieza después de leer el paquete y omite parte de su propio cierre; no mide toda la espera. El intento gráfico con el personaje nuevo Audit Tempo fue interrumpido por una desconexión de paro programado del servidor, anterior al clic registrado.

**Posibles soluciones del servidor:** indexar adyacencias y ocupación; calcular movimiento fuera del bloqueo y aplicar con comprobación de versión; separar geometría inmutable del estado mutable de combate; mantener validación transaccional mediante versiones; guardar checkpoints solo ante cambios y diseñar persistencia ordenada con garantías de recuperación; evitar enviar a sockets bajo bloqueos globales. Aplicar la política solicitada de zona activa, intervalo de 5 s, 25% de probabilidad y pasos aleatorios sin convertirla en sustituto de las optimizaciones estructurales.

**Validación necesaria:** medir cola de recepción, espera de locks, cálculo, estadísticas, checkpoint y envío por solicitud; comparar p50/p95/p99 con 1/16/32 grupos, varios combates y un receptor lento. Conservar integridad, recuperación y orden de acciones. Investigación y límites completos: [auditoría de rendimiento del servidor](auditoria-rendimiento-server-wakemu-2026-10-04.md). No se aplicó ninguna corrección.

EXTRA: Revisar tambien las llamadas a la base de datos, deberian ser pocas, la mayoria de llamadas deben ir a redis primero y 20 minutos despues actualizar
y en caso que redis no tenga la respuesta ahi si pedir a la base de datos. pero tener cuidado con duplicaciones de objetos, etc.

**Ampliación verificada del requisito Redis/20 minutos:** el diseño actual usa Redis como journal de ciertos dominios, no como caché completa previa a SQLite. `Store.character` consulta primero personaje, progresión, merkasaco, contenedores, objetos y builds SQL; luego `BuildJournal.overlay` sustituye las hojas pendientes. Por eso un hit Redis todavía consulta SQLite. Una fixture temporal con traza SQL registró **9 SELECT, 3 INSERT de inicialización idempotente y 7 CREATE IF NOT EXISTS** por carga con hit, repetidos tres veces; las inserciones no significan tres objetos creados ni duplicación. Fueron cargas inferiores a 1 ms en esa fixture; el número de consultas demuestra el diseño, no la causa de un retraso de 20 s.

El journal de builds difiere sus filas hasta **1.200 s**, comprobado con reloj simulado: a 1.199 s no escribió; a 1.200 s confirmó una fila y conservó la hoja. El guardado todavía hizo **20 SELECT y 2 UPDATE** SQL: la lease y salud siguen siendo dominios inmediatos. Cron configura builds/grupos a 1.200 s y posiciones a 2 s. No basta con cambiar un intervalo global para cumplir el requisito.

**Propuesta concreta:** separar catálogos inmutables, estado del personaje y transacciones de propiedad. Leer snapshots versionados de Redis primero y cargar desde SQL ante ausencia real, con hidratación única por solicitud; retirar DDL/inicialización del camino caliente mediante migraciones. Para inventario, identificación, reciclaje e intercambios, registrar atómicamente UID, cantidades, propiedades, revisión y recibo idempotente antes del ACK. No usar SQL antiguo como fallback si Redis falla teniendo mutaciones pendientes: `StateJournal` ya falla explícitamente en ese caso para evitar resucitar objetos consumidos. Diferenciar ausencia de clave de indisponibilidad/corrupción de Redis.

**Garantías y pruebas:** flush por revisión con comparación de baseline y limpieza condicional; si llega una edición durante el flush debe sobrevivir. Recuperar sin duplicar grants/recompensas ni volver a sortear elementos/engastes. La configuración Compose declara AOF con `appendfsync always`; se debe verificar la configuración del Redis realmente cargado antes de afirmar durabilidad. Se reejecutaron tests de journal de sesión reemplazada, caída Redis, conflicto SQL y revisión nueva durante checkpoint. El experimento usa MemoryRedis, no acredita rendimiento de red, caída del host ni pérdida de AOF. Detalles adicionales y artefactos en el informe de rendimiento.


### 1. Las semillas solo disminuyen al reconectar

**Confirmado:** `server/wakfu_server/maps/planting.py`, función `complete`, resta una unidad en SQLite dentro de la transacción. Envía creación de recurso `13135` y resultado `12954`, sin delta `12470`, porque la implementación asume que el manejador nativo del resultado consume la semilla visualmente. `server/local_game_server.py`, ruta `13429`, envía esos mensajes y actualiza el personaje. El registro contiene resultados aplicados.

**Hipótesis:** el estado persistido cambia, pero el cliente no consume o no refresca el stack con esa secuencia en el caso observado. Los prefijos de `12954` todavía tienen semántica parcialmente interpretada.

**Posible solución:** correlacionar UID, cantidad, solicitud, ocupación y resultado en una captura del fallo. Corregir el contexto o la sincronización según el manejador real; no añadir `12470` sin comprobar si duplicaría el consumo. **Validación:** cantidad correcta inmediatamente, al reconectar y tras repetir el resultado, tanto con una semilla como con un stack.

**Nuevo síntoma reportado por el usuario:** se pueden extraer semillas del mismo monstruo indefinidamente, sin cooldown. Es independiente del refresco del inventario al plantar. **Confirmado por código actual:** la ruta13481 llama a `HARVESTS.begin` con `cooldown_seconds=0`; el servicio conserva recibos y sabe validar un cooldown, pero queda desactivado en el dispatcher. **Prueba aislada:** acción3724 del jalató/ref1 produjo semillas7361 en tres extracciones sucesivas del mismo monstruo, esperando únicamente3000ms por acción. Con cooldown sintético10s, solo la primera completó; las siguientes iniciaron y fueron rechazadas al terminar. No se fija10s como tiempo oficial. [Evidencia y solución concreta](../soluciones-wakemu/01-semillas-sin-refresco/REVISION-RESPUESTAS.md).

### 2. Un bebé tofu nunca crece

**Confirmado:** `maps/planting_runtime.py::monster_growth_member` elige una referencia por nivel mínimo y referencia dentro de la familia, priorizando criaturas recolectables. El recurso plantado se transforma en un grupo, pero no se observó un ciclo posterior que cambie edad o referencia del monstruo vivo. El código no demuestra que una referencia de bebé deba convertirse automáticamente en otra.

**Posible solución:** definir y persistir una política de maduración por familia, con referencias compatibles, tiempos y actualización de estadísticas/visualización. Separar crecer una semilla de envejecer un NPC. **Validación:** bebé y adulto antes/después del plazo, conservación al reconectar y comportamiento durante combate.

### 3. Los monstruos no se reproducen ni amplían grupos

**Confirmado:** el crecimiento crea un grupo con un miembro; respawn recupera grupos derrotados y no equivale a reproducción. `server/cron-service/config.json` desactiva `population`; `storage/global_tasks.py` solo admite callbacks de persistencia.

**Posible solución:** servicio de población con reproducción y ampliación de grupos, límites por zona/familia, ocupación, identificadores únicos y persistencia idempotente. Definir explícitamente una política del emulador si no se dispone de reglas acreditadas. **Validación:** aparecen nuevas unidades sin duplicarlas por reintento y sin crecimiento ilimitado.

No debe haber respawn automatico excepto por mecanicas de reproduccion y siembra

### 4. El porcentaje de plantación mostrado no es real

**Confirmado:** `client/tools/java/OpenPlantingAgent.java` reemplaza `dev.am` por un retorno constante `1` y `ffY.C` por `100`. El lanzador activa la política abierta por defecto. En el servidor, completar una plantación válida usa resultado exitoso sin una tirada probabilística. El retorno `1` por sí solo no acredita la unidad del texto mostrado, pero sí que el cliente dejó de calcular su valor original.

**Posible solución:** distinguir modo de pruebas y modo normal; mostrar una probabilidad coherente con la decisión autoritativa del servidor. Suelo, clima y reglas territoriales deben alimentar el mismo cálculo. **Validación:** probabilidades 0%, 1% y 100% con RNG controlado y resultados estadísticos suficientes.

### 5. Cardo dice que el recurso pertenece a otra persona

**Hipótesis:** falta integrar autorizaciones/estado del recurso o se está mostrando un recurso que no coincide con el estado propio. `planting.py::resource_packet` fija dos campos a cero y la tabla `planted_resources` no almacena propietario. No hay ruta de recolección de plantas `12995` en el dispatcher revisado; sí existe recolección de monstruos `13481`. Esto no demuestra qué condición exacta dispara ese texto en Cardo.

**Posible solución:** identificar referencia de Cardo, acción y manejador del aviso; implementar ocupación/recolección vegetal, permisos y mensajes nativos adecuados. **Validación:** recurso propio, de otra persona y ocupado por otro actor; distinguir rechazo local del cliente de rechazo servidor.

### 6. Cardo no llega a su etapa final

**Confirmado:** `planting_runtime.py::mature` consulta solo `stage=1` y, para plantas, avanza únicamente a `2` si existe. No recorre todas las etapas del catálogo. Además, los errores de SQLite pueden impedir incluso esa transición.

**Posible solución:** identificar las etapas de la referencia concreta y programar cada transición válida con su fecha persistida y notificación. No asumir que todas las especies usan etapas consecutivas. **Validación:** recorrer todas las fases y reconectar entre ellas.

### 7. No sube Wakfu ni Stasis

**Pendiente:** las rutas de plantación y recolección revisadas no calculan ni persisten deltas personales de Wakfu/Stasis. El bootstrap ecológico de `maps/planting_context.py` sincroniza familias y poblaciones, lo cual no equivale a progresión personal.

**Posible solución:** estado propio persistido, política de acciones ecológicas y mensajes de actualización. Validar las reglas antes de asignar signo o cantidad. **Validación:** plantar/cosechar con diferentes estados de población y conservar el valor al reconectar.

### 8. No aumenta la experiencia de los oficios

**Confirmado:** `storage/profession_store.py` guarda oficio y nivel, sin XP; su encabezado declara ausencia de curva/progresión. La ruta de plantación no concede XP. `docs/reports/ecosistema.txt` documenta el paquete `12916` como delta de XP de oficio.

**Posible solución:** persistir XP, curva y nivel; conceder la recompensa una sola vez por acción completada y emitir su delta. El ejemplo capturado de +100 no es una fórmula universal. **Validación:** progreso inmediato, subida de nivel, reconexión y cancelación sin recompensa.

## Combate y progresión

### 9. No hay experiencia ni subida de nivel por combate

**Confirmado:** Compose y `combat/combat_lifecycle.py::policy_from_env` usan `WAKFU_LOCAL_FIGHT_XP=0` por defecto. Existen recompensa transaccional, curva de nivel y notificaciones en `combat_rewards.py`, `characters/progression.py` y `combat_xp_gain.py`.

**Posible solución:** definir una política de XP no nula y, si se desea progresión por enemigo, sustituir el importe fijo por un cálculo explícito. Verificar la configuración efectiva del proceso antes de atribuirle el valor de Compose. **Validación:** victoria, derrota, cruce de nivel, HP/aptitudes y ausencia de doble recompensa.

Dejar configurable un "multiplicador de xp"

### 10. No hay drops ni kamas

**Confirmado:** los kamas de combate también valen cero por defecto. `combat_rewards.py` y `combat_results.py` declaran que no generan loot.

**Posible solución:** configurar una política de kamas e implementar tablas de botín, tiradas, inserción de objetos y recibos de entrega en una transacción idempotente. **Validación:** resumen y wallet coinciden; el loot permanece al reconectar y no se duplica.

Dejar configurable un "multiplicador de drop y kks"

### 11. No se puede intercambiar con otros personajes

**Pendiente:** no se encontró un servicio de intercambio integrado en el dispatcher.

**Posible solución:** invitación/aceptación, oferta revisada, confirmación de ambas partes y transferencia atómica bajo leases. Cancelar por desconexión o cambio de oferta. **Validación:** dos clientes, cancelación, falta de espacio y ausencia de pérdida/duplicación.

### 12. No se puede pelear contra otros personajes

**Confirmado en la ruta revisada:** el inicio de combate resuelve el objetivo mediante `combat_group_for_target`, que busca miembros de grupos NPC disponibles. No se observó una ruta completa de desafío PvP.

**Posible solución:** separar desafío consensuado de ataque a NPC; coordinar aceptación, equipos, colocación, control, abandono y resultado. Definir las recompensas de duelo. **Validación:** ambos clientes comparten un único combate y salen correctamente.

### 13. Mensajes privados y otros canales de chat

**Confirmado:** el handler `12366` extrae texto y usa `WORLD.broadcast` con `wire.chat`; no implementa selección de canal ni resolución de destinatario privado. `characters/social.py` inicializa listas vacías, no un servicio de mensajería.

**Posible solución:** decodificar solicitudes específicas y enrutar por destinatario, proximidad, grupo o canal, con respuestas de error. **Validación:** tres clientes y comprobación de quién recibe cada mensaje; un privado no debe difundirse.

### 14. No se puede entrar al combate de otra persona

**Confirmado parcialmente:** existe `combat_multiplayer_wire.py::decode_join` para `13241`, pero no apareció su conexión al dispatcher. El estado de combate se mantiene en la sesión con variables `fight` y `fight_messages`.

**Posible solución:** registro compartido de combates, resolución del objetivo, validación de fase/equipo/cupos y publicación a todos los participantes. **Validación:** unión durante colocación y rechazo al cerrar la fase, con estado consistente en ambos clientes.

### 15. No hay grupos de jugadores

**Pendiente:** `COMBAT_GROUPS` administra grupos de monstruos, no parties de jugadores. No se encontró un flujo integrado de invitación, liderazgo y miembros.

**Posible solución:** entidad party independiente y su protocolo de invitación, salida, expulsión y desconexión; integrarla con chat y combate. **Validación:** liderazgo transferido y miembros coherentes tras salir o reconectar.

### 16. No se pueden ver los combates

**Confirmado parcialmente:** hay codec de envolvente externa `13753`, pero no se observó un servicio de espectador conectado a los combates vivos. El replay puede incluir paquetes de la captura inicial y filtra los de otro mapa; no representa un registro de combates actuales.

**Posible solución:** publicar marcadores de los combates propios y una sesión de observación sin control de actores, con snapshot inicial y eventos posteriores. **Validación:** observar inicio, turno y fin sin poder ejecutar acciones del participante.

### 17. No se pueden subir características

Extra: Ademas tambien cuando si se puede usar la aptitud, parece que el calculo se hace de manera incorrecta, de tal manera que cada vez que subo o bajo las caracteristicas el resultado final es totalmente diferente

**Confirmado:** sí existe validación/persistencia de aptitudes mediante `12772`, `items/builds.py` y `characters/aptitudes.py`. La XP cero puede impedir obtener nuevos puntos. El log contiene rechazos `Allocated aptitudes are unavailable`, criterios de equipo no implementados e identidades de slots adicionales no implementadas; algunos pueden corresponder a una versión anterior del código.

**Posible solución:** correlacionar el rechazo concreto con nivel, presupuesto por categoría y hoja enviada; distinguir puntos inexistentes de un fallo de protocolo o efectos no soportados. **Validación:** asignar puntos disponibles, rechazar sobreasignación y comprobar efecto, panel y persistencia.

### 18. No se puede elegir hacia dónde mirar en colocación

**Confirmado:** `combat_orientation.py::apply` exige fase `active`, turno propio y ausencia de ACK pendiente; por tanto rechaza colocación aunque la solicitud alcance `13655`.

**Posible solución:** ruta específica de orientación durante colocación, con autorización del actor y respuesta apropiada a esa fase. **Validación:** dirección visible antes de listo y conservada al iniciar combate, sin consumir AP/MP.

## Movimiento y población por zona

### 19. Todos los monstruos se mueven a la vez

**Confirmado:** `local_game_server.py::wander_monsters` usa un tick global aleatorio de 3 a 6 segundos. `maps/monster_wander.py::wander_location` intenta mover cada grupo elegible, sin tirada del 25%; `movement_packet` codifica un solo paso. La dirección es aleatoria entre candidatos, pero no la decisión de moverse.

**Posible solución según lo solicitado:** evaluación cada 5 segundos, oportunidad independiente del 25% por grupo y número aleatorio acotado de pasos válidos. Mantener miembros del grupo coordinados, colisiones y alturas; evitar sincronía visual si se decide distribuir evaluaciones. Acordar el rango de pasos. **Validación:** RNG controlado, distribución aproximada del 25%, grupos en combate/recolección inmóviles.

Asegurarnos de que esto sea suoper eficiente, unicamente mover monstuos en mapas donde haya gente

### 20. Pocos mobs iniciales, reproducción y pausa sin jugadores

**Confirmado parcialmente:** el movimiento ya limita la búsqueda a ubicaciones con jugadores y exige proximidad. Sin embargo, `grow_planted_resources` madura recursos persistidos globalmente y su comentario permite crecer tras desconectar al plantador; respawn tampoco exige jugadores. No existe el sistema de población solicitado.

**Posible solución:** activación por zona/instancia con jugadores presentes, población inicial pequeña por familia y límites. Pausar movimiento, reproducción y demás simulación acordada sin jugadores; definir si al regresar se recupera tiempo o se reanuda sin avance. **Validación:** comparar zona ocupada y vacía, reiniciar solo en una prueba autorizada y comprobar que no reaparece un lote duplicado.

## Cliente e inventario

### 21. Tools con configuración `.env` del servidor

**Confirmado:** scripts locales fijan `127.0.0.1`; el launcher portable ya admite host y puertos mediante JSON y variables concretas, pero no se encontró un cargador común `.env`. `portable_config.py` restringe el host a IPv4 numérica y el guard de red forma parte del arranque.

**Posible solución:** cargador único para host, API y puertos, con ejemplo versionable sin secretos, usado también al generar configuración y permiso de red. `127.0.0.1` apunta al equipo del usuario, no al remoto, salvo un túnel local. Mantener el inspector local separado de la dirección del juego. **Validación:** valores por defecto, IP remota, configuración inválida y todos los endpoints coherentes.

**Distribución:** `/client` está íntegramente excluido de Git por instrucción del usuario. Las herramientas propias redistribuibles deberán residir fuera de esa carpeta, sin incorporar binarios/assets del cliente.

Extra: igual permitir al servidor recibir request desde la red externa 0.0.0.0

### 22. Objetos sin identificar

Es extremadamente importante que los objetos funcionen como debe, lo que sucede es que todos los objetos aparecen con un enorme ? que normalmente significa que el objeto no está identificado. ¿Qué implica?
* Falta de elementos y huecos: El objeto aún no ha definido de manera aleatoria sus elementos de dominio/resistencia ni sus engarces de encantamiento.
* Cómo solucionarlo: Solo debes darle doble clic al objeto (si lo tienes en el inventario) para revelar y asignar sus características.

---

La identificación de elementos en Wakfu es el proceso mediante el cual configuras las estadísticas elementales y revelas el potencial de un objeto de equipo.
Tras las actualizaciones del juego, el sistema funciona de la siguiente manera:
1. La primera identificación (Doble clic)
Cuando obtienes un objeto no identificado (con el signo ?), no puedes equipártelo de inmediato. Al hacer doble clic sobre él en tu inventario, realizas dos acciones simultáneas:
• Elige tus elementos: Se abrirá una interfaz táctica que te permite seleccionar manualmente a qué elementos (Fuego, Agua, Tierra o Aire) quieres asignar el dominio elemental y las resistencias elementales del objeto.
• Revelación de engarces: El objeto revelará de forma aleatoria sus engarces de encantamiento (entre 1 y 4 ranuras), mostrando sus formas o colores (rojo, azul, verde, amarillo).
2. Los elementos ya no son definitivos
A diferencia de versiones antiguas del juego donde dependías de la suerte o de consumir consumibles (como las transmutaciones) para cambiar los elementos, el sistema actual es totalmente libre.
• Si cambias tu rama de hechizos o tu build, puedes volver a modificar los elementos del objeto en cualquier momento.
• Solo debes hacer clic derecho sobre el ítem y pulsar el botón de asignación elemental junto a las recetas para reconfigurar sus ramas. ¡Incluso puedes hacerlo mientras estás dentro de una mazmorra sin desequiparte el objeto!

---
El sistema de encantamiento de Wakfu reemplazó la antigua forjamagia para ofrecer una personalización absoluta de tus estadísticas. A diferencia de otros RPGs, aquí no compras runas prefabricadas, sino que modificas los engastes (o engarces) propios de cada objeto usando recursos que tú mismo reciclas.
1. Anatomía de los Engastes (Engarces)
Cada objeto de equipo puede albergar entre 1 y 4 engastes. Al identificarlo por primera vez, el número otorgado es completamente aleatorio.
Existen 4 tipos de engastes representados por colores y formas geométricas, y cada uno te permite elegir entre una lista específica de estadísticas:
Color / Forma	Estadísticas Seleccionables
Rojo (Triángulo)	Dominio Cuerpo a Cuerpo, Dominio Distancia, Dominio Berserker, Iniciativa.
Azul (Cuadrado)	Dominio Elemental, Vida (PdV), Placaje, Resistencia Elemental.
Verde (Círculo)	Dominio Crítico, Dominio Espalda, Esquiva, Iniciativa, Resistencia Elemental.
Blanco (Hexágono)	Comodín: Puede albergar el efecto de cualquier otro color.
💡 Regla del Doble Bonus: Si colocas un efecto en una ranura que corresponde al rol ideal de la pieza (por ejemplo, poner estadísticas de daño en armas o escudos), el beneficio estadístico se duplica automáticamente.
2. El combustible: Las Esquirlas Mágicas
Para darle poder a un engaste necesitas Esquirlas. Estas se obtienen utilizando el icono del martillo en tu inventario para romper/reciclar objetos de equipo que no utilices.
• La cantidad de esquirlas recibidas depende del nivel y la rareza del objeto destruido.
• Puedes subir el nivel de un efecto dentro del engaste consumiendo más esquirlas directamente desde tu inventario.
• Si decides retirar un efecto para cambiarlo por otro, el juego te devuelve el 90% de las esquirlas invertidas.
3. Modificación Avanzada: El Taller de Encantamiento
Ubicado en Astrub y en las capitales de cada Nación (identificado en el mapa con un icono de pergamino dorado o una "T"). Aquí es donde alteras la estructura física de tu equipamiento.
Para realizar modificaciones avanzadas, el sistema te exige sacrificar un objeto idéntico (mismo nombre, mismo nivel y misma rareza). Al destruirlo en la interfaz del taller, obtienes 7 Cargas. Estas cargas te permiten alterar tres aspectos:
1. Aumentar el Número de Engastes: Puedes gastar cargas para intentar desbloquear la 2ª, 3ª o 4ª ranura. También existe una opción de "éxito garantizado" sacrificando directamente otro objeto similar.
2. Cambiar Colores: Si tu personaje necesita ranuras rojas pero tu coraza tiene ranuras verdes, usas cargas para cambiar aleatoriamente el color de los engastes.
3. Cambiar el Orden: Altera la posición de los colores de izquierda a derecha. Esto es vital para el paso final: el fin del juego (endgame).
4. El objetivo final: Las Sublimaciones
Las Sublimaciones son pergaminos que añaden efectos pasivos únicos y extremadamente poderosos (como ganar PA bajo ciertas condiciones, infligir más daños si atacas primero, etc.).
Para poder aplicar una sublimación a tu objeto, este debe cumplir estrictamente dos condiciones:
• Tener exactamente 3 o 4 engastes abiertos.
• Los colores de tus engastes deben coincidir en el orden exacto que exige el pergamino de sublimación (por ejemplo: Rojo-Azul-Verde). Los engastes blancos (comodines) sustituyen cualquier color requerido.


**Hipótesis de la revisión inicial (código anterior):** `items/inventory_items.py::item_proto` transmitía solo UID, referencia y cantidad; `item_form` añadía ocho bytes a cero. Faltan propiedades de instancia en el modelo mínimo, pero no se verificó cuál campo controla el estado “identificado” ni qué referencias fallan.

**Posible solución:** identificar el campo nativo y persistir sus propiedades junto con efectos/variantes que corresponda; inicializar objetos nuevos según la política deseada. **Validación:** objetos recién obtenidos, stack, equipamiento y reconexión muestran el mismo estado.

Extra: revisar tambien el funcionamiento de la forjamagia y los engastes

**Contexto del usuario y alcance técnico:** el texto anterior describe el comportamiento esperado; no acredita todavía que cada regla corresponda al cliente instalado. Separar identificación, elección de elementos, revelación de engastes, reciclaje, cargas del taller y sublimación. No son un único booleano “identificado”. El contexto menciona amarillo y después blanco para el cuarto color, y cifras como 7 cargas/90% de devolución: conservarlas como requisitos a contrastar con catálogos y protocolo antes de implementar o cobrar recursos. No se verificó aquí una tasa oficial ni se probaron esas operaciones completas.

**Cambio concurrente comprobado en el checkout:** ahora existen `items/inventory_elements.py` y sus tests, añadidos por el otro agente. `grant` genera máscaras para efectos 1068/1069 y guarda `inventory_item_elements`; `item_proto` añade campo protobuf **56** (tag codificado 450), y `item_form` transmite la opción elemental. Es una selección aleatoria al otorgar el objeto, no la interfaz autoritativa de elección manual descrita por el usuario. La BD histórica sin esa fila conserva ausencia de elementos; no hay migración acreditada de todos los objetos viejos. Este resultado pertenece al código del checkout, no demuestra que el proceso principal ya lo haya cargado; la instancia de builds usa una copia anterior fija.

**Reproducido sin alterar objetos reales:** con referencia 2869 y RNG fijo, una nueva unidad recibió máscaras `[22,0]`: dominio Agua/Tierra/Aire y ninguna resistencia seleccionada. Reabrir la BD conservó las máscaras. La representación heredada del mismo objeto, sin propiedades de elementos, emitió solo tags 8/16/24 y ocho opciones nulas; la nueva emitió también tag 450 y diez bytes de opciones. Un probe del JAR instalado decodificó correctamente ambas máscaras mediante `kX/le` y `vj/foX`; no se modificó el cliente. Los **3 tests de elementos pasaron**, incluyendo persistencia y ausencia heredada. Esto acredita el codec y la persistencia de elementos, no la desaparición gráfica del “?” ni la existencia de engastes.

**Pendiente de implementación/verificación del servidor:** no se encontró en los módulos de items revisados un modelo persistido de colores/orden/efectos de engastes, cargas, esquirlas invertidas y sublimaciones. Destruir un objeto (`inventory_actions.destroy`) elimina el stack y emite decremento; no equivale a reciclarlo concediendo esquirlas. No deben reutilizarse esas operaciones confundiendo sus recompensas. Tampoco se identificó en el dispatcher revisado una ruta completa de selección/reasignación elemental o taller. Hace falta capturar las solicitudes concretas y validar los handlers nativos antes de asignar opcodes por suposición.

**Solución y validación ampliadas:** propiedades por UID con revisión y política explícita de identificación inicial; separar una unidad de un stack si sus propiedades pasan a ser individuales. Identificar una sola vez, persistiendo el sorteo antes del ACK; reintentar no vuelve a sortear. Aplicar selección elemental y bonus efectivos en builds y combate desde el mismo objeto. Reciclar/sacrificar debe consumir origen y conceder resultado en una única transición idempotente; validar identidad, rareza, nivel, propiedad, recursos y compatibilidad de sublimación. Probar doble clic repetido, desconexión después de confirmar y antes del ACK, inventario lleno, objeto equipado/referenciado por otra build, stack de varias unidades y flush Redis durante la operación. Ninguna de esas pruebas completas se da por aprobada por el probe de elementos.


### 23. Bolso Sadida apilado rompe la interfaz hasta reiniciar

**Confirmado:** `inventory_bags.py::equip` rechaza `quantity != 1`; `inventory_bag_rules.py::ordinary` también rechaza bolsos especializados o con criterios. El log registra `Unavailable or unsupported owned bag item` a las `2026-10-03T23:09:14Z`. El handler intenta resincronizar al rechazar.

**Evidencia visual:** la captura muestra “Bolso sadida negro x3 añadido”, UID `1099511628691`, inventario sin celdas y contador `0/0`, mundo negro y ficha con `2.147.483.647` PdV en rojo, mientras el indicador inferior muestra `2274`. El personaje figura en nivel 6. El chat informa mapa 1134, instancia 0 y posición (-19, 15, -8). Esto confirma una inconsistencia de varias vistas, no solo de la cantidad del bolso. La captura no tiene hora y no permite correlacionarla inequívocamente con el evento del registro.

**Hipótesis:** el rechazo de un stack deja cambios optimistas en la interfaz o la respuesta de resincronización invalida/desordena el estado nativo. `inventory_move.py::synchronization` envía `13713` con identidad y `inventory.bags(character)`; revisar ese codec y el orden frente a los mensajes de equipamiento. El valor mostrado de PdV equivale a `INT32_MAX`, compatible con un sentinel/límite o cálculo saturado interpretado como vida, pero no demuestra por sí mismo overflow, corrupción de SQLite ni un error específico de combate.

**Posible solución:** separar una unidad con UID propio dentro de la transacción, equiparla sin destruir el stack restante y restaurar todas las vistas ante rechazo. Evaluar filtros/criterios de esa referencia. Capturar la secuencia inmediatamente anterior y posterior al fallo y verificar el parser real de `13713`, número de contenedores, contenido y actualización de características. **Validación:** stack de 2+, espacio insuficiente, slot ocupado, rechazo y reconexión sin pérdida; inventario conserva capacidad/celdas, mapa sigue visible y PdV de ficha/HUD son coherentes. No se observó evidencia que vincule este evento con la corrupción posterior de SQLite.

**Causa confirmada en la prueba posterior:** la respuesta de rechazo usa `inventory_move.py::synchronization`, que serializa identidad seguida únicamente de `inventory.bags(character)`. El bytecode de `cwY` lee esa identidad y conserva el resto; el handler `chK`, rama `13713`, entrega el resto a `biB.as(byte[])`, deserialización de entidad, no a un lector aislado de bolsas. El cliente interpreta los bytes como secciones de personaje y falla. Detalles y correlación en la sección final. La restricción del stack provoca el rechazo; el payload incorrecto de recuperación es el segundo fallo que rompe el estado visual.

### 24. Pasaporte de Amakna por defecto

**Confirmado parcialmente:** `wire.py` fuerza las secciones de nación propia a cero y limpia sincronización nacional. Esto contradice que el servidor elija Amakna deliberadamente en esas secciones, pero no descarta otra sección del replay, item inicial o caché.

Lo mas probable es que este quemado en alguna parte del buffer, hay que revisar donde

**Posible solución:** identificar si el pasaporte es un objeto o estado de nación, localizar su origen y sustituir cualquier dato heredado por estado propio. **Validación:** personaje nuevo con perfil limpio y reconexión; no borrar datos personales como sustituto de modelar nación.

Identificado ademas que cada lugar tiene asignada una nacion de por defecto hay que forzar que los lugares no tengan alineamiento hasta el momento que hagamos esa mecanica

## Mundo e interacciones

### 25. Brechas dimensionales

**Pendiente:** no se encontró una implementación específica integrada de brechas, objetivos, oleadas y recompensa. Teleporters y transporte genérico no acreditan esa función.

**Posible solución:** inventariar los accesos y acciones concretas; separar entrada a instancia de reglas internas, grupos, temporizador y cierre. **Validación:** entrada/salida y progreso con dos jugadores, abandono y recompensas idempotentes.

### 26. No se pueden añadir merkagemas

**Confirmado parcialmente:** `items/haven_bag_store.py::rearrange_rooms` mueve/intercambia gemas ya existentes y declara que no crea objetos de inventario. Existe habitación inicial y edición de mobiliario, pero no se observó transferencia completa inventario → ranura de gema.

**Posible solución:** insertar/retirar gemas propias con validación de UID/tipo, consumo/devolución y actualización transaccional de habitación y mapa. **Validación:** habitación habilitada, persistencia, retirada y protección de la gema fija inicial.

### 27. Clima

**Confirmado:** tarea `weather` desactivada en configuración cron; no es un callback permitido por `GlobalTasks`. Activar el booleano no bastaría.

**Posible solución:** modelo climático por zona, calendario/transiciones y mensajes; integrarlo después con crecimiento y porcentaje de plantación. **Validación:** cambio visible y misma condición para todos los jugadores de la zona.

### 28. Bonus de área

**Pendiente:** no se encontró una aplicación integrada de satisfacción territorial/bonus a características. El bootstrap ecológico no demuestra que los bonus estén calculados. `zone_challenges` está desactivado, pero desafíos de zona y bonus de área no deben confundirse.

**Posible solución:** identificar fuentes de cada bonus, resolver estado territorial y aplicar/retirar modificadores al entrar, salir o cambiar la condición. **Validación:** estadísticas cambian una vez y no acumulan el bonus al reconectar.

### 29. Mazmorras

**Confirmado parcialmente:** `maps/world_static.py::interaction` clasifica puertas/teleporters, pero no ejecuta lógica de mazmorra. La ruta `12870` revisada registra numerosas interacciones y continúa sin resolverlas. `wire.py` vacía progreso heredado de mazmorra; eso no implementa instancias ni salas.

**Posible solución:** accesos, instancia compartida para el grupo, salas/encuentros, progreso, condiciones y salida. **Validación:** entrada con requisitos válidos, dos jugadores en la misma instancia, victoria y abandono sin quedar atrapados.

### 30. Mesas de oficio ausentes o inoperantes

**Confirmado parcialmente:** `world_static.py` avisa que `13984` actualiza objetos existentes y no crea los ausentes. Su dispatcher no resuelve mesas de oficio; tener una fila en un catálogo no prueba que el cliente cargue la entidad.

**Posible solución:** comprobar mapa y objeto, recurso visual y orden de carga, después implementar interacción, receta, consumo, resultado y XP. **Validación:** la mesa aparece y funciona para dos clientes; ingredientes/resultados se conservan correctamente.

### 31. Configuración repetida de celdas durante colocación

**Confirmado por código:** `combat/combat_placement_cells.py::generate` genera una formación determinista desde posiciones de actores y terreno dirigido. Ordena semillas, vecinos y candidatos por distancia y coordenada; el cupo predeterminado es seis celdas por equipo. No utiliza RNG ni diseños alternativos. Con iguales posiciones y geometría devuelve la misma formación. No significa que todos los mapas tengan exactamente las mismas celdas: depende del terreno y las semillas.

**Posible solución del servidor:** definir variantes de formación por zona/encuentro o muestreo controlado entre candidatos legales, persistiendo el resultado elegido para que ambos equipos y la reconexión reciban lo mismo. Conservar celdas iniciales ocupadas, equipos disjuntos, altura válida y alcanzabilidad; no fabricar suelo ni aumentar el coste de escanear el mapa descrito en el ítem 0.

**Validación:** varios encuentros con posiciones iguales y diferentes; diversidad según política, semilla reproducible, mapas pequeños/desniveles, cupos y reconexión sin regenerar otra formación. Las pruebas existentes comprueban legalidad de formación, no diversidad gráfica.

### 32. Permiso `is_admin` para comandos `!` del chat

**Confirmado:** el esquema de `storage/store.py` no contiene `is_admin` en cuentas. El handler `12366` de `local_game_server.py` ejecuta comandos `!` cuando `WAKFU_TEST_CONSOLE=1`, sin comprobar un rol por cuenta. Ese flag es global y no equivale a autorización individual. `maps/test_console.py` valida propiedad/lease de personaje y argumentos, pero tampoco rol administrativo.

**Hallazgo relacionado:** `api.py` atiende `/test/command` y algunas tareas `/test/tasks/` antes de la rama que valida el token API. Proteger solo el chat dejaría una ruta alternativa para ejecutar comandos por ID de personaje cuando la consola está habilitada. Es relevante antes de habilitar acceso externo, como solicita el ítem 21; no se cambió ninguna exposición de red.

**Posible solución del servidor:** migración de cuentas con `is_admin NOT NULL DEFAULT 0`, sin convertir automáticamente en administradores las cuentas existentes ni permitir elegir el rol al registrarse. Usar una comprobación central en todos los accesos a comandos, autenticando al solicitante también en API; distinguir comandos informativos de comandos que alteran datos si se define esa política. El rol se concede mediante operación administrativa explícita y debe poder revocarse durante una sesión. Mantener el flag global como interruptor adicional, no como sustituto del permiso.

**Validación:** cuenta normal rechazada por chat y API sin mutaciones; admin autorizado; petición anónima rechazada; revocación efectiva; intentos contra otro personaje y tareas predefinidas; registro de actor, comando y resultado sin credenciales.

### 33. Rendirse deja bloqueados nuevos combates y transporte

**Confirmado en registros:** a las `2026-10-04T16:03:31Z` (personaje 11, combate 92349904) y `16:21:34Z` (personaje 7, combate 193472141) se registra `combat_abandoned_waiting_return`. Aproximadamente 450–486 ms después llegan solicitudes `12925` de cinco bytes y se rechazan con `Abandon continuation must confirm native loss`. Hay otro rechazo equivalente el 3 de octubre. Esto es evidencia de la continuación fallida, no una reproducción gráfica nueva realizada en esta revisión.

**Causa delimitada:** `combat_abandon.py::prepare` marca fase `finished`, limpia ACK/pending y emite `12238`/flush, pero la sesión conserva `fight`, `fight_messages` y la reserva del grupo hasta completar `12925`. `return_to_world` exige que `combat_results.continuation` devuelva verdadero: ID propio y flag final `1`. El error registrado demuestra que la continuación pasó validación de longitud/ID/flag, pero devolvió falso (flag `0`). El catch solo registra el rechazo; no libera el estado. El inicio de combate exige `fight is None`, por lo que el bloqueo posterior queda explicado en el servidor. La ruta específica del zaap necesita correlación adicional; no atribuir todos los transportes a un mismo handler sin captura.

**Posible solución del servidor:** comprobar la semántica nativa del flag en la secuencia emitida por abandono y hacer que la continuación de un abandono ya autorizado dependa de esa transición propia, conservando ID/propiedad y sin aceptar resultados de combate ajenos. No invertir el flag globalmente: también lo usa el cierre normal. Diseñar finalización idempotente que libere reserva, estado de sesión y pertenencia al mundo incluso ante fallos recuperables, con recuperación explícita si falta continuación. No conceder XP, kamas ni drops al abandonar ni forzar un cambio de mapa arbitrario.

**Validación:** abandono en colocación/turno/ACK pendiente, continuación real con flag observado, solicitud duplicada, ID ajeno, desconexión y reconexión. Después se puede iniciar otro combate y usar transporte; HP persistido y grupo disponible, sin recompensa ni liberación doble. El test actual rechaza explícitamente flag `0`: que pase no acredita compatibilidad con el cliente observado.

### 34. Builds personalizadas: desbloqueo tardío y hojas no seleccionables — prioridad alta

**Reproducido con personaje nuevo en servidor aislado:** Audit Builds, ID 1, subió de 49 a 50 mediante la consola autorizada. El panel de personaje muestra nivel 50 y 550 PdV, pero el panel de builds conserva candado y aviso de disponibilidad desde nivel 50, incluso al cerrar/reabrirlo. El comando actual envía solo `13046` y pide expresamente volver a seleccionar el personaje para actualizar hechizos/puntos. Esta prueba acredita la ruta `!nivel`; la subida por XP necesita su caso propio.

**Repetición solicitada a nivel 100:** antes de reconectar, la ficha mostró 100/1.050 PdV pero el HUD y las builds conservaron el estado anterior. Tras relanzar solo el cliente aislado, desapareció el candado y apareció Build 2. Al seleccionarla se resaltó la fila pero quedó el contenido de Build por defecto; Equipables terminó vacío. El log nativo registra `NullPointerException` al desreferenciar `this.jFr` (modelo de equipo ausente), con `BuildSheetModel` índice 1. Confirma gráficamente el efecto de anunciar una build sin su colección de equipo. No se registró activación 13776 en esta secuencia; no afirmar que se activó ni se probó su deck en combate. El desbloqueo efectivo entre 50 y 100 requiere acotación adicional.

**Contrafactual y activación reproducidos posteriormente:** guardando hojas completas vacías mediante `Store.save_build` solo en Audit Builds ID 1 y reconectando, la secundaria Audit Complete pudo seleccionarse y mostrar Equipables con slots normales. Activarla sí emitió **13776 (9 bytes)** a las 18:09:57 UTC; el servidor autenticado/cargado la rechazó explícitamente por falta de handler. Aunque el cliente mostró Activa, al volver a seleccionar el mismo personaje quedó **Build por defecto Activa**, conservando la hoja secundaria. Esto acredita dos fallos diferentes: bootstrap incompleto y activación sin autoridad/persistencia. No se modificó código ni se probó un cast secundario exitoso.

**Confirmado por protocolo y código:** guardar (`12772`/respuesta `12284`) no activa una build. La selección nativa emite **13776**, con ID e índice, y el dispatcher no tiene handler. `Store.character` no carga una selección persistida; equipo y aptitudes usan índice 0 por defecto. El bootstrap `build_set` anuncia activo 0 aun cuando el diccionario de entrada tenga índice 2. Tanto listo como lanzamiento de hechizos leen explícitamente el deck 0. Es necesario corregir la transición completa, no únicamente el desbloqueo visual.

**Confirmado con pruebas aisladas:** en niveles 1/49/50/51/200, las colecciones nuevas anuncian builds `[0,1]`, aptitudes `[0,1]`, equipo `[0]` y decks `[0]`. Tras guardar builds secundarias con contenido, los registros sí las incluyen; la inconsistencia no afecta por igual a todos los casos. En nivel 51, una build secundaria con amuleto y aptitud propios produce **588 PdV y +1 PA** al evaluarla explícitamente, mientras el cálculo normal conserva **560 PdV y ningún equipo**. SQLite y el journal guardan las hojas, pero recargar pierde cualquier selección añadida solo al diccionario. También se reprodujo `Invalid aptitude sheet level` al subir de 49 a 50 con una hoja guardada con nivel fijo 49.

**Posible solución exclusivamente del servidor:** fuente única de builds disponibles/activas y hojas coherentes de equipo, aptitudes y decks; desbloqueo sincronizado tras progresión; activación autoritativa de 13776 con selección persistida/versionada; estadísticas y combate resueltos desde ese índice; recuperación y rechazos sin bloqueo ni pérdida de hojas. Distinguir hoja a nivel real (`-1`) de nivel limitado antes de ajustar validaciones. No reutilizar `12837`, que corresponde a borrado de build, como ACK de activación.

**Comprobación ampliada:** 40 tests enfocados ejecutados OK (10 omitidos por requerir Redis), 9 de journal con Redis real OK (1 omitido de inyección de caída) y 44 filas experimentales con assertions de evidencia. No equivalen a probar la interfaz completa ni a solucionar el problema. Detalles, artefactos, límites y resultados gráficos en [auditoría profunda del issue 34](auditoria-builds-issue34-wakemu-2026-10-04.md).

### Comprobaciones de esta ampliación

Revisión estática de los módulos citados y lectura del registro completo disponible. Se ejecutaron `test_builds.py`, `test_combat_abandon.py`, `test_combat_placement_cells.py` y `test_chat_console.py` mediante `unittest`, con `PYTHONPATH=server PYTHONDONTWRITEBYTECODE=1`: **23 pruebas, todas OK**. Usan fixtures/bases temporales; no se cambiaron cuentas o personajes existentes. No incluyen el flujo gráfico nuevo ni una matriz de autorización `is_admin`. Ninguna solución se implementó; el código puede seguir cambiando por trabajo concurrente.

## Hallazgos adicionales

1. **IA de monstruos incompleta:** en el tramo del log hay 26 rechazos por falta de ataque auditado para referencia/nivel, 16 por alcance/LOS adyacente y 8 por falta de evidencia LOS. Ampliar catálogos y verificar geometría; no interpretar todo turno sin ataque como comportamiento intencionado.
* Para solucionar esto, revisar: /Users/hectorpulido/dofus/ai-service (solo no utilizar laya, si no el sistema determinista)

2. **Región ecológica desconocida:** un evento `planting_context_unavailable` indica `Unknown native map region`. Revisar cobertura mapa/región; afecta a autorización y contexto visual de plantación.
3. **Equipamiento restringido:** el log contiene cuatro rechazos por criterios nativos de equipo no implementados y dos por identidades de slots clonados no implementadas. Añadir esas rutas por separado de aptitudes y comunicar el rechazo de forma consistente.
4. **Crecimiento ligado al modo de pruebas:** el arranque crea el worker de crecimiento solo con `COMBAT_TEST`. Desactivar combates de prueba puede detener plantaciones aunque no sea la intención; separar flags de las funciones de mundo.
* Guardar ese tipo de flags en la base de datos, junto la xp, drop, velocidad de crecimiento etc.

5. **Publicación de crecimiento y entrega:** `publish_growth` marca la outbox como publicada antes de que el caller emita sus paquetes. Un fallo entre ambos puede dejar el mundo visual atrasado; snapshots ayudan al reconectar, pero no garantizan entrega inmediata. Diseñar confirmación/reintento idempotente.
6. **Dependencias externas de un clone:** el volumen Compose apunta a una captura específica en `.runtime`, que no se distribuye. Las herramientas en `/client` tampoco se publican. Documentar o eliminar esas dependencias de arranque cuando se diseñe instalación reproducible.
* Sacar de .runtime la base de datos, que siga siendo privado pero que no este en una carpeta random

7. **Desconexión por errores de validación:** el catch exterior de la sesión incluye `ValueError`; cualquier validación que escape de su handler puede terminar la conexión. Revisar solicitudes de nuevas funciones y distinguir rechazo recuperable de framing inválido.
8. **PdV inconsistentes tras el fallo de bolso:** la imagen aporta `INT32_MAX` en la ficha frente a `2274` en el HUD. Revisar serialización/refresh de características y cálculo de regeneración junto con la resincronización del inventario; no tratar ese número como salud legítima ni atribuirlo a una causa sin captura correlacionada.

## Orden propuesto y comprobaciones posteriores

1. Aclarar versión efectiva y salud de almacenamiento; preservar evidencia del fallo de bolso sin tocar el entorno del otro agente.
2. Resolver permisos administrativos antes de exposición externa (ítem 32), salida de abandono (33), sincronización coherente de builds (34) y los costes/bloqueos del ítem 0, junto con semillas/bolsos y crecimiento por etapas.
3. Definir economía y progresión: XP/kamas, loot, oficios y Wakfu/Stasis.
4. Crear los servicios compartidos de combate/party/chat/intercambio antes de integrar PvP, espectadores y mazmorras.
5. Implementar simulación de zona activa, reproducción, clima y bonus con límites de población y política documentada.

Cada cambio futuro debería probarse con un caso de éxito, rechazo, reconexión y reintento. Los casos sociales requieren al menos dos clientes; privados requieren un tercero para comprobar aislamiento. Ninguna solución propuesta se implementó. Las comprobaciones posteriores siguientes no sustituyen la validación de todas las funciones.

## Comprobaciones posteriores con autorización del usuario

### Entorno y datos de prueba

Se creó una cuenta nueva y el personaje **Audit Sprout**, ID 9, cuenta 8, nivel 1, con perfil independiente `audit-20261004`. La creación se hizo mediante la API existente; no se editó SQL directamente. Se entregaron únicamente a ese personaje cinco semillas de Cardo (4275), cinco de tofu (7358) y tres bolsos Sadida negros (12493), usando la consola de pruebas de la API. Evidencia privada y capturas se conservan en `.runtime/local/instances/audit-20261004/`, fuera de Git.

El arranque usa los scripts existentes, que recompilan agentes Java de prueba en `.runtime/`; no se modificaron sus fuentes. Durante la prueba otro proceso detuvo/recreó el servicio de mundo. Se observó el aviso «Desconectado del servidor (paro programado)» y fue necesario relanzar nuestro cliente. No atribuir esas desconexiones a acciones de inventario.

### Estado actual de almacenamiento y políticas

- Consulta de SQLite en modo de solo lectura dentro del contenedor: `PRAGMA quick_check` devuelve `ok`. Esto acota los errores históricos de corrupción; no se confirmó corrupción vigente.
- Variables reales del contenedor: `WAKFU_LOCAL_FIGHT_XP=0`, `WAKFU_LOCAL_FIGHT_KAMAS=0`, `WAKFU_OPEN_PLANTING=1`, `WAKFU_PLANT_GROWTH_SECONDS=30`, `WAKFU_LOCAL_MONSTER_RESPAWN_SECONDS=0`, `WAKFU_ENABLE_COMBAT_TEST=1`.
- Baseline del personaje: nivel 1, XP 0, kamas 0; oficios aprendidos 64, 71, 72, 73, 74 y 75 en nivel 0. Inventario persiste las cantidades concedidas 5/5/3.
- Los cuatro Cardos preexistentes consultados permanecen en etapa 2, aunque el catálogo de su referencia 60 define `[1, 2, 3, 4, 16]`. No se alteraron esos recursos.
- Bolso Sadida negro 12493: capacidad 10, nivel mínimo 1, sin filtro especializado ni criterio de equipamiento. Es un caso válido de bolso ordinario; la restricción de stack es relevante.

### Observaciones gráficas y del cliente

- En una cuenta y perfil nuevos, la selección muestra «Sacrógrito · Niv. 1 · Amakna» para Audit Sprout. Confirma que la etiqueta predeterminada aparece sin reutilizar el perfil del usuario; todavía no identifica el origen exacto del pasaporte. Captura `character-selection.png`.
- El personaje entró al mapa 1134 en (-12, -8, -1), con 60 PdV visibles y mundo renderizado correctamente antes de los ensayos de inventario.
- El cliente registra repetidamente `[CHAT] Connection failed` y `java.net.ConnectException: Connection refused` al intentar el endpoint de chat `127.0.0.1:16337`. Es evidencia de una dependencia de red ausente/rechazada, además de las rutas de canales no implementadas; no se abrió ese servicio.

### Pruebas automatizadas existentes

Se ejecutaron con `PYTHONPATH=server PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s server/tests -p '<archivo>' -v`:

| Archivo | Resultado | Qué permite concluir |
| --- | --- | --- |
| `test_inventory_bags.py` | 3 pruebas, OK | Equipar/quitar bolsos unitarios y preservar propiedad en los casos cubiertos; no reproduce el stack en la interfaz. |
| `test_planting_runtime.py` | 5 pruebas, OK | Plantación, crecimiento local limitado, cancelación y reintento idempotente en BD temporales; no demuestra maduración completa de Cardo. |
| `test_combat_orientation.py` | 3 pruebas, OK | Orientación en turno activo y rechazo de fases no admitidas; el rechazo de colocación es parte del comportamiento actual. |

Los tests de persistencia usan bases temporales y personajes propios del test. No se ejecutó la suite completa. Un resultado OK no implica que los síntomas del usuario estén corregidos.

### Reproducción manual del bolso y causa del mundo negro

El usuario reprodujo manualmente el caso en el cliente de prueba y envió dos capturas. Antes: mundo visible, HUD con 60 PdV, tres slots ocupados de 30, semillas 5/5 y bolso apilado ×3. Después: mundo negro, HUD con 1677, pero los slots y cantidades todavía visibles en `3/30`, 5/5/3. Es una variante de la captura inicial: no exige que el inventario termine en `0/0` para acreditar el fallo.

En el servidor, a las **2026-10-04 06:57:27.017 UTC**, aparece `inventory_bag_rejected` para el personaje 9: `Unavailable or unsupported owned bag item`. En el registro del cliente, a las **01:57:27 UTC−5**, aparecen inmediatamente:

- `Part for active equipment sheet received from world, but BuildSheetSet is not empty`.
- Error al deserializar apariencia para identidad `144115188075855881`, distinta del personaje 9, seguido de `InvalidProtocolBufferException` por mensaje truncado.
- Error de mapa para celda `(-1291844352,0)` y XP inválida `294704301434798083`.
- Excepción al procesar **13713**, `BufferUnderflowException`, por la cadena `chK → big.as → eGj.as → eHd.ew`.
- Error final de carga de mapa.

Se inspeccionó el bytecode del cliente mediante `javap` sin modificar el JAR. Resultado conservado en `.runtime/local/instances/audit-20261004/bag-resync-bytecode.txt`: `cwY.dp` lee i64 de identidad y el resto del payload; `chK` entrega ese resto a `biB.as(byte[])`. La respuesta actual del servidor contiene solo bolsas, mientras esa ruta interpreta una entidad completa. Los campos absurdos y el underflow concuerdan con esa desalineación. No es evidencia de que la vida/XP reales hayan recibido esos valores.

Después del fallo, consultas SQL de solo lectura confirmaron: personaje 9 todavía nivel 1, XP 0, kamas 0; semillas 5/5 y bolso 3; `PRAGMA quick_check=ok`. Se conservó su desplazamiento en (-10, 7, -9). No hubo consumo ni equipamiento exitoso del bolso.

**Solución propuesta, sin implementar:** corregir la ruta de recuperación para enviar el formato completo de entidad exigido por `13713`, o seleccionar un mensaje nativo realmente destinado a sincronizar solo inventario. Debe verificarse el formato exacto y la seguridad de reaplicar secciones a una entidad ya cargada; no basta con anteponer un byte arbitrario o volver a reproducir la captura original. Separadamente, definir split transaccional de una unidad del stack para equipar y conservar las otras dos. Revisar otros rechazos que reutilizan `synchronization`, pues pueden disparar el mismo fallo sin usar un bolso Sadida.

**Pruebas UI restantes:** se abrió la información de Cardo y se confirmó condición de herbolario nivel 0 y cantidades. Los intentos de interacción no lograron iniciar una plantación; un click produjo movimiento. Por tanto, en esta sesión no se validaron consumo visual de semillas, porcentaje ni crecimiento de una plantación nueva. El subagente Luna detuvo sus interacciones al recibir las capturas manuales; no equipó el bolso. El cliente de prueba quedó abierto, sin reiniciarlo tras preservar el fallo.

## Nuevo reporte — E14: consumibles en accesos rápidos

El usuario indica que al asignar semillas, pan u otros consumibles a la barra rápida y cerrar/volver a entrar, el acceso no se guarda. Revisar persistencia y restauración de `SHORTCUT_INVENTORIES`, separadas de la existencia del objeto en inventario. [Carpeta de investigación](../soluciones-wakemu/E14-consumibles-barra-rapida-no-persisten/README.md). Causa pendiente de cotejo nativo y reproducción; no se modificaron servidor ni cliente.

## Aclaración — E13 canales generales y E15 gremios

E13 comprende los canales de chat en general, conforme a la aclaración del usuario. El defecto del decoder y las pruebas específicas de gremio se separan en [E15](../soluciones-wakemu/E15-gremios/README.md), conservando su evidencia. La creación de un gremio y su prueba real siguen pendientes; no se declara funcional por validar solo el formato de mensajes. [E13](../soluciones-wakemu/E13-canales-de-chat/README.md) mantiene la revisión global de canales.


## E19 — Sistema de logros (ampliación del5 de octubre)

La captura muestra definiciones nativas; el servidor actualmente envía `ACHIEVEMENTS` vacío y no contiene almacenamiento/evaluación de logros. Se extrajeron3.278 entradas del catálogo compartido de misiones/logros,6.029 objetivos,5.593 recompensas,396 variables y481 categorías;154 no es el tamaño del catálogo completo.

«Madera de jefe» es4228: seis objetivos y recompensa7936, tipo objeto,16942×1 (Gremialogema). «Entrenado por Gúltar» es3976, objetivo8539; título520 y diez14168. La validación de cinco entrenamientos necesita eventos autoritativos, no cinco solicitudes del cliente.5.021 objetivos carecen de expresiones en sus dos campos de criterio del cliente: falta reconstruir productores/reglas, no asumir éxito ante criterio vacío.

Pruebas offline verificaron el blob versión5, contador49→50, restauración de finalización/seguimiento y compresión zlib. No hubo progreso ni entrega de premios en una partida real. [Cotejo, protocolo, tablas, solución y pruebas de E19](../soluciones-wakemu/E19-logros/README.md). Prioridad8 con progresión/recompensas; no se implementaron cambios de servidor ni de cliente.
