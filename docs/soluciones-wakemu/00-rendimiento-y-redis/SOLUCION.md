# Solución propuesta — 0

Reducir retrasos reales de entrada, inicio y hechizos; cumplir Redis primero y flush a 20 minutos sin pérdida de autoridad.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Medir la latencia completa

Relacionar clic y frame recibido con boot/conexión/combate/acción. Añadir en una futura implementación tiempos monotónicos de cola, recepción, lease, espera/posesión de locks, arena, preparación, commit, checkpoint y envío. El elapsed actual empieza tarde y termina antes de parte del cierre: no usarlo como latencia total ni sumar cifras de ensayos distintos.

## 2. Reducir coste por grupo

Construir una vez el índice origen→vecinos por versión de mapa. Obtener posiciones/ocupación/versiones bajo lock, calcular fuera y confirmar mediante comparación de versión. Recoger mensajes bajo lock y enviar después; si el grupo entra en combate/recolección durante cálculo, desechar el plan. Probar con 1/16/32 grupos cercanos y zonas vacías.

## 3. Separar geometría de transacciones

Mantener terreno inmutable compartido e identificador de versión en el encuentro. Copiar solo actores, efectos, recursos y secuencias mutables; conservar las comprobaciones de obsolescencia. Cachear validación de geometría, no reducir radio para ocultar el problema. Comparar p 50/p 95/p 99 de primer cast y casts calientes preservando exactamente los resultados.

## 4. Diseñar lectura Redis primero por dominio

Catalogar cada lectura SQL del camino caliente. Cachear catálogos y snapshots versionados; ante clave ausente hidratar de SQL y reutilizar dentro de la solicitud. No confundir ausencia con error Redis: si hay journal pendiente, fallback SQL puede resucitar objetos. Sacar CREATE/INSERT de inicialización del camino de carga mediante migraciones separadas.

## 5. Persistir con garantías antes del ACK

Definir autoridad y revisión para inventario, wallets, salud, builds y mundo; inventario no se resuelve copiando un JSON por personaje. Consumir/conceder/transferir UID y cantidad junto con recibo idempotente en una operación durable. Redis debe confirmar durabilidad real antes de aceptar; AOF declarado no prueba configuración efectiva ni seguridad frente a caída del host.

## 6. Implementar flush de 1.200 segundos

Planificar lotes por revisión, baseline SQL y recibo. Confirmar SQL y limpiar Redis solo si sigue la revisión que se guardó; una revisión posterior permanece pendiente. Recuperar caída entre commit y limpieza sin reaplicar concesións. Definir barreras para operaciones de valor y semántica de salud/leases, actualmente inmediatas; no cambiar todos los intervalos ciegamente.

## 7. Aislar persistencia y sockets lentos

Eliminar checkpoints idénticos, usar escritor ordenado por encuentro con barreras de durabilidad y colas de salida acotadas por conexión. Decidir qué datos deben estar durables antes de respuesta. Un receptor saturado no debe retener WORLD.lock ni congelar otros jugadores. Mantener orden de eventos/ACK y recuperar desconexión.

## 8. Aceptar por carga y corrección

Comparar mediciones con misma versión/catálogo/fixtures, carga concurrente y tamaños de estado. Registrar CPU, SQL por operación, Redis hits/misses, bytes, cola y percentiles. Ejecutar fallos de recuperación en entorno propio autorizado; optimización que pierde recompensa, duplica objeto o rompe validación se rechaza aunque reduzca latencia.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Una solicitud de valor se aplica una vez; ninguna revisión nueva se borra por un flush antiguo; optimizar no cambia geometría legal, daños, orden de acciones o autoridad.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.

## Evidencia adicional ejecutada

[Cotejo posterior a las respuestas del usuario](REVISION-RESPUESTAS.md).
