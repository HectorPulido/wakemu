# E05. Selección no persistida y deck 0 fijo

> Current release2026-10-11: complete shared World/AI/ecology/admin deployed and automatically verified. Migration123; stable window released08:07 UTC. [Deployment evidence](../../reports/SYSTEMS-DEPLOYMENT-20261011.md). Graphical acceptance remains pending; any earlier prepared/not-deployed wording below is historical. Native planting bonus stays disabled pending its separate native-display acceptance.


Persistir y resolver una sola selección para stats, aptitudes y combate.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Closed after the final 2026-10-11 source review and automated verification.
`character_build_selection` persists the authoritative index/revision; equipment,
aptitudes and normal shared combat resolve that selection. Five legacy dispatcher
consumers now also use `active_build_index`. Missing fallback decks use each
build's effective level, while owned spell inventory retains real-level ownership.

The 26-test build-capacity gate passed, including a real combat regression with
different decks in builds0/1 after reopening storage and editing the inactive
build. Selection, health and revision remain consistent. These latest source
changes await the coordinated deployment; graphical acceptance is included in
the general systems checklist. Broader modulation work remains under issue34/E06.

## Dependencias

E04, E06, 17, 34. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

El mismo índice y revisión determinan todas las hojas y el encuentro; ningún consumidor fuerza 0 por omisión.
