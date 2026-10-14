"""Two actual Eniripsa owners preserve foreign Cunejo death areas."""
import os
import random
import struct
import unittest
from copy import deepcopy


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class AniripsaMultiOwnerDeathAreasTests(unittest.TestCase):
    def test_actual_two_cunejo_deaths_and_one_owner_replacement_are_isolated(self):
        from xelor_multiowner_fixture import TwoXelorFixture
        from tools.combat_audit_turns import advance_actual_turn
        from tools.class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_server_spell import (
            prepare_server_spell,
            prepare_server_turn_end,
            prepare_server_turn_start,
            server_runtime,
        )
        from wakfu_server.combat_spell_grant import granted_spells
        from wakfu_server.combat_hp_raw import set_hp_raw_current
        from wakfu_server.combat_effect_area_geometry import contains_area_cell
        from wakfu_server.fight_checkpoint_store import snapshot

        fight, characters, monster, decks = TwoXelorFixture().fixture(
            level=200,
            caster_breed=7,
            active_spells=(630, 779, 645),
            passive_spells=(5455,),
            second_player_breed=7,
            second_player_spells=(630, 779, 645),
            second_player_passives=(5455,),
            compact_arena=False,
            second_player_position=(-8, -6, -1),
            third_player_position=(-9, -7, -1),
            enemy_position=(-5, -7, -1),
        )
        rng = random.Random(7)
        common = dict(player_characters=characters, deck_blobs=decks, rng=rng)
        runtime = RuntimeMessages(
            fight,
            turn_end_provider=lambda p, **kw: prepare_server_turn_end(
                characters[7], {-7: monster}, p, decks[7], **common, **kw
            ),
            turn_start_provider=lambda p, **kw: prepare_server_turn_start(
                characters[7],
                {-7: monster},
                p,
                decks[7],
                area_callbacks=True,
                **common,
                **kw,
            ),
            expiration_runtime_factory=lambda *, action_id: server_runtime(
                characters[7],
                {-7: monster},
                decks[7],
                action_id=action_id,
                critical=False,
                **common,
            )[0],
        )
        action_id = 100

        def reach(owner, *, next_turn=False):
            if next_turn:
                advance_actual_turn(runtime)
            for _ in range(32):
                self.assertIsNotNone(runtime.fight.current)
                if runtime.fight.current.id == owner:
                    return
                advance_actual_turn(runtime)
            self.fail(f"Could not reach actual owner {owner} turn")

        def cast(owner, uid, target):
            nonlocal action_id
            action_id += 1
            before = snapshot(runtime.fight)
            tx = prepare_server_spell(
                struct.pack(">qqiih", owner, uid, *target),
                characters[owner],
                {-7: monster},
                runtime.fight,
                characters[owner]["account_id"],
                decks[owner],
                action_id=action_id,
                line_of_sight=lambda *args: True,
                critical=False,
                **common,
            )
            self.assertEqual(snapshot(runtime.fight), before)
            runtime.fight = tx.fight
            return tx

        def areas(owner):
            return {
                uid: row
                for uid, row in runtime.fight.native_effect_areas.items()
                if row["reference"] == 1814 and row.get("owner_id") == owner
            }

        def create_and_kill(owner):
            reach(owner)
            for attempt in range(12):
                uid = granted_spells(runtime.fight, owner)[7978]["uid"]
                _, adapter = server_runtime(
                    characters[owner],
                    {-7: monster},
                    decks[owner],
                    action_id=action_id + 1,
                    critical=False,
                    **common,
                )
                eligible = eligible_cast_targets(
                    runtime.fight,
                    characters[owner],
                    decks[owner],
                    uid,
                    adapter=adapter,
                    actor_id=owner,
                    limit=512,
                    maximum_eligible=16,
                    line_of_sight=lambda *args: True,
                )
                # Both real death glyphs must cover the same registered ally.
                # Area1814 is the native cross of radius one; the recipient
                # itself is occupied, so choose a legal adjacent summon cell.
                recipient_cell = runtime.fight.actors[9].position
                candidates = [
                    row
                    for row in eligible["eligible"]
                    if sum(abs(row["target"][i] - recipient_cell[i]) for i in (0, 1))
                    == 1
                ]
                candidates = sorted(
                    candidates,
                    key=lambda row: (
                        sum(
                            abs(
                                row["target"][i]
                                - runtime.fight.actors[owner].position[i]
                            )
                            for i in (0, 1)
                        ),
                        tuple(row["target"]),
                    ),
                )
                if candidates:
                    cast(owner, uid, candidates[0]["target"])
                    break
                reach(owner, next_turn=True)
            else:
                self.fail(f"No legal Cunejo creation for owner {owner}: {eligible!r}")
            summons = [
                actor
                for actor in runtime.fight.actors.values()
                if actor.hp > 0
                and getattr(actor, "native_summon_source", None)
                and actor.native_summon_source.get("caster_id") == owner
            ]
            self.assertEqual(len(summons), 1)
            summon_id = summons[0].id
            self.assertEqual(summons[0].native_summon_source["ref"], 182)
            for _ in range(40):
                reach(owner)
                try:
                    cast(
                        owner,
                        (owner << 32) | 630,
                        runtime.fight.actors[summon_id].position,
                    )
                except ValueError as error:
                    if "resources" not in str(error) and "maximum casts" not in str(
                        error
                    ):
                        raise
                    reach(owner, next_turn=True)
                    continue
                if runtime.fight.actors[summon_id].hp == 0:
                    self.assertEqual(len(areas(owner)), 1)
                    return summon_id, next(iter(areas(owner)))
            self.fail(
                f"Owner {owner} could not kill actual Cunejo within legal turn budget"
            )

        first_summon, first_uid = create_and_kill(7)
        second_summon, second_uid = create_and_kill(8)
        self.assertNotEqual(first_summon, second_summon)
        self.assertNotEqual(first_uid, second_uid)
        self.assertIn(first_uid, areas(7))
        self.assertIn(second_uid, areas(8))
        for uid in (first_uid, second_uid):
            self.assertTrue(
                contains_area_cell(
                    runtime.fight.native_effect_areas[uid],
                    runtime.fight.actors[9].position,
                )
            )
        reach(9)
        for owner in (7, 8):
            self.assertEqual(runtime.fight.actors[owner].effect_stats[114], 50)
            self.assertEqual(
                sum(
                    state.level
                    for state in runtime.fight.actors[owner].state_ledger.entries
                    if state.reference == 3912
                ),
                50,
            )
        # Keep setup at full HP so no prior effective healing resistance
        # obscures this first wounded-recipient numeric observation.
        set_hp_raw_current(runtime.fight.actors[9], 100)
        reach(9, next_turn=True)
        # Native371987/1084 at level200 yields4 + 0.1*200 =24 base.
        # Innate3912 level50 ->178118/1095 supplies50% final healing
        # (stat114), so24 *1.5 =36; the bare build has no healing mastery.
        # Shared3918 guard prevents the second overlapping area from healing
        # the same recipient again in this activation window.
        self.assertEqual(runtime.fight.actors[9].hp, 136)
        self.assertEqual(
            sum(
                state.reference == 3918
                for state in runtime.fight.actors[9].state_ledger.entries
            ),
            1,
        )
        self.assertIn(first_uid, areas(7))
        self.assertIn(second_uid, areas(8))
        foreign = deepcopy(areas(8)[second_uid])
        replacement_summon, replacement_uid = create_and_kill(7)
        self.assertNotEqual(replacement_summon, first_summon)
        self.assertNotEqual(replacement_uid, first_uid)
        self.assertNotIn(first_uid, runtime.fight.native_effect_areas)
        self.assertIn(first_uid, runtime.fight.native_retired_area_managers)
        self.assertIn(replacement_uid, areas(7))
        self.assertIn(second_uid, areas(8))
        for key in (
            "owner_id",
            "reference",
            "cell",
            "direction",
            "remaining_activations",
        ):
            self.assertEqual(areas(8)[second_uid].get(key), foreign.get(key), key)
        self.assertNotIn(second_uid, runtime.fight.native_retired_area_managers)
