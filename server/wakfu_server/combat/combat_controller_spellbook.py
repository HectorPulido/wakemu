"""Installed eZd.fQM controller-facing book selector (capacity8)."""
from .combat_target_copy_book import TargetCopyBookAction


def controller_spellbook(actions):
    """Stable descending cmZ, up to2 non-elemental then remaining non-neutral.

    Native selection slices before fyR insertion rejects already-present rows;
    duplicates therefore do not backfill the capacity.
    """
    if not isinstance(actions, tuple):
        raise ValueError("Missing actual controller book encounter order")
    eligible = []
    seen = set()
    for row in actions:
        if not isinstance(row, TargetCopyBookAction):
            raise ValueError("Missing typed controller book action")
        row.action.validate()
        if row.action.uid in seen:
            raise ValueError("Duplicate source controller book UID")
        seen.add(row.action.uid)
        if (
            not isinstance(row.root_effect_classes, tuple)
            or any(type(kind) is not int for kind in row.root_effect_classes)
            or row.elemental is not row.action.elemental
        ):
            raise ValueError("Missing actual controller root/element authority")
        if (
            row.elemental is None
            or row.action.special
            or any(kind in (307, 347, 324) for kind in row.root_effect_classes)
        ):
            continue
        eligible.append(row.action)
    elemental = sorted(
        (action for action in eligible if not action.neutral),
        key=lambda action: -action.level,
    )
    other = sorted(
        (action for action in eligible if not action.elemental),
        key=lambda action: -action.level,
    )[:2]
    selected = other + elemental[: max(0, 8 - len(other))]
    inserted, seen = [], set()
    for action in selected:
        if action.uid not in seen:
            inserted.append(action)
            seen.add(action.uid)
    return tuple(inserted)


def target_controller_spellbook(
    fight, target, authority, *, definitions, effects, effect_level
):
    """eZd.fQM uses running-effect level for roots and current spell level to rank."""
    from .combat_target_copy_source import target_copy_raw_records
    from .combat_character_copy_book import CopyBookAction
    from .combat_character_copy_metadata import native_copy_book_flags

    if type(effect_level) is not int or not 0 <= effect_level <= 32767:
        raise ValueError("Missing actual eZd running effect level")
    records, producer = target_copy_raw_records(fight, target, authority)
    flags, rows = native_copy_book_flags(), []
    for uid, reference, level in records:
        definition, row = definitions.get(str(reference)), flags.get(str(reference))
        if not isinstance(definition, dict) or not isinstance(row, dict):
            raise ValueError("Missing exact native controller action metadata")
        if effect_level == 0:
            roots = definition.get("level_zero_roots")
        else:
            levels = definition.get("levels")
            roots = (
                levels[effect_level - 1][2]
                if isinstance(levels, list) and effect_level <= len(levels)
                else None
            )
        if not isinstance(roots, list) or any(type(ref) is not int for ref in roots):
            raise ValueError("Missing exact controller effect-level roots")
        classes = []
        for ref in roots:
            effect = effects.get(str(ref))
            if (
                not isinstance(effect, dict)
                or type(effect.get("effect_class")) is not int
            ):
                raise ValueError("Missing exact controller root class")
            classes.append(effect["effect_class"])
        action = CopyBookAction(
            uid,
            reference,
            level,
            row["native_elO"],
            row["native_elemental_copy"],
            row["native_neutral_copy"],
        )
        rows.append(TargetCopyBookAction(action, tuple(classes), action.elemental))
    return controller_spellbook(tuple(rows)), producer


def controller_additional_payload(book, *, use_current_controller):
    """Native eZd.rHk.gun field71 and eWD.rBJ field17 (present false included)."""
    from .combat_effects import _varint, _integer
    from .combat_character_copy_book import CopyBookAction

    if (
        type(use_current_controller) is not bool
        or not isinstance(book, tuple)
        or len(book) > 8
    ):
        raise ValueError("Missing actual native eWD additional-data operands")
    entries, seen = [], set()
    for action in book:
        if not isinstance(action, CopyBookAction):
            raise ValueError("Missing typed native eWD published action")
        action.validate()
        if action.uid in seen:
            raise ValueError("Duplicate native eWD published UID")
        seen.add(action.uid)
        entry = (
            _integer(1, action.uid)
            + _integer(2, action.reference)
            + _integer(3, action.level)
        )
        entries.append(b"\x0a" + _varint(len(entry)) + entry)
    inventory = b"".join(entries)
    return (
        _integer(17, int(use_current_controller))
        + _varint((71 << 3) | 2)
        + _varint(len(inventory))
        + inventory
    )
