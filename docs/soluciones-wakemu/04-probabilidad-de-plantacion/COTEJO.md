# Cotejo de código — 4

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**El contexto enviado y la autorización de familia son piezas existentes; deben cotejarse con la probabilidad efectiva y el render nativo. El porcentaje visual no demuestra la tirada del servidor.**

Función `bootstrap`, línea 31 de [server/wakfu_server/maps/planting_context.py](../../../server/wakfu_server/maps/planting_context.py). SHA-256: `707de24e1d5d4f3477f7d749ae777dd748657da69a12e77934d338859779772c`.

```python
def bootstrap(
    map_id,
    region_id,
    *,
    monster_counts=None,
    plant_counts=None,
    test_monster_families=()
):
    """12789/cuE → chl → bRR.Jo + bRT.dT/bRU.dT.

    Absent counts mean an empty LOCAL population, never official population.
    Family rows must remain present even when population is zero; dev.am uses
    bRT.Jp(family) existence as a planting gate.
    """
    definition = region(map_id, region_id)

    def encode(kind, counts):
        counts = {} if counts is None else counts
        families = [r["family_id"] for r in definition[kind + "_families"]]
        if kind == "monster":
            for family in test_monster_families:
                if type(family) is not int or not 0 < family < 2**31:
                    raise ValueError("Invalid test ecosystem family")
                if family not in families:
                    families.append(family)
        if any(k not in families for k in counts):
            raise ValueError("Foreign ecosystem family")
        rows = []
        for family in families:
            count = counts.get(family, 0)
            if type(count) is not int or not 0 <= count < 2**31:
                raise ValueError("Invalid local population")
            rows.append(struct.pack(">ii", family, count))
        return struct.pack(">i", len(rows)) + b"".join(rows)

    monsters = encode("monster", monster_counts)
    plants = encode("plant", plant_counts)
    return (
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/maps/planting.py](../../../server/wakfu_server/maps/planting.py) | 1e7fffafce73 | `decode` L27, `resource_packet` L36, `result_packet` L57, `start_packet` L63, `schema` L73, `prepare` L89, `complete` L142, `publish_groups` L258 |
| [server/wakfu_server/maps/planting_context.py](../../../server/wakfu_server/maps/planting_context.py) | 707de24e1d5d | `region` L17, `bootstrap` L31, `authorize_family` L77, `encode` L47 |
| [server/wakfu_server/maps/planting_runtime.py](../../../server/wakfu_server/maps/planting_runtime.py) | 5247374d25ce | `state_packet` L260, `growth_schema` L274, `monster_growth_member` L282, `__init__` L16, `begin` L35, `cancel` L102, `complete` L113, `snapshots` L145, `mature` L155, `publish_growth` L216 |
| [server/local_game_server.py](../../../server/local_game_server.py) | edbb31c2577a | `known_transports` L99, `position_lease_active` L114, `flush_positions` L128, `flush_position_batches` L144, `pack_text` L210, `realms_local` L215, `fixture` L269, `character_list_local` L282, `player_template` L293, `write_records` L322 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Separar regla de ayudas de prueba | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Construir contexto autoritativo | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Definir fórmula versionada | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Aplicar RNG una sola vez | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Validar presentación y distribución | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.

## Fórmula nativa cotejada

`dev.am` busca la celda/ground y llama `fyi.b`. Fórmula: `clamp((T/100) × biome × (1 + PS),0,1)`. T usa primero la referencia de recurso (incluido0 explícito), después familia, después0. Biome vale1 para clima ausente, recurso sin restricción o compatible; de lo contrario0,8. `PS=eRL.a(eRJ.raN,professionId,2)/100`, modificador de oficio identificado por efecto2000. No aparece el nivel de oficio como factor directo ni densidad del ecosistema; los niveles y familias son autorizaciones separadas.

UI: si p<=0 muestra X (-1); en otro caso `Math.round(100*p)`. El helper de tirada usa `Random.nextDouble()<p` sin redondeo. Ejemplos cotejados: terreno50 + bonus50%→75%; terreno50 + bonus−50%→25%; terreno100 + clima incompatible→80%. Esto acredita el cálculo del cliente instalado, no prueba la implementación del servidor oficial.

`planting_probability.calculate/succeeds` implementa esta aritmética en fuente; adquisición de clima/bonus, RNG transaccional y alineación con el indicador intervenido siguen pendientes. No se usan valores del cliente como resultado confiable.
