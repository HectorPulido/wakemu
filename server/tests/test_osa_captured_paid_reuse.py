"""Actual Osa Ready/granted7348 -> captured324 -> recall859 -> paid reuse.

The owned source is a native5347 descriptor fixture, not an upstream encounter.
The production audit prepares/commits native transactions without socket/DB writes.
"""
from copy import deepcopy
from contextlib import contextmanager
import json
from pathlib import Path
import random
import struct
import tempfile
import sys
from types import SimpleNamespace
import unittest

from wakfu_server.characters.captured_roster import OwnedCapturedRoster
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_summon_spellbook import actor_action_book
from wakfu_server.combat_summon_retirement import retired_summon_ids
from wakfu_server.combat_qi_fight import current_registry
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.fight_checkpoint_store import snapshot


@contextmanager
def scoped_audit_modules():
    """Resolve the repository audit tools without leaking their path edits."""
    tools = Path(__file__).resolve().parents[1] / "tools"
    original_path = list(sys.path)
    try:
        sys.path.insert(0, str(tools))
        import audit_owned_captured324_transaction as captured_audit
        import audit_summon_recall_transaction as recall_audit

        for module, name in (
            (captured_audit, "audit_owned_captured324_transaction.py"),
            (recall_audit, "audit_summon_recall_transaction.py"),
            (captured_audit.ready_audit, "audit_ready_start.py"),
        ):
            if Path(module.__file__).resolve() != tools / name:
                raise AssertionError("Foreign audit module: " + name)
        yield captured_audit, recall_audit
    finally:
        sys.path[:] = original_path


class OsaPaidCapturedReuseTests(unittest.TestCase):
    def test_paid_native_invocation_recall_reuse_and_current_reconnect(self):
        with scoped_audit_modules() as (captured_audit, recall_audit):
            observed = []

            def lifecycle(runtime, character, monster, deck, stats, los, first_id):
                owner_id = character["id"]
                fight = runtime.fight
                first = fight.actors[first_id]
                book = deepcopy(actor_action_book(first))
                self.assertEqual(
                    [row["reference"] for row in book["actions"]], [7356, 7357, 7358]
                )
                self.assertEqual(first.native_summon_source["ref"], 5347)
                self.assertEqual(first.native_controller_id, owner_id)
                self.assertEqual(first.owner_id, character["account_id"])
                self.assertEqual(
                    current_registry(fight).slots[first.native_obstacle_id]["identity"],
                    ["actor", first_id],
                )
                self.assertFalse(
                    fight.native_captured_rosters[str(owner_id)]["available"][3]
                )
                recall = recall_audit.recall_committed_capture(
                    runtime, character, monster, deck, stats, los, first_id
                )
                self.assertEqual(recall["status"], "committed", recall)
                self.assertTrue(recall["qi_retirement_verified"], recall)
                self.assertTrue(recall["captured_slot_released"], recall)
                self.assertIn(first_id, retired_summon_ids(runtime.fight))
                self.assertNotIn(first_id, runtime.fight.order)
                released = OwnedCapturedRoster.from_record(
                    runtime.fight.native_captured_rosters[str(owner_id)],
                    expected_owner_id=owner_id,
                )
                self.assertTrue(released.available[3])
                self.assertEqual(released.slots[3].profile_id, 5347)
                self.assertFalse(
                    any(
                        row and row["identity"] == ["actor", first_id]
                        for row in current_registry(runtime.fight).slots
                    )
                )
                # Advance through real end/ACK callbacks; do not refill resources,
                # move actors, or bypass per-turn casting policy for slot reuse.
                old_turn = runtime.fight.turn_id
                for _ in range(len(runtime.fight.actors) * 3):
                    current = runtime.fight.current
                    runtime.end_turn(
                        current.owner_id, current.id, current.turn_count
                    ) if current.controlled else runtime.end_server_turn(
                        current.id, runtime.fight.turn_id
                    )
                    if runtime.awaiting_ack is not None:
                        runtime.acknowledge_turn(
                            struct.pack(">i", runtime.awaiting_ack)
                        )
                    if (
                        runtime.fight.current.id == owner_id
                        and runtime.fight.turn_id > old_turn
                    ):
                        break
                self.assertEqual(runtime.fight.current.id, owner_id)
                self.assertGreater(runtime.fight.turn_id, old_turn)
                grant = grant_record(runtime.fight, owner_id, 7348)
                self.assertIsNotNone(grant)
                baseline = snapshot(runtime.fight)
                caster = runtime.fight.actors[owner_id]
                resources = (caster.ap, caster.mp, caster.effect_stats[4])
                occupied = {
                    actor.position
                    for actor in runtime.fight.actors.values()
                    if actor.hp > 0
                }
                candidates = sorted(
                    cell
                    for cell in runtime.fight.walkable
                    if cell not in occupied
                    and 1
                    <= abs(cell[0] - caster.position[0])
                    + abs(cell[1] - caster.position[1])
                    <= 4
                )
                failures = []
                transaction = None
                for cell in candidates:
                    rng = random.Random(31)
                    rng_before = rng.getstate()
                    try:
                        transaction = prepare_server_spell(
                            struct.pack(">qqiih", owner_id, grant["uid"], *cell),
                            character,
                            {monster["id"]: monster},
                            runtime.fight,
                            character["account_id"],
                            deck,
                            action_id=runtime.action_id + 1,
                            line_of_sight=los,
                            critical=False,
                            rng=rng,
                        )
                    except ValueError as error:
                        self.assertEqual(snapshot(runtime.fight), baseline)
                        self.assertEqual(rng.getstate(), rng_before)
                        failures.append(str(error))
                        continue
                    break
                self.assertIsNotNone(transaction, failures)
                self.assertEqual(snapshot(runtime.fight), baseline)
                successors = set(transaction.fight.actors) - set(runtime.fight.actors)
                self.assertEqual(len(successors), 1)
                second_id = successors.pop()
                self.assertNotEqual(second_id, first_id)
                self.assertEqual(
                    (
                        transaction.fight.actors[owner_id].ap,
                        transaction.fight.actors[owner_id].mp,
                        transaction.fight.actors[owner_id].effect_stats[4],
                    ),
                    tuple(
                        value - transaction.plan["costs"][key]
                        for value, key in zip(resources, ("ap", "mp", "wp"))
                    ),
                )
                commit_spell_transaction(runtime, transaction, stats_serializer=stats)
                self.assertIn(first_id, retired_summon_ids(runtime.fight))
                self.assertNotIn(second_id, retired_summon_ids(runtime.fight))
                self.assertFalse(
                    runtime.fight.native_captured_rosters[str(owner_id)]["available"][3]
                )
                self.assertEqual(
                    actor_action_book(runtime.fight.actors[second_id]), book
                )
                self.assertEqual(
                    runtime.fight.actors[second_id].native_controller_id, owner_id
                )
                self.assertEqual(
                    current_registry(runtime.fight).slots[
                        runtime.fight.actors[second_id].native_obstacle_id
                    ]["identity"],
                    ["actor", second_id],
                )
                json.dumps(snapshot(runtime.fight), allow_nan=False)
                # Exercise the current owned reconstruction using actual serializer
                # and birth payloads; source gameplay remains exactly unchanged.
                from wakfu_server.combat_shared import Registry, Session
                from wakfu_server.combat_session_adapter import CombatSessionAdapter
                from wakfu_server.combat_reconnect_snapshot import owned_snapshot

                owner_session = Session(
                    character["account_id"],
                    owner_id,
                    "isolated-owned",
                    character["map_id"],
                    character.get("instance_id", 0),
                )
                registry = Registry(lambda session: session == owner_session)
                adapter = CombatSessionAdapter(
                    SimpleNamespace(
                        character=lambda account, identity: character
                        if (account, identity) == (character["account_id"], owner_id)
                        else self.fail("foreign owner")
                    )
                )
                adapter.registry = registry
                arena = dict(
                    runtime.fight.native_qi_snapshot,
                    map_id=character["map_id"],
                    instance_id=character.get("instance_id", 0),
                    min_z=min(c[2] for c in runtime.fight.walkable),
                    max_z=max(c[2] for c in runtime.fight.walkable),
                )
                shared = registry.register(
                    runtime.fight,
                    owner_session,
                    runtime=runtime,
                    join_context=dict(
                        arena=arena,
                        terrain_effect_id=46,
                        terrain_instance_id=-300,
                        leaders={0: owner_id, 1: monster["id"]},
                        monsters={monster["id"]: monster},
                    ),
                )
                before = snapshot(runtime.fight)
                packets = owned_snapshot(
                    runtime.fight,
                    shared,
                    owner_session,
                    actor_payload=adapter.actor_payload,
                )
                births = runtime.fight.native_summon_creation_deliveries
                retired_birth = (
                    births[first_id]["opcode"],
                    bytes.fromhex(births[first_id]["payload_hex"]),
                )
                current_birth = (
                    births[second_id]["opcode"],
                    bytes.fromhex(births[second_id]["payload_hex"]),
                )
                self.assertNotIn(retired_birth, packets)
                self.assertEqual(packets.count(current_birth), 1)
                self.assertEqual(snapshot(runtime.fight), before)
                observed.append(
                    dict(
                        first=first_id,
                        second=second_id,
                        recall=recall["status"],
                        checkpoint=True,
                        recovery_packets=len(packets),
                    )
                )
                return dict(status="verified", first=first_id, second=second_id)

            with tempfile.TemporaryDirectory() as temp:
                report = captured_audit.run(
                    Path(temp) / "osa.json",
                    commit_lifecycle=True,
                    captured_commit_callback=lifecycle,
                )
            self.assertEqual(len(observed), 1, report)
            self.assertEqual(
                report["owned_captured_transaction"]["captured_commit_callback"][
                    "status"
                ],
                "verified",
            )
            self.assertTrue(
                report["owned_captured_transaction"]["lifecycle"]["summon_turn_started"]
            )
            self.assertTrue(report["source_stable"])
