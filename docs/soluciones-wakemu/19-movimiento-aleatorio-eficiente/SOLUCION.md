# Solución propuesta — 19

Evaluar grupos cada 5 segundos con 25% independiente de moverse y varios pasos legales aleatorios solo donde hay jugadores.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Precisar unidad y rango

Aplicar la oportunidad al grupo NPC (miembros coordinados), no a cada miembro para separarlo. El usuario fija 5 s/25%; queda pendiente rango de pasos y distribución. Definir proximidad/zonas activas, duración de ruta y si evaluaciones se escalonan manteniendo 5 s por grupo.

## 2. Indexar geometría y ocupación

Reutilizar mapa origen→vecinos validado, ocupación por zona y versión. No convertir y recorrer 125.989 aristas por grupo. Scheduler recibe zonas/instancias con presencia; mapas sin gente no generan decisiones ni draws.

## 3. Sortear una decisión por ciclo

Usar RNG inyectable y event_id por grupo/ciclo. Draw inferior a 0,25 permite plan; elegir longitud en rango y vecinos legales sin ciclos triviales si política lo evita. Reintentar publicación no vuelve a tirar ni generar otro camino.

## 4. Planificar ruta válida

Validar cada arista/altura, obstáculos, miembros y reserva de destino; trayecto no cruza combate/recurso ocupado. Snapshot bajo lock, cálculo fuera y CAS al aplicar. Un grupo que entra en combate durante plan queda inmóvil.

## 5. Emitir secuencia multi-paso

movement_packet actual codifica un paso: probar codec de trayectoria/animación y orden antes de ampliar. Commit final y peers deben concordar con camino; no teletransportar ni mandar varios starts simultáneos. Duración y ocupación en tránsito necesitan contrato.

## 6. Medir distribución y CPU

RNG fijo verifica fronteras, luego muestra grande para frecuencia aproximada 25% con intervalo estadístico. CompararCPU/locks a 1/16/32 grupos y cero jugadores. Que todos usen un worker no debe forzar que todos se muevan cada tick.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Solo zonas presentes simulan; ninguna ruta mueve miembros durante combate/recolección o por celdas ilegales.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
