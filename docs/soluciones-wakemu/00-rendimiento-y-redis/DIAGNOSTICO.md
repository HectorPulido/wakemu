# Diagnóstico — 0

## Contexto registrado

**Alcance actualizado:** las mejoras solicitadas son exclusivamente del servidor. El cliente sirve como instrumento de reproducción; no se proponen modificaciones de cliente, interfaz ni herramientas. Las propuestas anteriores de cliente quedan fuera del alcance de implementación.

**Confirmado por mediciones aisladas:** el movimiento recalcula y recorre las 125.989 aristas del mapa 1134 para cada grupo cercano. Simular 16 grupos costó 1,94 s y 32 grupos 3,83 s, sin Redis ni red. El worker conserva bloqueos compartidos de grupos y recolección mientras calcula y publica; comenzar un combate puede esperar esos bloqueos. El coste CPU también puede competir con otros hilos del servidor.

**Confirmado en combate:** las transacciones copian y serializan la geometría completa repetidamente. En una prueba controlada de dos actores, el terreno de radio 89 produjo un estado de 844.397 bytes. Preparar y confirmar un hechizo caliente costó unos 299 ms, frente a 21 ms con radio 12. Es una comparación diagnóstica, no una recomendación de reducir arbitrariamente el terreno: el serializador de estadísticas fue sustituido por uno vacío y se excluyeron persistencia y red. También hay checkpoints síncronos completos en el camino de solicitudes.

**Límite de evidencia:** diez lanzamientos recientes en los registros tardaron aproximadamente 374–4.037 ms entre recepción y publicación; la entrada al mundo alcanzó 7,77 s. No se reprodujo todavía el retraso completo de 20 s. La traza actual empieza después de leer el paquete y omite parte de su propio cierre; no mide toda la espera. El intento gráfico con el personaje nuevo Audit Tempo fue interrumpido por una desconexión de paro programado del servidor, anterior al clic registrado.

**Posibles soluciones del servidor:** indexar adyacencias y ocupación; calcular movimiento fuera del bloqueo y aplicar con comprobación de versión; separar geometría inmutable del estado mutable de combate; mantener validación transaccional mediante versiones; guardar checkpoints solo ante cambios y diseñar persistencia ordenada con garantías de recuperación; evitar enviar a sockets bajo bloqueos globales. Aplicar la política solicitada de zona activa, intervalo de 5 s, 25% de probabilidad y pasos aleatorios sin convertirla en sustituto de las optimizaciones estructurales.

**Validación necesaria:** medir cola de recepción, espera de locks, cálculo, estadísticas, checkpoint y envío por solicitud; comparar p50/p95/p99 con 1/16/32 grupos, varios combates y un receptor lento. Conservar integridad, recuperación y orden de acciones. Investigación y límites completos: [auditoría de rendimiento del servidor](../../reports/auditoria-rendimiento-server-wakemu-2026-10-04.md). No se aplicó ninguna corrección.

EXTRA: Revisar tambien las llamadas a la base de datos, deberian ser pocas, la mayoria de llamadas deben ir a redis primero y 20 minutos despues actualizar
y en caso que redis no tenga la respuesta ahi si pedir a la base de datos. pero tener cuidado con duplicaciones de objetos, etc.

**Ampliación verificada del requisito Redis/20 minutos:** el diseño actual usa Redis como journal de ciertos dominios, no como caché completa previa a SQLite. `Store.character` consulta primero personaje, progresión, merkasaco, contenedores, objetos y builds SQL; luego `BuildJournal.overlay` sustituye las hojas pendientes. Por eso un hit Redis todavía consulta SQLite. Una fixture temporal con traza SQL registró **9 SELECT, 3 INSERT de inicialización idempotente y 7 CREATE IF NOT EXISTS** por carga con hit, repetidos tres veces; las inserciones no significan tres objetos creados ni duplicación. Fueron cargas inferiores a 1 ms en esa fixture; el número de consultas demuestra el diseño, no la causa de un retraso de 20 s.

El journal de builds difiere sus filas hasta **1.200 s**, comprobado con reloj simulado: a 1.199 s no escribió; a 1.200 s confirmó una fila y conservó la hoja. El guardado todavía hizo **20 SELECT y 2 UPDATE** SQL: la lease y salud siguen siendo dominios inmediatos. Cron configura builds/grupos a 1.200 s y posiciones a 2 s. No basta con cambiar un intervalo global para cumplir el requisito.

**Propuesta concreta:** separar catálogos inmutables, estado del personaje y transacciones de propiedad. Leer snapshots versionados de Redis primero y cargar desde SQL ante ausencia real, con hidratación única por solicitud; retirar DDL/inicialización del camino caliente mediante migraciones. Para inventario, identificación, reciclaje e intercambios, registrar atómicamente UID, cantidades, propiedades, revisión y recibo idempotente antes del ACK. No usar SQL antiguo como fallback si Redis falla teniendo mutaciones pendientes: `StateJournal` ya falla explícitamente en ese caso para evitar resucitar objetos consumidos. Diferenciar ausencia de clave de indisponibilidad/corrupción de Redis.

**Garantías y pruebas:** flush por revisión con comparación de baseline y limpieza condicional; si llega una edición durante el flush debe sobrevivir. Recuperar sin duplicar concesións/recompensas ni volver a sortear elementos/engastes. La configuración Compose declara AOF con `appendfsync always`; se debe verificar la configuración del Redis realmente cargado antes de afirmar durabilidad. Se reejecutaron tests de journal de sesión reemplazada, caída Redis, conflicto SQL y revisión nueva durante checkpoint. El experimento usa MemoryRedis, no acredita rendimiento de red, caída del host ni pérdida de AOF. Detalles adicionales y artefactos en el informe de rendimiento.

## Lectura actual

Carga tablas SQL antes de llamar a build_journal.overlay. La propuesta Redis primero exige cambiar la ruta de lectura; aumentar el intervalo de flush no basta.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Latencia objetivo de p 95/p 99 y carga esperada (jugadores, combates, grupos).
- Medición completa que reproduzca los 20 s reportados; las muestras parciales no la sustituyen.
- Qué dominios deben diferirse exactamente 20 minutos y qué barreras inmediatas deben mantenerse.
- Configuración Redis cargada, garantía AOF/replicación y política ante pérdida del host.

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
