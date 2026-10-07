"""Native bje/ffx creation resources followed by eHD descriptor transforms.

No world monster level policy is applied. Visual-copy equipment remains an
explicit guard until its owned cosmetics/equipment model is available.
"""
from .combat_actor_snapshot import (
    native_actor_catalog,
    native_npc_creation_values,
    build_npc_snapshot,
)
from .combat_state import Actor
from .combat_obstacle_ids import assign_obstacle_ids
from .combat_summon import SummonRegistration
from .combat_runtime_adapter import NativeActorAuthority
from .combat_ordinary_authority import native_property_catalog
from .combat_stat_effects import apply_current_stat


class NativeSummonBuilder:
    def __init__(self, actor_authority, *, characteristics=None, properties=None):
        self.actor_authority = actor_authority
        self.characteristics = (
            native_actor_catalog() if characteristics is None else characteristics
        )
        self.properties = (
            native_property_catalog() if properties is None else properties
        )

    def __call__(self, preview, specification, caster_id, actor_id, cell):
        caster = preview.actors[caster_id]
        parent = self.actor_authority(preview, caster)
        profile = self.properties["npc"].get(str(specification.reference))
        if profile is None:
            raise ValueError("Missing native summoned breed properties")
        fight_properties = frozenset(profile["fight_properties"])
        world_properties = frozenset(profile["world_properties"])
        world_provider = getattr(self.actor_authority, "world_properties", None)
        if not callable(world_provider):
            raise ValueError("Missing native summoner world-property authority")
        caster_world = frozenset(world_provider(preview, caster))
        # Actual eHD.a copies eHQ.pSW: category0/property47, after descriptor.
        if 47 in caster_world:
            world_properties = world_properties | {47}
        if 101 in fight_properties:
            raise ValueError(
                "Native SUMMONER_VISUAL_COPY needs owned visual/equipment authority"
            )
        # eZl.c has a distinct native equipment replication branch for3251.
        # Reject it until the actual eSU.dzQ/foA appearance model is supplied.
        if specification.reference == 3251:
            raise ValueError(
                "Native3251 requires caster cosmetic-equipment replication"
            )
        values = native_npc_creation_values(
            specification.reference, specification.level, catalog=self.characteristics
        )
        actor = Actor(
            actor_id,
            specification.team,
            cell,
            values[1]["current"],
            values[2]["current"],
            values[3]["current"],
            values[35]["current"],
            specification.level,
            max_hp=values[1]["maximum"],
            direction=specification.direction,
        )
        assign_obstacle_ids([*preview.actors.values(), actor])
        snapshot = build_npc_snapshot(
            {"id": actor_id, "ref": specification.reference},
            actor,
            wp_current=values[4]["current"],
            wp_maximum=values[4]["maximum"],
            running_effects=(),
            catalog=self.characteristics,
        )
        snapshot.install(actor)
        if 81 in fight_properties:
            if caster.effect_stats is None or 20 not in caster.effect_stats:
                raise ValueError("Missing native summoner DMG_IN_PERCENT20")
            result = apply_current_stat(
                family="eWQ",
                current=actor.effect_stats[20],
                minimum=actor.effect_minima[20],
                maximum=actor.effect_maxima[20],
                requested=caster.effect_stats[20],
                percent=False,
                executable=True,
                frozen=20 in actor.effect_frozen,
                source_guards_verified=True,
                limit_policy="NORMAL",
            )
            actor.effect_stats[20] = result["current"]
        controller_id = actor_id if specification.self_controlled else caster_id
        if not specification.self_controlled:
            actor.owner_id, actor.controlled = caster.owner_id, caster.controlled
        root_id = actor_id if specification.self_controlled else parent.summon_root_id
        if root_id is None:
            raise ValueError("Missing native controller chain root")
        targeting = dict(
            bcN=actor.native_obstacle_id,
            is_amO=True,
            is_eGj=True,
            is_Qq=False,
            is_eHH=True,
            bEe=42 not in fight_properties,
            UNTARGETTABLE_BY_OTHER=21 in fight_properties,
            buX=False,
            dTE=True,
            dpu_id=controller_id,
            baG=False,
            baK=False,
        )
        metadata = NativeActorAuthority(
            targeting,
            False,
            frozenset(),
            frozenset(),
            False,
            specification.reference,
            0,
            {},
            True,
            is_summon=True,
            summon_root_id=root_id,
            is_carrying=False,
            is_challenger=False,
            native_real_level=specification.level,
            native_instance_id=parent.native_instance_id,
        )
        actor.native_summon_source = dict(
            ref=specification.reference,
            level=specification.level,
            direction=specification.direction,
            caster_id=caster_id,
            controller_id=controller_id,
        )
        return actor, SummonRegistration(
            actor_id,
            caster_id,
            controller_id,
            metadata,
            fight_properties,
            world_properties,
        )
