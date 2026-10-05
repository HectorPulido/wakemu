# Cotejo de código — 9

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**La política existente debe revisarse junto con award; los valores por defecto de recompensa no demuestran recompensas reales. Un multiplicador necesita base verificable, redondeo y recibo.**

Función `policy_from_env`, línea 7 de [server/wakfu_server/combat/combat_lifecycle.py](../../../server/wakfu_server/combat/combat_lifecycle.py). SHA-256: `4d79dcf6b5ddb55e4fdaa219ec7eeff9f936cea2e15eb9c015efd30d7d06822c`.

```python
def policy_from_env(env=None):
    """Explicit local policy; both optional values default to zero."""
    env = os.environ if env is None else env
    values = []
    for key in ("WAKFU_LOCAL_FIGHT_XP", "WAKFU_LOCAL_FIGHT_KAMAS"):
        value = env.get(key, "0")
        if (
            not isinstance(value, str)
            or not value
            or not value.isascii()
            or not value.isdigit()
        ):
            raise ValueError("Invalid local reward setting " + key)
        values.append(int(value))
    return combat_rewards.Policy(*values)
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/combat/combat_rewards.py](../../../server/wakfu_server/combat/combat_rewards.py) | 13cf931a99a6 | `schema` L24, `load` L50, `award` L81, `wallet` L177, `_xp_info` L197, `report_metadata` L210, `__post_init__` L16 |
| [server/wakfu_server/combat/combat_lifecycle.py](../../../server/wakfu_server/combat/combat_lifecycle.py) | 4d79dcf6b5dd | `policy_from_env` L7, `prepare_finish` L24, `outside_progression` L84, `return_to_world` L112 |
| [server/wakfu_server/combat/combat_xp_gain.py](../../../server/wakfu_server/combat/combat_xp_gain.py) | 0e48f926f584 | `notification` L5 |
| [server/wakfu_server/characters/progression.py](../../../server/wakfu_server/characters/progression.py) | 8a560889941a | `level_xp` L14, `character_xp` L20 |
| [compose.yaml](../../../compose.yaml) | c56c61058637 | Configuración; revisar valores y uso por el proceso. |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Comprobar configuración efectiva | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Definir base y multiplicador | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Validar elegibilidad y confirmar | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Actualizar nivel y colecciones | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Ordenar delta y resumen | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
