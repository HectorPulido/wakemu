"""Bounded real owned-equipment execution fixture, not a Store/Ready receipt.

Uses production snapshots, equipment validation, pinning, initialization,
native targeting, QI registration and actual factory callbacks. Only the catalog
byte backend is the separately hash-pinned semantic projection. No gameplay
provider, eligibility decision, resolver or runner result is replaced.
"""
from copy import deepcopy
from pathlib import Path
import random
from types import SimpleNamespace

from tools.sublimation_bounded_census import BoundedDataset


def _factory(character, monsters, compiled, registry, rng):
    from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
    from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
    from wakfu_server.combat_ordinary_authority import (
        OrdinaryActorAuthority,
        ordinary_cast_authority,
    )
    from wakfu_server.combat_summon import RegisteredSummonAuthority
    from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
    from wakfu_server.combat_relative_probability import RelativeGroupAuthority
    from wakfu_server.combat_random_group import RandomGroupAuthority
    from wakfu_server.combat_equipment_external_contracts import (
        bind_owned_equipment_producers,
    )

    if not isinstance(monsters, dict) or any(
        type(key) is not int or row.get("id") != key for key, row in monsters.items()
    ):
        raise ValueError(
            "Semantic factory requires the complete explicit NPC source map"
        )
    sources = deepcopy(monsters)
    authority = RegisteredSummonAuthority(
        OrdinaryActorAuthority(
            characters={character["id"]: character},
            monsters=sources,
            decks={character["id"]: frozenset()},
            excluded_decks={character["id"]: frozenset()},
            deck_caps={character["id"]: None},
        )
    )
    cast = ordinary_cast_authority(
        actors=authority,
        timing=NativeEffectTimingProvider(compiled.source_states),
        rng=rng,
        critical=False,
    )
    adapter = NativeServerRuntimeAdapter(
        actor_authority=authority, cast=cast, viewer_id=character["id"]
    )
    factory = NativeEffectRuntimeFactory(
        effects=compiled.source_effects,
        state_catalog=compiled.source_states,
        compiled_effects=compiled,
        characteristic_registry=registry,
        action_id=1,
        contexts=adapter.contexts(),
        displacement_authority=authority,
        summon_authority=authority,
        transaction_rng=rng,
    )
    factory.native_rail_movement_authority = authority
    factory.relative_group_children = RelativeGroupAuthority(
        effects=factory.effects,
        actor_authority=authority,
        condition_context=adapter.condition,
        draw_integer=lambda total: rng.randint(1, total),
        draw_fraction=lambda fraction: rng.random() < fraction,
    )
    factory.random_group_children = RandomGroupAuthority(
        effects=factory.effects,
        condition_context=adapter.condition,
        draw_integer=lambda total: rng.randrange(total),
    )
    bind_owned_equipment_producers(factory)
    return factory


def build_fixture(
    scroll_ref,
    manifest,
    *,
    constructor_roles=None,
    terrain_cells=None,
    compiled_transform=None
):
    """Return an initialized native component fixture for one owned attachment.

    ``manifest`` is the separate manifest-semantic.json path. The returned
    dispatcher_for(preview, monster_sources=None) constructs a fresh real
    authority for that exact source map; it never extends an earlier factory's
    captured NPC dictionary. Transaction RNG remains the same owned object.

    This installs equipment and replays its opening1028 once. It deliberately
    does not fabricate class initialization or claim full character Ready.
    """
    if type(scroll_ref) is not int or scroll_ref <= 0:
        raise ValueError("Invalid original scroll identity")
    dataset = BoundedDataset(Path(manifest))
    required = (
        "native-actor-characteristics.json",
        "breed-innate-definitions.json",
        "aptitude-rules.json",
        "aptitude-effects.json",
        "item-equipment-conditions.json",
        "native-copied-equipment-definitions.json",
        "monsters.json",
        "monster-encyclopedia.json",
        "native-npc-spell-effect-trees.json",
    )
    missing = [key for key in required if key not in dataset.manifest["documents"]]
    if missing:
        raise ValueError(
            "Semantic manifest lacks original execution projections: "
            + ", ".join(missing)
        )
    dataset.install_catalog_backend()
    # Optional source catalogs use the public exists() path before load().
    # Resolve their existence from the original published inventory, while
    # preserving the strict projected-byte reader for every actual load.
    from wakfu_server import native_catalog

    inventory_entry = dataset.manifest.get("semantic", {}).get(
        "published_document_inventory"
    )
    if not isinstance(inventory_entry, dict):
        raise ValueError(
            "Semantic manifest lacks original published-document inventory"
        )
    document_inventory = dataset.read(inventory_entry)
    if not isinstance(document_inventory, dict) or any(
        not isinstance(name, str) for name in document_inventory
    ):
        raise ValueError("Invalid original published-document inventory")

    def source_exists(revision, name):
        if revision != dataset.manifest["revision"]:
            raise ValueError("Semantic catalog existence queried another revision")
        return name in document_inventory

    native_catalog._exists = source_exists
    from wakfu_server.combat_actor_snapshot import (
        build_player_snapshot,
        build_npc_snapshot,
        native_npc_creation_values,
    )
    from wakfu_server.combat_static_catalogs import CompiledEffects
    from wakfu_server.combat_effect_runtime import _merge_effects
    from wakfu_server.combat_state import Actor, Fight
    from wakfu_server.combat_qi_fight import (
        prepare_fresh_actor_slots,
        install_fresh_actor_slots,
    )
    from wakfu_server.combat_global_pv_collections import (
        initialize_global_pv_collections,
    )
    from wakfu_server.combat_geometry_snapshot import freeze_terrain
    from wakfu_server.combat_owned_equipment_pin import pin_transaction
    from wakfu_server.combat_owned_equipment import initialize_transaction
    from wakfu_server.combat_owned_equipment_factory import OwnedEquipmentRuntimeFactory
    from wakfu_server.combat_attachment_authority import CombatAttachmentAuthority
    from wakfu_server.sublimation_eligibility import CLIENT_JAR_SHA256
    from wakfu_server.equipment_stats import effective_character, combat_resources
    from wakfu_server.health import maximum
    from wakfu_server.wire import proto_field

    item = next(
        (row for row in dataset.manifest["scrolls"] if row["reference"] == scroll_ref),
        None,
    )
    if item is None:
        raise ValueError("Scroll is outside the source-pinned original denominator")
    options = dataset.manifest.get("semantic", {})
    parent = options.get("parent_by_kind", {}).get(item["kind"])
    if parent is None:
        if item["kind"] != "BASIC":
            raise ValueError(
                "Special attachment needs an original compatible semantic parent"
            )
        parent = {"reference": dataset.parent["reference"], "slot": 10}
    if type(parent.get("reference")) is not int or type(parent.get("slot")) is not int:
        raise ValueError("Missing native parent equipment reference/slot")
    patterns = [
        dict(
            reference=scroll_ref,
            pattern_type=item["kind"],
            slot_colors=item["slot_colors"],
            enabled=True,
            client_jar_sha256=CLIENT_JAR_SHA256,
        )
    ]
    targets = options.get("attachment_targets", [])
    if isinstance(targets, dict) and "path" in targets:
        targets = dataset.read(targets)
    authority = CombatAttachmentAuthority(patterns, targets)
    tag = 24 if item["kind"] == "BASIC" else 32
    state = b"".join(
        proto_field(10, proto_field(80, index) + proto_field(96, color))
        for index, color in enumerate(item["slot_colors"])
    ) + proto_field(tag, scroll_ref)
    gear = dict(
        uid=500,
        reference=parent["reference"],
        character_id=7,
        quantity=1,
        shard_state=state,
    )
    if authority(gear, state, scroll_ref, tag) is not True:
        raise ValueError("Original attachment is incompatible with the semantic parent")
    equipment = proto_field(
        10, proto_field(8, gear["uid"]) + proto_field(16, parent["slot"])
    )
    # Two actual initiative aptitude points (bonus20, original stat35 +4
    # per point) are allocated before Actor construction. At level100 this
    # legal selected build starts before native5525 INIT5 without overriding
    # the actor's native ordering/stat projection.
    aptitudes = proto_field(24, (1 << 64) - 1) + proto_field(
        34, proto_field(8, 20) + proto_field(16, 2)
    )
    level = options.get("actor_level", 100)
    breed = options.get("player_breed", 1)
    character = effective_character(
        dict(
            id=7,
            account_id=3,
            breed=breed,
            sex=False,
            level=level,
            real_level=level,
            map_id=1134,
            instance_id=0,
            x=0,
            y=0,
            z=0,
            hp=maximum(breed, level),
            inventory_items=[gear],
            active_build_index=0,
            builds={
                0: dict(
                    equipment=equipment.hex(),
                    sheet=proto_field(24, 0xFFFFFFFF).hex(),
                    aptitudes=aptitudes.hex(),
                )
            },
        )
    )
    # Full native initial health is chosen before Actor/snapshot construction;
    # no heal, HP override or post-Ready stat grant is performed.
    character["hp"] = character["max_hp"]
    resources = combat_resources(character)
    player_team = 0 if constructor_roles is None else constructor_roles.player_team
    npc_team = 1 if constructor_roles is None else constructor_roles.npc_team
    player = Actor(
        7,
        player_team,
        (0, 0, 0),
        character["hp"],
        resources["ap"],
        resources["mp"],
        resources["initiative"],
        level,
        owner_id=3,
        controlled=True,
        max_hp=character["max_hp"],
    )
    npc_ref = options.get("enemy_reference", 5525)
    npc_level = options.get("enemy_level", 1)
    values = native_npc_creation_values(npc_ref, npc_level)
    from wakfu_server.monsters import owned_instance

    monster = owned_instance(
        npc_ref, npc_level, -200, map_id=1134, instance_id=0, x=3, y=0, z=0, team=1
    )
    # The world monster keeps its original ordinary team1 source. The actor's
    # private combat side is independently constructed from frozen roles.
    enemy = Actor(
        -200,
        npc_team,
        (3, 0, 0),
        values[1]["current"],
        values[2]["current"],
        values[3]["current"],
        values[35]["current"],
        npc_level,
        max_hp=values[1]["maximum"],
    )
    player_snapshot = build_player_snapshot(
        character,
        player,
        wp_current=resources["wp"],
        wp_maximum=resources["wp"],
        running_effects=(),
    )
    npc_snapshot = build_npc_snapshot(
        monster,
        enemy,
        wp_current=values[4]["current"],
        wp_maximum=values[4]["maximum"],
        running_effects=(),
    )
    cells = (
        {(x, y, 0) for x in range(-6, 7) for y in range(-6, 7)}
        if terrain_cells is None
        else set(terrain_cells)
    )
    if (
        not cells
        or any(
            not isinstance(cell, tuple)
            or len(cell) != 3
            or any(type(value) is not int for value in cell)
            or cell[2] != 0
            for cell in cells
        )
        or player.position not in cells
        or enemy.position not in cells
    ):
        raise ValueError(
            "Semantic terrain requires complete explicit flat placement cells"
        )
    fight = Fight(
        1,
        (player, enemy),
        cells,
        {player_team: {player.position}, npc_team: {enemy.position}},
    )
    if constructor_roles is not None:
        from wakfu_server.combat_encounter_roles import bind_roles

        bind_roles(
            fight, constructor_roles, player_ids=(player.id,), npc_ids=(enemy.id,)
        )
    # Explicit synthetic component terrain, using the same real native QI
    # registration producer as native_combat_fixture; no original-map claim.
    x0, x1 = min(cell[0] for cell in cells), max(cell[0] for cell in cells)
    y0, y1 = min(cell[1] for cell in cells), max(cell[1] for cell in cells)
    fight.native_qi_snapshot = dict(
        x=x0,
        y=y0,
        width=x1 - x0 + 1,
        height=y1 - y0 + 1,
        cell_masks=[
            0 if (x, y, 0) in cells else 256
            for y in range(y0, y1 + 1)
            for x in range(x0, x1 + 1)
        ],
    )
    freeze_terrain(fight)
    # These are the concrete fresh registration bytes of this component's
    # player/NPC placement, also consumed by all later native serializers.
    player.native_obstacle_id, enemy.native_obstacle_id = 0, 1
    initialize_global_pv_collections(fight, tuple(fight.actors))
    install_fresh_actor_slots(
        fight,
        prepare_fresh_actor_slots(
            fight,
            physical_radii={
                7: player_snapshot.physical_radius,
                -200: npc_snapshot.physical_radius,
            },
        ),
    )
    fight.ready(3)
    player_snapshot.install(player)
    npc_snapshot.install(enemy)
    if fight.current is None or fight.current.id != 7:
        raise ValueError("Original fixture resources do not place the player first")
    fight.native_effect_uid_next = 1
    fight.native_obstacle_cells = frozenset()
    player.direction, enemy.direction = 0, 3

    # The closure includes copied-item definitions for admission. Production
    # starts with spell/state sources and adds item roots only through the
    # owned pin; preinjecting them would create a different source boundary.
    membership_entry = options.get("source_effect_membership")
    if not isinstance(membership_entry, dict):
        raise ValueError("Semantic manifest lacks original effect-source membership")
    membership = dataset.read(membership_entry)
    partitions = {}
    for key in ("base_effect_ids", "state_effect_ids", "owned_only_effect_ids"):
        references = membership.get(key)
        if (
            not isinstance(references, list)
            or any(type(ref) is not int or ref <= 0 for ref in references)
            or len(set(references)) != len(references)
        ):
            raise ValueError("Invalid original effect-source membership: " + key)
        partitions[key] = {str(ref) for ref in references}
    base_ids = partitions["base_effect_ids"]
    state_ids = partitions["state_effect_ids"]
    owned_ids = partitions["owned_only_effect_ids"]
    if (
        base_ids & owned_ids
        or base_ids | owned_ids != set(dataset.closure["effects"])
        or not state_ids <= base_ids
    ):
        raise ValueError("Original source membership differs from the bounded closure")
    effects = {
        ref: row for ref, row in dataset.closure["effects"].items() if ref in base_ids
    }
    state_catalog = dict(
        dataset.states,
        effects={
            ref: row
            for ref, row in dataset.states["effects"].items()
            if ref in state_ids
        },
    )
    supplements = []
    if "extra_effects" in options:
        supplements.append(options["extra_effects"])
    if "producer_effects" in dataset.manifest:
        supplements.append(dataset.manifest["producer_effects"])
    # These source-pinned definitions describe producer capabilities only;
    # they are never activated or added to owned attachment source roots.
    for entry in supplements:
        extra = dataset.read(entry)
        effects = _merge_effects(effects, extra)
        state_catalog = dict(
            state_catalog, effects=_merge_effects(state_catalog["effects"], extra)
        )
    if "extra_states" in options:
        extra_states = dataset.read(options["extra_states"])
        if not isinstance(extra_states, dict) or not isinstance(
            extra_states.get("states"), dict
        ):
            raise ValueError(
                "Semantic state supplement requires original state definitions"
            )
        states = dict(state_catalog["states"])
        for reference, definition in extra_states["states"].items():
            if reference in states and states[reference] != definition:
                raise ValueError(
                    "Conflicting original semantic state definition: " + reference
                )
            states[reference] = definition
        state_catalog = dict(state_catalog, states=states)
    compiled = CompiledEffects(effects, state_catalog)
    if compiled_transform is not None:
        compiled = compiled_transform(compiled)
        if type(compiled) is not CompiledEffects:
            raise TypeError(
                "Semantic compiled transform must preserve the production type"
            )
    registry = {"effects": dataset.closure["registry"]}
    rng = random.Random(700031)
    monsters = {monster["id"]: monster}
    factory = _factory(character, monsters, compiled, registry, rng)
    routes, capability = factory.equipment_operation_capability()
    fight, preparation = pin_transaction(
        fight,
        character,
        authority,
        compiled,
        registry,
        owner_id=3,
        ordinary_only=True,
        include_attachments=True,
        runtime_capability=(routes, capability),
    )
    if preparation["deferred"]:
        raise ValueError(
            "Native semantic source remains deferred: " + repr(preparation["deferred"])
        )
    compiled = preparation["compiled"]
    factory = _factory(character, monsters, compiled, registry, rng)
    factory = OwnedEquipmentRuntimeFactory(factory, compiled)
    fight, initialization_packets = initialize_transaction(
        fight, 7, preparation, factory, owner_id=3
    )
    plan = {
        "native_retained_container": dict(
            preparation["sources"][0]["native_retained_container"]
        )
    }

    def dispatcher_for(preview, monster_sources=None):
        sources = monsters if monster_sources is None else monster_sources
        current = _factory(character, sources, compiled, registry, rng)
        return OwnedEquipmentRuntimeFactory(current, compiled)(preview, plan)

    dispatcher, packets = dispatcher_for(fight)
    from wakfu_server.combat_event_replay import NativeExternalEvent

    for channel in (6, 60, 61):
        dispatcher.replay_event(
            NativeExternalEvent(7, (1028,), channel),
            authority=dispatcher.native_clone_authority,
        )
    # Component premise, published only after all three real opening deliveries
    # succeed. combat_start_events.deliver_fight_start publishes this marker
    # after its full startup replay; here class Ready and general1003 are
    # explicitly outside the component, so no class receipt is manufactured.
    # This permits the subsequent real owned START consumer under its unchanged
    # combat_turn_boundary.prepare_turn_delivery lifecycle guard.
    fight.native_start_event_delivered = True
    return SimpleNamespace(
        dataset=dataset,
        factory=factory,
        compiled=compiled,
        registry=registry,
        fight=fight,
        character=character,
        owner_id=3,
        plan=plan,
        monster_sources=deepcopy(monsters),
        dispatcher=dispatcher,
        packets=[*initialization_packets, *packets],
        damage_reference=options.get("native_damage_effect"),
        dispatcher_for=dispatcher_for,
        component_fixture=True,
        opening_1028_delivered=True,
        full_class_ready_qualified=False,
        start_boundary_is_component_premise=True,
    )
