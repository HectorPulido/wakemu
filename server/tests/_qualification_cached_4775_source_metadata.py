"""Read already cached native spell descriptors without another factory."""
import json, unittest
from pathlib import Path


def observe():
    import _qualification_retained_nox_factory_read as saved

    rows = {}
    for ref in (402300, 402301, 151632, 150122):
        effect = saved.last_factory.effects.get(
            str(ref), saved.last_factory.effects.get(ref)
        )
        rows[str(ref)] = {
            key: effect.get(key)
            for key in ("effect_class", "children", "parameters", "target_masks")
        }
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/tal4775-existing-cached-source-four-descriptors.json"
    ).write_text(json.dumps(rows, indent=2, default=repr))
    return unittest.TestSuite()
