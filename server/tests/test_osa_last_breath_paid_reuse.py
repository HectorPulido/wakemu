"""Exercise real Last Breath death and paid captured-profile reuse."""
from copy import deepcopy
import random
import struct
import tempfile
import unittest
from pathlib import Path

import test_osa_captured_paid_reuse as existing_workflow
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.characters.captured_roster_selection import select as select_captured
from wakfu_server.combat_captured_profiles import native_captured_profiles
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_timeline_snapshot import current_wire_turn
from wakfu_server.spells import validate_deck
from wakfu_server.fight_checkpoint_store import snapshot


class OsaLastBreathPaidReuseTests(unittest.TestCase):
    def test_last_breath_death_then_paid_reuse_of_profiles_87_and_4(self):
        with existing_workflow.scoped_audit_modules() as (captured_audit, _):
            ready_audit = captured_audit.ready_audit
            profiles = native_captured_profiles()
            completed = []

            def seed_roster(character, breed, level, passive):
                self.assertEqual((breed, level, passive), (2, 31, None))
                slots = [None] * 10
                slots[1] = CapturedCreature(1, 4, profiles["4"]["native_profile_name"])
                slots[2] = CapturedCreature(
                    2, 87, profiles["87"]["native_profile_name"]
                )
                available = [False] * 10
                available[1] = available[2] = True
                character["captured_roster"] = OwnedCapturedRoster(
                    character["id"], tuple(slots), tuple(available), 2
                ).to_record()

            def visible(character):
                return lambda source, destination, state: authoritative_visible(
                    character["map_id"],
                    source,
                    destination,
                    state,
                    blocking_footprints={
                        actor.id: {actor.position[:2]}
                        for actor in state.actors.values()
                        if actor.hp > 0
                    },
                )

            def prepare_capture(runtime, character, monster, deck, los):
                owner_id = character["id"]
                grant = grant_record(runtime.fight, owner_id, 7348)
                self.assertIsNotNone(grant, "native Ready grant 7348 missing")
                owner = runtime.fight.actors[owner_id]
                occupied = {
                    actor.position
                    for actor in runtime.fight.actors.values()
                    if actor.hp > 0
                }
                cells = sorted(
                    cell
                    for cell in runtime.fight.walkable
                    if cell not in occupied
                    and 1
                    <= abs(cell[0] - owner.position[0])
                    + abs(cell[1] - owner.position[1])
                    <= 4
                )
                baseline = snapshot(runtime.fight)
                failures = []
                for cell in cells:
                    try:
                        tx = prepare_server_spell(
                            struct.pack(">qqiih", owner_id, grant["uid"], *cell),
                            character,
                            {monster["id"]: monster},
                            runtime.fight,
                            character["account_id"],
                            deck,
                            action_id=runtime.action_id + 1,
                            line_of_sight=los,
                            critical=False,
                            rng=random.Random((runtime.fight.turn_id << 8) + cell[0]),
                        )
                    except ValueError as error:
                        self.assertEqual(snapshot(runtime.fight), baseline)
                        failures.append(str(error))
                        continue
                    self.assertEqual(snapshot(runtime.fight), baseline)
                    return tx
                self.fail(f"No legal native capture cell; errors={failures[-3:]}")

            def paid(before, tx):
                after = tx.fight.actors[before.id]
                costs = tx.plan["costs"]
                self.assertEqual(after.ap, before.ap - costs["ap"])
                self.assertEqual(after.mp, before.mp - costs["mp"])
                self.assertEqual(
                    after.effect_stats[4], before.effect_stats[4] - costs["wp"]
                )

            def end_and_ack(runtime):
                actor = runtime.fight.current
                if actor.controlled:
                    packets = runtime.end_turn(
                        actor.owner_id, actor.id, current_wire_turn(runtime.fight)
                    )
                else:
                    packets = runtime.end_server_turn(actor.id, runtime.fight.turn_id)
                if runtime.awaiting_ack is not None:
                    packets = tuple(packets) + tuple(
                        runtime.acknowledge_turn(
                            struct.pack(">i", runtime.awaiting_ack)
                        )
                    )
                return tuple(packets)

            def wait_for(runtime, actor_id, limit=32):
                for _ in range(limit):
                    if runtime.fight.current.id == actor_id:
                        return
                    end_and_ack(runtime)
                self.fail(
                    f"Actor {actor_id} did not receive a turn after {limit} native transitions"
                )

            def cast_when_legal(runtime, character, monster, deck, *, attempts=8):
                failures = []
                for _ in range(attempts):
                    wait_for(runtime, character["id"])
                    baseline = snapshot(runtime.fight)
                    try:
                        tx = prepare_capture(
                            runtime, character, monster, deck, visible(character)
                        )
                    except AssertionError as error:
                        # The helper only asserts after trying every legal native
                        # target cell. Preserve the actual cause and state.
                        self.assertEqual(snapshot(runtime.fight), baseline)
                        failures.append(str(error))
                        end_and_ack(runtime)
                        continue
                    return tx, runtime.fight.turn_id, failures
                self.fail(
                    f"7348 remained unavailable on natural owner turns: {failures[-3:]}"
                )

            def lifecycle(runtime, character, monster, deck, packets, stats):
                owner_id = character["id"]
                print("STAGE Ready callback", flush=True)
                owner = runtime.fight.actors[owner_id]
                roster = OwnedCapturedRoster.from_record(
                    getattr(runtime.fight, "native_captured_rosters", {}).get(
                        str(owner_id), character["captured_roster"]
                    ),
                    expected_owner_id=owner_id,
                )
                self.assertEqual(
                    (
                        roster.selected_slot,
                        roster.slots[1].profile_id,
                        roster.slots[2].profile_id,
                    ),
                    (2, 4, 87),
                )
                self.assertTrue(roster.available[1] and roster.available[2])

                first, _, _ = cast_when_legal(runtime, character, monster, deck)
                before_first = runtime.fight.actors[owner_id]
                paid(before_first, first)
                initial_ids = set(runtime.fight.actors)
                commit_spell_transaction(runtime, first, stats_serializer=stats)
                print("STAGE initial profile 87 committed", flush=True)
                first_ids = set(runtime.fight.actors) - initial_ids
                self.assertEqual(len(first_ids), 1)
                captured_id = first_ids.pop()
                captured = runtime.fight.actors[captured_id]
                self.assertEqual(captured.native_summon_source["ref"], 87)
                self.assertEqual(captured.native_captured_descriptor["profile_id"], 87)
                first_slot = captured.native_obstacle_id
                self.assertFalse(
                    runtime.fight.native_captured_rosters[str(owner_id)]["available"][2]
                )

                # 7322 is cast through the owner's actual native UID from the
                # validated deck. The summon-only action book does not contain it.
                self.assertIn(7322, validate_deck(deck, 2, 31)["active"])
                before_breath = snapshot(runtime.fight)
                caster = runtime.fight.actors[owner_id]
                breath = prepare_server_spell(
                    struct.pack(
                        ">qqiih", owner_id, (owner_id << 32) | 7322, *captured.position
                    ),
                    character,
                    {monster["id"]: monster},
                    runtime.fight,
                    character["account_id"],
                    deck,
                    action_id=runtime.action_id + 1,
                    line_of_sight=visible(character),
                    critical=False,
                    rng=random.Random(7322),
                )
                self.assertEqual(snapshot(runtime.fight), before_breath)
                paid(caster, breath)
                commit_spell_transaction(runtime, breath, stats_serializer=stats)
                print("STAGE 7322 committed", flush=True)
                self.assertGreater(runtime.fight.actors[captured_id].hp, 0)

                wait_for(runtime, captured_id)
                self.assertTrue(runtime.fight.actors[captured_id].controlled)
                death_packets = end_and_ack(runtime)
                death_indices = [
                    i for i, (op, _) in enumerate(death_packets) if op == 12727
                ]
                close_indices = [
                    i for i, (op, _) in enumerate(death_packets) if op == 12502
                ]
                self.assertEqual(
                    len(death_indices),
                    1,
                    f"death packet missing/duplicated: {[op for op, _ in death_packets]}",
                )
                self.assertTrue(
                    close_indices,
                    f"turn close missing: {[op for op, _ in death_packets]}",
                )
                self.assertLess(death_indices[0], close_indices[0])
                death_body = death_packets[death_indices[0]][1]
                self.assertEqual(
                    struct.unpack_from(">qB", death_body, len(death_body) - 9),
                    (captured_id, 2),
                )
                retired = runtime.fight.actors[captured_id]
                self.assertEqual(retired.hp, 0)
                self.assertEqual(
                    runtime.fight.native_global_pv_collections["fighter_status"][
                        str(captured_id)
                    ],
                    "OUT_OF_PLAY",
                )
                self.assertEqual(retired.native_obstacle_id, -1)
                self.assertIsNone(runtime.fight.native_qi_slots[first_slot])
                released = OwnedCapturedRoster.from_record(
                    runtime.fight.native_captured_rosters[str(owner_id)],
                    expected_owner_id=owner_id,
                )
                self.assertEqual(released.slots[2].profile_id, 87)
                self.assertTrue(released.available[2])
                print("STAGE captured profile 87 died and slot released", flush=True)

                # Keep the exact post-death state for an independent legal
                # profile-4 branch; native capacity need not allow two living captures.
                post_death = deepcopy(runtime)

                second, second_turn, waited = cast_when_legal(
                    runtime, character, monster, deck
                )
                second_before = runtime.fight.actors[owner_id]
                paid(second_before, second)
                second_ids_before = set(runtime.fight.actors)
                commit_spell_transaction(runtime, second, stats_serializer=stats)
                second_ids = set(runtime.fight.actors) - second_ids_before
                self.assertEqual(len(second_ids), 1)
                second_id = second_ids.pop()
                self.assertEqual(
                    runtime.fight.actors[second_id].native_summon_source["ref"], 87
                )
                self.assertEqual(
                    runtime.fight.actors[second_id].native_obstacle_id, first_slot
                )
                print("STAGE paid profile 87 reuse committed", flush=True)

                select_captured(
                    None,
                    character["account_id"],
                    character,
                    struct.pack(">qb", owner_id, 1),
                    fight=post_death.fight,
                )
                selected = OwnedCapturedRoster.from_record(
                    post_death.fight.native_captured_rosters[str(owner_id)],
                    expected_owner_id=owner_id,
                )
                self.assertEqual(selected.selected_slot, 1)
                alternate, alternate_turn, alternate_waited = cast_when_legal(
                    post_death, character, monster, deck
                )
                alternate_before = post_death.fight.actors[owner_id]
                paid(alternate_before, alternate)
                alternate_ids_before = set(post_death.fight.actors)
                commit_spell_transaction(post_death, alternate, stats_serializer=stats)
                alternate_ids = set(post_death.fight.actors) - alternate_ids_before
                self.assertEqual(len(alternate_ids), 1)
                alternate_id = alternate_ids.pop()
                self.assertEqual(
                    post_death.fight.actors[alternate_id].native_summon_source["ref"], 4
                )
                self.assertIs(
                    post_death.fight.native_captured_rosters[str(owner_id)][
                        "available"
                    ][1],
                    False,
                )
                print(
                    "STAGE paid profile 4 invocation committed on post-death branch",
                    flush=True,
                )
                completed.append(
                    {
                        "profiles": [87, 87, 4],
                        "death_packet": 12727,
                        "death_before_turn_close": True,
                        "slot_reused": first_slot,
                        "reuse_turn": second_turn,
                        "reuse_wait_reasons": waited[-2:],
                        "alternate_turn": alternate_turn,
                        "alternate_wait_reasons": alternate_waited[-2:],
                    }
                )
                return {"status": "verified", "profile_sequence": [87, 87, 4]}

            with tempfile.TemporaryDirectory() as temp:
                report = ready_audit.run(
                    Path(temp) / "osa-last-breath-paid-reuse.json",
                    cases_override=[(2, 31, None)],
                    turn_cycle=True,
                    turn_steps=0,
                    active_deck_provider=lambda breed, level, passive: [
                        7307,
                        7317,
                        7322,
                    ],
                    character_fixture_provider=seed_roster,
                    monster_reference=5525,
                    monster_level=1,
                    on_runtime=lifecycle,
                )
            row = report["rows"][0]
            self.assertTrue(
                completed,
                f"real Ready lifecycle failed: status={row.get('status')} stage={row.get('failed_stage')} "
                f"reason={row.get('reason')} traceback={row.get('traceback')}",
            )
            self.assertTrue(report["source_stable"], row)
            self.assertTrue(report["ready_gate_passed"], row)
            self.assertEqual(report["status_counts"], {"ready_started": 1})


if __name__ == "__main__":
    unittest.main()
