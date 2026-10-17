"""Private, unexecuted native7348 upstream witness; no live service mutation.

The placed reference4/level8 is an explicitly owned test NPC, not a claim about
an authentic encounter. Definitions, HP, Ready, payment and lethal effect remain
production data/code. Foreign-source coverage below is a criterion witness,
not a fabricated second participant or a second player's executed damage.
"""
from copy import deepcopy
from contextlib import contextmanager
from dataclasses import replace
import json
from pathlib import Path
import random
import struct
import sys
import tempfile
import unittest

from postgres_case import PostgresCase
from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.combat_captured_profiles import native_captured_profiles
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    evaluate_condition,
)
from wakfu_server.combat_melee import prepare_server_unarmed
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_timeline_snapshot import current_wire_turn
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.fight_checkpoint_store import Checkpoints, snapshot

EXPECTED_PROFILES = {
    4,
    41,
    87,
    1152,
    2076,
    2367,
    2577,
    2988,
    3079,
    3393,
    3861,
    4079,
    4210,
    4229,
    4238,
    4247,
    4510,
    4723,
    4728,
    4741,
    4757,
    4886,
    4922,
    5112,
    5129,
    5136,
    5181,
    5186,
    5281,
    5294,
    5347,
    5631,
    5637,
}


class WorkflowFixture:
    cached = None

    @classmethod
    def base(cls):
        if cls.cached is None:
            # Find the repository through the already imported production path;
            # this private file is deliberately outside server/tests.
            tools = (
                Path(sys.modules["wakfu_server"].__file__).resolve().parents[1]
                / "tools"
            )
            previous = list(sys.path)
            try:
                sys.path.insert(0, str(tools))
                import audit_ready_start as audit

                assert Path(audit.__file__).resolve() == tools / "audit_ready_start.py"
                results = []

                def receive(runtime, character, monster, deck, packets, stats):
                    assert monster["ref"] == 4 and monster["level"] == 8
                    assert runtime.fight.actors[-7].max_hp == monster["max_hp"]
                    assert character["breed"] == 2
                    assert grant_record(runtime.fight, 7, 7348) is not None
                    results.append(
                        (
                            deepcopy(runtime),
                            deepcopy(character),
                            deepcopy(monster),
                            deck,
                            stats,
                        )
                    )
                    return {"status": "captured_fixture", "native_profile": 4}

                with tempfile.TemporaryDirectory() as temp:
                    report = audit.run(
                        Path(temp) / "ready.json",
                        cases_override=[(2, 153, None)],
                        turn_cycle=True,
                        turn_steps=1,
                        monster_reference=4,
                        monster_level=8,
                        on_runtime=receive,
                    )
                assert len(results) == 1, report.get("rows")
                assert (
                    report["source_stable"] and report["ready_gate_passed"]
                ), report.get("rows")
                cls.cached = results[0]
            finally:
                sys.path[:] = previous
        runtime, character, monster, deck, stats = cls.cached
        return deepcopy(runtime), deepcopy(character), deepcopy(monster), deck, stats


def mark(runtime, character, monster, deck):
    grant = grant_record(runtime.fight, character["id"], 7348)
    return prepare_server_spell(
        struct.pack(
            ">qqiih",
            character["id"],
            grant["uid"],
            *runtime.fight.actors[monster["id"]].position
        ),
        character,
        {monster["id"]: monster},
        runtime.fight,
        character["account_id"],
        deck,
        action_id=runtime.action_id + 1,
        line_of_sight=lambda a, b, preview: authoritative_visible(
            character["map_id"],
            a,
            b,
            preview,
            blocking_footprints={
                actor.id: {actor.position[:2]}
                for actor in preview.actors.values()
                if actor.hp > 0
            },
        ),
        critical=False,
        rng=random.Random(3),
    )


def kill_owned(test, runtime, character, monster, stats):
    """Actual paid native item2145, ordinary damage/death producer, real ACKs."""
    for _ in range(100):
        target = runtime.fight.actors[monster["id"]]
        if target.hp == 0:
            return
        current = runtime.fight.current
        if current.id != character["id"] or current.ap < 3:
            if current.controlled:
                runtime.end_turn(
                    current.owner_id, current.id, current_wire_turn(runtime.fight)
                )
            else:
                runtime.end_server_turn(current.id, runtime.fight.turn_id)
            if runtime.awaiting_ack is not None:
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
            continue
        baseline = snapshot(runtime.fight)
        pc = runtime.fight.actors[character["id"]]
        wp = pc.effect_stats[4]
        tx = prepare_server_unarmed(
            struct.pack(">qqbiih", pc.id, -1, 15, *target.position),
            character,
            {monster["id"]: monster},
            runtime.fight,
            character["account_id"],
            unarmed=True,
            wp_current=wp,
            wp_maximum=wp,
            action_id=runtime.action_id + 1,
            effect_uid=runtime.fight.native_effect_uid_next,
            critical_chance=0,
            caster_running_effects=(),
            target_running_effects=(),
            caster_bonuses={},
            target_bonuses={},
            mitigate=lambda value, *args: value,
            rng=random.Random(17),
        )
        test.assertEqual(snapshot(runtime.fight), baseline)
        test.assertEqual(tx.fight.actors[pc.id].ap, pc.ap - 3)
        test.assertLess(tx.fight.actors[target.id].hp, target.hp)
        commit_spell_transaction(runtime, tx, stats_serializer=stats)
    test.fail(
        "Native unarmed attacks did not produce the required actual lethal transition"
    )


class NativeCaptureWorkflowTests(unittest.TestCase):
    def test_paid_mark_actual_owned_lethal_event_captures_lowest_slot(self):
        runtime, character, monster, deck, stats = WorkflowFixture.base()
        self.assertEqual(
            OwnedCapturedRoster.from_record(
                character["captured_roster"], expected_owner_id=7
            ).free_slots,
            10,
        )
        baseline = snapshot(runtime.fight)
        ap = runtime.fight.actors[7].ap
        tx = mark(runtime, character, monster, deck)
        self.assertEqual(snapshot(runtime.fight), baseline)
        self.assertEqual(
            tx.plan["costs"],
            dict(
                ap=1,
                mp=0,
                wp=0,
                conditional_rules=0,
                extra_resource_deltas={},
                extra_resource_values={},
            ),
        )
        self.assertEqual(tx.fight.actors[7].ap, ap - 1)
        self.assertTrue(
            any(
                row.reference == 7128
                for row in tx.fight.actors[-7].state_ledger.entries
            )
        )
        self.assertFalse(getattr(tx.fight, "native_captured_roster_updates", {}))
        commit_spell_transaction(runtime, tx, stats_serializer=stats)
        kill_owned(self, runtime, character, monster, stats)
        roster = OwnedCapturedRoster.from_record(
            runtime.fight.native_captured_roster_updates["7"], expected_owner_id=7
        )
        self.assertEqual(roster.free_slots, 9)
        self.assertEqual(roster.selected_slot, 0)
        self.assertEqual(roster.slots[0].profile_id, 4)
        self.assertTrue(roster.available[0])
        self.assertEqual(runtime.fight.actors[-7].hp, 0)
        self.assertTrue(
            any(
                row["event_id"] == 1013 and row["actor_id"] == -7
                for row in runtime.fight.native_death_event_deliveries.values()
            )
        )
        encoded = json.loads(json.dumps(snapshot(runtime.fight), allow_nan=False))
        self.assertEqual(
            encoded["native_captured_roster_updates"]["7"], roster.to_record()
        )

    def test_full_or_duplicate_roster_skips_original_mark_but_pays_eligible_cast(self):
        for mode in ("duplicate", "full"):
            with self.subTest(mode=mode):
                runtime, character, monster, deck, stats = WorkflowFixture.base()
                slots = [None] * 10
                if mode == "duplicate":
                    slots[0] = CapturedCreature(0, 4, "Already owned")
                else:
                    for slot, profile in enumerate(
                        sorted(EXPECTED_PROFILES - {4})[:10]
                    ):
                        slots[slot] = CapturedCreature(slot, profile, "Owned")
                record = OwnedCapturedRoster(
                    7, tuple(slots), (True,) * 10, 0
                ).to_record()
                character["captured_roster"] = record
                runtime.fight.native_captured_rosters = {"7": deepcopy(record)}
                baseline = snapshot(runtime.fight)
                ap = runtime.fight.actors[7].ap
                tx = mark(runtime, character, monster, deck)
                self.assertEqual(snapshot(runtime.fight), baseline)
                self.assertEqual(tx.fight.actors[7].ap, ap - 1)
                self.assertFalse(
                    any(
                        row.reference == 7128
                        for row in tx.fight.actors[-7].state_ledger.entries
                    )
                )
                commit_spell_transaction(runtime, tx, stats_serializer=stats)
                kill_owned(self, runtime, character, monster, stats)
                self.assertEqual(runtime.fight.native_captured_rosters["7"], record)
                self.assertFalse(
                    getattr(runtime.fight, "native_captured_roster_updates", {})
                )

    def test_insufficient_payment_rejects_before_mark_and_preserves_complete_source(
        self,
    ):
        runtime, character, monster, deck, stats = WorkflowFixture.base()
        # Explicit resource-boundary fixture; no claim that this was an executed
        # preceding cast, and no production payment/turn handler is replaced.
        runtime.fight.spend(character["account_id"], 7, ap=runtime.fight.actors[7].ap)
        baseline = snapshot(runtime.fight)
        with self.assertRaises(ValueError):
            mark(runtime, character, monster, deck)
        self.assertEqual(snapshot(runtime.fight), baseline)

    def test_original_listener_all_33_profiles_and_foreign_source_refusal(self):
        effects = native_catalog.load(DATA_ROOT / "combat-state-definitions.json")[
            "effects"
        ]
        criterion = effects["326382"]["criteria"]
        self.assertEqual(set(map(int, native_captured_profiles())), EXPECTED_PROFILES)
        self.assertEqual(effects["326382"]["target_masks"][5], [1013])
        # Native predicate coverage, deliberately separate from actual lethal
        # integration: all33 species and source identity, not fake encounters.
        for profile in sorted(EXPECTED_PROFILES | {5525}):
            owner = ConditionActor(actor_id=7, breed_id=2)
            target = ConditionActor(actor_id=-7, breed_id=profile)
            context = ConditionContext(
                actors={"caster": owner, "target": target},
                triggering_effect_present=True,
                triggering_effect_caster_id=7,
                breed_in_symbiot_query=lambda profile, selector: False,
            )
            with self.subTest(profile=profile):
                self.assertEqual(
                    evaluate_condition(criterion, context), profile in EXPECTED_PROFILES
                )
                self.assertFalse(
                    evaluate_condition(
                        criterion, replace(context, triggering_effect_caster_id=99)
                    )
                )
                self.assertFalse(
                    evaluate_condition(
                        criterion,
                        replace(
                            context,
                            breed_in_symbiot_query=lambda profile, selector: True,
                        ),
                    )
                )


class NativeCapturePersistenceTests(PostgresCase):
    def test_actual_capture_checkpoint_commit_reopen_and_rollback(self):
        # Actual Ready fixture is owner7/account3. Provision those identities in
        # the isolated schema; never rewrite a live fight or use a fake Store.
        self.store.clock = lambda: 1000
        accounts = [
            self.store.register("capture-" + str(i), "local-password")["id"]
            for i in range(3)
        ]
        self.assertEqual(accounts[-1], 3)
        for index, letter in enumerate("ABCDEF"):
            self.store.create_character(
                1 if index < 3 else 2, "Placeholder " + letter, breed=2
            )
        owner = self.store.create_character(3, "Capture Owner", breed=2)
        self.assertEqual(owner["id"], 7)
        generation = self.store.begin_session(3)
        self.store.select_character(3, generation, 7)
        runtime, character, monster, deck, stats = WorkflowFixture.base()
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO combat_fights(id,status) OVERRIDING SYSTEM VALUE VALUES(%s,'active')",
                (runtime.fight.id,),
            )
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team,session_generation) VALUES(%s,7,3,0,%s)",
                (runtime.fight.id, generation),
            )
        checkpoints = Checkpoints(self.store)
        initial = checkpoints.save(3, generation, runtime.fight, runtime=runtime)
        tx = mark(runtime, character, monster, deck)
        commit_spell_transaction(runtime, tx, stats_serializer=stats)
        kill_owned(self, runtime, character, monster, stats)
        expected = runtime.fight.native_captured_roster_updates["7"]
        # Wrong CAS must preserve both the old checkpoint AND empty durable bag.
        with self.assertRaises(ValueError):
            checkpoints.save(
                3,
                generation,
                runtime.fight,
                expected_revision=initial + 1,
                runtime=runtime,
            )
        self.assertEqual(checkpoints.read(3, runtime.fight.id)["revision"], initial)
        self.assertEqual(
            OwnedCapturedRoster.from_record(
                self.reopen().character(3, 7)["captured_roster"], expected_owner_id=7
            ).free_slots,
            10,
        )
        revision = checkpoints.save(
            3, generation, runtime.fight, expected_revision=initial, runtime=runtime
        )
        reopened = self.reopen()
        self.assertEqual(reopened.character(3, 7)["captured_roster"], expected)
        saved = Checkpoints(reopened).read(3, runtime.fight.id)
        self.assertEqual(saved["revision"], revision)
        self.assertEqual(saved["snapshot"]["native_captured_rosters"]["7"], expected)
        self.assertEqual(
            saved["snapshot"]["native_captured_roster_updates"]["7"], expected
        )


class NativeForeignKillIntegrationTests(unittest.TestCase):
    def test_actual_second_owner_lethal_attack_does_not_capture_marked_enemy(self):
        """Two source-bound PCs initialized before Ready; no source-ID rewrite."""
        from unittest.mock import patch
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
            actor_effects,
        )
        from wakfu_server.combat_state import Actor
        from wakfu_server.combat_global_pv_collections import register_global_fighter
        from wakfu_server.combat_actor_snapshot import (
            initialize_fight_snapshots,
            build_player_snapshot,
        )
        from wakfu_server.combat_join_registration import register_joined_fighter
        from wakfu_server.combat_class_initialization import BREEDS
        from wakfu_server.combat_terrain import map_geometry
        from wakfu_server.combat_arena_selection import bounded_arena
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_turn_start,
            prepare_server_turn_end,
            server_runtime,
        )
        from wakfu_server.combat_ready import prepare_ready
        from wakfu_server.combat_timeline_snapshot import current_wire_turn
        from wakfu_server.spells import encode_deck

        tools = (
            Path(sys.modules["wakfu_server"].__file__).resolve().parents[1] / "tools"
        )
        previous = list(sys.path)
        try:
            sys.path.insert(0, str(tools))
            import audit_active_spells as fixture

            self.assertEqual(
                Path(fixture.__file__).resolve(), tools / "audit_active_spells.py"
            )
            geometry = map_geometry(1134)
            edges = [(tuple(a), tuple(b)) for a, b in geometry["edges"]]
            # Both PCs start adjacent to the same native target cell. All three
            # cells and edges come from the actual terrain, not an LOS bypass.
            neighbors = {}
            for a, b in edges:
                if abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1:
                    neighbors.setdefault(a, set()).add(b)
                    neighbors.setdefault(b, set()).add(a)
            target = next(
                cell
                for cell, adjacent in sorted(neighbors.items())
                if len(adjacent) >= 2
            )
            origin, second_position = sorted(neighbors[target])[:2]
            terrain = bounded_arena(
                geometry, origin, [target, second_position], radius=12
            )
            characters = {}
            resources = BREEDS[2]["resources"]

            def initialize_multi(
                fight,
                *,
                characters: object,
                monsters,
                wp_resources,
                running_effects,
                initial_effect_uid,
                **kwargs
            ):
                first = characters[7]
                second = deepcopy(first)
                second.update(
                    id=8,
                    account_id=4,
                    name="Foreign Capture Owner",
                    x=second_position[0],
                    y=second_position[1],
                    z=second_position[2],
                    captured_roster=OwnedCapturedRoster(8).to_record(),
                )
                actor = Actor(
                    8,
                    0,
                    second_position,
                    second["hp"],
                    resources["AP"],
                    resources["MP"],
                    0,
                    153,
                    4,
                    True,
                    max_hp=second["max_hp"],
                )
                # The first population uses its actual fresh initializer.
                # Then the same production joined-fighter primitive registers
                # a separately initialized PC into QI/fdt before either Ready.
                # This is an owned fixture, not socket/session admission proof.
                initialize_fight_snapshots(
                    fight,
                    characters=characters,
                    monsters=monsters,
                    wp_resources=wp_resources,
                    running_effects=running_effects,
                    initial_effect_uid=initial_effect_uid,
                    **kwargs
                )
                build_player_snapshot(
                    second,
                    actor,
                    wp_current=resources["WP"],
                    wp_maximum=resources["WP"],
                    running_effects=(),
                ).install(actor)
                fight.placement[0].add(second_position)
                register_joined_fighter(fight, actor, second_position)
                constructed.update({7: first, 8: second})

            constructed = {}
            with patch.object(fixture, "initialize_fight_snapshots", initialize_multi):
                character, monster, fight = fixture.fixture(
                    2,
                    153,
                    target,
                    terrain,
                    origin,
                    ready=False,
                    monster_reference=4,
                    monster_level=8,
                )
            characters = constructed
        finally:
            sys.path[:] = previous
        decks = {identity: encode_deck() for identity in characters}
        common = dict(player_characters=characters, deck_blobs=decks)
        state = {"fight": fight}

        def stats(actor, preview=None):
            preview = state["fight"] if preview is None else preview
            if actor.id in characters:
                return actual_actor_stats(
                    characters[actor.id],
                    actor,
                    preview.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=resources["WP"],
                )
            return actual_monster_actor_stats(
                monster,
                actor,
                preview.id,
                wp_current=monster["wp"],
                wp_maximum=monster["wp"],
            )

        def initialize(preview, action_id):
            packets = []
            for identity in (7, 8):
                preview, tail = prepare_server_initialization(
                    characters[identity],
                    {-7: monster},
                    preview,
                    characters[identity]["account_id"],
                    decks[identity],
                    action_id=action_id,
                    rng=random.Random(7),
                    fight_start=identity == 8,
                    **common
                )
                packets.extend(tail)
            state["fight"] = preview
            return preview, packets

        boundary = dict(
            initialize=initialize,
            stats_serializer=stats,
            runtime_stats_serializer=stats,
            effects_serializer=actor_effects,
            turn_end_provider=lambda preview, **kw: prepare_server_turn_end(
                character,
                {-7: monster},
                preview,
                decks[7],
                rng=random.Random(7),
                **common,
                **kw
            ),
            turn_start_provider=lambda preview, **kw: prepare_server_turn_start(
                character,
                {-7: monster},
                preview,
                decks[7],
                rng=random.Random(7),
                **common,
                **kw
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                character,
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                rng=random.Random(7),
                **common
            )[0],
        )
        fight, runtime, _ = prepare_ready(fight, 3, True, **boundary)
        self.assertIsNone(runtime)
        fight, runtime, _ = prepare_ready(fight, 4, True, **boundary)
        self.assertIsNotNone(runtime)

        def advance():
            current = runtime.fight.current
            if current.controlled:
                runtime.end_turn(
                    current.owner_id, current.id, current_wire_turn(runtime.fight)
                )
            else:
                runtime.end_server_turn(current.id, runtime.fight.turn_id)
            if runtime.awaiting_ack is not None:
                runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))

        for _ in range(16):
            if runtime.fight.current.id == 7:
                break
            advance()
        self.assertEqual(runtime.fight.current.id, 7)
        grant = grant_record(runtime.fight, 7, 7348)
        self.assertIsNotNone(grant)
        original = snapshot(runtime.fight)
        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, grant["uid"], *target),
            character,
            {-7: monster},
            runtime.fight,
            3,
            decks[7],
            action_id=runtime.action_id + 1,
            line_of_sight=lambda a, b, preview: authoritative_visible(
                1134,
                a,
                b,
                preview,
                blocking_footprints={
                    actor.id: {actor.position[:2]}
                    for actor in preview.actors.values()
                    if actor.hp > 0
                },
            ),
            critical=False,
            rng=random.Random(3),
            **common
        )
        self.assertEqual(snapshot(runtime.fight), original)
        self.assertTrue(
            any(
                row.reference == 7128
                for row in tx.fight.actors[-7].state_ledger.entries
            )
        )
        commit_spell_transaction(runtime, tx, stats_serializer=stats)
        for _ in range(100):
            enemy = runtime.fight.actors[-7]
            if enemy.hp == 0:
                break
            current = runtime.fight.current
            if current.id != 8 or current.ap < 3:
                advance()
                continue
            before = snapshot(runtime.fight)
            tx = prepare_server_unarmed(
                struct.pack(">qqbiih", 8, -1, 15, *enemy.position),
                characters[8],
                {-7: monster},
                runtime.fight,
                4,
                unarmed=True,
                wp_current=current.effect_stats[4],
                wp_maximum=resources["WP"],
                action_id=runtime.action_id + 1,
                effect_uid=runtime.fight.native_effect_uid_next,
                critical_chance=0,
                caster_running_effects=(),
                target_running_effects=(),
                caster_bonuses={},
                target_bonuses={},
                mitigate=lambda value, *args: value,
                rng=random.Random(17),
                **common
            )
            self.assertEqual(snapshot(runtime.fight), before)
            self.assertEqual(tx.plan["actor_id"], 8)
            self.assertEqual(tx.plan["target_id"], -7)
            self.assertLess(tx.fight.actors[-7].hp, enemy.hp)
            commit_spell_transaction(runtime, tx, stats_serializer=stats)
        self.assertEqual(runtime.fight.actors[-7].hp, 0)
        self.assertTrue(
            any(
                row["event_id"] == 1013 and row["actor_id"] == -7
                for row in runtime.fight.native_death_event_deliveries.values()
            )
        )
        for identity in (7, 8):
            record = getattr(runtime.fight, "native_captured_rosters", {}).get(
                str(identity), characters[identity]["captured_roster"]
            )
            self.assertEqual(
                OwnedCapturedRoster.from_record(
                    record, expected_owner_id=identity
                ).free_slots,
                10,
            )
        self.assertFalse(getattr(runtime.fight, "native_captured_roster_updates", {}))
