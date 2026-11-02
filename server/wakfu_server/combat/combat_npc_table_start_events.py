"""Explicit native-initial-state listeners on the existing reviewed table clock.

This schedules declared native global1003 bodies, like reviewed scene listeners.
It is Wakemu encounter authoring, not a recovered original server publisher.
"""
from copy import deepcopy
from hashlib import sha256
import json

POLICY = "wakemu.reviewed-native-initial-state-table-start-v1"


def _digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def _program(catalog, reference, root):
    state = catalog["states"].get(str(reference))
    if not isinstance(state, dict) or root not in state.get("effect_ids", ()):
        raise ValueError("Native table listener is not a direct constructor-state root")
    effect = catalog["effects"].get(str(root))
    if not isinstance(effect, dict):
        raise ValueError("Native table listener has no original effect")
    return {"state": state, "effect": effect}


def _validated(declaration, catalog, metadata):
    if (
        not isinstance(declaration, dict)
        or set(declaration)
        != {
            "policy",
            "state_id",
            "root_id",
            "source_sha256",
            "metadata_sha256",
            "authority",
            "source_uri",
        }
        or declaration["policy"] != POLICY
    ):
        raise ValueError("Missing explicit native table-listener authoring")
    if any(
        type(declaration[k]) is not int or declaration[k] <= 0
        for k in ("state_id", "root_id")
    ):
        raise ValueError("Invalid native table-listener source identity")
    if any(
        not isinstance(declaration[k], str) or not declaration[k].strip()
        for k in ("authority", "source_uri")
    ):
        raise ValueError("Missing native table-listener provenance")
    program = _program(catalog, declaration["state_id"], declaration["root_id"])
    root = program["effect"]
    native = metadata.get(str(declaration["root_id"]), {})
    if (
        _digest(program) != declaration["source_sha256"]
        or _digest(native) != declaration["metadata_sha256"]
        or root.get("effect_class") != 330
        or root.get("target_masks") != [None, None, None, None, None, [1003], None]
        or native.get("subscription") is not True
        or native.get("event_global_subscription") is not True
        or native.get("event_reverse_subscription") is not False
        or native.get("event_caster_code") != 2
        or native.get("event_target_code") != 2
        or native.get("event_execution_count") != -1
        or native.get("event_execution_count_per_level") != 0
    ):
        raise ValueError(
            "Native table-listener program or unlimited global source changed"
        )
    return declaration


def freeze_initial_listeners(fight, actor, reference, receipt):
    """Freeze actual constructor carriers; never apply a second native state."""
    from .combat_npc_attack import npc_spell_catalog
    from .combat_npc_event_controller import event_controller_record
    from .combat_server_spell import states_catalog
    from .combat_retained_runtime import native_retained_metadata
    from .combat_npc_table_declarations import constructor_table_declarations
    from .combat_encounter_player_table_events import freeze_player_table_listeners

    freeze_player_table_listeners(fight, actor, reference, receipt)

    policy = npc_spell_catalog()["activation_policy"]
    admitted = event_controller_record(policy, reference, actor.effective_level)
    declarations = (
        []
        if admitted is None
        else admitted["event_controller"].get("repeat_at_round_start", [])
    )
    if not isinstance(declarations, list):
        raise ValueError("Invalid declared native initial table listeners")
    # A real spell book does not remove the actor's native constructor callbacks.
    # Keep event-only admission separate from explicit shared table publication.
    declarations = declarations + constructor_table_declarations(reference)
    if not declarations:
        return []
    if (
        actor.controlled
        or receipt.get("initialized") is not True
        or receipt.get("ref") != reference
    ):
        raise ValueError(
            "Native table listener requires its actual ordinary constructor"
        )
    catalog, metadata = states_catalog(), native_retained_metadata()["effects"]
    resolved = {s["state_id"] for s in receipt["resolved_states"]}
    result, seen = [], set()
    for declaration in declarations:
        declaration = _validated(declaration, catalog, metadata)
        identity = declaration["state_id"], declaration["root_id"]
        if identity in seen or declaration["state_id"] not in resolved:
            raise ValueError(
                "Native table listener lacks a unique constructor-state source"
            )
        carriers = [
            s
            for s in actor.state_ledger.entries
            if s.reference == declaration["state_id"]
            and s.target_id == actor.id
            and s.caster_id == actor.id
        ]
        if len(carriers) != 1:
            raise ValueError("Native table listener has no unique actual state UID")
        result.append(
            dict(declaration=deepcopy(declaration), state_uid=carriers[0].uid)
        )
        seen.add(identity)
    return result


def has_initial_table_interest(fight):
    return any(
        r.get("table_start_listeners")
        for r in getattr(fight, "native_npc_initialization_receipts", {}).values()
    )


def _constructor_successor(actor, listener, ancestry):
    """Follow actual self-reapplication, never another same-reference state."""
    reference = listener["declaration"]["state_id"]
    original_uid = listener["state_uid"]
    successors = []
    for carrier in actor.state_ledger.entries:
        if (
            carrier.reference != reference
            or carrier.target_id != actor.id
            or carrier.caster_id != actor.id
        ):
            continue
        current, seen = carrier.uid, set()
        while current is not None and current not in seen:
            seen.add(current)
            source = ancestry.get(current)
            if (
                source is None
                or source["state_reference"] != reference
                or source["target_id"] != actor.id
                or source["caster_id"] != actor.id
            ):
                break
            if current == original_uid:
                successors.append(carrier)
                break
            if source["parent_known"] is not True:
                break
            current = source["parent_state_uid"]
    if len(successors) > 1:
        raise ValueError(
            "Native initial table listener has ambiguous constructor successors"
        )
    return successors[0] if successors else None


def initial_table_deliveries(dispatcher):
    """Select only declared, still-owned, source-qualified retained Qf entries."""
    from .combat_npc_external_event_scope import qualified_npc_uids
    from .combat_server_spell import states_catalog
    from .combat_retained_runtime import native_retained_metadata

    fight = dispatcher.native_retention.fight
    receipts = getattr(fight, "native_npc_initialization_receipts", {})
    if not has_initial_table_interest(fight):
        return []
    qualified = qualified_npc_uids(dispatcher)
    entries = tuple(dispatcher.native_retention.view().entries)
    catalog, metadata = states_catalog(), native_retained_metadata()["effects"]
    result, ancestry = [], None
    for identity, receipt in receipts.items():
        listeners = receipt.get("table_start_listeners", ())
        actor = fight.actors.get(identity)
        if not listeners or actor is None or actor.hp <= 0:
            continue
        if (
            actor.controlled
            or receipt.get("initialized") is not True
            or receipt.get("descriptor_level") != actor.effective_level
        ):
            raise ValueError("Native initial table listener lost constructor custody")
        selected = set()
        for listener in listeners:
            declaration = _validated(listener["declaration"], catalog, metadata)
            carrier = next(
                (
                    s
                    for s in actor.state_ledger.entries
                    if s.uid == listener["state_uid"]
                ),
                None,
            )
            if carrier is None:
                # An additive native callback can replace its own constructor
                # carrier. Preserve that exact ancestry across later rounds;
                # removal or unrelated reinstallation supplies no authority.
                from .combat_retained_source_provenance import state_source_provenance

                if ancestry is None:
                    ancestry = state_source_provenance(fight)
                carrier = _constructor_successor(actor, listener, ancestry)
                if carrier is None:
                    continue
            if (
                carrier.reference != declaration["state_id"]
                or carrier.target_id != identity
                or carrier.caster_id != identity
            ):
                raise ValueError("Native initial table listener source UID changed")
            for entry in entries:
                retained = getattr(fight, "native_owned_group_effects", {}).get(
                    entry.uid, {}
                )
                if (
                    entry.uid in qualified
                    and entry.manager_id == identity
                    and entry.generic_effect == declaration["root_id"]
                    and retained.get("invocation", {}).get("state_uid") == carrier.uid
                ):
                    selected.add(entry.uid)
        result.append(dict(actor_id=identity, eligible_uids=sorted(selected)))
    return result
