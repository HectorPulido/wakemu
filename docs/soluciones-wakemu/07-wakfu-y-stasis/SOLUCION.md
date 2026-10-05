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
