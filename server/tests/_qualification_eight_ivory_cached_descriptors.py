"""Export eight already cached native descriptors, with representation types."""
import json, unittest
from pathlib import Path


def observe():
    import _qualification_retained_nox_factory_read as saved

    factory = saved.last_factory
    assert factory is not None
    keys = (
        "effect_class",
        "parameter_count",
        "parameters",
        "criteria",
        "area_class",
        "native_target_selector",
    )
    result = {}
    for reference in (238154, 238155, 240706, 240707, 240709, 240710, 240712, 240713):
        row = factory.effects.get(str(reference), factory.effects.get(reference))
        result[str(reference)] = {
            key: dict(type=type(row.get(key)).__name__, value=row.get(key))
            for key in keys
        }
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/ivory258-eight-existing-cached-descriptors.json"
    ).write_text(json.dumps(result, indent=2, default=repr))
    return unittest.TestSuite()
