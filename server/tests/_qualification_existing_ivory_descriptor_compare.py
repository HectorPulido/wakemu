"""Compare an existing cached factory mapping with one indexed native row."""
import json, unittest
from pathlib import Path


def observe():
    import _qualification_retained_nox_factory_read as saved
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    factory = saved.last_factory
    assert factory is not None
    actual = factory.effects.get("240712", factory.effects.get(240712))
    original = native_catalog.record(
        DATA_ROOT / "combat-state-definitions.json", "effects", 240712
    )
    keys = (
        "effect_class",
        "parameter_count",
        "parameters",
        "criteria",
        "area_class",
        "native_target_selector",
    )

    def plain(row):
        return {k: dict(type=type(row.get(k)).__name__, value=row.get(k)) for k in keys}

    result = dict(
        source="Existing retained Nox factory mapping; no reconstruction or catalog cache clearing",
        reference=240712,
        cached_factory=plain(actual),
        native_database=plain(original),
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/ivory240712-existing-factory-descriptor-typed-comparison.json"
    ).write_text(json.dumps(result, indent=2, default=repr))
    return unittest.TestSuite()
