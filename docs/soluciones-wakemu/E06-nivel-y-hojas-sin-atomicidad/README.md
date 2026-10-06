# E06. Subida de nivel y hojas de aptitudes

El cambio parcial de nivel, XP, salud y hojas fijas ya tiene cobertura PostgreSQL en el checkout actual. `!nivel` prepara salud y snapshot dentro de la operación transaccional; un fallo de snapshot revierte la progresión. La transición 49→50 con hoja fija 49 conserva nivel real50, nivel efectivo49, XP, salud y hoja al reabrir el Store. La misma suite verifica rollback de nivel/recompensa cuando falla la actualización de salud.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Implementación](IMPLEMENTACION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y límites

**Parcialmente implementado; no certificado de extremo a extremo.** La revalidación PostgreSQL se hizo en dos lotes separados: 54 pruebas de aptitudes/builds/equipo y 16 pruebas del comando `!nivel` y recompensas. Cubre las transacciones del comando y de recompensas, y la persistencia de una hoja fija. No acredita el cliente visual, notificaciones/roster después de cambiar nivel, todas las reglas de hojas moduladas, ni una matriz completa de consumidores de `effective_level` en combate.

La migración de la hoja 49→50 descrita en los probes viejos fue reemplazada por el comportamiento actual de hoja fija válida. Esos probes quedan como evidencia histórica del defecto previo, no como resultado vigente.

Dependencias: 9, 17 y 34. El motor de hechizos no se modificó en esta revalidación.
