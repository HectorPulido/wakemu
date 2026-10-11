# E06. Subida de nivel y hojas de aptitudes

> Current release2026-10-11: complete shared World/AI/ecology/admin deployed and automatically verified. Migration123; stable window released08:07 UTC. [Deployment evidence](../../reports/SYSTEMS-DEPLOYMENT-20261011.md). Graphical acceptance remains pending; any earlier prepared/not-deployed wording below is historical. Native planting bonus stays disabled pending its separate native-display acceptance.


El cambio parcial de nivel, XP, salud y hojas fijas ya tiene cobertura PostgreSQL en el checkout actual. `!nivel` prepara salud y snapshot dentro de la operación transaccional; un fallo de snapshot revierte la progresión. La transición 49→50 con hoja fija 49 conserva nivel real50, nivel efectivo49, XP, salud y hoja al reabrir el Store. La misma suite verifica rollback de nivel/recompensa cuando falla la actualización de salud.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Implementación](IMPLEMENTACION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y límites

**Parcialmente implementado; no certificado de extremo a extremo.** La revalidación PostgreSQL se hizo en dos lotes separados: 54 pruebas de aptitudes/builds/equipo y 16 pruebas del comando `!nivel` y recompensas. Cubre las transacciones del comando y de recompensas, y la persistencia de una hoja fija. No acredita el cliente visual, notificaciones/roster después de cambiar nivel, todas las reglas de hojas moduladas, ni una matriz completa de consumidores de `effective_level` en combate.

La migración de la hoja 49→50 descrita en los probes viejos fue reemplazada por el comportamiento actual de hoja fija válida. Esos probes quedan como evidencia histórica del defecto previo, no como resultado vigente.

Dependencias: 9, 17 y 34. El motor de hechizos no se modificó en esta revalidación.

## Aceptación manual y defecto de biblioteca — 6 de octubre

El usuario confirma que Npers sube correctamente de nivel. Captura de Personaje: nivel50,550PdV,6PA,3PM,6PW; builds24/24 con CupoReemplazo activa. La biblioteca mantiene hechizos grises con requisitos inferiores al nivel actual. Por tanto la subida visual está confirmada, pero **el desbloqueo de hechizos al subir no funciona** según la prueba del usuario. Esta evidencia no basta para inferir qué carrier o cache es responsable: hay que cotejar actualización de biblioteca y nivel efectivo con la sesión que mantiene los hechizos.

No se modifican codecs, catálogo ni motor de hechizos desde esta tarea. E06 continúa **Solucionado parcialmente**: modulación integral y desbloqueo de biblioteca pendientes; la subida de nivel básica no debe volver a figurar como prueba visual no ejecutada.

## Current source review — 2026-10-11

The immediate library-refresh gap remains reproducible from source: `!nivel`
publishes only the format3 progression snapshot, which has no `SPELL_INVENTORY`.
The command explicitly asks the player to select the character again. This
explains why an updated visible level does not certify the spell library's
refresh; it does not prove that reconnecting leaves the library broken.
`owned_spell_records` already derives ownership and spell levels from the real
character level. Active build caps are resolved independently by the Store,
equipment/health evaluation and shared combat adapter.

The current source correction makes fallback decks use the effective build
level and resolves each missing deck independently when publishing multiple
builds. Spell ownership, catalog unlock thresholds and casting rules are
unchanged. Integrated tests, deployment and live acceptance must be recorded
separately before declaring the broader issue closed.

`characters/level_publication.py::refresh` now prepares an owned format10
spellbook/deck refresh followed by the real-level character roster. The
dispatcher must publish it after the existing `!nivel` progression packets.
Native `ciu` bytecode4335–4479 for15548 first resolves the existing local actor
by ID (or its owned registry entry) and calls `biB.as(blob)` on that same object.
It does not activate or spawn a second actor. The private reproducible dump is
`.runtime/local/level-publication-ciu.javap.txt`, generated with
`javap -classpath client/lib/wakfu-client.jar -c -p ciu`.
This proves update identity handling, not live UI acceptance of spell unlocks.
