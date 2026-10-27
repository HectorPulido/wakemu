"""Authorized Wakemu reconstruction of Rushu's missing initial vestige scene.

Sixteen original typed glyphs use the observed relative community layout on
validated native1332 cells. Absolute positions and the layout RNG are explicit
server policy; no original server coordinates, states or event are claimed.
"""
from copy import deepcopy
from random import Random

from .combat_encounter_area_seeds import (
    NativeEncounterAreaSeed,
    install_native_area_seeds,
)
from wakfu_server.combat_encounter_roles import assigned_roles

POLICY = "wakemu.rushu.initial-vestiges.v2"
_LEGACY_POLICY = "wakemu.rushu.initial-vestiges.v1"


def initial_vestige_plan(layout, *, seed, programs):
    """Freeze one random permutation over all16 observed fixed glyph cells."""
    if type(seed) is not int or seed < 0:
        raise ValueError("Rushu setup requires an explicit nonnegative layout seed")
    cells = tuple(tuple(cell) for cell in layout["glyph_cells"])
    if layout["map_id"] != 1332 or len(cells) != 16 or len(set(cells)) != 16:
        raise ValueError("Rushu setup requires sixteen distinct native glyph positions")
    if len(programs) != len(cells):
        raise ValueError(
            "Rushu setup requires its complete frozen seed program inventory"
        )
    creators = list(programs)
    Random(seed).shuffle(creators)
    seeds = tuple(
        NativeEncounterAreaSeed(
            row["area_reference"],
            row["creator_reference"],
            row["level"],
            cell,
            program_reference=row["program_reference"],
            state_reference=row["state_reference"],
            state_effect_reference=row["state_effect_reference"],
        )
        for row, cell in zip(creators, cells)
    )
    return seeds, dict(
        authority="authorized_wakemu_content_reconstruction",
        placement="observed_relative_layout_translated_to_validated_native_cells",
        layout_policy=layout["policy"],
        type_distribution="all_sixteen_unique_original_types_random_permutation",
        layout_seed=seed,
        native_program="ordered_original_349_315_304_with_singleton_scene_population",
        initial_level_authority="explicit_wakemu_reconstructed_initial_level",
        initial_level_context="native_SP_field4_transmitted_by_original_flag16",
        initial_levels=sorted({row["level"] for row in creators}),
        content_source="https://methodwakfu.com/pvm/boss-ultimes/palais-de-rushu/",
        original_server_coordinates_claimed=False,
        state_damage_cost_or_event_overrides=False,
    )


def install_rushu_encounter_setup(dispatcher, *, map_id, monsters, layout, seed=None):
    """Seed the declared scene once before actual native fight-start1003.

    The caller owns its unpublished initialization preview and discards the
    preview and outbox on failure. Native315 owns Qq construction, publication,
    registration, callbacks, expiry and later removal; original349 also executes
    its original304 sibling against the newly registered area.
    """
    fight = dispatcher.native_retention.fight
    candidates = [
        identity
        for identity, source in monsters.items()
        if source.get("ref") == 5306 and identity in fight.actors
    ]
    if not candidates or map_id != 1332:
        return False
    if len(candidates) != 1 or layout["map_id"] != map_id:
        raise ValueError("Rushu setup requires one actual native boss on its scene")
    boss_id = candidates[0]
    if seed is None:
        seed = fight.id
    receipts = getattr(fight, "native_encounter_area_setups", {})
    if POLICY not in receipts and _LEGACY_POLICY in receipts:
        # A completed old setup is immutable history. Validate its exact old
        # representation and return its existing no-op, never upgrade its Qq.
        plan = receipts[_LEGACY_POLICY].get("plan", {})
        old_seeds = tuple(
            NativeEncounterAreaSeed(
                row["area_reference"],
                row["effect_reference"],
                row["level"],
                tuple(row["cell"]),
            )
            for row in plan.get("seeds", ())
        )
        old_provenance = plan.get("provenance", {})
        if (
            len(old_seeds) != 16
            or plan.get("creator_id") != boss_id
            or any(
                set(row) != {"area_reference", "effect_reference", "level", "cell"}
                for row in plan.get("seeds", ())
            )
            or {item.cell for item in old_seeds}
            != {tuple(cell) for cell in layout["glyph_cells"]}
            or old_provenance.get("layout_seed") != seed
            or old_provenance.get("layout_policy") != layout["policy"]
        ):
            raise ValueError(
                "Legacy Rushu setup differs from its committed initial plan"
            )
        return install_native_area_seeds(
            dispatcher,
            policy=_LEGACY_POLICY,
            creator_id=boss_id,
            seeds=old_seeds,
            provenance=old_provenance,
        )
    from .combat_encounter_seed_programs import (
        encounter_seed_programs,
        freeze_encounter_seed_program_policy,
        seed_program_policy_from_record,
    )

    previous = getattr(fight, "native_encounter_area_setups", {}).get(POLICY)
    if previous is not None and not hasattr(fight, "native_encounter_area_seed_policy"):
        manifest = previous["plan"]["provenance"]["seed_program_manifest"]
        fight.native_encounter_area_seed_policy = seed_program_policy_from_record(
            manifest
        )
    freeze_encounter_seed_program_policy(fight, roles=assigned_roles(fight))
    programs = encounter_seed_programs(fight, boss_reference=monsters[boss_id]["ref"])
    seeds, provenance = initial_vestige_plan(layout, seed=seed, programs=programs)
    provenance["seed_program_manifest"] = deepcopy(
        fight.native_encounter_area_seed_policy
    )
    if POLICY in getattr(fight, "native_encounter_area_setups", {}):
        # Native callbacks may already have consumed glyphs or moved actors.
        # A matching committed plan is evidence of setup, never a respawn.
        return install_native_area_seeds(
            dispatcher,
            policy=POLICY,
            creator_id=boss_id,
            seeds=seeds,
            provenance=provenance,
        )
    boss = fight.actors[boss_id]
    roles = assigned_roles(fight)
    native = getattr(fight, "native_npc_initialization_receipts", {}).get(boss_id, {})
    constructor = fight.native_encounter_area_seed_policy["boss_constructor_state"]
    if (
        boss.controlled
        or boss.hp <= 0
        or boss.team != roles.npc_team
        or native.get("initialized") is not True
        or native.get("ref") != 5306
        or not any(
            row.get("state_id") == constructor
            for row in native.get("resolved_states", ())
        )
        or tuple(boss.position) != tuple(layout["source"])
    ):
        raise ValueError("Rushu setup differs from its native constructed boss")
    player_slots = {tuple(cell) for cell in layout["party_placement_cells"]}
    if any(
        tuple(actor.position) not in player_slots
        for actor in fight.actors.values()
        if actor.team == roles.player_team
    ):
        raise ValueError("Rushu players were not constructed in the declared scene")
    # This content shuffle is independent of damage/critical RNG. Persisting
    # the actual fight-specific seed makes replay stable without a second draw.
    return install_native_area_seeds(
        dispatcher,
        policy=POLICY,
        creator_id=boss_id,
        seeds=seeds,
        provenance=provenance,
    )
