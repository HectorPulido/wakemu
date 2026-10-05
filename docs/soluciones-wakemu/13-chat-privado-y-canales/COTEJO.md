# Cotejo de código — 13

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La difusión espacial existente puede servir para canales locales, pero no define destinatario privado ni alcance de gremio/grupo. Validar sesión, membresía y canal antes del envío.**

Función `broadcast`, línea 69 de [server/wakfu_server/maps/world.py](../../../server/wakfu_server/maps/world.py). SHA-256: `b41d86cdcc95c6f7c69fe78389bfffecf172294ca613d88735feaaa6602c479a`.

```python
    def broadcast(self, generation, character_id, opcode, body, *, include_sender=True):
        with self.lock:
            existing = self.players.get(character_id)
            if not existing or existing[0] != generation:
                raise ValueError("Character is no longer in this world session")
            for _, peer, other in self.players.values():
                if (include_sender or other["id"] != character_id) and self.location(
                    other
                ) == self.location(existing[2]):
                    self._send(peer, opcode, body)
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |
| [server/wakfu_server/maps/world.py](../../../server/wakfu_server/maps/world.py) | b41d86cdcc95 | `__init__` L6, `location` L14, `snapshot` L17, `_send` L24, `join` L34, `leave` L46, `update` L57, `broadcast` L69, `emit_location` L80 |
| [server/wakfu_server/wire.py](../../../server/wakfu_server/wire.py) | 53c52ffa187c | `minimal_entity` L51, `appearance_section` L102, `initial_progression` L126, `character_levels` L144, `without_equipment_appearance` L156, `varint` L174, `proto_fields` L183, `proto_field` L210, `attribute_sheets` L218, `identity` L249 |
| [server/wakfu_server/characters/social.py](../../../server/wakfu_server/characters/social.py) | cf52cfc40899 | `company` L22, `adapt` L30 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Inventariar peticiones por canal | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Definir presencia y destinatarios | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Separar comandos de mensajes | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Enviar con contrato por canal | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Validar entrega y aislamiento | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
