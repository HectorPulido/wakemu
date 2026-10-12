"""Source-qualified839 eHI planning for an actual owned class target.

NPC targets deliberately require their separate connected visual producer.
This planner never inserts a creature, assigns a controller, or emits packets.
"""
from dataclasses import asdict
from .combat_target_copy_source import target_copy_raw_records
from .combat_three_spell_copy_book import TargetCopyBookAction, copy_target_book
from .combat_character_copy_book import CopyBookAction
from .combat_character_copy_codec import (
    CopiedCharacterDescriptor,
    connected_copy_appearance,
)
from .combat_character_copy_metadata import (
    native_copy_book_flags,
    native_copy_characteristics,
    native_copy_maximum_caps,
)
from .combat_character_copy_stats import copy_characteristics


def plan_class_target_copy(
    fight, target, authority, *, definitions, effects, percentage=100
):
    """Reuse existing class-connected appearance/ffh authority without UID cloning."""
    metadata = authority(fight, target)
    ordinary = getattr(authority, "ordinary", authority)
    source = getattr(ordinary, "characters", {}).get(target.id)
    if (
        not isinstance(source, dict)
        or source.get("id") != target.id
        or not isinstance(source.get("name"), str)
        or metadata.native_actor_type != 0
        or metadata.native_is_ehp is not True
    ):
        raise ValueError("Missing actual connected class target-copy source")
    raw, producer = target_copy_raw_records(fight, target, authority)
    flags = native_copy_book_flags()
    actions = []
    for uid, reference, level in raw:
        definition, row = definitions.get(str(reference)), flags.get(str(reference))
        if (
            not isinstance(definition, dict)
            or not isinstance(row, dict)
            or type(level) is not int
            or level < 0
        ):
            raise ValueError("Missing exact target-copy action definition")
        if level == 0:
            roots = definition.get("level_zero_roots")
        else:
            levels = definition.get("levels")
            roots = (
                levels[level - 1][2]
                if isinstance(levels, list) and level <= len(levels)
                else None
            )
        if not isinstance(roots, list) or any(type(ref) is not int for ref in roots):
            raise ValueError("Missing exact current-level target-copy roots")
        kinds = []
        for ref in roots:
            effect = effects.get(str(ref))
            if (
                not isinstance(effect, dict)
                or type(effect.get("effect_class")) is not int
            ):
                raise ValueError("Missing exact target-copy root class")
            kinds.append(effect["effect_class"])
        action = CopyBookAction(
            uid,
            reference,
            level,
            row["native_elO"],
            row["native_elemental_copy"],
            row["native_neutral_copy"],
        )
        action.validate()
        actions.append(TargetCopyBookAction(action, tuple(kinds), action.elemental))
    book = copy_target_book(actions)
    characteristics = native_copy_characteristics()
    level = metadata.native_real_level
    curves = characteristics["breeds"].get(str(metadata.breed_id))
    if curves is None:
        raise ValueError("Missing exact target class copied characteristic curves")
    copied = copy_characteristics(
        target.effect_stats,
        target.effect_maxima,
        fresh_definitions=characteristics["fresh_characteristics"],
        breed_curves=curves,
        level=level,
        percentage=percentage,
        maximum_caps=native_copy_maximum_caps(characteristics, level),
        native_order=tuple(characteristics["native_characteristic_order"]),
    )
    descriptor = CopiedCharacterDescriptor(
        metadata.breed_id,
        source["name"],
        target.hp,
        -1,
        level,
        -1,
        -1,
        -1,
        False,
        percentage,
        connected_copy_appearance(authority, fight, target),
        book,
        copied,
    )
    return descriptor, dict(
        producer="eZp839.faD.actual_target_book",
        source_actor_id=target.id,
        raw_book_producer=producer,
        borrowed_uids=[action.uid for action in book],
        profile=1549,
        descriptor_subtype=1,
        native_book_capacity=3,
        native_self_controlled=True,
        source_actions=[asdict(row.action) for row in actions],
        source_root_classes=[list(row.root_effect_classes) for row in actions],
        copied_actions=[asdict(action) for action in book],
    )
