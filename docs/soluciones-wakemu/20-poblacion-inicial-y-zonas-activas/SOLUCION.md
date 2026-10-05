# Solución propuesta — 20

Sembrar población inicial pequeña una sola vez y pausar simulación sin jugadores.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Definir zona y presencia

Elegir clave mapa/instancia/subzona y qué cuenta como jugador presente, evitando crear presencia por spectator/desconectado. Registrar transiciones 0→1 y 1→0 con revisión. Movimiento actual filtra ubicaciones, pero crecimiento y respawn no acreditan pausa común.

## 2. Crear bootstrap idempotente

Configurar familias y pequeña cantidad inicial por zona y versión de población. Guardar marcador seeded más UIDs/celdas en una transición; entrar de nuevo o reiniciar no vuelve a sembrar. Acordar si zona totalmente exterminada se mantiene vacía hasta siembra/reproducción.

## 3. Unificar reloj activo

Guardar tiempo activo acumulado/remaining de crecimiento, maduración y reproducción. Al último jugador salir, pausar y quitar tareas del índice activo. Por el requisito no simular ni reproducir en ausencia; no catch-up masivo al regresar salvo decisión explícita diferente.

## 4. Activar de manera eficiente

Primer jugador reactiva deadlines relativas al reloj activo. Elegir candidatos y límites de capacidad; validar ocupación antes de bootstrap. Compartir scheduler con 19 para no recorrer todas las zonas vacías cada 5 s.

## 5. Integrar combate y siembra

Grupos reservados no simulan aunque haya jugadores. Semillas confirmadas persisten cuando su plantador sale; su crecimiento usa reloj zonal elegido. Retirar respawn incompatible con 3 y preservar reservas/recibos en journal.

## 6. Recuperar presencia y mundo

Presencia se reconstruye de sesiones válidas, no de un contador antiguo tras caída. Reabrir datos de seeded/población/timers sin duplicar grupos; no requerir que el usuario borre la BD para activar una zona correctamente.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Seeding una vez por zona/version; estado vacío no se rellena implícitamente al entrar.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
