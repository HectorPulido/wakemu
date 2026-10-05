# Solución propuesta — 12

Permitir desafíos consensuados entre personajes sin usar el resolver de grupos NPC.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Delimitar duelo y agresión

Identificar el clic/solicitud de desafío, invitación, aceptar/rechazar y fin. El scope propuesto cubre duelo consensuado; agresión territorial requiere reglas de nación distintas. Definir rewards, pérdida de HP y efectos al terminar, no copiar muerte de NPC por defecto.

## 2. Crear invitación y reserva

Persistir desafío con caducidad y ambos IDs/leasess. Validar mapa/instancia, distancia y que ninguno participa en otro encuentro. Aceptación reserva a los dos de forma atómica; rechazar, timeout o desconexión libera sin crear combate.

## 3. Construir autoridad compartida

Un único fight_id y runtime con dos equipos/controladores; registrar pertenencia de ambas sesiones. Seleccionar arena/celdas una vez con 31, no un fight local por cliente. Bootstrap envía a ambos actores, equipo/aptitudes/deck activos y orientaciones legales.

## 4. Procesar acciones por dueño y turno

Toda solicitud comprueba propietario del actor, fase, AP/MP, secuencia y revisión. Propagar eventos/ACK a participantes sin permitir que A controle B. Definir cómo una sesión lenta/desconectada afecta al reloj del encuentro, sin duplicar turnos.

## 5. Finalizar según política PvP

Victoria, rendición y desconexión generan transición compartida idempotente, liberan pertenencia y restauran mundo. No otorgar loot de NPC ni XP/kamas sin política de duelo. Un combate nuevo puede comenzar después sin reserva residual.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Un desafío aceptado crea un combate compartido; control y resultados no dependen del cliente que inició.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
