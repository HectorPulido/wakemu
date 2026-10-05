# Solución propuesta — 14

Unir jugadores durante colocación a un encuentro compartido ya existente.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Verificar solicitud y política

Revisar decode_join 13241 y captura de target/equipo; localizar combate por registro compartido, no por variable fight de la conexión. Definir cupos, party-only/abierto, nivel, distancia y autorización del líder.

## 2. Introducir registro compartido

Mapa fight_id→runtime/participantes/leases/fase/revisión. Una sesión referencia el mismo objeto autoritativo; no copiar fights por jugador. Mantener reserva de NPC y pertenencia al mundo consistentes con cleanup 33.

## 3. Reservar entrada y celda

Bajo revisión del encuentro validar placement y capacidad del equipo. Reservar al personaje y celda libre legal, construir actor desde build activa. Carrera ready/start versus join se decide con una versión: nunca entrar después del cierre a medias.

## 4. Sincronizar snapshot y evento

El nuevo participante recibe bootstrap consistente de arena, actores, sheets y fase; los existentes reciben incorporación una vez. Versionar secuencia para que eventos que ocurren durante snapshot no se pierdan ni se envíen dos veces. No reiniciar colocación de todos por cada join.

## 5. Compartir listo, turnos y salida

Ready por participante; start una única vez según reloj/regla. Autorizar actor propio, ACK y turnos compartidos. Abandono parcial, expulsión y desconexión requieren cleanup por participante sin destruir combate de otros; rewards 10/9 según contribución definida.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Todas las sesiones ven un único encuentro; entrar tarde no altera sus actores ni su turno.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
