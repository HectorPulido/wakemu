# E05. Selección no persistida y deck 0 fijo

Persistir y resolver una sola selección para stats, aptitudes y combate.

[Diagnóstico](DIAGNOSTICO.md) · [Cotejo de código](COTEJO.md) · [Solución](SOLUCION.md) · [Pruebas](PRUEBAS.md) · [Información pendiente](FALTANTES.md)

## Estado y alcance

Implementación parcial comprobada en fuente actual: `character_build_selection` persiste índice/revisión; `Store.activate_build` confirma selección y salud de forma transaccional. Equipo y aptitudes resuelven `active_build_index`, y `13776` publica la selección autoritativa mediante `13811`. Los documentos de diagnóstico anteriores describen el estado histórico.

La brecha de deck continúa: `local_game_server.py` aún consulta `character.get("builds", {}).get(0, {})` en consumidores de combate, incluido `apply_readiness`. No cerrar E05 hasta que ready, inicio/fin de turno, arma y áreas resuelvan el mismo índice activo. La regresión requiere decks distintos en builds 0 y 1, alternancia, reconexión y guardar una build inactiva sin cambiar la activa. Los cambios de decks/hechizos están reservados a la otra sesión.

## Dependencias

E04, E06, 17, 34. Ver el [índice general](../README.md) y las [reglas transversales](../TRANSVERSALES.md).

## Invariante de aceptación

El mismo índice y revisión determinan todas las hojas y el encuentro; ningún consumidor fuerza 0 por omisión.
