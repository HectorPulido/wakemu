"""Bulk actual class initialization and owned grant access; never live services."""
import argparse
import json
import os
import struct
from copy import deepcopy
from pathlib import Path

import audit_class_initialization as initialization
import audit_ready_start as ready_audit
from wakfu_server.combat_cast import resolve_owned_spell_action
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_server_spell import (
    compiled_runtime_catalog,
    server_runtime,
    prepare_server_spell,
)
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.combat_native_spell_casting import catalog as native_casting_catalog
from inventory_class_spell_state_access import state_references
from wakfu_server.spells import validate_deck
from class_spell_eligible_targets import eligible_cast_targets


def state_population(fight):
    return {
        identity: tuple(
            (entry.reference, entry.level, entry.uid)
            for entry in actor.state_ledger.entries
        )
        for identity, actor in fight.actors.items()
    }


def changed_state_references(before, after):
    changed = set()
    for identity in set(before) | set(after):
        old, new = before.get(identity, ()), after.get(identity, ())
        if old != new:
            changed.update(row[0] for row in set(old) ^ set(new))
    return changed


def inspect(preview, character, monster, deck, packets):
    records = []
    actor = preview.actors[character["id"]]
    before = snapshot(preview)
    factory, adapter = server_runtime(
        character, {monster["id"]: monster}, deck, action_id=1, critical=False
    )
    book = adapter.actor_authority(preview, actor).native_spellbook
    native_casting = native_casting_catalog()
    original_states = state_population(preview)
    original_grants = deepcopy(granted_spells(preview, actor.id))

    def los(origin, target, fight):
        return authoritative_visible(
            fight.map_id,
            origin,
            target,
            fight,
            blocking_footprints={
                value.id: {value.position[:2]}
                for value in fight.actors.values()
                if value.hp > 0
            },
        )

    for reference in sorted(granted_spells(preview, actor.id)):
        record = grant_record(preview, actor.id, reference)
        row = dict(
            record,
            actual_owned_book_level=book.level(reference),
            actual_progression_present=reference in (book.progression_levels or {}),
        )
        if preview.current is not actor:
            row["access"] = "deferred_actual_actor_not_current"
        else:
            try:
                (
                    selected,
                    selected_reference,
                    selected_level,
                ) = resolve_owned_spell_action(
                    dict(actor_id=actor.id, spell_uid=record["uid"]),
                    character,
                    preview,
                    actor.owner_id,
                    deck,
                )
                row.update(
                    access="owned_uid_resolved",
                    actor_id=selected.id,
                    evaluation_level=selected_level,
                    resolved_reference=selected_reference,
                )
                selection = eligible_cast_targets(
                    preview,
                    character,
                    deck,
                    record["uid"],
                    adapter=adapter,
                    line_of_sight=los,
                    actor_id=actor.id,
                )
                row["target_selection"] = selection
                attempts = []
                for candidate in selection["eligible"]:
                    target = candidate["target"]
                    try:
                        transaction = prepare_server_spell(
                            struct.pack(">qqiih", actor.id, record["uid"], *target),
                            character,
                            {monster["id"]: monster},
                            preview,
                            actor.owner_id,
                            deck,
                            action_id=1,
                            line_of_sight=los,
                            critical=False,
                        )
                        attempts.append(
                            dict(
                                target=target,
                                status="prepared_transaction",
                                packet_count=len(transaction.packets),
                            )
                        )
                        changed = changed_state_references(
                            original_states, state_population(transaction.fight)
                        )
                        attempts[-1]["changed_state_references"] = sorted(changed)
                        draft = transaction.fight
                        draft_grants = granted_spells(draft, actor.id)
                        added_grants = {
                            reference
                            for reference, entry in draft_grants.items()
                            if original_grants.get(reference) != entry
                        }
                        removed_grants = set(original_grants) - set(draft_grants)
                        attempts[-1]["added_grant_references"] = sorted(added_grants)
                        attempts[-1]["removed_grant_references"] = sorted(
                            removed_grants
                        )
                        attempts[-1]["state_population_after"] = state_population(draft)
                        if changed or added_grants:
                            followups = []
                            owned_actions = {
                                value: dict(uid=(actor.id << 32) | value)
                                for value in validate_deck(
                                    deck, character["breed"], character["level"]
                                )["active"]
                                if value
                            }
                            owned_actions.update(granted_spells(draft, actor.id))
                            for dependent in sorted(owned_actions):
                                definition = native_casting[str(dependent)]
                                relevant_states = state_references(definition) & changed
                                if (
                                    not relevant_states
                                    and dependent not in added_grants
                                ):
                                    continue
                                dependent_record = owned_actions[dependent]
                                next_selection = eligible_cast_targets(
                                    draft,
                                    character,
                                    deck,
                                    dependent_record["uid"],
                                    adapter=adapter,
                                    line_of_sight=los,
                                    actor_id=actor.id,
                                )
                                if not next_selection["eligible"]:
                                    followups.append(
                                        dict(
                                            reference=dependent,
                                            status=next_selection["status"],
                                            target_selection=next_selection,
                                        )
                                    )
                                for next_candidate in next_selection["eligible"]:
                                    next_target = next_candidate["target"]
                                    try:
                                        next_transaction = prepare_server_spell(
                                            struct.pack(
                                                ">qqiih",
                                                actor.id,
                                                dependent_record["uid"],
                                                *next_target
                                            ),
                                            character,
                                            {monster["id"]: monster},
                                            draft,
                                            actor.owner_id,
                                            deck,
                                            action_id=1,
                                            line_of_sight=los,
                                            critical=False,
                                        )
                                        followups.append(
                                            dict(
                                                reference=dependent,
                                                target=next_target,
                                                status="prepared_transaction",
                                                packet_count=len(
                                                    next_transaction.packets
                                                ),
                                                target_selection=next_selection,
                                            )
                                        )
                                    except Exception as error:
                                        followups.append(
                                            dict(
                                                reference=dependent,
                                                target=next_target,
                                                status="rejected",
                                                error=type(error).__name__,
                                                reason=str(error),
                                                stage="effect_transaction",
                                                target_selection=next_selection,
                                            )
                                        )
                            attempts[-1]["state_followups"] = followups
                    except Exception as error:
                        attempts.append(
                            dict(
                                target=target,
                                status="rejected",
                                error=type(error).__name__,
                                reason=str(error),
                                stage="effect_transaction",
                            )
                        )
                row["cast_attempts"] = attempts
                owned = [
                    uid
                    for uid, entry in preview.owned_stat_effects.items()
                    if entry.get("family") == "eWn"
                    and entry["target_id"] == actor.id
                    and entry["spell_id"] == reference
                ]
                if owned:
                    clone = deepcopy(preview)
                    dispatcher, removed_packets = factory(
                        clone,
                        dict(
                            actor_id=actor.id,
                            spell_id=reference,
                            evaluation_level=record["level"],
                            target=actor.position,
                            roots=(),
                            critical=False,
                        ),
                    )
                    retention = dispatcher.native_retention
                    retention.removal(retention.view()).remove((owned[0],))
                    try:
                        resolve_owned_spell_action(
                            dict(actor_id=actor.id, spell_uid=record["uid"]),
                            character,
                            clone,
                            actor.owner_id,
                            deck,
                        )
                        row["after_owned_removal"] = "incorrectly_accessible"
                    except ValueError as error:
                        row.update(
                            after_owned_removal="expired_uid_rejected",
                            removal_reason=str(error),
                            removal_packets=len(removed_packets),
                            removed_effect_uid=owned[0],
                        )
            except ValueError as error:
                row.update(access="rejected", reason=str(error))
        records.append(row)
    if snapshot(preview) != before:
        raise AssertionError("Grant access audit changed its source fight")
    return dict(
        grants=records,
        current_actor_id=None if preview.current is None else preview.current.id,
        application_packets=sum(opcode == 13497 for opcode, body in packets),
        initial_state_population=original_states,
        native_flag=os.environ.get("WAKFU_NATIVE_GRANTED_CAST", "0"),
        gameplay_verified=False,
        source_criteria_executed_by_common_initialization=True,
        rollback_preserved=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    ready_audit.run(
        args.output,
        basics_only=True,
        turn_cycle=True,
        turn_steps=1,
        cases_override=[
            (breed, level, None)
            for breed in sorted(initialization.BREEDS)
            for level in (1, 200)
        ],
        on_ready=inspect,
    )
