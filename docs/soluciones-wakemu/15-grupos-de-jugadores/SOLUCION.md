# Solución propuesta — 15

Crear parties con invitaciones, miembros y liderazgo coherentes entre sesiones.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Definir party separada de NPC

Entidad propuesta party_id, leader_id, member_ids, revisión e invitaciones. COMBAT_GROUPS no sirve: modela monstruos/reservas de encuentro. Identificar carriers de invitación/aceptación/salida/expulsión y snapshot social del cliente.

## 2. Validar invitaciones

Comprobar presencia, pertenencia previa, cupo, líder y caducidad. Un personaje no pertenece a dos parties; carreras de invitación aceptada requieren CAS/unique. Invitación expirada o de una lease reemplazada no incorpora al jugador.

## 3. Implementar transiciones atómicas

Aceptar añade miembro y elimina invitación una vez; salir/expulsar actualiza versión y liderazgo determinista. Si sale último miembro cerrar party. Definir persistencia o party efímera con TTL/recovery explícito; no duplicar al reconectar.

## 4. Sincronizar roster y cambios

Snapshot inicial más eventos por revisión, misma lista para todos. Enviar fuera de WORLD.lock. Manejar miembro offline/reconnect sin duplicación de slot; política decide si se expulsa o se mantiene con estado offline.

## 5. Integrar consumidores

Chat de grupo 13 usa roster vigente; joins 14 y mazmorras 29 validan membresía/revisión pero no confunden estar en party con estar en el mismo fight. Una salida cancela permisos pendientes y no borra recompensas ya confirmadas.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Cada personaje pertenece a una sola party; todos sus miembros reciben la misma revisión de roster.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
