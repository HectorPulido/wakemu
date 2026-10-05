# Solución propuesta — 16

Mostrar combates vivos y permitir observación sin autoridad para actuar.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Separar marcador y espectador

Identificar envolvente 13753 y solicitudes de observar/salir. Un paquete heredado de captura no anuncia un combate vivo; el registro 14 debe ser fuente de marcadores por mapa/instancia. Definir privacidad, fase permitida y máximo observadores.

## 2. Publicar ciclo del marcador

Crear marcador al reservar/iniciar fight y retirarlo al final/cancelar. Incluir identidad/posición/equipos verificadas. Un jugador que entra al mapa recibe solo combates actuales; nunca reintroducir IDs de la captura original.

## 3. Iniciar snapshot consistente

Asignar subscription de solo lectura ligada a lease. Enviar arena, actores, fase, turno y estado vigente a secuenciaN; buffer/replay desde N+1 para cerrar carrera. No enviar inventario privado completo ni secretos por compartir serializer de participante.

## 4. Distribuir eventos sin control

Espectador recibe orden de acciones/resultados, pero no adquiere owner_id ni voto ready. ACK de espectadores no bloquea la ejecución de participantes; salida/desconexión quita subscription. Rechazar cast/move/orientación del observador a cualquier actor.

## 5. Cerrar y recuperar observación

Fin retira marcador/subscription y restaura mundo de observadores una vez. Snapshot atrasado tras cierre debe rechazarse por revisión. Limitar colas para que un espectador lento no retenga fight lock ni detenga turnos.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Observar nunca concede control; un cliente lento o desconectado no bloquea el combate observado.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
