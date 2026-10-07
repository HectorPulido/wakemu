# E06. Subida de nivel y hojas de aptitudes

El cambio parcial de nivel, XP, salud y hojas fijas ya tiene cobertura PostgreSQL en el checkout actual. `!nivel` prepara salud y snapshot dentro de la operación transaccional; un fallo de snapshot revierte la progresión. La transición 49→50 con hoja fija 49 conserva nivel real50, nivel efectivo49, XP, salud y hoja al reabrir el Store. La misma suite verifica rollback de nivel/recompensa cuando falla la actualización de salud.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Implementación](IMPLEMENTACION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y límites

**Parcialmente implementado; no certificado de extremo a extremo.** La revalidación PostgreSQL se hizo en dos lotes separados: 54 pruebas de aptitudes/builds/equipo y 16 pruebas del comando `!nivel` y recompensas. Cubre las transacciones del comando y de recompensas, y la persistencia de una hoja fija. No acredita el cliente visual, notificaciones/roster después de cambiar nivel, todas las reglas de hojas moduladas, ni una matriz completa de consumidores de `effective_level` en combate.

La migración de la hoja 49→50 descrita en los probes viejos fue reemplazada por el comportamiento actual de hoja fija válida. Esos probes quedan como evidencia histórica del defecto previo, no como resultado vigente.

Dependencias: 9, 17 y 34. El motor de hechizos no se modificó en esta revalidación.

## Aceptación manual y defecto de biblioteca — 6 de octubre

El usuario confirma que Npers sube correctamente de nivel. Captura de Personaje: nivel50,550PdV,6PA,3PM,6PW; builds24/24 con CupoReemplazo activa. La biblioteca mantiene hechizos grises con requisitos inferiores al nivel actual. Por tanto la subida visual está confirmada, pero **el desbloqueo de hechizos al subir no funciona** según la prueba del usuario. Esta evidencia no basta para inferir qué carrier o cache es responsable: hay que cotejar actualización de biblioteca y nivel efectivo con la sesión que mantiene los hechizos.

No se modifican codecs, catálogo ni motor de hechizos desde esta tarea. E06 continúa **Solucionado parcialmente**: modulación integral y desbloqueo de biblioteca pendientes; la subida de nivel básica no debe volver a figurar como prueba visual no ejecutada.
