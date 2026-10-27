"""Actual PJ item-PL/self application after source-proved fight registration."""
from copy import copy


def equipment_effect_definitions(plan):
    """Compile exported native fields without guessing variants or group children."""
    definitions = {}

    def visit(row):
        required = {
            "reference",
            "effect_class",
            "parameters",
            "parameter_count",
            "variant",
            "minimum_level",
            "maximum_level",
            "children",
            "child_definitions",
            "metadata",
        }
        if not isinstance(row, dict) or not required <= row.keys():
            raise ValueError("Missing native copied equipment effect closure")
        children = row["children"]
        nested = row["child_definitions"]
        if (
            not isinstance(children, list)
            or not isinstance(nested, list)
            or [child.get("reference") for child in nested] != children
        ):
            raise ValueError("Conflicting native copied equipment child order")
        metadata = row["metadata"]
        if (
            not isinstance(metadata, dict)
            or not {
                "target_masks",
                "native_target_selector",
                "native_effect_flags",
                "native_definition_class",
                "area_class",
                "area_native",
                "probability_base",
                "probability_per_level",
            }
            <= metadata.keys()
        ):
            raise ValueError("Missing native copied equipment metadata")
        criteria = row.get("criterion_raw")
        if criteria is None:
            if row.get("criterion_native") is not None:
                raise ValueError(
                    "Missing original copied equipment criterion expression"
                )
            criteria = ""  # Native null criterion, not an invented predicate.
        definition = dict(
            metadata,
            effect_class=row["effect_class"],
            parameters=list(row["parameters"]),
            parameter_count=row["parameter_count"],
            variant=row["variant"],
            minimum_level=row["minimum_level"],
            maximum_level=row["maximum_level"],
            children=list(children),
            criteria=criteria,
        )
        identity = str(row["reference"])
        if identity in definitions and definitions[identity] != definition:
            raise ValueError("Conflicting native copied equipment definition")
        definitions[identity] = definition
        for child in nested:
            visit(child)

    for root in plan["roots"]:
        visit(root)
    return definitions


def equipment_initializer(factory):
    if not callable(factory):
        raise ValueError("Missing native copied equipment runtime factory")

    def initialize(fight, actor, source):
        plan = source.get("native_plan")
        if plan is None or not plan["roots"]:
            return
        from .combat_effect_dispatch import EffectInvocation
        from .combat_summon import RegisteredSummonAuthority

        if fight.actors.get(actor.id) is not actor or not isinstance(
            factory.summon_authority, RegisteredSummonAuthority
        ):
            raise ValueError("Missing registered native PJ destination")
        metadata = factory.summon_authority(fight, actor)
        if metadata.is_summon is not True or metadata.native_in_play is not True:
            raise ValueError("Missing native PJ registered fight context")
        definitions = equipment_effect_definitions(plan)
        from .combat_static_catalogs import DefinitionOverlay

        nested = copy(factory)
        nested.effects = DefinitionOverlay(factory.effects, definitions)
        nested.state_catalog = dict(
            factory.state_catalog,
            effects=DefinitionOverlay(factory.state_catalog["effects"], definitions),
        )
        container = dict(plan["native_retained_container"])
        hp_before, maximum_before = actor.hp, actor.max_hp
        dispatcher, outbox = nested(fight, {"native_retained_container": container})
        # Native PJ has null PS and explicit destination SELF. Its item PL is
        # independent of the current fight PZ; preserve the actual fight PZ.
        for root in plan["roots"]:
            dispatcher.execute(
                EffectInvocation(
                    root["reference"],
                    container["level"],
                    actor.id,
                    actor.id,
                    actor.position,
                    native_retained_container=container,
                    native_explicit_target=True,
                )
            )
        # Client307/1002 reconstruction performs the same PJ constructor call.
        # Retain authoritative PA/Qf mutations, not duplicate constructor wire.
        actor.native_applied_equipment_calls = getattr(
            actor, "native_applied_equipment_calls", []
        ) + [
            dict(
                source_actor_id=source["source_actor_id"],
                dsK=source["dsK"],
                container=container,
                roots=[row["reference"] for row in plan["roots"]],
                hp_before=hp_before,
                maximum_before=maximum_before,
                hp_after=actor.hp,
                maximum_after=actor.max_hp,
                native_pn="eGj.a(fcb).pGz.fqH.dnL.fcb.bbg.eVw",
                native_ps=None,
            )
        ]

    return initialize
