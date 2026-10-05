# Diagnóstico — 9

## Contexto registrado

**Confirmado:** Compose y `combat/combat_lifecycle.py::policy_from_env` usan `WAKFU_LOCAL_FIGHT_XP=0` por defecto. Existen recompensa transaccional, curva de nivel y notificaciones en `combat_rewards.py`, `characters/progression.py` y `combat_xp_gain.py`.

**Posible solución:** definir una política de XP no nula y, si se desea progresión por enemigo, sustituir el importe fijo por un cálculo explícito. Verificar la configuración efectiva del proceso antes de atribuirle el valor de Compose. **Validación:** victoria, derrota, cruce de nivel, HP/aptitudes y ausencia de doble recompensa.

Dejar configurable un "multiplicador de xp"

## Lectura actual

La política existente debe revisarse junto con award; los valores por defecto de recompensa no demuestran recompensas reales. Un multiplicador necesita base verificable, redondeo y recibo.

El contexto anterior conserva la evidencia del informe; puede describir una instancia o snapshot anterior. El [cotejo](COTEJO.md) identifica el código leído hoy y sus límites.

## Qué falta para confirmar el recorrido

- Fórmula base y reparto entre jugadores/companions.
- Nombre/rango del multiplicador y política de ceros/fracciones.
- Configuración efectiva del mundo que produjo el síntoma y captura de subida por XP (distinta de !nivel).

## Evidencia de origen

[Informe completo](../../reports/auditoria-problemas-wakemu-2026-10-04.md). No se copian capturas privadas, bases, credenciales ni archivos del cliente.
