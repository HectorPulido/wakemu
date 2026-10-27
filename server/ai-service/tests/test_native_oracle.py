"""Actor-complete native oracle tests; no world wiring or client packets."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[3]
for _path in (str(_ROOT / "server"), str(_ROOT / "server" / "tests")):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from wakfu_ai.context.native_context import NativeGraph
from wakfu_ai.native.native_oracle import NativeOracle
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_state import Actor, Fight


class NativeOracleTests(unittest.TestCase):
    def test_live_boundary_executes_injured_tofu_owned_internal_trigger(self):
        self._assert_injured_tofu_owned_internal_trigger(704, 14)

    def test_live_boundary_executes_dominant_tofu_owned_internal_trigger(self):
        self._assert_injured_tofu_owned_internal_trigger(4092, 18)

    def _assert_injured_tofu_owned_internal_trigger(self, reference, level):
        import struct
        from wakfu_server.combat_triggered_spell import (
            triggered_spell_plan,
            consume_triggered_costs,
        )
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_server_spell import prepare_server_initialization
        from wakfu_server.spells import default_deck

        fixture = self.wonejo_fixture(monster_ref=reference, monster_level=level)
        # wonejo_fixture already runs initialize_fight_snapshots, including
        # the real ordinary NPC constructor and initial-state installation.
        self.assertTrue(
            fixture.fight.native_npc_initialization_receipts[fixture.npc.id][
                "initialized"
            ]
        )
        self.assertTrue(
            any(entry.reference == 4412 for entry in fixture.npc.state_ledger.entries)
        )
        deck = default_deck(fixture.character)
        # Complete actual class/equipment/start lifecycle before delivering a
        # turn callback; constructor installation alone is not fight start.
        fixture.fight, _ = prepare_server_initialization(
            fixture.character,
            {fixture.npc.id: fixture.monster},
            fixture.fight,
            fixture.character["account_id"],
            deck,
            action_id=1,
            fight_start=True,
        )
        fixture.pc = fixture.fight.actors[fixture.pc.id]
        fixture.npc = fixture.fight.actors[fixture.npc.id]
        self.assertTrue(fixture.fight.native_start_event_delivered)
        # Reconstruct the incident's native start-boundary prerequisites: alive,
        # below half HP, at least two AP and an adjacent hostile fighter.
        set_hp_raw_current(fixture.npc, min(49, fixture.npc.max_hp // 2))
        fixture.fight.order = [fixture.npc.id, fixture.pc.id]
        fixture.fight.turn_index = 0
        fixture.npc.turn_count = 1
        runtime = RuntimeMessages(fixture.fight)
        oracle = self.oracle_for(
            runtime,
            fixture.character,
            fixture.monster,
            deck,
        )
        before = self.effects(fixture.fight)
        # Importing dependency definitions does not grant helper ownership to
        # ordinary NPC casts; this spell remains reachable only by its state.
        with self.assertRaisesRegex(ValueError, "does not own requested spell"):
            oracle.cast(
                runtime,
                dict(
                    type="cast",
                    spellId=5795,
                    level=level,
                    targetId=fixture.pc.id,
                    target=list(fixture.pc.position),
                ),
            )
        plans, payments = [], []

        def observe_plan(*args, **kwargs):
            plan = triggered_spell_plan(*args, **kwargs)
            plans.append(copy.deepcopy(plan))
            return plan

        def observe_payment(actor, plan, **kwargs):
            prior = (actor.ap, actor.mp, actor.effect_stats[4])
            result = consume_triggered_costs(actor, plan, **kwargs)
            after = (actor.ap, actor.mp, actor.effect_stats[4])
            payments.append((prior, after, copy.deepcopy(plan["costs"])))
            return result

        # Observe real producers; execute their original implementations and
        # native data, without substituting a book, rule, cost or effect.
        with patch(
            "wakfu_server.combat_triggered_spell.triggered_spell_plan",
            side_effect=observe_plan,
        ), patch(
            "wakfu_server.combat_triggered_spell.consume_triggered_costs",
            side_effect=observe_payment,
        ):
            candidate, packets = oracle.live_start_boundary(
                fixture.fight, actor_id=fixture.npc.id, action_id=7
            )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0]["spell_id"], 5795)
        self.assertEqual(plans[0]["evaluation_level"], level)
        self.assertEqual(plans[0]["effect_ids"], (183331,))
        self.assertEqual(len(payments), 1)
        prior, after, costs = payments[0]
        self.assertEqual(
            tuple(a - b for a, b in zip(prior, after)),
            (costs["ap"], costs["mp"], costs["wp"]),
        )
        self.assertNotEqual(
            candidate.actors[fixture.npc.id].position, fixture.npc.position
        )
        self.assertEqual(candidate.actors[fixture.pc.id].hp, fixture.pc.hp)
        # Native state4412/root183304 invokes eYZ183305 -> spell5795. The
        # resulting movement/cost/packet proves the reaction actually executed.
        self.assertNotEqual(self.effects(candidate), before)
        self.assertTrue(packets)
        self.assertTrue(
            any(
                opcode == 12613
                and len(payload) >= 19
                and struct.unpack(">iiiBih", payload[:19])[4] == 426
                for opcode, payload in packets
            )
        )
        self.assertEqual(self.effects(fixture.fight), before)

    def test_factory_preserves_owned_npc_books_for_published_turn_boundaries(self):
        import random
        from wakfu_server.combat_npc_spellbook import ordinary_npc_spellbook
        from wakfu_server.combat_spell_level import NativeSpellBook
        from wakfu_server.combat_triggered_spell import (
            InternalTriggeredAbility,
            NativeTriggeredSpellRequest,
            triggered_spell_level,
        )
        from wakfu_server.spells import default_deck

        # The live tofu incident and a different NPC both use the same provider.
        for reference, level in ((704, 14), (5525, 1)):
            with self.subTest(reference=reference):
                fixture = self.wonejo_fixture(
                    monster_ref=reference, monster_level=level
                )
                runtime = RuntimeMessages(fixture.fight)
                oracle = self.oracle_for(
                    runtime,
                    fixture.character,
                    fixture.monster,
                    default_deck(fixture.character),
                )
                factory, adapter = oracle.factory(fixture.fight, 1, random.Random(7))
                self.assertIs(
                    adapter.actor_authority.ordinary.npc_spellbook,
                    ordinary_npc_spellbook,
                )
                with patch(
                    "wakfu_server.monsters.native_abilities",
                    return_value=[dict(spell_id=123, spell_level=level)],
                ) as abilities:
                    native = factory.displacement_authority(fixture.fight, fixture.npc)
                    self.assertIsInstance(native.native_spellbook, NativeSpellBook)
                    self.assertIs(native.native_spellbook.player_character, False)
                    self.assertEqual(native.native_spellbook.level(123), level)
                    request = NativeTriggeredSpellRequest(
                        123, fixture.npc.id, fixture.npc.position, False
                    )
                    self.assertEqual(triggered_spell_level(request, native), level)
                    helper = NativeTriggeredSpellRequest(
                        124, fixture.npc.id, fixture.npc.position, False
                    )
                    self.assertEqual(
                        triggered_spell_level(
                            helper, native, InternalTriggeredAbility(183305, 124, 100)
                        ),
                        level,
                    )
                    abilities.assert_called_once_with(reference, level)
                    player = factory.displacement_authority(fixture.fight, fixture.pc)
                    self.assertIs(player.native_spellbook.player_character, True)
                    abilities.assert_called_once()

    def test_lethal_npc_commit_delivers_death_and_failed_delivery_is_atomic(self):
        import struct
        from wakfu_ai.context.native_context import encode
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.spells import default_deck

        def setup():
            fixture = self.wonejo_fixture()
            # A genuinely injured target; death is produced by native 7962.
            set_hp_raw_current(fixture.pc, 1)
            runtime = RuntimeMessages(fixture.fight)
            oracle = self.oracle_for(
                runtime,
                fixture.character,
                fixture.monster,
                default_deck(fixture.character),
            )
            action = dict(
                type="cast",
                spellId=7962,
                level=1,
                targetId=fixture.pc.id,
                target=list(fixture.pc.position),
            )
            return runtime, oracle, action, fixture.pc.id

        runtime, oracle, action, target_id = setup()
        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            packets = oracle.commit(action, stats_serializer=lambda *args: b"")
        deaths = [
            struct.unpack(">iiiqB", body)[3:]
            for opcode, body in packets
            if opcode == 12727
        ]
        # Ordinary player victims retain reversible KO and their native QI slot.
        self.assertEqual(deaths, [(target_id, 0)])
        target = runtime.fight.actors[target_id]
        self.assertTrue(target.controlled)
        self.assertIsNone(getattr(target, "native_summon_source", None))
        from wakfu_server.combat_global_pv_collections import global_fighter_guards
        from wakfu_server.combat_qi_fight import current_registry

        self.assertEqual(
            global_fighter_guards(runtime.fight, target_id),
            dict(baF=False, baG=True, baK=False),
        )
        self.assertEqual(
            current_registry(runtime.fight).slots[target.native_obstacle_id][
                "identity"
            ],
            ["actor", target_id],
        )
        self.assertEqual(runtime.fight.actors[target_id].hp, 0)
        self.assertIn(target_id, runtime._reported_deaths)

        runtime, oracle, action, _ = setup()
        before = encode(runtime)
        with patch(
            "wakfu_server.combat_los.authoritative_visible", return_value=True
        ), patch(
            "wakfu_server.combat_death.death_messages",
            side_effect=ValueError("fixture death serialization failure"),
        ):
            with self.assertRaisesRegex(ValueError, "death serialization failure"):
                oracle.commit(action, stats_serializer=lambda *args: b"")
        self.assertEqual(encode(runtime), before)

    def test_npc_casting_root_prerequisite_is_exact_and_fail_open(self):
        oracle = object.__new__(NativeOracle)
        actor_id = -77
        oracle.characters = {}
        oracle.monsters = {actor_id: {"id": actor_id}}
        oracle.owned_spells = lambda fight, identity: {
            100: 1,
            200: 0,
            300: 1,
        }
        fight = SimpleNamespace(
            actors={actor_id: SimpleNamespace(id=actor_id, hp=20)},
            native_summon_registrations={},
            sequence=13,
        )
        casting = {
            "100": {
                "levels": [[1, 0, [81, 82]]],
                # Conditional target/range data does not change the baseline
                # roots selected by NativeOracle.cast.
                "conditional": [{"levels": [[2, 0, [999]]]}],
            },
            "300": {"levels": [[1, 0, [83]]]},
        }
        roots = {
            "roots": {
                "81": {"native_casting_collision_area": None},
                "83": {"native_casting_collision_area": None},
            }
        }
        with patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value=casting,
        ), patch(
            "wakfu_server.combat_casting_context.casting_root_catalog",
            return_value=roots,
        ):
            result = oracle.native_casting_root_prerequisites(
                fight, actor_id, "state-13"
            )

        self.assertEqual(
            result,
            dict(
                schema="native-casting-root-prerequisites-v1",
                sourceState="state-13",
                actorId=actor_id,
                stateRevision=13,
                complete=True,
                unavailable=[
                    dict(
                        spellId=100,
                        level=1,
                        reason="missing_root_metadata",
                        missingRootIds=[82],
                    )
                ],
            ),
        )
        oracle.characters = {actor_id: {"id": actor_id}}
        self.assertIsNone(
            oracle.native_casting_root_prerequisites(fight, actor_id, "state-13")
        )

    def test_npc_casting_root_prerequisite_omits_unknown_rows_fail_open(self):
        oracle = object.__new__(NativeOracle)
        actor_id = -78
        oracle.characters = {}
        oracle.monsters = {actor_id: {"id": actor_id}}
        oracle.owned_spells = lambda fight, identity: {400: 1}
        fight = SimpleNamespace(
            actors={actor_id: SimpleNamespace(id=actor_id, hp=20)},
            native_summon_registrations={},
            sequence=14,
        )
        with patch(
            "wakfu_server.combat_native_spell_casting.catalog",
            return_value={"400": {"levels": "future-schema"}},
        ), patch(
            "wakfu_server.combat_casting_context.casting_root_catalog",
            return_value={"roots": {"1": {}}},
        ):
            result = oracle.native_casting_root_prerequisites(
                fight, actor_id, "state-14"
            )

        self.assertEqual(result["unavailable"], [])
        self.assertIs(result["complete"], True)

    def test_native_search_selects_back_route_only_for_real_damage_gain(self):
        from wakfu_ai.context.native_context import encode
        from wakfu_ai.planning.query_search import search
        from test_native_session import StubTransport
        from wakfu_ai.bridge.world_bridge import NativeSession
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.spells import default_deck

        fixture = self.wonejo_fixture()
        fixture.pc.direction = 1
        # This isolated positioning fixture configures four MP in a complete PA
        # snapshot. MP is characteristic3; characteristic2 is AP. Keep raw,
        # effective and actor views coherent instead of corrupting AP.
        fixture.npc.mp = fixture.npc.max_mp = 4
        fixture.npc.effect_stats[3] = 4
        fixture.npc.effect_resource_raw_currents[3] = 4
        fixture.npc.effect_base_maxima[3] = 4
        fixture.npc.effect_maxima[3] = 4
        fixture.npc.effect_percentages[3] = 0
        # Native ffh16 is rear mastery (equipment_damage.damage). At
        # level1 the unmodified spell rounds SIDE and BACK to the same six
        # damage, so spending two extra MP correctly favors SIDE. Give this
        # isolated PA fixture explicit rear mastery to test a real BACK gain.
        fixture.npc.effect_stats[16] = 100
        route = [
            (-7, -7, -1),
            (-7, -6, -1),
            (-8, -6, -1),
            (-9, -6, -1),
            (-9, -7, -1),
        ]
        fixture.fight.walkable = set(route) | {fixture.pc.position}
        fixture.fight.edges = set(zip(route, route[1:])) | set(zip(route[1:], route))
        freeze_terrain(fixture.fight)
        runtime = RuntimeMessages(fixture.fight)
        oracle = self.oracle_for(
            runtime, fixture.character, fixture.monster, default_deck(fixture.character)
        )
        transport = StubTransport()
        session = NativeSession(
            oracle,
            transport,
            None,
            policy=dict(limits=dict(depth=2, beam=12, nodes=256, budgetMs=10000)),
            policy_version="native-flank-test",
            fight_instance_id="native-flank-test",
        )
        envelope = session.envelope()
        # Isolate positioning/cast utility; rival projection has its own corpus.
        envelope["operations"] = [
            name for name in envelope["operations"] if name != "project_turn"
        ]
        store = type("Store", (), {"json": lambda _, key: transport.graphs[key]})()
        before = encode(runtime)
        coroutine = search(envelope, store)
        request = next(coroutine)
        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            front, _, _ = oracle.preview(
                runtime,
                dict(
                    type="cast",
                    spellId=7962,
                    level=1,
                    targetId=fixture.pc.id,
                    target=list(fixture.pc.position),
                ),
            )
            while True:
                try:
                    request = coroutine.send(session.query(request))
                except StopIteration as completed:
                    decision = completed.value
                    break
        self.assertEqual(decision["plan"][0]["type"], "move")
        selected_path = [tuple(cell) for cell in decision["plan"][0]["path"]]
        self.assertTrue(selected_path)
        self.assertIn(selected_path[-1], route[1:])
        self.assertLessEqual(len(selected_path), fixture.npc.mp)
        movement = [fixture.npc.position, *selected_path]
        self.assertTrue(
            all(
                origin == target or (origin, target) in fixture.fight.edges
                for origin, target in zip(movement, movement[1:])
            )
        )
        # Keep the complete corridor frontier available before casting.
        # The objective is a native BACK cast with strictly greater actual
        # damage, not a particular equally valid flank coordinate.
        self.assertEqual(decision["plan"][1]["type"], "cast")
        self.assertGreater(
            decision["components"]["damage"],
            fixture.pc.hp - front.fight.actors[fixture.pc.id].hp,
        )
        self.assertEqual(
            decision["orientationEvidence"][-1]["arithmeticLocalization"], "BACK"
        )
        self.assertEqual(encode(runtime), before)
        session.guard()

    def test_real_native_damage_observation_preserves_state_packets_and_source(self):
        from wakfu_ai.native.native_damage_observer import evidence, current
        from wakfu_ai.context.native_context import encode
        from wakfu_server.spells import default_deck

        fixture = self.wonejo_fixture()
        fixture.pc.direction = 5
        runtime = RuntimeMessages(fixture.fight)
        oracle = self.oracle_for(
            runtime, fixture.character, fixture.monster, default_deck(fixture.character)
        )
        action = dict(
            type="cast",
            spellId=7962,
            level=1,
            targetId=fixture.pc.id,
            target=list(fixture.pc.position),
        )
        before = encode(runtime)
        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            ordinary, packets, transaction = oracle.preview(runtime, action)
            (
                observed,
                observed_packets,
                observed_tx,
                samples,
            ) = oracle.preview_with_evidence(runtime, action)
        self.assertEqual(self.effects(ordinary.fight), self.effects(observed.fight))
        self.assertEqual(packets, observed_packets)
        self.assertEqual(
            oracle.state_identity(ordinary), oracle.state_identity(observed)
        )
        self.assertEqual(transaction.outcomes, observed_tx.outcomes)
        self.assertEqual(encode(runtime), before)
        self.assertIsNone(current())
        rows = evidence(samples)
        self.assertTrue(rows)
        self.assertTrue(all(row["observedLocalization"] == "BACK" for row in rows))
        self.assertTrue(all(row["targetId"] == fixture.pc.id for row in rows))
        self.assertTrue(
            all(
                row["arithmeticLocalization"] == "FRONT"
                for row in rows
                if not row["localizationEnabled"]
            )
        )

    @classmethod
    def setUpClass(cls):
        # One warmup in this process; real cast cases share the immutable cache.
        from wakfu_server.combat_server_spell import prewarm_runtime_catalogs

        prewarm_runtime_catalogs()

    @staticmethod
    def wonejo_fixture(
        *,
        compact=False,
        terrain_effect_id=46,
        map_id=1134,
        player_position=(-8, -7, -1),
        monster_position=(-7, -7, -1),
        monster_ref=5525,
        monster_level=1,
    ):
        from tests.test_combat_npc_attack import NativeNpcAttackTests
        from wakfu_server.combat_actor_snapshot import initialize_fight_snapshots
        from wakfu_server.combat_bootstrap import create_placement
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.monsters import owned_instance

        fixture = NativeNpcAttackTests()
        fixture.setUp()
        character = dict(fixture.character)
        character.update(
            map_id=map_id,
            instance_id=0,
            x=player_position[0],
            y=player_position[1],
            z=player_position[2],
            active_build_index=0,
        )
        monster = owned_instance(
            monster_ref,
            monster_level,
            fixture.npc.id,
            map_id=map_id,
            x=monster_position[0],
            y=monster_position[1],
            z=monster_position[2],
            instance_id=0,
        )
        # Preserve the adjacent casting fixture; the default live arena policy
        # may spread opponents to a different native cell.
        terrain = local_arena(
            map_id,
            77,
            player_position,
            monster_position,
            relocate_monsters=False,
            compact=compact,
        )
        fight, _ = create_placement(
            character,
            monster,
            terrain,
            fight_id=77,
            player_ap=6,
            player_mp=3,
            player_wp=6,
            player_initiative=fixture.pc.initiative,
            terrain_effect_id=terrain_effect_id,
            terrain_instance_id=-300,
        )
        initialize_fight_snapshots(
            fight,
            characters={character["id"]: character},
            monsters={monster["id"]: monster},
            wp_resources={7: (6, 6), fixture.npc.id: (monster["wp"], monster["wp"])},
            running_effects={7: (), fixture.npc.id: ()},
            initial_effect_uid=1,
        )
        fight.ready(character["account_id"])
        fixture.character = character
        fixture.monster = monster
        fixture.fight = fight
        fixture.pc = fight.actors[character["id"]]
        fixture.npc = fight.actors[monster["id"]]
        return fixture

    @staticmethod
    def oracle_for(runtime, character, monster, deck, *, flags=None):
        return NativeOracle(
            runtime,
            characters={character["id"]: character},
            monsters={monster["id"]: monster},
            decks={character["id"]: deck},
            excluded_decks={character["id"]: frozenset()},
            viewer_id=character["id"],
            flags=flags or {},
        )

    @staticmethod
    def effects(fight):
        return {
            "actors": {
                identity: (
                    actor.hp,
                    actor.ap,
                    actor.mp,
                    None if actor.effect_stats is None else dict(actor.effect_stats),
                    actor.position,
                    getattr(actor, "direction", None),
                )
                for identity, actor in fight.actors.items()
            },
            "usage": copy.deepcopy(fight.native_spell_usage),
            "events": copy.deepcopy(fight.events),
        }

    def test_authority_requires_all_pc_and_npc_sources_and_decks(self):
        from wakfu_server.spells import default_deck

        pc1 = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 9, True)
        pc2 = Actor(8, 0, (2, 0, 0), 60, 6, 3, 9, 1, 10, True)
        npc = Actor(-7, 1, (1, 0, 0), 20, 4, 3, 8, 1)
        cells = {(x, 0, 0) for x in range(3)}
        fight = Fight(
            77, [pc1, pc2, npc], cells, {0: {(0, 0, 0), (2, 0, 0)}, 1: {(1, 0, 0)}}
        )
        fight.ready(9)
        fight.ready(10)
        runtime = RuntimeMessages(fight)
        chars = {
            7: dict(id=7, breed=15, level=1, account_id=9),
            8: dict(id=8, breed=15, level=1, account_id=10),
        }
        decks = {identity: default_deck(char) for identity, char in chars.items()}
        monsters = {-7: dict(id=-7, ref=5525, level=1, map_id=1134)}
        oracle = NativeOracle(
            runtime,
            characters=chars,
            monsters=monsters,
            decks=decks,
            excluded_decks={7: frozenset(), 8: frozenset()},
            viewer_id=7,
            flags={},
        )
        self.assertEqual(set(oracle.authorities()["characters"]), {7, 8})
        self.assertEqual(set(oracle.authorities()["decks"]), {7, 8})

        with self.assertRaisesRegex(ValueError, "complete character/deck"):
            NativeOracle(
                runtime,
                characters=chars,
                monsters=monsters,
                decks={7: decks[7]},
                excluded_decks={7: frozenset()},
                viewer_id=7,
                flags={},
            )
        with self.assertRaisesRegex(ValueError, "Incomplete encounter actor authority"):
            NativeOracle(
                runtime,
                characters={7: chars[7]},
                monsters=monsters,
                decks={7: decks[7]},
                excluded_decks={7: frozenset()},
                viewer_id=7,
                flags={},
            )

    def test_registered_creature_ownership_wire_and_supported_lifecycle_are_explicit(
        self,
    ):
        import random
        import struct
        from wakfu_ai.context.native_context import encode
        from wakfu_ai.native.native_stats import NativeStats
        from wakfu_server.spells import default_deck
        from wakfu_server.combat_summon import SummonSpecification
        from wakfu_server.combat_summon_creation import NativeSummonBuilder

        fixture = self.wonejo_fixture()
        fight = fixture.fight
        summon_cell = next(
            cell
            for cell in sorted(fight.walkable)
            if cell not in {fixture.pc.position, fixture.npc.position}
            and abs(cell[0] - fixture.npc.position[0])
            + abs(cell[1] - fixture.npc.position[1])
            == 1
        )
        fight.order, fight.turn_index = [fixture.npc.id, fixture.pc.id], 0
        runtime = RuntimeMessages(fight)
        oracle = self.oracle_for(
            runtime, fixture.character, fixture.monster, default_deck(fixture.character)
        )
        _, adapter = oracle.factory(fight, 1, random.Random(1))
        authority = adapter.actor_authority
        actor, registration = NativeSummonBuilder(authority)(
            fight,
            SummonSpecification(5528, 1, False, 3, 1, "caster", 1),
            fixture.npc.id,
            901,
            summon_cell,
        )
        authority.register(
            fight,
            actor,
            registration,
            new_order=[fixture.npc.id, 901, fixture.pc.id],
            new_turn_index=0,
        )
        fight.turn_index = 1
        actor.turn_count = 1
        before = encode(runtime)
        self.assertEqual(oracle.owned_spells(fight), {7988: 1})
        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            private, packets, transaction = oracle.preview(
                runtime,
                dict(
                    type="cast",
                    spellId=7988,
                    level=1,
                    targetId=fixture.pc.id,
                    target=list(fixture.pc.position),
                ),
            )
        self.assertEqual(transaction.outcomes, (True,))
        self.assertEqual(private.fight.actors[actor.id].ap, actor.ap - 3)
        self.assertEqual(
            private.fight.native_summon_registrations[actor.id],
            fight.native_summon_registrations[actor.id],
        )
        self.assertTrue(packets)
        # Registered ownership remains available to the wire serializer after
        # the now-supported native lifecycle executes in a private preview.
        from wakfu_server.combat_spells import cast_animation

        wire = cast_animation(
            fight.id,
            1,
            oracle.descriptor(fight, actor),
            7988,
            (0, 0, 0),
            native_uid=7988,
            native_level=1,
        )
        self.assertEqual(struct.unpack_from(">q", wire, 12)[0], 901)
        self.assertEqual(struct.unpack_from(">qih", wire, 20), (7988, 7988, 1))
        serializer = NativeStats(
            characters=oracle.characters,
            monsters=oracle.monsters,
            fight_id=fight.id,
            registrations=fight.native_summon_registrations,
            map_id=fixture.character["map_id"],
        )
        self.assertEqual(
            struct.unpack_from(
                ">q", serializer(actor, fight), len(serializer(actor, fight)) - 20
            )[0],
            901,
        )
        self.assertEqual(encode(runtime), before)

    def test_registered_creature_ownership_wire_and_state_lifecycle_are_explicit(
        self,
    ):
        import random
        import struct
        from wakfu_ai.context.native_context import encode
        from wakfu_ai.native.native_stats import NativeStats
        from wakfu_server.spells import default_deck
        from wakfu_server.combat_summon import SummonSpecification
        from wakfu_server.combat_summon_creation import NativeSummonBuilder

        fixture = self.wonejo_fixture()
        fight = fixture.fight
        summon_cell = next(
            cell
            for cell in sorted(fight.walkable)
            if cell not in {fixture.pc.position, fixture.npc.position}
            and abs(cell[0] - fixture.npc.position[0])
            + abs(cell[1] - fixture.npc.position[1])
            == 1
        )
        fight.order, fight.turn_index = [fixture.npc.id, fixture.pc.id], 0
        runtime = RuntimeMessages(fight)
        oracle = self.oracle_for(
            runtime, fixture.character, fixture.monster, default_deck(fixture.character)
        )
        _, adapter = oracle.factory(fight, 1, random.Random(1))
        authority = adapter.actor_authority
        actor, registration = NativeSummonBuilder(authority)(
            fight,
            SummonSpecification(5528, 1, False, 3, 1, "caster", 1),
            fixture.npc.id,
            901,
            summon_cell,
        )
        authority.register(
            fight,
            actor,
            registration,
            new_order=[fixture.npc.id, 901, fixture.pc.id],
            new_turn_index=0,
        )
        fight.turn_index = 1
        actor.turn_count = 1
        before = encode(runtime)
        self.assertEqual(oracle.owned_spells(fight), {7988: 1})
        action = dict(
            type="cast",
            spellId=7988,
            level=1,
            targetId=fixture.pc.id,
            target=list(fixture.pc.position),
        )
        before_ap = actor.ap
        before_stat = fixture.pc.effect_stats.get(27, 0)
        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            private, packets, transaction = oracle.preview(runtime, action)
        self.assertEqual(transaction.outcomes, (True,))
        target = private.fight.actors[fixture.pc.id]
        self.assertEqual(target.effect_stats[27], before_stat - 50)
        self.assertTrue(
            any(
                entry.reference == 8030 and entry.level == 50 and entry.duration == 2
                for entry in target.state_ledger.entries
            )
        )
        caster = private.fight.actors[actor.id]
        self.assertEqual(caster.ap, before_ap - 3)
        self.assertEqual(caster.effect_resource_raw_currents[2], caster.ap)
        self.assertEqual(caster.effect_stats[2], caster.ap)
        self.assertEqual(
            private.fight.native_summon_registrations[901],
            fight.native_summon_registrations[901],
        )
        self.assertEqual([opcode for opcode, _ in packets[:2]], [12588, 12678])
        self.assertTrue(
            any(event["kind"] == "state_applied" for event in transaction.events)
        )
        self.assertEqual(encode(runtime), before)
        # A failure after private spending and effect dispatch cannot leak state.
        with patch(
            "wakfu_server.combat_los.authoritative_visible", return_value=True
        ), patch(
            "wakfu_server.combat_spells.cast_animation",
            side_effect=ValueError("codec failure"),
        ):
            with self.assertRaisesRegex(ValueError, "codec failure"):
                oracle.preview(runtime, action)
        self.assertEqual(encode(runtime), before)
        from wakfu_server.combat_spells import cast_animation

        wire = cast_animation(
            fight.id,
            1,
            oracle.descriptor(fight, actor),
            7988,
            (0, 0, 0),
            native_uid=7988,
            native_level=1,
        )
        self.assertEqual(struct.unpack_from(">q", wire, 12)[0], 901)
        self.assertEqual(struct.unpack_from(">qih", wire, 20), (7988, 7988, 1))
        serializer = NativeStats(
            characters=oracle.characters,
            monsters=oracle.monsters,
            fight_id=fight.id,
            registrations=fight.native_summon_registrations,
            map_id=fixture.character["map_id"],
        )
        self.assertEqual(
            struct.unpack_from(
                ">q", serializer(actor, fight), len(serializer(actor, fight)) - 20
            )[0],
            901,
        )
        self.assertEqual(encode(runtime), before)

    def test_npc_oracle_selects_import_catalog_per_owned_actor_and_spell(self):
        from wakfu_server.combat_npc_attack import (
            npc_runtime_catalog,
            npc_spell_catalog,
        )
        from wakfu_server.spells import default_deck

        fixture = self.wonejo_fixture()
        runtime = RuntimeMessages(fixture.fight)
        oracle = self.oracle_for(
            runtime, fixture.character, fixture.monster, default_deck(fixture.character)
        )
        original = npc_spell_catalog()
        action = dict(
            type="cast",
            spellId=7962,
            level=1,
            targetId=fixture.pc.id,
            target=list(fixture.pc.position),
        )
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                document = dict(
                    original,
                    baseline_effects=original["effects"],
                    activation_policy={
                        "schema": "native-npc-activation-v1",
                        "legacy_spell_ids": [7962],
                        "enabled_monsters": {
                            "5525": {
                                "min_level": 1,
                                "max_level": 1,
                                "spell_ids": [7962],
                            }
                        }
                        if enabled
                        else {},
                    },
                )
                npc_runtime_catalog.cache_clear()
                try:
                    with patch(
                        "wakfu_server.combat_npc_attack.npc_spell_catalog",
                        return_value=document,
                    ), patch(
                        "wakfu_server.combat_npc_attack.npc_runtime_catalog",
                        wraps=npc_runtime_catalog,
                    ) as compiled, patch(
                        "wakfu_server.combat_los.authoritative_visible",
                        return_value=True,
                    ):
                        private, _, tx = oracle.preview(runtime, action)
                    compiled.assert_called_once_with(imported=enabled)
                    self.assertEqual(tx.outcomes, (True,))
                    self.assertEqual(
                        private.fight.actors[fixture.pc.id].hp, fixture.pc.hp - 5
                    )
                    self.assertIn(7962, oracle.owned_spells(runtime.fight))
                finally:
                    npc_runtime_catalog.cache_clear()

    def test_complete_state_retains_future_fields_and_aliases(self):
        from wakfu_server.spells import default_deck

        fixture = self.wonejo_fixture()
        runtime = RuntimeMessages(fixture.fight)
        oracle = self.oracle_for(
            runtime, fixture.character, fixture.monster, default_deck(fixture.character)
        )
        shared = {"extension": [1, 2, b"all-bytes"]}
        runtime.future_runtime_field = shared
        runtime.future_fight_alias = fixture.fight
        fixture.fight.future_fight_field = shared
        fixture.fight.future_fight_alias = fixture.fight
        fixture.fight.future_actor_alias = fixture.pc
        fixture.pc.future_actor_field = shared
        fixture.pc.future_fight_alias = fixture.fight

        graph = NativeGraph(json.loads(json.dumps(oracle.complete_state(runtime))))

        self.assertEqual(graph.data["encoding"], "wakfu-native-graph-1")
        runtime_node = next(
            node
            for node in graph.nodes
            if node.get("type") == "object"
            and node.get("name", "").endswith("RuntimeMessages")
            and "future_runtime_field" in node.get("fields", {})
        )
        fight_node = next(
            node
            for node in graph.nodes
            if node.get("type") == "object"
            and node.get("name", "").endswith("Fight")
            and "future_fight_field" in node.get("fields", {})
        )
        actor_node = next(
            node
            for node in graph.nodes
            if node.get("type") == "object"
            and node.get("name", "").endswith("Actor")
            and "future_actor_field" in node.get("fields", {})
        )
        self.assertEqual(
            runtime_node["fields"]["future_runtime_field"],
            fight_node["fields"]["future_fight_field"],
        )
        self.assertEqual(
            actor_node["fields"]["future_actor_field"],
            fight_node["fields"]["future_fight_field"],
        )
        self.assertEqual(
            runtime_node["fields"]["future_fight_alias"],
            fight_node["fields"]["future_fight_alias"],
        )
        self.assertEqual(
            actor_node["fields"]["future_fight_alias"],
            runtime_node["fields"]["future_fight_alias"],
        )

    def test_fork_preserves_absent_lifecycle_callbacks(self):
        from wakfu_server.spells import default_deck

        fixture = self.wonejo_fixture()
        runtime = RuntimeMessages(fixture.fight)
        self.assertIsNone(runtime.turn_start_provider)
        self.assertIsNone(runtime.turn_end_provider)
        oracle = self.oracle_for(
            runtime, fixture.character, fixture.monster, default_deck(fixture.character)
        )

        private = oracle.fork(runtime=runtime)

        self.assertIsNone(private.turn_start_provider)
        self.assertIsNone(private.turn_end_provider)

    def test_fork_missing_optional_pa_helper_falls_back_without_hiding_import_errors(
        self,
    ):
        import builtins

        runtime = SimpleNamespace(
            fight=None,
            pending=[(13078, b"pending")],
            awaiting_ack=7,
            turn_start_provider=None,
            turn_end_provider=None,
            stats_serializer=None,
            runtime_stats_serializer=None,
        )
        oracle = NativeOracle.__new__(NativeOracle)
        oracle.runtime = runtime
        original_import = builtins.__import__

        def import_with(error):
            def guarded(name, *args, **kwargs):
                if name == "wakfu_server.combat_preview_copy":
                    raise error
                return original_import(name, *args, **kwargs)

            return guarded

        missing = ModuleNotFoundError(
            "Optional helper absent", name="wakfu_server.combat_preview_copy"
        )
        with patch("builtins.__import__", side_effect=import_with(missing)):
            private = oracle.fork(runtime=runtime)
        self.assertIsNot(private, runtime)
        self.assertIsNot(private.pending, runtime.pending)
        private.pending.clear()
        self.assertEqual(runtime.pending, [(13078, b"pending")])
        self.assertEqual(private.awaiting_ack, 7)
        self.assertIsNone(private.turn_start_provider)
        self.assertIsNone(private.turn_end_provider)
        for error in (
            ModuleNotFoundError("Broken dependency", name="helper_dependency"),
            ImportError("Broken helper export"),
        ):
            with self.subTest(error=type(error).__name__):
                with patch("builtins.__import__", side_effect=import_with(error)):
                    with self.assertRaises(type(error)) as caught:
                        oracle.fork(runtime=runtime)
                self.assertIs(caught.exception, error)

    def test_npc_native_oracle_matches_existing_native_spell_preview(self):
        from wakfu_server.combat_tactical_ai import NativeProvider
        from wakfu_server.spells import default_deck

        fixture = self.wonejo_fixture()
        runtime = RuntimeMessages(fixture.fight)
        deck = default_deck(fixture.character)
        oracle = self.oracle_for(runtime, fixture.character, fixture.monster, deck)
        provider = NativeProvider(
            fixture.character, {fixture.npc.id: fixture.monster}, deck
        )
        action = {
            "type": "cast",
            "spellId": 7962,
            "level": 1,
            "targetId": fixture.pc.id,
            "target": list(fixture.pc.position),
        }
        before = self.effects(runtime.fight)

        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            native, native_packets, native_tx = oracle.preview(runtime, action)
            tactical = provider.preview(
                runtime.fight, action, runtime.action_id + 1, forecast=True
            )

        self.assertEqual(self.effects(native.fight), self.effects(tactical.fight))
        self.assertEqual(native_packets, tactical.packets)
        self.assertIsNotNone(native_tx)
        self.assertEqual(self.effects(runtime.fight), before)

    def test_real_pc_cast_uses_own_character_level_deck_and_private_usage(self):
        import random
        from tests.test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.spells import encode_deck

        fixture = SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(2, 19, native_qi=True)
        fight.actors[7].owner_id = 3
        fight.actors[7].position = (-8, -7, -1)
        fight.actors[-7].position = (-6, -7, -1)
        terrain = local_arena(1134, 7, (-8, -7, -1), (-6, -7, -1))
        fight.walkable = terrain["validated_cells"]
        fight.edges = terrain["valid_edges"]
        freeze_terrain(fight)
        fight.order = [7, -7]
        fight.turn_index = 0
        fight.actors[7].turn_count = 1
        runtime = RuntimeMessages(fight)
        deck = encode_deck([7320])
        oracle = self.oracle_for(runtime, character, monster, deck)
        action = {
            "type": "cast",
            "spellId": 7320,
            "level": 19,
            "targetId": -7,
            "target": [-6, -7, -1],
        }
        before = self.effects(fight)

        private, packets, transaction = oracle.preview(runtime, action)

        self.assertLess(private.fight.actors[-7].hp, fight.actors[-7].hp)
        self.assertLess(private.fight.actors[7].ap, fight.actors[7].ap)
        self.assertEqual(
            private.fight.native_spell_usage,
            {
                "7": {
                    "last": {},
                    "turn": 1,
                    "casts": {"7320": 1},
                    "targets": {"7320": {"-7": 1}},
                }
            },
        )
        self.assertEqual(fight.native_spell_usage, before["usage"])
        self.assertIsNotNone(transaction)
        self.assertTrue(packets)
        self.assertEqual(self.effects(fight), before)
        self.assertEqual(oracle.owned_spells(fight), {7320: 19})

        wrong_deck = self.oracle_for(runtime, character, monster, encode_deck([]))
        with self.assertRaisesRegex(ValueError, "does not own|deck|spell"):
            wrong_deck.preview(runtime, action)

    def test_commit_cast_adopts_native_wonejo_damage_and_serializer_failure_rolls_back(
        self,
    ):
        import random
        import struct
        from wakfu_ai.context.native_context import encode
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_terrain import local_arena
        from wakfu_server.spells import encode_deck
        from tests.test_combat_spell_transaction import SpellTransactionTests

        rng_type = random.Random

        class SeededRandom(rng_type):
            def __init__(self, *args, **kwargs):
                super().__init__(1)

        def setup():
            character, monster, fight = SpellTransactionTests().native_server_fixture(
                2, 19, native_qi=True
            )
            monster.update(id=-7, ref=5525, level=1, map_id=1134)
            fight.actors[7].position = (-8, -7, -1)
            fight.actors[-7].position = (-6, -7, -1)
            terrain = local_arena(1134, 7, (-8, -7, -1), (-6, -7, -1))
            fight.walkable = terrain["validated_cells"]
            fight.edges = terrain["valid_edges"]
            freeze_terrain(fight)
            runtime = RuntimeMessages(fight)
            deck = encode_deck([7320])
            oracle = self.oracle_for(runtime, character, monster, deck)
            action = {
                "type": "cast",
                "spellId": 7320,
                "level": 19,
                "targetId": -7,
                "target": [-6, -7, -1],
            }
            return runtime, oracle, action, character, monster, deck

        runtime, oracle, action, character, monster, deck = setup()
        before_hp, before_ap, before_id = (
            runtime.fight.actors[-7].hp,
            runtime.fight.actors[7].ap,
            runtime.action_id,
        )
        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            native = prepare_server_spell(
                struct.pack(">qqiih", 7, (7 << 32) | 7320, -6, -7, -1),
                character,
                {-7: monster},
                runtime.fight,
                3,
                deck,
                action_id=1,
                line_of_sight=lambda *_: True,
                critical=False,
                rng=rng_type(1),
            )
            self.assertLess(native.fight.actors[-7].hp, before_hp)
            with patch(
                "wakfu_ai.native.native_oracle.random.Random",
                new=SeededRandom,
            ):
                packets = oracle.commit(
                    action, stats_serializer=lambda actor, fight: b""
                )
        self.assertTrue(packets)
        self.assertLess(runtime.fight.actors[-7].hp, before_hp)
        self.assertLess(runtime.fight.actors[7].ap, before_ap)
        self.assertEqual(runtime.fight.actors[-7].hp, native.fight.actors[-7].hp)
        self.assertEqual(
            runtime.fight.actors[-7].position, native.fight.actors[-7].position
        )
        self.assertEqual(runtime.action_id, before_id + 1)
        self.assertIsNone(runtime.awaiting_ack)

        runtime, oracle, action, _, _, _ = setup()
        source_before = encode(runtime)

        def failing_serializer(actor, fight):
            raise ValueError("fixture serializer failure")

        with patch("wakfu_server.combat_los.authoritative_visible", return_value=True):
            with self.assertRaisesRegex(ValueError, "fixture serializer failure"):
                with patch(
                    "wakfu_ai.native.native_oracle.random.Random",
                    new=SeededRandom,
                ):
                    oracle.commit(action, stats_serializer=failing_serializer)
        self.assertEqual(encode(runtime), source_before)
        self.assertEqual(runtime.fight.actors[-7].hp, 200)
        self.assertEqual(runtime.fight.actors[7].ap, 6)

    def test_commit_end_turn_keeps_real_ack_barrier_and_bound_callbacks(self):
        from wakfu_server.spells import default_deck
        from wakfu_ai.native.native_stats import NativeStats

        fixture = self.wonejo_fixture()
        fixture.fight.order = [fixture.pc.id, fixture.npc.id]
        fixture.fight.turn_index = 0
        fixture.fight.turn_id = 1
        fixture.fight.native_start_event_delivered = True
        fixture.pc.turn_count = 1
        fixture.npc.turn_count = 0
        runtime = RuntimeMessages(fixture.fight)
        oracle = self.oracle_for(
            runtime, fixture.character, fixture.monster, default_deck(fixture.character)
        )

        def obsolete_single_viewer(*args, **kwargs):
            raise AssertionError("Live commit must replace single-viewer callbacks")

        runtime.turn_start_provider = obsolete_single_viewer
        runtime.turn_end_provider = obsolete_single_viewer
        runtime.stats_serializer = obsolete_single_viewer
        runtime.runtime_stats_serializer = obsolete_single_viewer

        serializer = NativeStats(
            characters=oracle.characters,
            monsters=oracle.monsters,
            fight_id=runtime.fight.id,
        )
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )

        with patch(
            "wakfu_server.combat_actor.actual_actor_stats",
            wraps=actual_actor_stats,
        ) as character_encoder, patch(
            "wakfu_server.combat_actor.actual_monster_actor_stats",
            wraps=actual_monster_actor_stats,
        ) as monster_encoder:
            packets = oracle.commit({"type": "end_turn"}, stats_serializer=serializer)

        self.assertTrue(packets)
        self.assertEqual(runtime.awaiting_ack, 1)
        self.assertTrue(runtime.pending)
        self.assertIsNotNone(runtime.turn_start_provider)
        self.assertIsNotNone(runtime.turn_end_provider)
        self.assertEqual(runtime.fight.current.id, fixture.npc.id)
        calls = character_encoder.call_args_list + monster_encoder.call_args_list
        self.assertTrue(calls)
        for call in calls:
            actor = call.args[1]
            fight = call.kwargs.get("fight")
            self.assertIsNotNone(fight)
            self.assertEqual(fight.id, runtime.fight.id)
            self.assertIs(fight.actors[actor.id], actor)

    def test_defensive_facing_commit_rejects_stale_revision_then_publishes_cardinal(
        self,
    ):
        from wakfu_server.spells import default_deck
        from wakfu_ai.native.native_stats import NativeStats
        from wakfu_server.combat_displacement_geometry import cardinal_vector

        fixture = self.wonejo_fixture()
        fixture.fight.order = [fixture.npc.id, fixture.pc.id]
        fixture.fight.turn_index = 0
        fixture.fight.turn_id = 1
        fixture.fight.native_start_event_delivered = True
        fixture.npc.turn_count = 1
        runtime = RuntimeMessages(fixture.fight)
        oracle = self.oracle_for(
            runtime, fixture.character, fixture.monster, default_deck(fixture.character)
        )
        npc, target = runtime.fight.current, runtime.fight.actors[fixture.pc.id]
        vector = cardinal_vector(
            target.position[0] - npc.position[0], target.position[1] - npc.position[1]
        )
        direction = {(1, 0): 1, (0, 1): 3, (-1, 0): 5, (0, -1): 7}[vector]
        npc.direction = (direction + 2) % 8
        evidence = dict(
            actorId=npc.id,
            turnId=runtime.fight.turn_id,
            stateRevision=runtime.fight.sequence - 1,
            actors=[
                dict(id=actor.id, position=actor.position)
                for actor in runtime.fight.actors.values()
            ],
            visibleActorIds=list(runtime.fight.actors),
            rivals=[],
        )
        before = self.effects(runtime.fight)
        serializer = NativeStats(
            characters=oracle.characters,
            monsters=oracle.monsters,
            fight_id=runtime.fight.id,
        )

        with self.assertRaisesRegex(ValueError, "Stale defensive facing evidence"):
            oracle.commit(
                {"type": "end_turn"},
                stats_serializer=serializer,
                defensive_facing=evidence,
            )
        self.assertEqual(self.effects(runtime.fight), before)
        evidence["stateRevision"] = runtime.fight.sequence
        packets = oracle.commit(
            {"type": "end_turn"},
            stats_serializer=serializer,
            defensive_facing=evidence,
        )

        opcodes = [packet[0] for packet in packets]
        self.assertLess(opcodes.index(13494), opcodes.index(12502))
        self.assertEqual(runtime.fight.actors[npc.id].direction, direction)

    def test_native_movement_direction_edges_and_authoritative_los(self):
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_geometry_snapshot import freeze_terrain
        from wakfu_server.spells import default_deck

        fixture = self.wonejo_fixture()
        runtime = RuntimeMessages(fixture.fight)
        oracle = self.oracle_for(
            runtime, fixture.character, fixture.monster, default_deck(fixture.character)
        )
        los_source, los_target = (-23, -143, 70), (-22, -143, 70)
        from wakfu_server.combat_qi_fight import move_registered_actor

        move_registered_actor(fixture.fight, fixture.npc, los_source)
        move_registered_actor(fixture.fight, fixture.pc, los_target)
        fixture.npc.direction = 3
        fixture.pc.direction = 0
        self.assertTrue(oracle.visible(fixture.fight, los_source, los_target))

        move_registered_actor(fixture.fight, fixture.npc, (-7, -7, -1))
        move_registered_actor(fixture.fight, fixture.pc, (-4, -7, -1))
        fight_cells = {(-7, -7, -1), (-6, -7, -1), (-5, -7, -1), (-4, -7, -1)}
        fixture.fight.walkable = fight_cells
        fixture.fight.edges = {
            (source, target)
            for source, target in zip(sorted(fight_cells), sorted(fight_cells)[1:])
        }
        fixture.fight.edges |= {
            (target, source) for source, target in fixture.fight.edges
        }
        freeze_terrain(fixture.fight)
        before = self.effects(fixture.fight)

        private, packets, _ = oracle.preview(
            runtime, {"type": "move", "path": [[-6, -7, -1]]}
        )
        self.assertEqual(private.fight.actors[fixture.npc.id].position, (-6, -7, -1))
        self.assertEqual(private.fight.actors[fixture.npc.id].direction, 1)
        self.assertTrue(packets)
        self.assertEqual(self.effects(fixture.fight), before)

        missing_edge = oracle.fork(runtime=runtime)
        missing_edge.fight.walkable = fight_cells
        missing_edge.fight.edges = {((-7, -7, -1), (-6, -7, -1))}
        with self.assertRaisesRegex(ValueError, "path|transition|edge|walkable"):
            oracle.preview(missing_edge, {"type": "move", "path": [[-5, -7, -1]]})

    def test_private_end_start_callbacks_expiration_and_turn_ack(self):
        from tests.test_combat_timed_expiration import TimedExpirationTests
        from wakfu_server.combat_timed_expiration import prepare_timed_expiration
        from wakfu_server.spells import default_deck

        # Exercise real native1002/1001 callbacks and the existing turn ACK
        # entirely inside two successive oracle forks.
        fixture = self.wonejo_fixture()
        fixture.fight.native_start_event_delivered = True
        fixture.fight.native_effect_uid_next = 1
        fixture.fight.order = [fixture.pc.id, fixture.npc.id]
        fixture.fight.turn_index = 0
        fixture.fight.turn_id = 1
        fixture.pc.turn_count = 1
        fixture.npc.turn_count = 0
        runtime = RuntimeMessages(fixture.fight)
        runtime.round = 1
        oracle = self.oracle_for(
            runtime, fixture.character, fixture.monster, default_deck(fixture.character)
        )
        # Bind the real callbacks explicitly: the oracle must preserve the
        # lifecycle providers configured by the runtime, never synthesize them.
        runtime.turn_start_provider = oracle.start_boundary
        runtime.turn_end_provider = oracle.end_boundary
        live_events = copy.deepcopy(fixture.fight.events)

        npc_turn, _, _ = oracle.preview(runtime, {"type": "end_turn"})
        self.assertEqual(npc_turn.fight.current.id, fixture.npc.id)
        self.assertIsNone(npc_turn.awaiting_ack)
        self.assertEqual(npc_turn.pending, [])
        player_turn, _, _ = oracle.preview(npc_turn, {"type": "end_turn"})
        self.assertEqual(player_turn.fight.current.id, fixture.pc.id)
        self.assertIsNone(player_turn.awaiting_ack)
        self.assertEqual(player_turn.pending, [])
        self.assertTrue(
            any(
                key.endswith(":end")
                for key in player_turn.fight.native_turn_event_deliveries
            )
        )
        self.assertTrue(
            any(
                key.endswith(":start")
                for key in player_turn.fight.native_turn_event_deliveries
            )
        )
        self.assertEqual(fixture.fight.events, live_events)

        # Verify a real timed native effect still expires through a private
        # preview and leaves its source untouched.
        TimedExpirationTests.setUpClass()
        fight, _ = TimedExpirationTests().make_stat()
        live_effects = copy.deepcopy(fight.owned_stat_effects)
        expired, packets = prepare_timed_expiration(
            fight, actor_id=7, round_number=2, phase="start", action_id=2
        )
        self.assertNotIn(200, expired.owned_stat_effects)
        self.assertTrue(packets)
        self.assertEqual(fight.owned_stat_effects, live_effects)


if __name__ == "__main__":
    unittest.main()
