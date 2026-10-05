# Solución propuesta — 25

Implementar acceso, instancia, oleadas/objetivos y cierre de brechas con progreso y rewards fiables.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Identificar brecha concreta

Obtener mapa/objeto/action del acceso y una sesión con secuencia completa. No inferir función por teleporter. Reunir nivel, cupo, duración, oleadas y objetivos verificables; los números de mecánicas no se conocen aún y quedan bloqueados por evidencia.

## 2. Definir catálogo y estado de instancia

Modelo propuesto rift_id/instance_id, participantes, estado, seed, progreso, clock y origen/salida. Definición versionada contiene grupos/objetivos y rewards. Reusar service de instancias 29 y combates 14; no introducir dos sistemas incompatibles.

## 3. Autorizar entrada compartida

Verificar requisitos, party/cupo y leases; reservar grupo/instancia juntos. Mover jugadores a destino real con bootstrap de mundo. Desconexión entre reservar y entrar debe recuperar/cancelar, no generar otra instancia con el mismo recibo.

## 4. Ejecutar oleadas por transición

Spawn de grupos según seed/oleada/objetivo con idempotencia. Victoria confirmada actualiza progreso y programa siguiente; abandono/derrota no avanza salvo regla acreditada. Reloj, pausa sin jugadores y máximo activo deben ser explícitos, sin usar respawn global para representar oleadas.

## 5. Cerrar y repartir una vez

Al cumplir/fallar objetivo fijar estado terminal, rewards por participante y salida. Usar recibos de 9/10 y liberar grupos/presencia/subscriptions. Reconectar a instancia cerrada vuelve a salida segura conservando premio; nunca repetir todo el loot al cargar.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Oleada/objetivo cambia una vez por evento; todos ven misma instancia y cierre terminal.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
