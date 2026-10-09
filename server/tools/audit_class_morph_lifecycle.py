"""Actual class933 temporary book lifecycle; offline, no services or injected states."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import random
import struct
from unittest.mock import patch
import audit_ready_start as ready
from audit_class_normal_casts import root_failure
from audit_class_character_copy_lifecycle import reach, advance
from class_spell_eligible_targets import eligible_cast_targets
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import prepare_server_spell, server_runtime
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_morph_spellbook import morph_record
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import available_spells
from morph_audit_serialization import normalize_morph_evidence


class OwnedMorphLifecycle:
    def __init__(self, partial_output=None):
        self.partial_output = partial_output

    def __call__(
        self, runtime, character, monster, deck, initial_packets, stats_serializer
    ):
        original = snapshot(runtime.fight)
        branch = deepcopy(runtime)
        trace = []
        result = dict(
            scope="native_class11_8587_933_profile5900_owned_lifecycle",
            full_client_verified=False,
            lifecycle_verified=False,
        )

        def los(origin, target, fight):
            return authoritative_visible(
                fight.map_id,
                origin,
                target,
                fight,
                blocking_footprints={
                    a.id: {a.position[:2]} for a in fight.actors.values() if a.hp > 0
                },
            )

        def prepare(uid, target):
            return prepare_server_spell(
                struct.pack(">qqiih", character["id"], uid, *target),
                character,
                {monster["id"]: monster},
                branch.fight,
                character["account_id"],
                deck,
                action_id=branch.action_id + 1,
                line_of_sight=los,
                critical=False,
                rng=random.Random(17),
            )

        def select(uid):
            _, adapter = server_runtime(
                character,
                {monster["id"]: monster},
                deck,
                action_id=branch.action_id + 1,
                critical=False,
                rng=random.Random(17),
            )
            return eligible_cast_targets(
                branch.fight,
                character,
                deck,
                uid,
                adapter=adapter,
                line_of_sight=los,
                actor_id=character["id"],
                limit=128,
                maximum_eligible=1,
            )

        def cast(uid):
            selected = select(uid)
            result.setdefault("target_selections", []).append(
                dict(uid=uid, selection=selected)
            )
            if not selected["eligible"]:
                raise ValueError("Actual owned morph action has no legal native target")
            target = tuple(selected["eligible"][0]["target"])
            before = snapshot(branch.fight)
            with combat_diagnostic_scope(lambda **e: trace.append(e), limit=4096):
                tx = prepare(uid, target)
            if snapshot(branch.fight) != before:
                raise AssertionError("Morph preparation mutated its source")
            costs = tx.plan["costs"]
            commit_spell_transaction(branch, tx, stats_serializer=stats_serializer)
            return dict(uid=uid, target=target, costs=costs)

        try:
            result["owner_turns"] = reach(branch, character["id"])
            grant = grant_record(branch.fight, character["id"], 8587)
            if grant is None:
                raise ValueError("Original Ready649 did not grant parent8587")
            result["producer_steps"] = []
            # Original8587 criterion requires9322. Native innate damage/turn
            # reactions produce it from actual Sacrier state9324 thresholds.
            # Fire5028 supplies a legal source self-HP-loss producer; all HP,
            # stacks, resource costs and timers remain production outcomes.
            for attempt in range(32):
                selected = select(grant["uid"])
                result.setdefault("target_selections", []).append(
                    dict(
                        uid=grant["uid"],
                        stage="parent_prerequisite",
                        selection=selected,
                    )
                )
                if selected["eligible"]:
                    break
                if branch.fight.phase != "active":
                    raise ValueError("Fight ended before actual morph prerequisite")
                actor = branch.fight.actors[character["id"]]
                states = [
                    dict(reference=e.reference, level=e.level)
                    for e in actor.state_ledger.entries
                    if e.reference in (9312, 9313, 9322, 9324, 9342)
                ]
                step = dict(
                    attempt=attempt, hp=actor.hp, max_hp=actor.max_hp, states=states
                )
                before = snapshot(branch.fight)
                try:
                    step["cast"] = cast((character["id"] << 32) | 5028)
                except ValueError as error:
                    if snapshot(branch.fight) != before:
                        raise AssertionError("Rejected legal producer changed source")
                    step["rejection"] = str(error)
                    step["turns"] = []
                    # Force a real boundary rather than reach() returning the
                    # same exhausted caster turn without resource recovery.
                    step["turns"].append(dict(packet_count=len(advance(branch))))
                    step["turns"].extend(reach(branch, character["id"]))
                result["producer_steps"].append(step)
            else:
                raise ValueError("Actual legal self-damage sequence did not unlock9322")
            result["pre_parent_states"] = [
                dict(reference=e.reference, level=e.level, uid=e.uid)
                for e in branch.fight.actors[character["id"]].state_ledger.entries
            ]
            result["parent"] = cast(grant["uid"])
            result["post_parent_states"] = [
                dict(reference=e.reference, level=e.level, uid=e.uid)
                for e in branch.fight.actors[character["id"]].state_ledger.entries
            ]
            book = morph_record(branch.fight, character["id"])
            if book is None or book["profile_id"] != 5900:
                raise ValueError("Actual parent8587 did not install native profile5900")
            result["temporary_book"] = deepcopy(book)
            result["foreign_uid_rejections"] = []
            raw_uid = next(iter(book["levels"]))
            for foreign in (
                (character["id"] << 32) | raw_uid,
                (monster["id"] << 32) | raw_uid,
            ):
                before = snapshot(branch.fight)
                try:
                    prepare(foreign, branch.fight.actors[character["id"]].position)
                except ValueError as error:
                    result["foreign_uid_rejections"].append(
                        dict(uid=foreign, reason=str(error))
                    )
                else:
                    raise AssertionError(
                        "Foreign UID accepted by actual temporary book"
                    )
                if snapshot(branch.fight) != before:
                    raise AssertionError("Foreign UID rejection changed source")
            result["child_attempts"] = []
            qualified = deepcopy(branch)
            qualified_checkpoint = snapshot(qualified.fight)
            result["qualified_post_parent_checkpoint"] = qualified_checkpoint
            chosen = None
            used = None
            for uid in tuple(book["levels"]):
                # Each original action receives the same real qualified source,
                # not resources or usage counters modified by its siblings.
                branch = deepcopy(qualified)
                before = snapshot(branch.fight)
                trace_start = len(trace)
                row = dict(uid=uid, scope="independent_same_actual_post_parent_source")
                try:
                    committed = cast(uid)
                except ValueError as error:
                    if snapshot(branch.fight) != before:
                        raise AssertionError("Rejected child action changed source")
                    row.update(
                        status="rejected",
                        reason=str(error),
                        failure=root_failure(error, trace[trace_start:]),
                    )
                else:
                    row.update(
                        committed,
                        status="committed",
                        committed_checkpoint=snapshot(branch.fight),
                    )
                    json.dumps(row["committed_checkpoint"], allow_nan=False)
                    if chosen is None:
                        chosen = deepcopy(branch)
                        used = committed
                row["trace"] = trace[trace_start:]
                row["qualified_source_preserved"] = (
                    snapshot(qualified.fight) == qualified_checkpoint
                )
                if not row["qualified_source_preserved"]:
                    raise AssertionError("Independent child mutated qualified baseline")
                result["child_attempts"].append(row)
            result["all_three_children_committed"] = len(
                result["child_attempts"]
            ) == 3 and all(
                row["status"] == "committed" for row in result["child_attempts"]
            )
            if chosen is None:
                raise ValueError("No actual temporary-book child committed")
            branch = chosen
            result["restoration_path_child_uid"] = used["uid"]
            result["restoration_steps"] = []
            for _ in range(16):
                current = morph_record(branch.fight, character["id"])
                if current is None:
                    break
                if (
                    branch.awaiting_ack is None
                    and branch.fight.current.id == character["id"]
                ):
                    # Native profile's own legal actions may explicitly restore
                    # the base book; no direct book/state removal is permitted.
                    for uid in tuple(current["levels"]):
                        if uid == used["uid"]:
                            continue
                        before = snapshot(branch.fight)
                        try:
                            step = cast(uid)
                        except ValueError as error:
                            if snapshot(branch.fight) != before:
                                raise AssertionError(
                                    "Rejected restoration changed source"
                                )
                            result["restoration_steps"].append(
                                dict(uid=uid, rejected=str(error))
                            )
                        else:
                            result["restoration_steps"].append(step)
                            if morph_record(branch.fight, character["id"]) is None:
                                break
                if morph_record(branch.fight, character["id"]) is None:
                    break
                packets = advance(branch)
                result["restoration_steps"].append(dict(turn_packets=len(packets)))
            result["restored"] = morph_record(branch.fight, character["id"]) is None
            if not result["restored"]:
                raise ValueError(
                    "Temporary book not restored by actual legal actions/turns"
                )
            before = snapshot(branch.fight)
            try:
                prepare(raw_uid, branch.fight.actors[character["id"]].position)
            except ValueError as error:
                result["expired_raw_uid_rejection"] = str(error)
            else:
                raise AssertionError(
                    "Restored base book still accepts old raw morph UID"
                )
            if snapshot(branch.fight) != before:
                raise AssertionError("Expired UID rejection changed source")
            json.dumps(snapshot(branch.fight), allow_nan=False)
            if not result["all_three_children_committed"]:
                raise ValueError(
                    "Some original temporary-book children did not commit independently"
                )
            result.update(status="lifecycle_completed", lifecycle_verified=True)
        except Exception as error:
            result.update(status="rejected", failure=root_failure(error, trace))
        result["trace"] = trace
        result["source_preserved"] = snapshot(runtime.fight) == original
        if not result["source_preserved"]:
            raise AssertionError("Morph auditor mutated original Ready source")
        projections = []
        normalized = normalize_morph_evidence(result, set_projections=projections)
        normalized["json_set_projections"] = projections
        if self.partial_output is not None:
            self.partial_output.write_text(
                json.dumps(normalized, indent=2, allow_nan=False) + "\n"
            )
        return normalized


def run(output):
    original_fixture = ready.fixture_module.fixture

    def native_enemy_fixture(*args, **kwargs):
        return original_fixture(
            *args, **dict(kwargs, monster_reference=5574, monster_level=133)
        )

    # Original source-confirmed133..138 enemy, with unchanged native HP4500.
    with patch.object(ready.fixture_module, "fixture", native_enemy_fixture):
        return ready.run(
            output,
            cases_override=[(11, 200, None)],
            turn_cycle=True,
            turn_steps=1,
            active_deck_provider=lambda breed, level, passive: [
                s["id"] for s in available_spells(breed, level) if s["kind"] == "active"
            ][:12],
            on_runtime=OwnedMorphLifecycle(output.with_suffix(".partial.json")),
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    run(parser.parse_args().output)
