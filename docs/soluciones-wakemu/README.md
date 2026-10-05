# Auditoría y soluciones de Wakemu

Carpetas para los **35 issues del informe (0–34)** y **18 issues adicionales (E01–E18)**. Cada una separa contexto, cotejo del código, pasos de solución, pruebas y datos pendientes. Trabajo limitado al servidor; las soluciones no están implementadas.

## Documentación por issue

| ID | Problema | Carpeta |
| --- | --- | --- |
| 0 | Retrasos al iniciar combates y lanzar hechizos | [Abrir](00-rendimiento-y-redis/README.md) |
| 1 | Las semillas solo disminuyen al reconectar | [Abrir](01-semillas-sin-refresco/README.md) |
| 2 | Un bebé tofu nunca crece | [Abrir](02-maduracion-de-monstruos/README.md) |
| 3 | Los monstruos no se reproducen ni amplían grupos | [Abrir](03-reproduccion-sin-respawn/README.md) |
| 4 | El porcentaje de plantación mostrado no es real | [Abrir](04-probabilidad-de-plantacion/README.md) |
| 5 | Plantas y árboles (Cardo, fresnos y otros) aparecen como recursos ajenos | [Abrir](05-permisos-y-recoleccion-de-cardo/README.md) |
| 6 | Cardo no llega a su etapa final | [Abrir](06-etapas-completas-de-cardo/README.md) |
| 7 | No sube Wakfu ni Stasis | [Abrir](07-wakfu-y-stasis/README.md) |
| 8 | No aumenta la experiencia de los oficios | [Abrir](08-experiencia-de-oficios/README.md) |
| 9 | No hay experiencia ni subida de nivel por combate | [Abrir](09-experiencia-de-combate/README.md) |
| 10 | No hay drops ni kamas | [Abrir](10-drops-y-kamas/README.md) |
| 11 | No se puede intercambiar con otros personajes | [Abrir](11-intercambio-entre-personajes/README.md) |
| 12 | No se puede pelear contra otros personajes | [Abrir](12-duelos-pvp/README.md) |
| 13 | Mensajes privados y otros canales de chat | [Abrir](13-chat-privado-y-canales/README.md) |
| 14 | No se puede entrar al combate de otra persona | [Abrir](14-unirse-a-combates/README.md) |
| 15 | No hay grupos de jugadores | [Abrir](15-grupos-de-jugadores/README.md) |
| 16 | No se pueden ver los combates | [Abrir](16-espectadores-y-marcadores/README.md) |
| 17 | No se pueden subir características | [Abrir](17-aptitudes-y-calculo-de-estadisticas/README.md) |
| 18 | No se puede elegir hacia dónde mirar en colocación | [Abrir](18-orientacion-en-colocacion/README.md) |
| 19 | Todos los monstruos se mueven a la vez | [Abrir](19-movimiento-aleatorio-eficiente/README.md) |
| 20 | Pocos mobs iniciales, reproducción y pausa sin jugadores | [Abrir](20-poblacion-inicial-y-zonas-activas/README.md) |
| 21 | Tools con configuración `.env` del servidor | [Abrir](21-conexion-remota-y-configuracion/README.md) |
| 22 | Objetos sin identificar | [Abrir](22-identificacion-elementos-y-encantamiento/README.md) |
| 23 | Bolso Sadida apilado rompe la interfaz hasta reiniciar | [Abrir](23-bolso-sadida-apilado/README.md) |
| 24 | Pasaporte de Amakna por defecto | [Abrir](24-nacion-y-pasaporte-neutral/README.md) |
| 25 | Brechas dimensionales | [Abrir](25-brechas-dimensionales/README.md) |
| 26 | No se pueden añadir merkagemas | [Abrir](26-insertar-y-retirar-merkagemas/README.md) |
| 27 | Clima | [Abrir](27-clima-por-zona/README.md) |
| 28 | Bonus de área | [Abrir](28-bonus-de-area/README.md) |
| 29 | Mazmorras | [Abrir](29-mazmorras-e-instancias/README.md) |
| 30 | Mesas de oficio ausentes o inoperantes | [Abrir](30-mesas-de-oficio-y-crafting/README.md) |
| 31 | Configuración repetida de celdas durante colocación | [Abrir](31-diversidad-de-celdas-de-colocacion/README.md) |
| 32 | Permiso `is_admin` para comandos `!` del chat | [Abrir](32-roles-admin-y-comandos/README.md) |
| 33 | Rendirse deja bloqueados nuevos combates y transporte | [Abrir](33-rendicion-y-retorno-al-mundo/README.md) |
| 34 | Builds personalizadas: desbloqueo tardío y hojas no seleccionables — prioridad alta | [Abrir](34-builds-personalizadas/README.md) |
| E01 | Corrupción histórica de SQLite interrumpe crecimiento | [Abrir](E01-corrupcion-sqlite/README.md) |
| E02 | Recuperación de inventario 13713 serializa bolsas como entidad | [Abrir](E02-resincronizacion-inventario-invalida/README.md) |
| E03 | API de pruebas ejecuta antes de autenticar | [Abrir](E03-api-test-sin-autenticacion/README.md) |
| E04 | Activación 13776 sin handler | [Abrir](E04-activar-build-sin-handler/README.md) |
| E05 | Selección no persistida y deck 0 fijo | [Abrir](E05-seleccion-build-y-deck-cero/README.md) |
| E06 | Subida de nivel parcialmente confirmada con hoja fija inválida | [Abrir](E06-nivel-y-hojas-sin-atomicidad/README.md) |
| E07 | Borrado nativo de build sin handler | [Abrir](E07-borrado-de-build-sin-handler/README.md) |
| E08 | Capacidad 24 en interfaz versus índices 0–2 en validación | [Abrir](E08-limite-de-builds-inconsistente/README.md) |
| E09 | Hit Redis conserva lecturas SQL e inicializaciones repetidas | [Abrir](E09-sql-redundante-con-redis/README.md) |
| E10 | Actualización equipment_set no crea entradas nuevas | [Abrir](E10-equipment-set-omite-build-nueva/README.md) |
| E11 | Prueba de desplazamiento sin terreno exportado — reservada a otra sesión | [Abrir](E11-test-desplazamiento-sin-terreno-exportado/README.md) |
| E12 | Curación al alternar aptitudes | [Abrir](E12-curacion-al-alternar-aptitudes/README.md) |
| E19 | Logros, objetivos y recompensas sin motor persistente | [Abrir](E19-logros/README.md) |

## Cómo usar los planes

Leer DIAGNOSTICO y COTEJO antes de SOLUCION. Verificar hashes y reproducir el defecto en almacenamiento aislado; resolver FALTANTES y ejecutar PRUEBAS antes de cerrar. Las propuestas reutilizan piezas existentes, pero no afirman corrección integral de sistemas incompletos.

Priorizar E03/32 antes de exposición remota; E01 antes de ensayos sobre una base sospechosa; E02/23 para recuperación de inventario; E04–E08/E10 junto con 34 para builds; 0/E09 con 19/20 para rendimiento y persistencia. Esta prioridad es técnica y no autoriza despliegues ni reinicios.

[Reglas transversales](TRANSVERSALES.md) · [Validación](VALIDACION.md) · [Identidad de fuentes](manifest.json).

## Respuestas del usuario y alcance actualizado

[Decisiones incorporadas y responsabilidad de investigación](DECISIONES-Y-REVISION.md). Los hechizos quedan reservados a otra sesión. La auditoría continúa: generar carpetas no equivale a terminar el cotejo y las reproducciones.

## Nuevo defecto verificado

[E12 — Curación al alternar aptitudes](E12-curacion-al-alternar-aptitudes/README.md).

## Cobertura exhaustiva en curso

[Seguimiento de todos los issues](seguimiento-todos-los-issues.json). Ninguno se declara terminado por tener una carpeta o un plan. Las respuestas del usuario se conservan; los faltantes técnicos son trabajo de investigación, no decisiones que volver a solicitar. Toda interacción UI se delega a Luna con razonamiento low.

## Hallazgo adicional E13

[E13: canales de chat en general](E13-canales-de-chat/README.md). Alcance corregido por el usuario; el hallazgo específico de gremios se separa en E15.

## Nuevo reporte E14

[E14 — Consumibles en barra rápida no persisten](E14-consumibles-barra-rapida-no-persisten/README.md). Se incorpora a la auditoría como issue abierto. El total actual es 53, incluyendo E15 y E11 reservado a otra sesión.

## Priorización provisional de implementación

Esta clasificación usa el cotejo disponible. **No cierra la auditoría**: esfuerzo es relativo, sin estimaciones de horas; la prioridad final debe revisarse con reproducciones pendientes. No autoriza aplicar fixes.

Los números conservan los bloques de prioridad anteriores: varias filas pueden compartir orden. Los issues antes mencionados fuera de la tabla se incluyen como transversales, por definir o reservados, sin asignarles una prioridad nueva.

| Orden | Issue | Nombre del issue | Impacto y esfuerzo relativo | Dependencias y criterio de avance |
| --- | --- | --- | --- | --- |
| 1 | E03 | [API de pruebas ejecuta antes de autenticar](E03-api-test-sin-autenticacion/README.md) | Alto; acotado frente a sistemas nuevos | Autenticar antes de ejecutar la API; comprobar rechazo sin efectos. Antes de exposición remota. |
| 1 | 32 | [Permiso `is_admin` para comandos `!` del chat](32-roles-admin-y-comandos/README.md) | Alto; acotado frente a sistemas nuevos | Autorizar comandos por is_admin; rechazar acciones sin permisos ni efectos. Antes de exposición remota. |
| 2 | E01 | [Corrupción histórica de SQLite interrumpe crecimiento](E01-corrupcion-sqlite/README.md) | Muy alto en persistencia; migración de esfuerzo alto | Migrar las 27 tablas a PostgreSQL como único backend, sin retrocompatibilidad; validar fuente, UID, transacciones, journals y restauración. Antes de ampliar sistemas persistentes. |
| 2 | E02 | [Recuperación de inventario 13713 serializa bolsas como entidad](E02-resincronizacion-inventario-invalida/README.md) | Muy alto en persistencia; migración de esfuerzo alto | Resincronización nativa válida para inventario y bolsas; cotejar consumidor y recuperación junto con 23. |
| 2 | 23 | [Bolso Sadida apilado rompe la interfaz hasta reiniciar](23-bolso-sadida-apilado/README.md) | Muy alto en persistencia; migración de esfuerzo alto | Rechazar bolsas apiladas sin pérdida; verificar inventario y recuperación junto con E02. |
| 3 | 34 | [Builds personalizadas: desbloqueo tardío y hojas no seleccionables — prioridad alta](34-builds-personalizadas/README.md) | Muy alto para personajes; medio–alto | Resolver desbloqueo, selección y persistencia de builds junto con E04–E08/E10/E12; no modificar hechizos. |
| 3 | E04 | [Activación 13776 sin handler](E04-activar-build-sin-handler/README.md) | Muy alto para personajes; medio–alto | Implementar activación 13776 con validación y actualización coherente de la build activa; coordinar con 34/E05. |
| 3 | E05 | [Selección no persistida y deck 0 fijo](E05-seleccion-build-y-deck-cero/README.md) | Muy alto para personajes; medio–alto | Persistir selección y usar el deck de la build activa; coordinar con 34/E04 sin invadir hechizos de otra sesión. |
| 3 | E06 | [Subida de nivel parcialmente confirmada con hoja fija inválida](E06-nivel-y-hojas-sin-atomicidad/README.md) | Muy alto para personajes; medio–alto | Confirmar nivel y hojas de forma atómica; no publicar Redis antes del commit. |
| 3 | E07 | [Borrado nativo de build sin handler](E07-borrado-de-build-sin-handler/README.md) | Muy alto para personajes; medio–alto | Validar borrado nativo y referencias de la build activa; coordinar con 34/E05. |
| 3 | E08 | [Capacidad 24 en interfaz versus índices 0–2 en validación](E08-limite-de-builds-inconsistente/README.md) | Muy alto para personajes; medio–alto | Unificar capacidad de interfaz y validación de índices; comprobar límites junto con 34. |
| 3 | E10 | [Actualización equipment_set no crea entradas nuevas](E10-equipment-set-omite-build-nueva/README.md) | Muy alto para personajes; medio–alto | Crear entradas nuevas de equipment_set y mantenerlas al activar/reconectar; coordinar con 34. |
| 3 | E12 | [Curación al alternar aptitudes](E12-curacion-al-alternar-aptitudes/README.md) | Muy alto para personajes; medio–alto | Evitar curación al alternar aptitudes; mantener coherencia de HP, nivel, hojas y equipo. |
| 3 | 17 | [No se pueden subir características](17-aptitudes-y-calculo-de-estadisticas/README.md) | Muy alto para personajes; medio–alto | Persistir aptitudes y recalcular estadísticas de forma atómica con nivel, build, equipo y HP. |
| 4 | E14 | [Consumibles en barra rápida no persisten](E14-consumibles-barra-rapida-no-persisten/README.md) | Mejoras visibles de alcance relativamente acotado | Handler, persistencia y bootstrap de barra WORLD; confirmar asignación GUI y restauración al reconectar. |
| 4 | 1 | [Las semillas solo disminuyen al reconectar](01-semillas-sin-refresco/README.md) | Mejoras visibles de alcance relativamente acotado | Acreditar cantidad visual inmediata tras consumo. El cooldown de extracción requiere validación independiente y configuración en DB. |
| 4 | 18 | [No se puede elegir hacia dónde mirar en colocación](18-orientacion-en-colocacion/README.md) | Mejoras visibles de alcance relativamente acotado | Validar orientación por fase y actor, y confirmar sincronización durante colocación. |
| 4 | E17 | [Monturas equipadas que no permiten montarse](E17-monturas-y-dragopavos/README.md) | Mejoras visibles de alcance relativamente acotado | Desbloqueo por defecto sin misión, PET/item persistidos y handlers de montar/desmontar; alimentación y ciclo completo amplían alcance. |
| 5 | 0 | [Retrasos al iniciar combates y lanzar hechizos](00-rendimiento-y-redis/README.md) | Alto en rendimiento; medio–alto | Medir SQL/Redis, locks, serialización y latencia real; retirar trabajo redundante del camino caliente. Hechizos reservados. |
| 5 | E09 | [Hit Redis conserva lecturas SQL e inicializaciones repetidas](E09-sql-redundante-con-redis/README.md) | Alto en rendimiento; medio–alto | Lectura Redis primero y eliminación de SQL/inicializaciones redundantes; diferenciar ausencia de caché de fallo con mutaciones pendientes. |
| 5 | 19 | [Todos los monstruos se mueven a la vez](19-movimiento-aleatorio-eficiente/README.md) | Alto en rendimiento; medio–alto | Movimiento aleatorio con adyacencias indexadas, sin cálculo/envío bajo bloqueo global; intervalo y probabilidad en DB. |
| 5 | 20 | [Pocos mobs iniciales, reproducción y pausa sin jugadores](20-poblacion-inicial-y-zonas-activas/README.md) | Alto en rendimiento; medio–alto | Presencia por zona, población inicial y pausa sin jugadores; temporizadores y probabilidades en DB antes de aumentar población. |
| 6 | E18 | [Motor de IA táctica de enemigos](E18-ia-tactica-enemigos/README.md) | Muy alto para PvE; alto, entregable por etapas | Autoridad NPC y preview del motor común; luego ranking, secuencias, espalda, alturas y coordinación. Depende de 0 y validación multijugador 14/15; antes de certificar dificultad 29/25. |
| 7 | 5 | [Plantas y árboles (Cardo, fresnos y otros) aparecen como recursos ajenos](05-permisos-y-recoleccion-de-cardo/README.md) | Alto en ecosistema; alto | Validar propiedad y permisos para todas las plantas/árboles; incluir cooldown persistente y recolección autoritativa. |
| 7 | 6 | [Cardo no llega a su etapa final](06-etapas-completas-de-cardo/README.md) | Alto en ecosistema; alto | Cotejar etapas finales y transiciones para todas las plantas/árboles, con persistencia y crecimiento autoritativo. |
| 7 | 2 | [Un bebé tofu nunca crece](02-maduracion-de-monstruos/README.md) | Alto en ecosistema; alto | Definir maduración y transiciones de referencia/edad de monstruos; coordinar con 3/20. |
| 7 | 3 | [Los monstruos no se reproducen ni amplían grupos](03-reproduccion-sin-respawn/README.md) | Alto en ecosistema; alto | Reproducción persistente y límites por zona; coordinar con crecimiento, población y pausa sin jugadores. |
| 7 | 4 | [El porcentaje de plantación mostrado no es real](04-probabilidad-de-plantacion/README.md) | Alto en ecosistema; alto | Calcular probabilidades con conteos autoritativos y condiciones de zona; cotejar porcentaje anunciado y resultado. |
| 7 | 7 | [No sube Wakfu ni Stasis](07-wakfu-y-stasis/README.md) | Alto en ecosistema; alto | Actualizar Wakfu/Stasis desde acciones del ecosistema confirmadas y persistir el resultado. |
| 7 | 28 | [Bonus de área](28-bonus-de-area/README.md) | Alto en ecosistema; alto | Aplicar bonus desde estado autoritativo del ecosistema y condiciones de zona; depende de conteos y reglas de población. |
| 8 | 8 | [No aumenta la experiencia de los oficios](08-experiencia-de-oficios/README.md) | Alto para progresión/economía; alto | Alcance correcto de XP de oficio y persistencia; integrar acciones, recetas y estaciones con 30. |
| 8 | 30 | [Mesas de oficio ausentes o inoperantes](30-mesas-de-oficio-y-crafting/README.md) | Alto para progresión/economía; alto | Fuentes de estaciones/mesas, recetas y acceso; validar fabricación y XP junto con 8. |
| 8 | 9 | [No hay experiencia ni subida de nivel por combate](09-experiencia-de-combate/README.md) | Alto para progresión/economía; alto | Recompensas durables y subida de nivel atómica. Verificar XP positiva y reconexión; el cero de la captura coincide con el umbral de nivel. |
| 8 | 10 | [No hay drops ni kamas](10-drops-y-kamas/README.md) | Alto para progresión/economía; alto | Loot por jugador, fórmula y resumen/inventario nativos; recibos durables para evitar premios duplicados tras reinicio. |
| 8 | E19 | [Logros, objetivos y recompensas sin motor persistente](E19-logros/README.md) | Alto para progresión/economía; alto | Importar catálogo, formalizar eventos y dependencias, persistir objetivos/ciclos y conceder premios una sola vez. Depende de E01; logro 4228 entrega Gremialogema antes del flujo E15. |
| 9 | 13 | [Mensajes privados y otros canales de chat](13-chat-privado-y-canales/README.md) | Alto para multijugador; alto | General funciona en prueba manual; validar privados y cada canal, permisos, routing y recepción real. |
| 9 | E13 | [Canales de chat en general](E13-canales-de-chat/README.md) | Alto para multijugador; alto | Auditar todos los canales con autorización y routing; coordinar con 13. El sistema completo de gremios corresponde a E15. |
| 9 | 15 | [No hay grupos de jugadores](15-grupos-de-jugadores/README.md) | Alto para multijugador; alto | Party persistente/coherente y membresía compartida; precede joins, espectadores e instancias. |
| 9 | 14 | [No se puede entrar al combate de otra persona](14-unirse-a-combates/README.md) | Alto para multijugador; alto | Registro compartido de combate y permisos de entrada; depende de 15 y ciclo de combate, incluidos 31/33. |
| 9 | 16 | [No se pueden ver los combates](16-espectadores-y-marcadores/README.md) | Alto para multijugador; alto | Registro compartido y publicación para espectadores; coordinar con 14/15 y retorno al mundo. |
| 9 | 12 | [No se puede pelear contra otros personajes](12-duelos-pvp/README.md) | Alto para multijugador; alto | Duelos con autorización y ciclo completo, sin premios; verificar retorno al mundo y varios personajes. |
| 9 | 11 | [No se puede intercambiar con otros personajes](11-intercambio-entre-personajes/README.md) | Alto para multijugador; alto | Confirmación bilateral y transferencia atómica de propiedad/cantidades; recuperación sin duplicaciones. |
| 10 | 22 | [Objetos sin identificar](22-identificacion-elementos-y-encantamiento/README.md) | Variable; medio–alto | Identificación, elementos y encantamiento con contratos propios; persistir resultados sin volver a sortear al reconectar. |
| 10 | 26 | [No se pueden añadir merkagemas](26-insertar-y-retirar-merkagemas/README.md) | Variable; medio–alto | Inserción y retirada de merkagemas con validación y persistencia del merkasaco. |
| 10 | 24 | [Pasaporte de Amakna por defecto](24-nacion-y-pasaporte-neutral/README.md) | Variable; medio–alto | Contrato de nación/pasaporte y estado inicial coherente; no extrapolar éxito de un paquete al sistema completo. |
| 10 | 27 | [Clima](27-clima-por-zona/README.md) | Variable; medio–alto | Estado de clima por zona, actualización y forecast coherentes, con reglas configurables. |
| 11 | 29 | [Mazmorras](29-mazmorras-e-instancias/README.md) | Alto; estructural | Acreditar población por sala; party, sesiones, avance tras victoria/derrota, dificultad y premios. Depende de persistencia y ciclo de combate. |
| 11 | 25 | [Brechas dimensionales](25-brechas-dimensionales/README.md) | Alto; estructural | Ciclos/oleadas y recompensas propios; validar instancias y dificultad con IA básica disponible. |
| 11 | E15 | [Sistema completo de gremios](E15-gremios/README.md) | Alto; estructural | Creación, membresía, permisos y durabilidad reales; depende de E01, social y flujo de Gremialogema de E19. |
| Transversal | 21 | [Tools con configuración `.env` del servidor](21-conexion-remota-y-configuracion/README.md) | Sin clasificación individual previa | Infraestructura: separar host, puertos y secretos de reglas en DB; alcance exclusivo del servidor. |
| Transversal | 31 | [Configuración repetida de celdas durante colocación](31-diversidad-de-celdas-de-colocacion/README.md) | Sin clasificación individual previa | Revisar diversidad de colocación junto al ciclo de combate, antes de certificar joins o instancias. |
| Transversal | 33 | [Rendirse deja bloqueados nuevos combates y transporte](33-rendicion-y-retorno-al-mundo/README.md) | Sin clasificación individual previa | Garantizar retorno tras rendición y desbloqueo de combate/transporte antes de certificar joins o instancias. |
| Por definir | E16 | [Monstruos con nombre «Grupo local»](E16-nombres-genericos-monstruos/README.md) | Sin clasificación individual previa | Cotejar nombres individuales y fallback nativo, variantes e idiomas; no depende de reproducción ni mazmorras. |
| Reservado | E11 | [Prueba de desplazamiento sin terreno exportado — reservada a otra sesión](E11-test-desplazamiento-sin-terreno-exportado/README.md) | Fuera de esta sesión | Reservado a otra sesión; no ejecutar ni modificar pruebas de hechizos/desplazamiento en este alcance. |

### Incorporación de las últimas revisiones

- **PostgreSQL — prioridad 2, antes de nuevos sistemas persistentes.** La revisión ya inventaría las 27 tablas y los cambios de SQL, tipos, claves, secuencias y transacciones. La implementación debe usar PostgreSQL como único backend; conservar una exportación puntual de SQLite para el corte no implica mantener compatibilidad. Criterio de aceptación: importación cotejada, UID sin colisiones, recompensas idempotentes, journals reconciliados y recuperación desde backup probada. [Comparación y recomendación](E01-corrupcion-sqlite/SQLITE-VS-POSTGRESQL.md) · [Migración tabla por tabla](E01-corrupcion-sqlite/MIGRACION-POSTGRESQL-TABLAS.md).
- **XP visible — validación dentro de prioridad 8, sin fix para la captura aportada.** Los 59.929.868.921 XP persistidos coinciden con el inicio del nivel 200; el cálculo nativo muestra cero dentro del nivel. Con 123 XP adicionales devuelve 123. Sigue pendiente verificar el recorrido de una recompensa real, paquete y reconexión; también cotejar el límite 200 del servidor frente al 246 declarado por la curva nativa antes de ampliar niveles. Esta explicación no cierra el issue de XP por combate. [Diagnóstico y evidencia](09-experiencia-de-combate/XP-CERO-EN-VENTANA.md).

**33 y 31** deben revisarse junto al ciclo de combate antes de certificar joins o instancias: retorno tras rendición y diversidad de colocación no quedan cubiertos por desbloquear una puerta. **21** es configuración de infraestructura/conexión del servidor; separar host/puertos/secretos de parámetros de reglas en DB. [Parámetros del servidor](PARAMETROS-SERVIDOR-EN-DB.md).


## E15 — Sistema completo de gremios

[E15: creación, persistencia y funcionamiento de gremios](E15-gremios/README.md). Evidencia offline preservada; creación y prueba con un gremio real pendientes. El inventario actual tiene **54 issues**, incluido E11 reservado a otra sesión.


## E16 — Nombres genéricos de monstruos

[E16: «Grupo local» enviado como nombre individual](E16-nombres-genericos-monstruos/README.md). Causa reproducida en serialización del servidor; consumidor/fallback y variantes visuales pendientes. Cambio potencialmente acotado tras ese cotejo; no requiere resolver reproducción ni mazmorras.

## E17 — Monturas y dragopavos

[E17: equipo válido sin estado de montura ni handlers](E17-monturas-y-dragopavos/README.md). Desbloqueo por defecto sin misión solicitado por el usuario. Prioridad 4 para montar/desmontar y restauración básica; alimentación, cosméticos y validación temporal forman parte del alcance completo. El inventario suma **54 issues**.

## E18 — IA táctica de enemigos

[E18: clasificación de hechizos, planes, espalda/elevaciones y coordinación](E18-ia-tactica-enemigos/README.md). Reutiliza la arquitectura de Dofus sin Laya mediante adaptadores Wakfu. **Prioridad 6: después de estabilizar la ejecución NPC del motor común de hechizos**, antes de certificar dificultad de mazmorras; implementar primero decisiones deterministas y luego coordinación. Alto impacto PvE, esfuerzo alto. El catálogo de habilidades existe; no implica soporte completo del motor. Total: **54 issues**.


## E19 — Sistema de logros

[E19: catálogo, progreso, recompensas y restauración del diario](E19-logros/README.md). El catálogo compartido contiene3.278 definiciones,6.029 objetivos y5.593 recompensas; el servidor envía un estado vacío. Consumidor nativo probado offline, incluyendo contador, finalización y seguimiento. **Prioridad8**, junto con progresión/recompensas; depende de E01 para durabilidad y alimenta E15 por la Gremialogema del logro4228. Reglas de escenarios y validación en partida siguen abiertas. Total: **54 issues**.
