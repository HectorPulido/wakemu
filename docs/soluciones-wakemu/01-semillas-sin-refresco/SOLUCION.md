# Solución propuesta — 1

Consumir exactamente una semilla por plantación aplicada y mostrar la cantidad correcta sin reconectar.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Preparar una réplica identificable

Crear personaje propio con una semilla unitária y otro stack de cinco; anotar UID, referencia, cantidad, mapa/celda y revisión. Capturar inicio/completado y consultar estado de la copia de BD, sin reutilizar el personaje del usuario. El intento gráfico anterior solo movió al actor y no acredita plantación.

## 2. Delimitar consumo y presentación

Seguir complete y la ruta 13429: la transacción SQL descuenta y devuelve creación 13135/resultados 12954. Correlacionar por UID las cantidades antes/después y paquetes; separar persistencia correcta de una interfaz que conserva el stack. Decodificar el resultado mediante el lector nativo y comprobar sus prefijos antes de prescribir un delta.

## 3. Resolver un contrato único de consumo

El consumidor nativo `cgN.a(cAZ)` ya acredita que12954 llama `dev.getItem()` y `bJt.d(item,1)` tanto en éxito como fallo. **No acompañar el resultado con12470 para la misma resta:** produciría consumo doble. Revisar que el resultado llegue cuando el modo `dev` conserva la semilla activa, y correlacionar cantidad SQL/visual. Cancelación no debe recibir un resultado que reste; failure consume una sin XP y success consume una con XP, según respuesta del usuario.

## 4. Confirmar recurso y semilla juntos

Validar lease, pertenencia, cantidad, celda ocupada, distancia y reserva; atomizar consumo, recurso creado y recibo de operación. Reintento del mismo completado devuelve el resultado previo, sin nuevo recurso ni consumo. Con Redis pendiente, validar revisión y no leer cantidad SQL vieja.

## 5. Publicar después de confirmar

Enviar resultado/delta propio e informar creación a peers del mapa en orden probado. Una desconexión posterior al commit no revierte el recurso ni repite la resta al reconectar. La recuperación publica desde un outbox/recibo durable y evita mensajes que pretendan sincronizar inventario usando un codec de entidad incompleto.

## 6. Verificar todas las vistas

Comparar cantidad visual, hoja de equipo si aplica, estado propio y reconexión. Probar agotamiento del último ítem y UID retirado; no mantener stack de cantidad cero. Repetir con segunda cuenta mirando para comprobar que solo el dueño recibe el decremento de su inventario.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

cantidad_antes = cantidad_después + consumo_confirmado; nunca dos consumos por un resultado repetido.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.


## Cooldown de extracción: integración acreditada

El dispatcher **13481** pasa explícitamente `cooldown_seconds=0`, aunque `Harvests.complete` ya consulta `MAX(completed_at)` por `(monster_id, action_id)`. Con cero, la comparación no impone espera entre extracciones exitosas. La consulta y el premio están en `BEGIN IMMEDIATE`, junto con el recibo: conservar esa atomicidad en la solución.

Cargar cantidad y cooldown desde reglas versionadas en DB por referencia/acción y guardar la revisión efectiva en el ticket. La duración de animación (`duration_ms`) es un concepto separado del cooldown; no usarla como tasa oficial. Validar al empezar para evitar animar una acción que ya está bloqueada y volver a validar al completar para cubrir carreras entre sesiones/procesos. No basta con el lock Python, limitado a una instancia.

La clave actual es global por ID de monstruo/acción, compartida entre personajes. Acreditar alcance de regla antes de añadir personaje/cuenta a la clave. Para IDs reutilizados tras reinicio/respawn, definir identidad duradera de entidad o incluir zona/instancia y generación de spawn; no heredar ni perder accidentalmente cooldown al reciclar IDs. El recibo actual no guarda mapa/instancia/revisión. Mantener separación entre recibo idempotente de operación y estado consultable de cooldown para poder retener/depurar historial sin reabrir la extracción.

Cancelar, fallar por inventario lleno o recibir callback prematuro no debe conceder semillas ni consumir cooldown de éxito salvo regla acreditada. Emitir rechazo y liberar ocupación coherentemente. Probar última plaza, dos personajes sobre el mismo objetivo, dos procesos, reinicio y cambio de regla durante la acción. [Cotejo actual y hashes](probe-cotejo-cooldown-actual.json). No se fija una duración arbitraria ni se implementan cambios.


## Coste de consulta de cooldown cotejado

El schema de recibos define solo la PK `token`; la consulta por monstruo/acción no tiene índice compuesto en el módulo. Se ejecutó `EXPLAIN QUERY PLAN` y `EXPLAIN` sobre SQLite aislado con ese schema: el plan actual no usa índice para ese filtro y la VM recorre mediante `Rewind/Next`. Un índice candidato `(monster_id,action_id,completed_at)` genera búsqueda con índice cubriente por ambas claves. Es prueba del plan, **no benchmark ni migración aplicada**.

Si se conserva la consulta sobre historial, incluir ese acceso en la migración y medir coste con volumen representativo. Si se separa estado actual de cooldown, usar PK de identidad duradera/acción y actualizarla en la misma transacción del recibo/premio; no depender de que todo el historial permanezca indefinidamente. El diseño definitivo de clave depende de alcance/identidad de spawn acreditados. [Planes ejecutados](probe-plan-consulta-cooldown.json). Esta dependencia también afecta 0/E09.
