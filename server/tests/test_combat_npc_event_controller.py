"""Event-only ordinary admission and genuine native Nogord turn boundaries."""
from copy import deepcopy
import hashlib
import json
import struct
import unittest
from pathlib import Path
from random import Random
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_npc_event_controller import event_controller_record
from wakfu_server.combat_npc_ai_initialization import initial_ai_actors
from wakfu_server.combat_npc_activation import imports_enabled
from wakfu_server.combat_npc_initialization import initial_plans

FIXTURE = Path(__file__).with_name("fixtures") / "nogord-event-controller-native.json"


def admission():
    return json.loads(FIXTURE.read_text())


def activation(row=None):
    return dict(
        schema="native-npc-activation-v1",
        legacy_spell_ids=[],
        enabled_monsters={"3433": admission() if row is None else row},
    )


class NpcEventControllerTests(unittest.TestCase):
    def sources(self, *, controlled=False, hp=595000, book=None):
        actor = SimpleNamespace(
            id=-200,
            controlled=controlled,
            effective_level=200,
            native_summon_action_book=None,
        )
        fight = SimpleNamespace(actors={-200: actor}, native_summon_registrations={})
        native = dict(
            min_level=200,
            max_level=200,
            native_abilities=[] if book is None else book,
            statistics={"HP": {"base": hp}},
        )
        return actor, fight, native

    def bindings(self, native):
        masks = admission()["event_controller"]["callback_roots"][0]["target_masks"]
        return (
            patch("wakfu_server.monsters.reference", return_value=native),
            patch(
                "wakfu_server.spell_audit.states_catalog",
                return_value={
                    "effects": {
                        "186446": dict(
                            effect_class=330, target_masks=masks, children=[186788]
                        )
                    }
                },
            ),
            patch(
                "wakfu_server.combat_definitions.state_profile",
                return_value={"effects": [186446]},
            ),
        )

    def test_explicit_native_event_admission_initializes_without_any_paid_spell(self):
        actor, fight, native = self.sources()
        a, b, c = self.bindings(native)
        with a, b, c, patch(
            "wakfu_server.combat_npc_attack.npc_spell_catalog",
            return_value={"activation_policy": activation()},
        ), patch("wakfu_server.monsters.native_abilities", return_value=[]):
            self.assertEqual(initial_ai_actors(fight, {-200: {"ref": 3433}}), {-200})
            _, raw, plan = initial_plans(fight, {-200: {"ref": 3433}})[-200]
            self.assertEqual(raw, (4509, 1, 0, 5619, 1, 0, 7998, 1, 1))
            self.assertEqual([item.state_id for item in plan], [4509, 5619, 7998])
            for spell in (1, 5795, 7962):
                self.assertFalse(imports_enabled(activation(), 3433, 200, spell))

    def test_unqualified_empty_book_does_not_authorize_constructor_or_turn(self):
        _, fight, _ = self.sources()
        row = admission()
        del row["event_controller"]
        with patch(
            "wakfu_server.combat_npc_attack.npc_spell_catalog",
            return_value={"activation_policy": activation(row)},
        ), patch("wakfu_server.monsters.native_abilities", return_value=[]):
            self.assertFalse(initial_ai_actors(fight, {-200: {"ref": 3433}}))
            self.assertFalse(initial_plans(fight, {-200: {"ref": 3433}}))

    def test_decorative_or_populated_book_sources_cannot_use_event_only_admission(self):
        for options in ({"hp": 0}, {"book": [{"spell_id": 7962}]}):
            with self.subTest(options=options):
                _, _, native = self.sources(**options)
                a, b, c = self.bindings(native)
                with a, b, c, self.assertRaises(ValueError):
                    event_controller_record(activation(), 3433, 200)

    def test_missing_or_foreign_callback_root_cannot_authorize_turn(self):
        _, _, native = self.sources()
        for callbacks in (
            [],
            [dict(state_id=4509, effect_id=1, target_masks=[[1001]])],
            [
                dict(
                    state_id=4509,
                    effect_id=186446,
                    target_masks=[[1001], None, None, None, None, None, None],
                )
            ],
            [
                dict(
                    state_id=4509,
                    effect_id=186446,
                    target_masks=[None, None, None, None, None, [True, 1001], None],
                )
            ],
        ):
            row = admission()
            row["event_controller"]["callback_roots"] = callbacks
            a, b, c = self.bindings(native)
            with self.subTest(callbacks=callbacks), a, b, c, self.assertRaises(
                ValueError
            ):
                event_controller_record(activation(row), 3433, 200)

    def test_changed_descriptor_or_triples_are_rejected(self):
        for mutate in (
            lambda row: row["initial_state_triples"].append(1),
            lambda row: row["event_controller"]["descriptor"].update(reference=1),
        ):
            row = admission()
            mutate(row)
            with self.subTest(row=row), self.assertRaises(ValueError):
                event_controller_record(activation(row), 3433, 200)

    def test_player_summon_and_out_of_range_do_not_receive_controller(self):
        for kind in ("player", "summon", "range"):
            actor, fight, native = self.sources(controlled=kind == "player")
            if kind == "summon":
                fight.native_summon_registrations[-200] = {"actor_id": -200}
            if kind == "range":
                actor.effective_level = 199
            a, b, c = self.bindings(native)
            with self.subTest(kind=kind), a, b, c, patch(
                "wakfu_server.combat_npc_attack.npc_spell_catalog",
                return_value={"activation_policy": activation()},
            ), patch("wakfu_server.monsters.native_abilities", return_value=[]):
                self.assertFalse(initial_ai_actors(fight, {-200: {"ref": 3433}}))


class NativeNogordEventControllerTests(unittest.TestCase):
    def _run_native(self, *, off_ray):
        import validate_monster_spell_activation as validator
        from native_recorded_instance_fixture import original_bootstrap_publication
        from native_witness_fixture import legal_witness_cell, native_level200_fixture
        from wakfu_server.combat_npc_attack import npc_spell_catalog
        from wakfu_server.combat_event_replay import NativeEventReplay
        from wakfu_server.combat_effect_dispatch import EffectDispatcher
        from wakfu_server.combat_server_spell import (
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )
        from wakfu_server.monsters import native_abilities
        from wakfu_server.combat_effective_control import effective_server_controlled

        original_catalog = npc_spell_catalog()
        candidate_catalog = dict(original_catalog)
        candidate_policy = deepcopy(original_catalog["activation_policy"])
        if "3433" in candidate_policy["enabled_monsters"]:
            self.assertEqual(candidate_policy["enabled_monsters"]["3433"], admission())
        candidate_policy["enabled_monsters"]["3433"] = admission()
        candidate_catalog["activation_policy"] = candidate_policy
        observed = []
        original_replay = NativeEventReplay.__call__
        activations = []
        original_activation = EffectDispatcher.execute_activation

        def capture_activation(dispatcher, invocation, **kwargs):
            source = kwargs["source"]
            activations.append(
                (invocation.reference, source.manager_actor_id, source.event_ids)
            )
            return original_activation(dispatcher, invocation, **kwargs)

        def capture(dispatcher, event, **kwargs):
            outcome = original_replay(dispatcher, event, **kwargs)
            observed.append(
                dict(
                    manager=event.manager_actor_id,
                    event_ids=event.event_ids,
                    outcomes=list(outcome),
                )
            )
            return outcome

        with patch(
            "wakfu_server.combat_npc_attack.npc_spell_catalog",
            return_value=candidate_catalog,
        ), patch.object(NativeEventReplay, "__call__", capture), patch.object(
            EffectDispatcher, "execute_activation", capture_activation
        ):
            enemy, placement = legal_witness_cell()
            fixture, facts = native_level200_fixture(validator)
            if off_ray:
                from wakfu_server.combat_group_cells import group_cells
                from wakfu_server.combat_area_geometry import native_area_contains
                from wakfu_server.combat_obstacle_condition import footprint
                from wakfu_server.combat_los import authoritative_visible
                from wakfu_server.combat_terrain import local_arena

                with original_bootstrap_publication():
                    probe, _, _, _ = fixture(3433, 200, enemy, native_lifecycle=False)
                caster = probe.actors[-200]
                root = candidate_catalog["effects"]["186070"]
                damage = candidate_catalog["effects"]["186071"]
                parent_cells = group_cells(
                    probe, root, caster.position, caster_id=caster.id
                )
                player = probe.actors[7]
                occupied = {
                    cell
                    for actor in probe.actors.values()
                    for cell in footprint(actor.position, actor.physical_radius)
                }
                candidates = sorted(
                    probe.walkable,
                    key=lambda cell: (
                        abs(cell[0] - caster.position[0])
                        + abs(cell[1] - caster.position[1]),
                        cell,
                    ),
                )
                selected = None
                for cell in candidates:
                    distance = abs(cell[0] - caster.position[0]) + abs(
                        cell[1] - caster.position[1]
                    )
                    if not 2 <= distance <= 6 or tuple(cell[:2]) in occupied:
                        continue
                    if any(
                        native_area_contains(
                            damage,
                            origin=center,
                            reference=caster.position,
                            point=cell,
                            direction=caster.direction,
                            radius=player.physical_radius,
                        )
                        for center in parent_cells
                    ):
                        continue
                    try:
                        arena = local_arena(
                            1134,
                            0,
                            cell,
                            caster.position,
                            relocate_monsters=False,
                            compact=True,
                            variation_seed=1,
                            minimum_dimensions=(9, 9),
                        )
                    except ValueError:
                        continue
                    if cell not in arena["validated_cells"] or any(
                        place in arena["native_border_cells"]
                        for place in (cell, caster.position)
                    ):
                        continue
                    if not authoritative_visible(
                        1134,
                        caster.position,
                        cell,
                        probe,
                        blocking_footprints={
                            actor.id: footprint(actor.position, actor.physical_radius)
                            for actor in probe.actors.values()
                        },
                    ):
                        continue
                    selected = cell
                    break
                self.assertIsNotNone(selected, "No lawful native off-ray placement")
                self.placement_evidence = dict(
                    source=list(caster.position),
                    facing=caster.direction,
                    caster_radius=caster.physical_radius,
                    target_radius=player.physical_radius,
                    root_reference=186070,
                    damage_reference=186071,
                    parent_cells=list(parent_cells),
                    selected=list(selected),
                    validation="Actual QI/PV/facing + eYg group cells + native area membership + published local arena + footprint/LOS",
                )
                enemy = selected
            with original_bootstrap_publication():
                fight, character, monsters, deck = fixture(
                    3433, 200, enemy, native_lifecycle=True
                )
            npc = fight.actors[-200]
            if off_ray:
                self.assertTrue(
                    authoritative_visible(
                        1134,
                        npc.position,
                        fight.actors[7].position,
                        fight,
                        blocking_footprints={
                            actor.id: footprint(actor.position, actor.physical_radius)
                            for actor in fight.actors.values()
                        },
                    )
                )
            self.assertEqual(native_abilities(3433, 200), [])
            self.assertEqual(character["level"], 200)
            receipt = fight.native_npc_initialization_receipts[-200]
            self.assertTrue(receipt["initialized"])
            self.assertEqual(
                receipt["raw_triples"], admission()["initial_state_triples"]
            )
            self.assertEqual(
                {row["state_id"] for row in receipt["resolved_states"]},
                {4509, 5619, 7998},
            )
            self.assertTrue(
                any(
                    row["manager"] == -200 and 1003 in row["event_ids"]
                    for row in observed
                )
            )
            self.assertTrue(
                {4503, 4502} <= {entry.reference for entry in npc.state_ledger.entries}
            )
            self.assertTrue(effective_server_controlled(fight, npc))
            self.assertEqual(fight.current.id, npc.id)
            rng = Random(0)

            def stats(actor, current):
                kw = dict(
                    wp_current=actor.effect_stats[4],
                    wp_maximum=actor.effect_maxima[4],
                    fight=current,
                )
                if actor.controlled:
                    return actual_actor_stats(character, actor, current.id, **kw)
                return actual_monster_actor_stats(
                    monsters[actor.id], actor, current.id, **kw
                )

            runtime = RuntimeMessages(
                fight,
                runtime_stats_serializer=stats,
                turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                    character,
                    monsters,
                    p,
                    deck,
                    rng=rng,
                    native_events=True,
                    area_callbacks=True,
                    **kw
                ),
                turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                    character, monsters, p, deck, rng=rng, **kw
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    character,
                    monsters,
                    deck,
                    action_id=action_id,
                    critical=False,
                    rng=rng,
                )[0],
            )
            packets = list(runtime.turn_started())
            self.assertTrue(
                any(
                    row["manager"] == -200 and 1001 in row["event_ids"]
                    for row in observed
                )
            )
            self.assertTrue(
                any(
                    root == 186446 and manager == -200 and 1001 in ids
                    for root, manager, ids in activations
                )
            )
            if not off_ray:
                self.assertEqual(fight.phase, "finished")
                self.assertIsNone(fight.current)
                self.assertEqual(fight.actors[7].hp, 0)
                self.assertGreater(fight.actors[-200].hp, 0)
                self.assertTrue(
                    any(
                        event["kind"] == "damage"
                        and event["source_id"] == -200
                        and event["target_id"] == 7
                        and event["amount"] == 2050
                        for event in fight.events
                    )
                )
                self.assertTrue(
                    any(
                        event["kind"] == "finished" and event["winner"] == 1
                        for event in fight.events
                    )
                )
                self.assertFalse(
                    any(event["kind"] == "npc_cast" for event in fight.events)
                )
                return
            self.assertGreater(fight.actors[7].hp, 0)
            self.assertEqual(fight.current.id, -200)
            packets.extend(runtime.end_server_turn(-200, fight.turn_id))
            self.assertIsNotNone(runtime.awaiting_ack)
            packets.extend(
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
            )
            self.assertNotEqual(fight.current.id, -200)
            self.assertTrue(
                any(
                    row["manager"] == -200 and 1002 in row["event_ids"]
                    for row in observed
                )
            )
            self.assertFalse(any(event["kind"] == "npc_cast" for event in fight.events))
            self.assertTrue(packets)

    def test_native_opening_ray_kills_bare_opponent_and_finishes_normally(self):
        self._run_native(off_ray=False)
