# Cotejo de código — 24

## Versión inspeccionada

Checkout local `main`, HEAD `7eb67928818af54eb04bddff29397ef0ccdec1ba`, con modificaciones concurrentes. La identidad por archivo queda en [manifest.json](../manifest.json); HEAD por sí solo no identifica estos bytes. No se afirma que esta sea la versión desplegada.

## Hallazgo contrastado

**Revisar defaults de creación junto con bootstrap: eliminar visualmente un pasaporte no define ciudadanía ni neutralidad de territorios. La propuesta necesita separar nación, permisos y UI.**

Función `create_character`, línea 211 de [server/wakfu_server/storage/store.py](../../../server/wakfu_server/storage/store.py). SHA-256: `9e69e69bb17084485601f474ae4a8fb5a262a152c07b604ea03742595b9bb547`.

```python
    def create_character(
        self,
        account_id,
        name,
        breed=15,
        sex=0,
        face=0,
        hair=0,
        colors=None,
        appearance=None,
    ):
        if appearance is not None:
            if not isinstance(appearance, dict) or any(
                key not in APPEARANCE_FIELDS
                or type(value) is not int
                or not -(1 << 31) <= value < (1 << 31)
                for key, value in appearance.items()
            ):
                raise ValueError("Apariencia protobuf inválida.")
            appearance = dict(appearance)
            sex = appearance.get("sex", sex)
            face = appearance.get("faceIndex", face)
            hair = appearance.get("clothIndex", hair)
        name = name.strip()
        if not re.fullmatch(r"[A-Za-z][A-Za-z -]{2,23}", name):
            raise ValueError("Nombre: 3–24 letras, espacios o guiones.")
        if (
            breed not in range(1, 19)
            or sex not in (0, 1)
            or face not in range(32)
            or hair not in range(32)
        ):
            raise ValueError("Apariencia inválida.")
        colors = colors if colors is not None else [0xFFFFFF] * 3
        if len(colors) != 3 or any(
            type(c) is not int or not 0 <= c <= 0xFFFFFF for c in colors
        ):
            raise ValueError("Se requieren tres colores RGB.")
# Fragmento truncado; consultar la función completa en el enlace.
```

## Archivos que debe recorrer la implementación

| Fuente | SHA-256 abreviado | Puntos de entrada |
| --- | --- | --- |
| [server/wakfu_server/wire.py](../../../server/wakfu_server/wire.py) | 53c52ffa187c | `minimal_entity` L51, `appearance_section` L102, `initial_progression` L126, `character_levels` L144, `without_equipment_appearance` L156, `varint` L174, `proto_fields` L183, `proto_field` L210, `attribute_sheets` L218, `identity` L249 |
| [server/wakfu_server/characters/creation.py](../../../server/wakfu_server/characters/creation.py) | 6b4db8399a76 | `create` L5 |
| [server/wakfu_server/maps/planting_context.py](../../../server/wakfu_server/maps/planting_context.py) | 707de24e1d5d | `region` L17, `bootstrap` L31, `authorize_family` L77, `encode` L47 |
| [server/wakfu_server/maps/world_static.py](../../../server/wakfu_server/maps/world_static.py) | 40311961155d | `objects` L22, `snapshots` L27, `interaction` L44 |

## Correspondencia con el plan

| Paso | Situación |
| --- | --- |
| 1. Identificar cada superficie | Propuesta; requiere cambio, prueba y revisión del contrato |
| 2. Localizar carriers heredados | Propuesta; requiere cambio, prueba y revisión del contrato |
| 3. Modelar neutralidad explícita | Propuesta; requiere cambio, prueba y revisión del contrato |
| 4. Sustituir cada sección por estado propio | Propuesta; requiere cambio, prueba y revisión del contrato |
| 5. Verificar reload y futuras naciones | Propuesta; requiere cambio, prueba y revisión del contrato |

La columna anterior clasifica el trabajo propuesto, no dice que cada pieza falte íntegramente. Reutilizar las validaciones, transacciones y codecs existentes identificados arriba; completar únicamente las brechas descritas.

## Límites de verificación

La existencia de una función o codec no demuestra integración de extremo a extremo. Las ausencias de handler deben comprobarse en el dispatcher y con una solicitud autenticada; las fórmulas, políticas y respuestas nativas pendientes se enumeran en [FALTANTES.md](FALTANTES.md). Si cambia un hash, repetir el cotejo antes de implementar.
