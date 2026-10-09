"""Lossless JSON projection of declared native morph-book semantic sets."""

SEMANTIC_INTEGER_SETS = frozenset(
    {"removed_raw_uids", "active_spell_ids", "ActiveSpellIDs"}
)


def normalize_morph_evidence(value, *, path=(), set_projections=None):
    if set_projections is None:
        set_projections = []
    if isinstance(value, (set, frozenset)):
        if not path or path[-1] not in SEMANTIC_INTEGER_SETS:
            raise ValueError("Undeclared semantic set at " + repr(path))
        if any(type(item) is not int for item in value):
            raise ValueError(
                "Native integer-set evidence contains non-integer at " + repr(path)
            )
        set_projections.append(
            dict(
                path=list(path),
                source_type=type(value).__name__,
                semantic="unordered_native_integer_id_set",
            )
        )
        return sorted(value)
    if isinstance(value, dict):
        return {
            key: normalize_morph_evidence(
                item, path=path + (key,), set_projections=set_projections
            )
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            normalize_morph_evidence(
                item, path=path + (index,), set_projections=set_projections
            )
            for index, item in enumerate(value)
        ]
    if value is None or type(value) in (bool, int, float, str):
        return value
    raise ValueError(
        "Unsupported audit evidence type " + type(value).__name__ + " at " + repr(path)
    )
