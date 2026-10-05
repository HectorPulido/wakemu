# Solución propuesta — 27

Simular clima consistente por zona y sincronizarlo con crecimiento y probabilidad.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Identificar carriers y reglas

Capturar clima visual/contexto al entrar y cambiar condición. Determinar IDs/escala de temperatura, lluvia, viento, estaciones y áreas afectadas. weather.enabled=false y callback no permitido son hechos; activar flag no construye un modelo ni prueba la fórmula.

## 2. Modelar zona y tiempo

Persistir estado climático, revisión, seed/transición y calendario. Acordar reloj global o activo y cómo afecta a zonas vacías 20; separar presentación de clima y simulación ecológica. Un cambio de día/huso horario no debe ejecutar dos transiciones iguales.

## 3. Implementar scheduler seguro

Registrar tarea de clima explícita y autorizada, con lease/event_id/retry. Generar nuevo estado una vez por intervalo según catálogo, no un draw independiente por jugador. Definir límites y cambios abruptos/interpolación solo si hay evidencia.

## 4. Aplicar a sistemas consumidores

Plantación 4 y crecimiento 6 leen el mismo climate_revision y la política de snapshot por acción. Bonus 28 y oficios no reciben modificadores inventados. Cachear contexto por zona/version para no repetir cálculo por entidad cada tick.

## 5. Publicar y recuperar

Bootstrap de recién llegado y update a presentes llevan el mismo estado nativo. Repetir cron no emite nuevo cambio ni altera seed. Recovery conserva siguiente transición y no resetea estaciones por restart.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Clima de una zona es compartido, versionado y no recalculado por jugador.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
