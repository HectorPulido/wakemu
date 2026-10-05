# Cotejo de código — E01

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**El manejo de conexiones no demuestra integridad física de una base histórica. Se requiere comprobar una copia consistente; no vincular la corrupción histórica con el bolso sin evidencia causal.**

Función `connection`, línea 78 de [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py). SHA-256: `9e69e69bb17084485601f474ae4a8fb5a262a152c07b604ea03742595b9bb547`.

```python
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        try:
            with db:
                yield db
        finally:
            db.close()
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py) | 9e69e69bb170 | `__init__` L15, `connection` L78, `password_hash` L90, `register` L95, `authenticate` L113, `digest` L126, `issue_token` L129, `token` L148, `revoke_token` L162, `begin_session` L166 |
| [server/wakfu_server/maps/planting_runtime.py](../../../server/wakfu_server/maps/planting_runtime.py) | 5247374d25ce | `state_packet` L260, `growth_schema` L274, `monster_growth_member` L282, `__init__` L16, `begin` L35, `cancel` L102, `complete` L113, `snapshots` L145, `mature` L155, `publish_growth` L216 |
| [server/wakfu_server/storage/build_journal.py](../../../server/wakfu_server/storage/build_journal.py) | 345f0d271da9 | `_sql` L15, `_checked` L24, `_units` L46, `__init__` L78, `_key` L119, `overlay` L123, `save` L141, `flush` L191, `flush_due` L230, `close` L233 |
| [server/wakfu_server/storage/state_journal.py](../../../server/wakfu_server/storage/state_journal.py) | d67f24a195c5 | `__init__` L19, `_call` L24, `field` L31, `encode` L35, `read` L38, `put` L58, `records` L83, `checkpoint` L95 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Identificar BD y versión afectadas | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Preservar backup verificable | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Diagnosticar sobre copia | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Elegir recovery explícito | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Ensayar reparación y cutover | Propuesta; requiere cambio, prueba y revisión del contrato |
| 6. Evitar repetición | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
