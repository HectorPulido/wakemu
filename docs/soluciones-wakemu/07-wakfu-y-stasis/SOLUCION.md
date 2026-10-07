# Solución propuesta — 7

Actualizar el estado ecológico personal por acciones válidas con reglas explícitas.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Separar estado personal y población

El contexto ecológico de familias no es la barra personal. Identificar sección/carrier del valor propio y distinguirlo de bonus de área. Anotar antes/después de sembrar y cosechar; no asumir +1 por todas las acciones.

## 2. Definir política ecológica

Determinar signo/magnitud según acción, familia, población y límites. Capturar estado de población antes del commit y versionar fórmula. Si faltan reglas oficiales, ofrecer política configurable pendiente de aprobación, sin presentarla como dato del catálogo.

## 3. Modelar progreso y recibos

Guardar valor personal, límites y revisión; asociar delta al recibo de acción. Semilla/cosecha confirmada y delta deben pertenecer a la misma transición durable. Un tick de crecimiento automático no se atribuye al jugador salvo regla explícita.

## 4. Aplicar y sincronizar

Calcular contra estado autoritativo, limitar valor y enviar actualización nativa al dueño tras commit. Con Redis/SQL diferido usar snapshot y recibo versionados. Bootstrap debe reemplazar la barra con el valor propio, sin datos de otra cuenta capturada.

## 5. Verificar límites y concurrencia

Sembrar/cosechar a ambos lados de la población objetivo, repetir solicitudes y reabrir storage. Dos acciones concurrentes suman según orden versionado sin perder una; comparar valor de BD/journal con barra inmediatamente y al reconectar.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Solo acciones confirmadas alteran progreso una vez; los valores pertenecen al personaje correcto.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.

## Revisión de progresión solicitada por el usuario — 6 de octubre

Problema confirmado: el usuario percibe un salto aproximado90% Stasis→30% Wakfu al talar. SQL acredita varias retiradas consecutivas bajo la política temporal+500, valores−1825→−1325→−825→−325→175→675. Esa política ya fue retirada; no atribuirlo a una única acción comprobada. Aun así, añadir unidades nativas constantes no mantiene una velocidad porcentual intuitiva.

Propuesta concreta para implementar y verificar: guardar afinidad firmada en puntos básicos (−9900..9900);1 punto porcentual=100 unidades. Paso inicialSQL por acción favorable+25 unidades (=0,25 puntos porcentuales), desfavorable−25. Porcentaje visible=abs(afinidad)/100. A−9000, una acción favorable lleva−8975 (89,75% Stasis);20acciones dejan−8500 (85%);360acciones llegan a0; otras20alcanzan500 (5% Wakfu). Paso fijo, transición continua por cero y cap99% en ambos sentidos. La reproducción natural y extracción sin afectar población no alteran afinidad.

El cliente nativo conserva su curva exponencial; el encoder convierte el porcentaje objetivo mediante su inversa, sin editar el cliente: `native=sign(afinidad)*round(-500*log2(1-abs(afinidad)/10000))`. Error de cuantización entero debe medirse y probarse, especialmente cerca de cero. La transformación inversa pertenece solo al protocolo; el dominio/DB manejan puntos básicos. La migración debe preservar el porcentaje visible actual de los personajes, y dejar unidades explícitas en recibos y política; no conservar dos modelos paralelos.

La clasificación de acciones también necesita cotejo: corregir carencia/exceso es favorable; empeorar una desviación es desfavorable. Dentro de la banda debe definirse una recompensa menor o ninguna para evitar progreso ilimitado plantando/cortando el mismo recurso. No afirmar que la fórmula o esos pasos sean oficiales: son diseño del emulador. Estado En revision: propuesta preparada, sin cambiar todavía los valores guardados ni el encoder runtime.

## Feedback informativo del ecosistema

Solicitud del usuario: mostrar en el chat de información si una acción suma o resta afinidad y los datos del ecosistema. Formatter `ecology_feedback.describe` preparado en fuente: población antes→después, banda, clasificación según distancia y delta realmente aplicado (incluye saturación), afinidad antes→después con signo/porcentaje y decimales españoles. Ejemplo: población9→10, equilibrio10–100; mejora el equilibrio:0,25puntos haciaWakfu; afinidad89,75%Stasis→89,50%Stasis. Evitar decir que se ganó Wakfu positivo cuando solo disminuyó Stasis. Caso neutral informa sin cambio; extracción de semillas debe explicar que no retira población. Entrega al dueño de la acción, sin emitir recompensas nuevas ni mensajes repetidos al reproducir recibos. Codec nativo confirmado por bytecode y probe offline: SystemNotification NE, opcode349, subtipo4, i16 longitud de bytes UTF-8 + texto. Este subtipo entrega a GAME_INFORMATION; no confundir con canal4 del chat comunitario. Conectado en fuente a plantación, retirada y extracción sin pérdida de población; nacimiento de monstruos informa únicamente al sembrador conectado. Fallo de arraigo informa que no cambian población ni afinidad. No se envía texto a observadores ni se repite al reproducir operaciones. Pendiente despliegue y aceptación visual.

Implementación nueva de afinidad en fuente: migración034 (conserva porcentaje visible, unidades DB explícitas), dominio en puntos básicos y encoder inverso. Mejora/empeora distancia a banda:±25bps; distancia igual:0. Fallback vegetal mínimo10 únicamente cuando era0, para que reponer un hábitat local vacío tenga objetivo positivo; límites nativos por familia no se cambian. Pendiente gate/despliegue de034, que no se aplicó mientras se prueba Fresno.


Despliegue verificado: imagen `a08ba92cef47a26621d57d5fec5b052db59ec1eaa1faffe830c652909ae1fb20`, world healthy y prefijo SQL034. Gates en imagen sin montar fuente/protocol:75 ecología/INFO;83 posición/Redis/wire/social (9 skips);24 selección con dirección/builds/social. La imagen inicial falló los checks de orientación/catálogo; se reconstruyó coherentemente con código actual y catálogo item-equipment-conditions antes de desplegar. Audiluna conserva el mismo wire675 y revisión32: afinidad DB675 nativa→6077bps (60,77%). Backup previo del DB correcto wakemu_runtime en `.runtime/backups/pre-ecology-034-20261006.dump`. La clasificación ahora mejora distancia=+0,25pp, empeora=−0,25pp, igual=0; no recompensa ciclos dentro de banda. INFO349 entregado tras commit y solo al actor. Aceptación visual pendiente; no se modifica ejecución de hechizos ni se cierra el issue completo por este lote.
