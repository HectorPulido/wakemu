"""Bounded real Rift carrier graphs; synthetic arena and ordinary NPC roster.

This is a native state/accepted-wave component, not an original boss-composition
or complete class Ready receipt. Only catalog bytes use a hash-pinned backend;
actor snapshots, context authority, targeting, handlers and state clocks remain
production implementations. Run explicitly with WAKFU_RIFT_CARRIER_DATASET.
"""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import random
from types import SimpleNamespace
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_RIFT_CARRIER_DATASET"),
    "Explicit bounded Rift projection required",
)
class NativeRiftCarrierComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tools.sublimation_bounded_census import BoundedDataset
        from wakfu_server import native_catalog

        path = Path(os.environ["WAKFU_RIFT_CARRIER_DATASET"])
        raw = path.read_bytes()
        expected = os.environ.get("WAKFU_RIFT_CARRIER_SHA256")
        if not expected or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Rift carrier source projection must be hash-pinned")
        cls.native = json.loads(raw)
        cls.dataset = BoundedDataset(os.environ["WAKFU_SUBLIMATION_SEMANTIC_MANIFEST"])
        if cls.native["revision"] != cls.dataset.manifest["revision"] or cls.native.get(
            "unresolved_dynamic_state_references"
        ):
            raise ValueError("Rift carrier source revision or closure differs")
        cls.dataset.install_catalog_backend()
        original_read = native_catalog._read_published
        original_metadata = json.loads(
            original_read("native-retained-effect-metadata.json")
        )
        metadata = deepcopy(original_metadata)
        for kind in ("effects", "states"):
            metadata[kind] = {
                **metadata.get(kind, {}),
                **cls.native["retained_metadata"][kind],
            }
        metadata_bytes = json.dumps(metadata).encode()

        def read_projection(name):
            if name == "native-retained-effect-metadata.json":
                return metadata_bytes
            return original_read(name)

        native_catalog._read_published = read_projection
        inventory = cls.dataset.read(
            cls.dataset.manifest["semantic"]["published_document_inventory"]
        )
        native_catalog._exists = lambda revision, name: (
            revision == cls.dataset.manifest["revision"] and name in inventory
        )
        from wakfu_server.combat_static_catalogs import CompiledEffects
        from wakfu_server.combat_effect_runtime import _merge_effects

        effects = _merge_effects(
            cls.dataset.closure["effects"], {"effects": cls.native["effects"]}
        )
        states = {**cls.dataset.states["states"], **cls.native["states"]}
        cls.compiled = CompiledEffects(effects, {"states": states, "effects": effects})
        cls.registry = {
            "effects": {**cls.dataset.closure["registry"], **cls.native["registry"]}
        }

    @staticmethod
    def policy():
        from wakfu_server.rift_native_gameplay_policy import POLICY
        from wakfu_server.rift_company_compensation import GRADE_POLICY
        from wakfu_server.rift_encounter_roles import POLICY as ROLE_POLICY

        return dict(
            policy_kind="local_dev_not_official",
            enabled=True,
            max_members=6,
            turn_budget=40,
            starting_wave=1,
            classic_wave_size=2,
            ultimate_wave_size=2,
            selection="uniform_with_replacement",
            scaling="native_base_grade",
            rewards="callback_only",
            quest_requirements=[],
            key_requirements=[],
            native_gameplay=dict(
                enabled=True,
                policy=POLICY,
                authority="native_consumers_with_reconstructed_producers",
                enabled_types=["ULTIMATE_INFINITE_WAVE"],
                wave_state=6807,
                encounter_roles=dict(policy=ROLE_POLICY, player_team=1, npc_team=0),
                compensation=dict(
                    native_state=6808,
                    grade_policy=GRADE_POLICY,
                    classic_grade_by_company_size={
                        str(n): max(0, 4 - n) for n in range(1, 7)
                    },
                    ultimate_grade_by_company_size={
                        str(n): 5 - n if n <= 4 else 0 for n in range(1, 7)
                    },
                ),
            ),
        )

    def fixture(
        self,
        quantity,
        *,
        controller_registration=False,
        native_map_id=1134,
        rift_type="ULTIMATE_INFINITE_WAVE",
        enabled_native_types=None
    ):
        from wakfu_server.combat_actor_snapshot import (
            build_player_snapshot,
            build_npc_snapshot,
            native_npc_creation_values,
        )
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.equipment_stats import effective_character, combat_resources
        from wakfu_server.health import maximum
        from wakfu_server.wire import proto_field
        from wakfu_server.monsters import owned_instance
        from wakfu_server.rift_encounter_roles import roles_for_catalog
        from wakfu_server.combat_encounter_roles import bind_roles
        from wakfu_server.combat_qi_fight import (
            prepare_fresh_actor_slots,
            install_fresh_actor_slots,
        )
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
        )

        policy = self.policy()
        if enabled_native_types is not None:
            policy["native_gameplay"]["enabled_types"] = list(enabled_native_types)
        catalog = dict(
            type=rift_type,
            map_id=native_map_id,
            wave_id=1,
            species_refs=[5525],
        )
        roles = roles_for_catalog(catalog, policy, monster_references=(5525, 5525))
        actors, characters, snapshots = [], {}, {}
        aptitudes = proto_field(24, (1 << 64) - 1) + proto_field(
            34, proto_field(8, 20) + proto_field(16, 2)
        )
        for index in range(quantity):
            uid = 7 + index
            character = effective_character(
                dict(
                    id=uid,
                    account_id=3,
                    breed=1,
                    sex=False,
                    level=100,
                    real_level=100,
                    map_id=native_map_id,
                    instance_id=1,
                    x=-index,
                    y=0,
                    z=0,
                    hp=maximum(1, 100),
                    inventory_items=[],
                    active_build_index=0,
                    builds={
                        0: dict(
                            equipment="",
                            sheet=proto_field(24, 0xFFFFFFFF).hex(),
                            aptitudes=aptitudes.hex(),
                        )
                    },
                )
            )
            character["hp"] = character["max_hp"]
            resources = combat_resources(character)
            actor = Actor(
                uid,
                roles.player_team,
                (-index, 0, 0),
                character["hp"],
                resources["ap"],
                resources["mp"],
                resources["initiative"],
                100,
                owner_id=3,
                controlled=True,
                max_hp=character["max_hp"],
            )
            snapshots[uid] = build_player_snapshot(
                character,
                actor,
                wp_current=resources["wp"],
                wp_maximum=resources["wp"],
                running_effects=(),
            )
            actors.append(actor)
            characters[uid] = character
        monsters = {}
        for uid, position in ((-200, (3, 0, 0)), (-201, (4, 0, 0))):
            source = owned_instance(
                5525,
                1,
                uid,
                map_id=native_map_id,
                instance_id=1,
                x=position[0],
                y=position[1],
                z=position[2],
                team=1,
            )
            values = native_npc_creation_values(5525, 1)
            actor = Actor(
                uid,
                roles.npc_team,
                position,
                values[1]["current"],
                values[2]["current"],
                values[3]["current"],
                values[35]["current"],
                1,
                max_hp=values[1]["maximum"],
            )
            snapshots[uid] = build_npc_snapshot(
                source,
                actor,
                wp_current=values[4]["current"],
                wp_maximum=values[4]["maximum"],
                running_effects=(),
            )
            actors.append(actor)
            monsters[uid] = source
        cells = {(x, y, 0) for x in range(-8, 9) for y in range(-8, 9)}
        edges = {
            (cell, (cell[0] + dx, cell[1] + dy, 0))
            for cell in cells
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (cell[0] + dx, cell[1] + dy, 0) in cells
        }
        fight = Fight(
            77,
            actors,
            cells,
            roles.placement_cells(
                [a.position for a in actors if a.controlled],
                [a.position for a in actors if not a.controlled],
            ),
            valid_edges=edges,
        )
        bind_roles(fight, roles, player_ids=tuple(characters), npc_ids=tuple(monsters))
        # Install each original fresh snapshot before any helper can fill its
        # characteristic or collision fields. QI consumes its real radius.
        for uid, snap in snapshots.items():
            snap.install(fight.actors[uid])
        fight.native_qi_snapshot = dict(
            x=-8,
            y=-8,
            width=17,
            height=17,
            cell_masks=[0] * (17 * 17),
        )
        for slot, actor in enumerate(fight.actors.values()):
            actor.native_obstacle_id = slot
        initialize_global_pv_collections(
            fight, tuple(fight.actors), controller_registration=controller_registration
        )
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(
                fight,
                physical_radii={
                    uid: actor.physical_radius for uid, actor in fight.actors.items()
                },
            ),
        )
        from wakfu_server.combat_geometry_snapshot import freeze_terrain

        freeze_terrain(fight)
        fight.ready(3)
        fight.native_effect_uid_next = 1
        fight.native_obstacle_cells = frozenset()
        fight.rift_wave_state = dict(
            instance_id=1,
            wave=1,
            turn_budget=40,
            wave_actor_ids=list(monsters),
            catalog=catalog,
            policy=policy,
            seed="native-component",
            actor_id_pool=[-202, -203, -204, -205],
            world_group_id=77,
        )
        fight.rift_monsters = deepcopy(monsters)
        rng = random.Random(719)

        def factory(current):
            from wakfu_server.combat_effect_runtime import NativeEffectRuntimeFactory
            from wakfu_server.combat_runtime_adapter import NativeServerRuntimeAdapter
            from wakfu_server.combat_ordinary_authority import (
                OrdinaryActorAuthority,
                ordinary_cast_authority,
            )
            from wakfu_server.combat_summon import RegisteredSummonAuthority
            from wakfu_server.combat_native_timing_context import (
                NativeEffectTimingProvider,
            )
            from wakfu_server.combat_relative_probability import RelativeGroupAuthority
            from wakfu_server.combat_random_group import RandomGroupAuthority

            authority = RegisteredSummonAuthority(
                OrdinaryActorAuthority(
                    characters=characters,
                    monsters=current.rift_monsters,
                    decks={uid: frozenset() for uid in characters},
                    excluded_decks={uid: frozenset() for uid in characters},
                    deck_caps={uid: None for uid in characters},
                )
            )
            cast = ordinary_cast_authority(
                actors=authority,
                timing=NativeEffectTimingProvider(self.compiled.source_states),
                rng=rng,
                critical=False,
            )
            adapter = NativeServerRuntimeAdapter(
                actor_authority=authority, cast=cast, viewer_id=7
            )
            runtime = NativeEffectRuntimeFactory(
                effects=self.compiled.source_effects,
                state_catalog=self.compiled.source_states,
                compiled_effects=self.compiled,
                characteristic_registry=self.registry,
                action_id=1,
                contexts=adapter.contexts(),
                displacement_authority=authority,
                summon_authority=authority,
                transaction_rng=rng,
            )
            runtime.native_rail_movement_authority = authority
            runtime.relative_group_children = RelativeGroupAuthority(
                effects=runtime.effects,
                actor_authority=authority,
                condition_context=adapter.condition,
                draw_integer=lambda total: rng.randint(1, total),
                draw_fraction=lambda fraction: rng.random() < fraction,
            )
            runtime.random_group_children = RandomGroupAuthority(
                effects=runtime.effects,
                condition_context=adapter.condition,
                draw_integer=lambda total: rng.randrange(total),
            )
            return runtime(current, {"native_retained_container": {"present": False}})

        return SimpleNamespace(
            fight=fight, factory=factory, rng=rng, characters=characters
        )

    def test_original_native_graphs_company_bulk_and_wave_retry_rollback(self):
        from wakfu_server.rift_company_compensation import install_company_compensation
        from wakfu_server.rift_native_gameplay import install_wave_state, policy
        from wakfu_server.rift_encounter_roles import roles_for_catalog
        from wakfu_server.combat_encounter_roles import roles_from_record
        from wakfu_server.fight_checkpoint_store import snapshot
        from wakfu_server.combat_random_transaction import rollback_external_rng

        for quantity in range(1, 7):
            with self.subTest(company=quantity):
                component = self.fixture(quantity)
                fight = component.fight
                before = {
                    uid: (
                        fight.actors[uid].max_ap,
                        fight.actors[uid].max_mp,
                        fight.actors[uid].max_hp,
                    )
                    for uid in component.characters
                }
                dispatcher, outbox = component.factory(fight)
                with fight.effect_resolution():
                    installed = install_company_compensation(
                        dispatcher, actor_ids=tuple(component.characters)
                    )
                    self.assertTrue(
                        install_wave_state(dispatcher, actor_ids=(-200, -201), wave=1)
                    )
                grade = 5 - quantity if quantity <= 4 else 0
                self.assertEqual(installed, bool(grade))
                for uid in component.characters:
                    entries = [
                        row
                        for row in fight.actors[uid].state_ledger.entries
                        if row.reference == 6808
                    ]
                    self.assertEqual(
                        [row.level for row in entries], [grade] if grade else []
                    )
                    if grade:
                        self.assertEqual(
                            fight.actors[uid].max_ap - before[uid][0], 3 * grade
                        )
                        self.assertGreater(fight.actors[uid].max_hp, before[uid][2])
                    else:
                        self.assertEqual(
                            (
                                fight.actors[uid].max_ap,
                                fight.actors[uid].max_mp,
                                fight.actors[uid].max_hp,
                            ),
                            before[uid],
                        )
                checkpoint = snapshot(fight)
                rng_before = component.rng.getstate()
                packet_count = len(outbox)
                self.assertFalse(
                    install_company_compensation(
                        dispatcher, actor_ids=tuple(reversed(component.characters))
                    )
                )
                self.assertFalse(
                    install_wave_state(dispatcher, actor_ids=(-201, -200), wave=1)
                )
                self.assertEqual(snapshot(fight), checkpoint)
                self.assertEqual(component.rng.getstate(), rng_before)
                self.assertEqual(len(outbox), packet_count)
                if quantity != 1:
                    continue
                with self.assertRaises(ValueError):
                    install_company_compensation(dispatcher, actor_ids=(7, 999))
                bad = deepcopy(fight.native_encounter_roles)
                bad["player_team"] = 0
                with self.assertRaises(ValueError):
                    roles_from_record(bad)
                classic = deepcopy(fight.rift_wave_state["catalog"])
                classic["type"] = "INFINITE_WAVE"
                ordinary = roles_for_catalog(
                    classic,
                    fight.rift_wave_state["policy"],
                    monster_references=(5525, 5525),
                )
                self.assertEqual((ordinary.player_team, ordinary.npc_team), (0, 1))
                classic_preview = deepcopy(fight)
                classic_preview.rift_wave_state["catalog"] = classic
                self.assertIsNone(policy(classic_preview))
                from wakfu_server.rift_dispatch_lifecycle import next_roster
                from wakfu_server.rift_npc_creation import install_native_wave

                # Trusted FSM damage clears the actual initial roster. Native
                # death/orb consumers are outside this carrier component.
                for identity in (-200, -201):
                    fight.apply_damage(7, identity, fight.actors[identity].hp)
                self.assertEqual(
                    fight.rift_wave_state["pending_wave"]["completed_wave"], 1
                )
                pending = deepcopy(fight)
                pending_snapshot = snapshot(pending)
                rng_before = component.rng.getstate()

                def admit(preview, *, reject_after_native_state=False):
                    monsters = next_roster(
                        preview, preview.rift_wave_state["pending_wave"]
                    )
                    preview.rift_monsters = {
                        **preview.rift_monsters,
                        **{source["id"]: source for source in monsters},
                    }

                    def initialize_wave(current, actors, sources):
                        current_dispatcher, packets = component.factory(current)
                        identities = tuple(actor.id for actor in actors)
                        self.assertTrue(
                            install_wave_state(
                                current_dispatcher, actor_ids=identities, wave=2
                            )
                        )
                        # Same pending accepted roster can be retried before ACK.
                        self.assertFalse(
                            install_wave_state(
                                current_dispatcher, actor_ids=identities, wave=2
                            )
                        )
                        return tuple(packets)

                    def initialize_actor(current, actor, source):
                        if reject_after_native_state:
                            self.assertTrue(
                                any(
                                    entry.reference == 6807
                                    for entry in actor.state_ledger.entries
                                )
                            )
                            raise ValueError(
                                "Reject unpublished birth after native carrier"
                            )
                        return ()

                    return install_native_wave(
                        preview,
                        monsters,
                        initialize_actor=initialize_actor,
                        initialize_wave=initialize_wave,
                    )

                @rollback_external_rng
                def rejected(*, rng):
                    return admit(deepcopy(pending), reject_after_native_state=True)

                with self.assertRaisesRegex(ValueError, "after native carrier"):
                    rejected(rng=component.rng)
                self.assertEqual(snapshot(pending), pending_snapshot)
                self.assertEqual(component.rng.getstate(), rng_before)
                successful = deepcopy(pending)
                births = admit(successful)
                self.assertEqual(successful.rift_wave_state["wave"], 2)
                self.assertIsNone(successful.rift_wave_state["pending_wave"])
                self.assertEqual(sum(opcode == 13091 for opcode, _ in births), 2)
                self.assertTrue({-202, -203} <= set(successful.actors))
                for identity in (-202, -203):
                    self.assertEqual(
                        [
                            entry.level
                            for entry in successful.actors[
                                identity
                            ].state_ledger.entries
                            if entry.reference == 6807
                        ],
                        [2],
                    )
                old_receipts = pending.rift_wave_state["native_wave_entries"]
                self.assertTrue(
                    all(
                        successful.rift_wave_state["native_wave_entries"][key] == value
                        for key, value in old_receipts.items()
                    )
                )

    def test_classic_native_wave_growth_roles_and_achievement_bindings(self):
        """Shared native graph through accepted births; no boss/orb UI claim."""
        from unittest.mock import patch
        from psycopg.pq import TransactionStatus
        from wakfu_server.rift_encounter_roles import (
            roles_for_catalog,
            roles_from_record,
        )
        from wakfu_server.combat_encounter_roles import assigned_roles
        from wakfu_server.rift_native_gameplay import install_wave_state, policy
        from wakfu_server.rift_company_compensation import install_company_compensation
        from wakfu_server.rift_dispatch_lifecycle import next_roster
        from wakfu_server.rift_npc_creation import install_native_wave
        from wakfu_server.achievements.rift_facts import load_locked

        old_policy = self.policy()
        classic = dict(type="INFINITE_WAVE", map_id=1134, species_refs=[5525])
        old_roles = roles_for_catalog(
            classic, old_policy, monster_references=(5525, 5525)
        )
        self.assertEqual((old_roles.player_team, old_roles.npc_team), (0, 1))
        self.assertIsNone(
            policy(
                SimpleNamespace(
                    rift_wave_state=dict(catalog=classic, policy=old_policy)
                )
            )
        )
        unrelated = roles_for_catalog(
            dict(classic, type="ORDINARY"), old_policy, monster_references=(5525,)
        )
        self.assertEqual((unrelated.player_team, unrelated.npc_team), (0, 1))

        component = self.fixture(
            1,
            rift_type="INFINITE_WAVE",
            enabled_native_types=("INFINITE_WAVE", "ULTIMATE_INFINITE_WAVE"),
        )
        fight = component.fight
        roles = assigned_roles(fight)
        self.assertEqual((roles.player_team, roles.npc_team), (1, 0))
        self.assertEqual(roles_from_record(roles.record()).record(), roles.record())
        self.assertEqual(
            roles.record()["rift_scope"]["catalog"]["type"], "INFINITE_WAVE"
        )
        self.assertTrue(all(row["team"] == 1 for row in fight.rift_monsters.values()))
        base_hp = fight.actors[-200].max_hp
        player_ap = fight.actors[7].max_ap
        dispatcher, packets = component.factory(fight)
        with fight.effect_resolution():
            self.assertTrue(install_company_compensation(dispatcher, actor_ids=(7,)))
            self.assertTrue(
                install_wave_state(dispatcher, actor_ids=(-200, -201), wave=1)
            )
        self.assertEqual(fight.actors[7].max_ap, player_ap + 9)
        first_hp = fight.actors[-200].max_hp
        self.assertGreaterEqual(first_hp, base_hp)
        history = [(1, tuple(fight.rift_wave_state["wave_actor_ids"]))]
        fight.rift_wave_state["actor_id_pool"] = [-202, -203, -204, -205, -206, -207]

        for wave in (2, 3, 4):
            # Genuine FSM clearing/accepted births exercise the shared carrier
            # boundary. Native dispatcher death/orb events are separate tests.
            for uid in tuple(fight.rift_wave_state["wave_actor_ids"]):
                fight.apply_damage(7, uid, fight.actors[uid].hp)
            self.assertEqual(
                fight.rift_wave_state["pending_wave"]["completed_wave"], wave - 1
            )
            sources = next_roster(fight, fight.rift_wave_state["pending_wave"])
            fight.rift_monsters.update({row["id"]: row for row in sources})

            def initialize_wave(current, actors, monsters):
                runtime, outbox = component.factory(current)
                ids = tuple(actor.id for actor in actors)
                with current.effect_resolution():
                    self.assertTrue(
                        install_wave_state(runtime, actor_ids=ids, wave=wave)
                    )
                    self.assertFalse(
                        install_wave_state(runtime, actor_ids=ids, wave=wave)
                    )
                return tuple(outbox)

            births = install_native_wave(
                fight,
                sources,
                initialize_actor=lambda current, actor, source: (),
                initialize_wave=initialize_wave,
            )
            self.assertEqual(sum(opcode == 13091 for opcode, _ in births), 2)
            self.assertEqual(fight.rift_wave_state["wave"], wave)
            ids = tuple(fight.rift_wave_state["wave_actor_ids"])
            history.append((wave, ids))
            for uid in ids:
                self.assertEqual(fight.actors[uid].team, roles.npc_team)
                self.assertEqual(
                    [
                        entry.level
                        for entry in fight.actors[uid].state_ledger.entries
                        if entry.reference == 6807
                    ],
                    [wave],
                )
                self.assertEqual(
                    fight.rift_wave_state["native_wave_entries"][str(uid)]["wave"], wave
                )
        fourth_hp = fight.actors[history[-1][1][0]].max_hp
        self.assertGreater(fourth_hp, first_hp)
        self.assertEqual(
            [
                entry.level
                for entry in fight.actors[-200].state_ledger.entries
                if entry.reference == 6807
            ],
            [1],
        )

        # Real achievement adapter uses canonical durable binding loader and
        # actual reward source validation. Only database transport is replaced.
        run = dict(
            instance_id=1,
            fight_id=fight.id,
            status="won",
            members=[7],
            completed_waves=3,
            defeated_monsters=6,
            wave=4,
            catalog=deepcopy(fight.rift_wave_state["catalog"]),
            policy=deepcopy(fight.rift_wave_state["policy"]),
            seed="native-component",
        )
        result = dict(outcome="won", turn=40, completed_waves=3, defeated_monsters=6)
        receipt = dict(outcome="won", result=result)
        rosters = [
            dict(wave=wave, actor_ids=sorted(ids), species_refs=[5525, 5525])
            for wave, ids in history
        ]

        def execute(query, params):
            if "rift_settlement_receipts" in query:
                return SimpleNamespace(fetchone=lambda: receipt)
            if "rift_wave_rosters" in query:
                self.assertIn("wave,actor_ids,species_refs", query)
                return SimpleNamespace(fetchall=lambda: rosters)
            if "rift_wave_actor_bindings" in query:
                ids = history[params[1] - 1][1]
                values = [
                    dict(ordinal=i, actor_id=uid, species_reference=5525)
                    for i, uid in enumerate(ids)
                ]
                return SimpleNamespace(fetchall=lambda: values)
            raise AssertionError("Unexpected achievement query/mutation: " + query)

        db = SimpleNamespace(
            info=SimpleNamespace(transaction_status=TransactionStatus.INTRANS),
            execute=execute,
        )
        fight.phase, fight.winner = "finished", roles.player_team
        with patch("wakfu_server.rift_runtime._run", return_value=run):
            facts = load_locked(db, fight, component.characters[7], (7,))
            self.assertEqual(len(facts), 6)
            self.assertEqual(
                {row["id"] for row in facts},
                {uid for _, ids in history[:-1] for uid in ids},
            )
            self.assertEqual(
                load_locked(db, fight, component.characters[7], (7,)), facts
            )
            fight.winner = roles.npc_team
            with self.assertRaisesRegex(ValueError, "survival or progress"):
                load_locked(db, fight, component.characters[7], (7,))
            run["status"] = receipt["outcome"] = result["outcome"] = "lost"
            self.assertEqual(load_locked(db, fight, component.characters[7], (7,)), ())
        self.assertEqual(component.fight.rift_wave_state["wave"], 4)
