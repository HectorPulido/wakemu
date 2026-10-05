# Solución propuesta — 11

Intercambiar objetos y kamas entre dos cuentas con confirmaciones revisadas y transferencia atómica.

Leer primero [COTEJO.md](COTEJO.md). Estos pasos son una especificación para implementar y validar; no describen una corrección aplicada.

## 1. Descubrir protocolo y restricciones

Capturar invitación, aceptar, añadir/quitar, confirmar y cancelar con dos personajes nuevos. Identificar IDs/status/ownership, distancia, fase y límites. No inventar opcodes: inventory_move es traslado dentro de dueño, no transferencia entre cuentas.

## 2. Crear sesión de intercambio compartida

Modelo propuesto con trade_id, participantes, leases, estado, revisión, ofertas y confirmaciones. Estados: invitado→abierto→confirmado_por_ambos→committed, o cancelado. Cada cambio de oferta incrementa revisión y borra ambas confirmaciones; confirmar revisión vieja debe fallar.

## 3. Reservar unidades y valores

Verificar propiedad/cantidad, elementos/engastes, restricciones vinculadas y referencias en todas las builds. Reservar recursos para impedir equiparlos/consumirlos mientras están ofrecidos; la reserva no concede propiedad al receptor. Validar espacio final considerando salidas y límites de stack antes del commit.

## 4. Transferir de forma atómica

Orden estable de locks por ID; comparar leases/revisión/ofertas y confirmar ambos lados, wallet, unidades, propiedades y recibo en un commit. Si SQL sigue autoridad usar una transacción; si Redis primero definir operación atómica y recovery entre dominios. No hacer dos commits independientes de quitar/dar.

## 5. Sincronizar y recuperar

Emitir resultado una vez a ambos y deltas propios. Corte antes de commit cancela/resuelve reservas; corte después devuelve recibo committed. Timeout, cambio de mapa/combate y sesión reemplazada deben seguir transición definida sin perder un lado. Conservar UID o split unitario según codec y regla, nunca regenerar propiedades al transferir.

## Cierre y recuperación

Aplicar las barreras de [TRANSVERSALES.md](../TRANSVERSALES.md): validar antes de mutar, conservar recibos y revisiones, y confirmar durabilidad antes de respuestas que anuncien cambios de valor. Ensayar fallo antes del commit, después del commit y antes del ACK. Si hay una migración, probar compatibilidad sobre copias y definir recuperación antes de habilitarla. No revertir a un estado anterior que pierda mutaciones ya confirmadas.

## Aceptación

Suma de kamas y cantidades se conserva; una misma revisión requiere las dos confirmaciones actuales.

Completar la matriz de [PRUEBAS.md](PRUEBAS.md), resolver los faltantes bloqueantes y registrar los bytes/estados esperados antes y después. No dar por cerrado el issue por una mejora visual aislada.
