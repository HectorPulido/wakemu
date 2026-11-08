"""Collect unreachable terminal fighter effect graphs, never accounting actors.

Candidate only: invoke on an unpublished preview after all native dispatch,
replay and removal callbacks have drained. Caller must supply pending roots.
"""
from collections import deque
from functools import lru_cache
from dataclasses import dataclass
import struct


_EFFECT_MAPS = (
    "owned_stat_effects",
    "native_owned_group_effects",
    "native_owned_area_effects",
    "native_owned_spatial_effects",
    "native_owned_state_containers",
)
# These are durable accounting/provenance, not a request to execute an effect.
# They are retained verbatim by the sweep. Live invocation references to their
# actor identities are traversed separately and retain that actor's effects.
_HISTORY = frozenset(
    (
        "events",
        "rift_monsters",
        "rift_wave_state",
        "native_npc_ai_actors",
        "native_timeline_removed",
        "native_turn_event_deliveries",
        "native_death_event_deliveries",
        "native_ordinary_npc_turn_roots",
        "native_ordinary_qi_retirements",
        "native_summon_retirements",
        "native_state_source_provenance",
        "native_artifact_activation_receipts",
        "native_instance_difficulty_snapshots",
        "native_retained_order",
        "placement",
        "native_spell_usage",
        "wakemu_ai_cast_history",
        "native_rift_creation_deliveries",
        "native_summon_creation_deliveries",
        # Actor -> (staged receipt index, actor offset), not an executable root.
        "native_rift_birth_locations",
        "native_npc_initialization_receipts",
        "native_encounter_roles",
        "native_spell_grants",
        "native_ai_team_context",
        "native_retained_tracking",
        "native_global_pv_collections",
    )
)
_SCALAR_KEY_MAPS = frozenset(
    (
        "effect_stats",
        "effect_minima",
        "effect_maxima",
        "effect_percentages",
        "effect_base_minima",
        "effect_base_maxima",
        "effect_resource_raw_currents",
        "effect_characteristic_raw_currents",
        "native_fight_property_counts",
        "native_world_property_counts",
        "spell_ap_cost_modifiers",
        "spell_range_modifiers",
        "selected_values",
        "active_cosmetics",
        "native_resource_numeric_observers",
    )
)
_ACTOR_CHARACTERISTIC_MAPS = frozenset(
    (
        "effect_stats",
        "effect_minima",
        "effect_maxima",
        "effect_percentages",
        "effect_base_minima",
        "effect_base_maxima",
    )
)


def _characteristic_scalar_map(value):
    """Checkpoint keys identify characteristics; values are numeric magnitudes."""
    if type(value) is not dict:
        return False
    for key, item in dict.items(value):
        if type(item) is not int:
            return False
        if type(key) is int:
            continue
        if type(key) is not str:
            return False
        try:
            if str(int(key)) != key:
                return False
        except ValueError:
            return False
    return True


def _actor_reference_fields(row):
    # Only direct native Actor fields have this meaning. A same-named map in
    # an invocation or extension retains the conservative generic traversal.
    if type(row) is not dict:
        return row
    return {
        key: value
        for key, value in dict.items(row)
        if not (
            type(key) is str
            and key in _ACTOR_CHARACTERISTIC_MAPS
            and _characteristic_scalar_map(value)
        )
    }


_UID_FIELDS = frozenset(
    (
        "uid",
        "base_uid",
        "owner_uid",
        "state_uid",
        "related_uid",
        "native_running_uid",
        "native_delayed_uid",
        "source_parent_uid",
        "parent_state_uid",
        "effect_uid",
    )
)


# Native producers key these collections by fighter identity, never runner UID.
_ACTOR_KEYED_ROOTS = frozenset(
    (
        "native_social_contexts",
        "native_class_initializations",
        "native_owned_equipment_sources",
        "native_timeline_member_counters",
        "native_consumable_initializations",
        "native_owned_equipment_initializations",
    )
)


def _delay_queue_entries(queue):
    """Validate TC/Tu shape; its insertion counter is not a running UID."""
    if (
        type(queue) is not dict
        or set(queue) != {"source", "next_sequence", "entries"}
        or queue["source"] != "native.eZR.bbS.SU.TC.Tu.v1"
        or type(queue["next_sequence"]) is not int
        or queue["next_sequence"] < 1
        or type(queue["entries"]) is not list
    ):
        raise ValueError("Unknown retained delay queue")
    previous = 0
    for row in queue["entries"]:
        if (
            type(row) is not dict
            or set(row)
            != {"sequence", "uid", "clock_id", "round", "phase", "invocation"}
            or any(
                type(row[key]) is not int
                for key in ("sequence", "uid", "clock_id", "round")
            )
            or row["uid"] <= 0
            or not previous < row["sequence"] < queue["next_sequence"]
            or row["phase"] not in ("start", "end")
            or type(row["invocation"]) is not dict
        ):
            raise ValueError("Unknown retained delay registration")
        previous = row["sequence"]
    return queue["entries"]


@dataclass(frozen=True)
class RetainedGCPlan:
    actor_ids: frozenset
    effect_uids: frozenset
    marked_actor_ids: frozenset
    opaque_sources: tuple
    orphan_container_uids: frozenset = frozenset()
    orphan_provenance_uids: frozenset = frozenset()


_CHILD_MAPS = (
    "owned_stat_effects",
    "native_owned_group_effects",
    "native_owned_area_effects",
    "native_owned_spatial_effects",
)


def _orphaned_containers(collections, facts, swept_uids):
    """Descriptors newly orphaned by this sweep, matching synchronize users.

    A carrier and its immutable PL descriptor share a UID but have distinct
    lifetimes. Removing the last child does not remove the carrier itself.
    """
    removed_users, remaining_users = set(), set()
    for collection in collections:
        for key, row in collection.items():
            uid = row.get("state_uid")
            if uid is None:
                continue
            if type(uid) is not int:
                raise ValueError("Noncanonical retained state container user")
            (removed_users if int(key) in swept_uids else remaining_users).add(uid)
    return frozenset(removed_users - remaining_users - swept_uids) & frozenset(
        int(key) for key in facts
    )


def _fields(payload, *, duplicate_scalars=()):
    # Deliberately avoid wire.py's catalog-owning import graph. Decode only
    # protobuf primitive wire fields, with strict bounds and no domain loads.
    result, offset = {}, 0

    def varint():
        nonlocal offset
        value = 0
        for shift in range(0, 70, 7):
            if offset >= len(payload):
                raise ValueError("Truncated GC wire varint")
            byte = payload[offset]
            offset += 1
            if shift == 63 and byte > 1:
                raise ValueError("Overflow GC wire varint")
            value |= (byte & 127) << shift
            if not byte & 128:
                return value
        raise ValueError("Overflow GC wire varint")

    while offset < len(payload):
        tag = varint()
        number, wire = tag >> 3, tag & 7
        if wire == 0:
            value = varint()
        elif wire in (1, 2, 5):
            length = varint() if wire == 2 else 8 if wire == 1 else 4
            value = payload[offset : offset + length]
            offset += length
            if len(value) != length:
                raise ValueError("Truncated GC wire field")
        else:
            raise ValueError("Unknown GC wire type")
        if (
            number == 0
            or number in result
            and not (
                number in duplicate_scalars and wire == 0 and result[number][0] == 0
            )
        ):
            raise ValueError("Unknown retained wire schema")
        result[number] = (wire, value)
    return result


def _signed(value):
    return value - (1 << 64) if value >= (1 << 63) else value


def _summon_307_references(outer):
    """Exact ordinary eZl vJ/wU/SQ descriptor; captured324 is a different ABI."""
    if 7 in outer or outer.get(6, (None,))[0] != 0:
        raise ValueError("Unknown retained summon recipient/caster")
    if any(outer.get(number, (None,))[0] != 2 for number in (8, 12)):
        raise ValueError("Missing complete retained summon descriptor")
    additional, summon = _fields(outer[8][1]), _fields(outer[12][1])
    if set(additional) != {1} or additional[1][0] != 2:
        raise ValueError("Unknown retained summon descriptor fields")
    if set(summon) != {4} or summon[4][0] != 0 or not 0 < summon[4][1] < 1 << 63:
        raise ValueError("Unknown retained summon actor identity")
    blob = additional[1][1]
    prefix = struct.Struct(">hHiqhBBBiqB")
    suffix = struct.Struct(">BqiB")
    minimum = 1 + prefix.size + 2 + suffix.size
    if len(blob) < minimum or blob[0] not in (0, 1):
        raise ValueError("Truncated or unknown retained summon descriptor")
    (
        reference,
        name_length,
        minimum_hp,
        actor_id,
        level,
        obstacle,
        vk,
        vm,
        direction,
        owner_id,
        from_symbiot,
    ) = prefix.unpack_from(blob, 1)
    offset = 1 + prefix.size
    count = struct.unpack_from(">H", blob, offset)[0]
    offset += 2
    if len(blob) != minimum + count * 2:
        raise ValueError("Unknown retained summon descriptor length")
    properties = blob[offset : offset + count * 2]
    if (
        reference <= 0
        or name_length != 0
        or minimum_hp != -1
        or actor_id != summon[4][1]
        or level < 0
        or vk != 0
        or vm != 0
        or not 0 <= direction < 8
        or owner_id != -1
        or from_symbiot != 0
        or any(value >= 128 for value in properties[::2])
        or len(set(properties[::2])) != count
        or any(value != 1 for value in properties[1::2])
    ):
        raise ValueError("Unknown retained summon descriptor values")
    anchor, caster_id, timeline_offset, team = suffix.unpack_from(
        blob, offset + count * 2
    )
    if (
        anchor not in (0, 1, 2)
        or team not in (0, 1)
        or caster_id == 0
        or caster_id != _signed(outer[6][1])
    ):
        raise ValueError("Mismatched retained summon timeline source")
    return {actor_id, caster_id}


def _wire_references(payload, family):
    """Exact source schemas; unknown extensions retain their whole manager."""
    outer = _fields(bytes.fromhex(payload))
    if set(outer) - set(range(1, 14)):
        raise ValueError("Unknown retained outer field")
    actors, uids, areas = set(), set(), set()
    for number, (wire, value) in outer.items():
        if number in (1, 2, 3, 4, 6, 7, 9, 10):
            if wire != 0:
                raise ValueError("Unknown retained scalar wire")
            if number in (6, 7):
                actors.add(_signed(value))
            elif number in (1, 2) and value:
                uids.add(value)
        elif wire != 2:
            raise ValueError("Unknown retained nested wire")
    if family == 307:
        actors.update(_summon_307_references(outer))
    for number in (5, 8, 11, 12, 13):
        if family == 307 and number in (8, 12):
            continue  # Fully checked together, including cross-field actor identities.
        if number not in outer:
            continue
        nested = _fields(
            outer[number][1], duplicate_scalars=(2, 5) if number == 11 else ()
        )
        if number == 5:
            permitted = {1, 2, 3}
        elif number == 8:
            if family == 57:
                # eWO.b(iP) writes ij.xF/xH through il.x/y: current-resource
                # restore/reduction booleans, never actor or running-effect IDs.
                if set(nested) != {34, 35} or any(
                    wire != 0 or value not in (0, 1) for wire, value in nested.values()
                ):
                    raise ValueError("Unknown native maximum-reduction flags")
                continue
            elif family in (20, 31, 41, 191, 991):
                # NativeMaximumResourceHandler.payload_for: effective maximum
                # delta and two current-resource flags, never reference IDs.
                if (
                    set(nested) != {10, 31, 32}
                    or any(wire != 0 for wire, _ in nested.values())
                    or not -(1 << 31) <= _signed(nested[10][1]) < 1 << 31
                    or nested[31][1] not in (0, 1)
                    or nested[32][1] not in (0, 1)
                ):
                    raise ValueError("Unknown retained maximum resource fields")
                continue
            permitted = (
                {10, 13, 17, 18, 19, 21, 22, 50}
                if family == 310
                else {14, 16, 17, 21}
                if family == 315
                else {10, 14, 19, 20}
                if family == 649
                else {12, 25}
            )
            if family == 315 and 21 in nested:
                areas.add(_signed(nested[21][1]))
            for key in (13, 50) if family == 310 else ():
                if key in nested and nested[key][1]:
                    uids.add(nested[key][1])
        elif number == 13:
            permitted = {1, 2, 4, 5, 6, 7, 8, 9}
        elif number == 12:
            # Summon additional data has further family-owned fields; preserve
            # its component until its complete source schema is admitted.
            raise ValueError("Opaque summon additional data")
        else:
            permitted = {1, 2, 3, 4, 5}
            if 3 in nested:
                if nested[3][0] != 2:
                    raise ValueError("Unknown timing deadline")
                deadline = _fields(nested[3][1])
                if set(deadline) - {1, 2, 3} or any(
                    w != 0 for w, _ in deadline.values()
                ):
                    raise ValueError("Unknown timing clock schema")
                if 1 in deadline and deadline[1][1]:
                    actors.add(_signed(deadline[1][1]))
        if set(nested) - permitted or any(
            w != 0 for key, (w, _) in nested.items() if not (number == 11 and key == 3)
        ):
            raise ValueError("Unknown retained nested fields")
    # PL1 id is packed state reference/level, not a running state UID. PL3 is
    # an area identity and is resolved through area nodes by the graph walk.
    if outer.get(9) == (0, 3) and 10 in outer:
        areas.add(_signed(outer[10][1]))
    return actors, uids, areas


# Validation remains eager for every row, including unreachable components.
# Cache only immutable, bounded wire inputs: no Fight, owner or source row is
# retained, and unknown/malformed schemas still raise on every attempted read.
_WIRE_REFERENCE_PARSER = _wire_references
_WIRE_FIELDS_PARSER = _fields
_WIRE_SIGNED_VALUE = _signed


@lru_cache(maxsize=4096)
def _cached_planner_wire_references(payload, family):
    return tuple(
        frozenset(values) for values in _WIRE_REFERENCE_PARSER(payload, family)
    )


def _planner_wire_references(payload, family):
    # Summon307 also reads the external struct ABI; retain its original path.
    # Custom functions/subclass hash/equality must never reach a cached lookup.
    if (
        type(payload) is str
        and len(payload) <= 4096
        and type(family) is int
        and family != 307
        and _wire_references is _WIRE_REFERENCE_PARSER
        and _fields is _WIRE_FIELDS_PARSER
        and _signed is _WIRE_SIGNED_VALUE
    ):
        return _cached_planner_wire_references(payload, family)
    return _wire_references(payload, family)


def reference_schema_value_known(value, key=None):
    """Context-sensitive opaque cases not excluded by plain graph admission."""
    if key not in ("native_context_hex", "child_effect_uids"):
        return True
    kind = type(value)
    # Contextual container aliases may already be visited under another key.
    # Keep these uncommon shapes on the complete legacy traversal.
    if kind not in (dict, str, int, bool, float, type(None)):
        return False
    if key == "child_effect_uids" and kind is dict:
        return all(
            type(children) in (list, tuple)
            and all(type(uid) is int for uid in children)
            for children in value.values()
        )
    if key == "native_context_hex" and kind is str:
        try:
            fields = _fields(bytes.fromhex(value)) if value else {}
            return not (set(fields) - {1, 2, 4, 5, 6, 7, 8, 9}) and all(
                wire == 0 for wire, _ in fields.values()
            )
        except (ValueError, TypeError):
            return False
    return True


def reference_schemas_known(snapshot):
    """Pure projected-data counterpart of the native canonical admission proof."""
    active = set()

    def visit(value, key=None):
        if not reference_schema_value_known(value, key):
            return False
        kind = type(value)
        if kind in (str, int, bool, float, type(None)):
            return True
        if kind not in (dict, list, tuple) or id(value) in active:
            return False
        active.add(id(value))
        try:
            if kind is dict:
                return all(
                    type(field) in (str, int) and visit(item, field)
                    for field, item in value.items()
                )
            return all(visit(item, key) for item in value)
        finally:
            active.remove(id(value))

    try:
        return visit(snapshot)
    finally:
        visit = None


def _group_listener_reference_fields(row, record):
    """Old triggering-event context is replaced before native group replay.

    Only the attested native group map calls this helper. Actual delayed
    invocations, source caster/target/owner fields and all other maps keep
    their complete reference graph. Stored source bytes are never rewritten.
    """
    from .combat_subscription_contracts import GROUP_SUBSCRIPTION_FAMILIES

    if (
        type(row) is not dict
        or type(record) is not dict
        or type(row.get("uid")) is not int
        or row["uid"] != record.get("uid")
        or type(row.get("effect_class")) is not int
        or row["effect_class"] not in GROUP_SUBSCRIPTION_FAMILIES
        or row["effect_class"] != record.get("effect_class")
    ):
        return row
    invocation = row.get("invocation")
    if (
        type(invocation) is not dict
        or type(invocation.get("native_trigger_context")) is not dict
        or invocation.get("native_delayed_uid") is not None
        or row.get("native_delayed_uid") is not None
        or "native_subscription_masks" not in row
        or "native_selector" not in row
        or "children" not in row
    ):
        return row
    return dict(
        row,
        invocation={
            key: value
            for key, value in invocation.items()
            if key != "native_trigger_context"
        },
    )


def plan_retired_effects(
    snapshot,
    terminal_ids,
    *,
    pending_roots,
    _reference_schemas_valid=False,
    _native_group_trigger_history=False
):
    """Pure graph plan from canonical snapshot-shaped data plus attested IDs.

    This helper does not attest terminal lifecycle. Production callers must
    validate that evidence before supplying terminal_ids. No actor is removed.
    """
    actors = {int(key): row for key, row in snapshot["actors"].items()}
    records = {
        int(key): row for key, row in snapshot["native_retained_records"].items()
    }
    active_areas = {
        int(key): row for key, row in snapshot.get("native_effect_areas", {}).items()
    }
    retired_areas = {
        int(key): row
        for key, row in snapshot.get("native_retired_area_managers", {}).items()
    }
    nodes = set(actors) | set(active_areas) | set(retired_areas)
    candidates = set(terminal_ids) & set(actors)
    owners = {uid: row["manager_id"] for uid, row in records.items()}
    # Replaced carrier descriptors may still own live state children. They
    # participate in reachability even when no longer retained as a Qf entry.
    for key, row in snapshot.get("native_owned_state_containers", {}).items():
        owners.setdefault(int(key), row.get("target_id"))
    storage_uids = set(owners)
    provenance = snapshot.get("native_state_source_provenance", {}).get("entries", {})
    for key, row in provenance.items():
        owners.setdefault(int(key), row.get("target_id"))
    owner_uids = set(owners)
    # Qs retirement keeps Qq as a PL/source descriptor. The admitted empty-
    # exit contracts never consume old child hints; activation appends new
    # hints. Restrict metadata-only edges to explicit PL/area_uid references.
    # Target/caster callbacks and pending roots retain the operational node.
    retained_managers = set(owners.values())
    dormant_areas = {
        identity
        for identity, row in retired_areas.items()
        if identity not in retained_managers
        and row.get("native_area_contract") in ("faM", "fbc", "fbd")
        and row.get("native_running_effect_manager") is False
        and row.get("executing") is False
        and row.get("removing") is False
        and not (row.get("state_ledger") or {}).get("entries", ())
    }
    area_source_node = lambda identity: ("area_source", identity)
    uid_node = lambda uid: ("effect", uid)
    edges = {identity: set() for identity in nodes}
    edges.update({area_source_node(identity): set() for identity in dormant_areas})
    edges.update({uid_node(uid): set() for uid in owners})
    edges.update({("operative", uid): {uid_node(uid)} for uid in owners})
    # A full actor root exposes its whole manager. A source/PL-only UID root
    # does not expose unrelated siblings owned by the same terminal actor.
    for uid, owner in owners.items():
        if owner in edges and uid in records:
            edges[owner].add(("operative", uid))
    # Areas still in Qs are executable roots regardless of their owner status.
    # A retired Qq with retained rows remains a root until area GC is audited.
    marked = (
        (set(actors) - candidates)
        | set(active_areas)
        | (set(retired_areas) & set(owners.values()))
    )
    # GetStateCountInRange(..., False) observes terminal carriers globally.
    # Preserve their value/identity without making their dormant children
    # executable roots or retaining unrelated state-owned runners.
    marked.update(
        uid_node(uid) for uid, row in records.items() if row.get("effect_class") == 310
    )
    opaque = []
    deferred = {} if _reference_schemas_valid is True else None
    wire_by_uid = {}

    def link(
        owner,
        actor_refs=(),
        uid_refs=(),
        *,
        operative=False,
        proof=False,
        source_areas=False
    ):
        area_metadata = type(owner) is tuple and owner[0] == "area_source"
        actor_targets = set() if area_metadata else set(actor_refs) & nodes
        if source_areas and not operative:
            actor_targets = {
                area_source_node(identity) if identity in dormant_areas else identity
                for identity in actor_targets
            }
        if area_metadata:
            operative = False
        uids = set(uid_refs) & owner_uids
        uid_targets = {uid_node(uid) for uid in uids}
        if operative:
            actor_targets.update(owners[uid] for uid in uids if owners[uid] in nodes)
        # Runner actor aliases are only read if that runner can execute. Store
        # these dependencies on its full manager node, not its source-only UID.
        if type(owner) is tuple and owner[0] == "effect":
            if not proof:
                edges[("operative", owner[1])].update(actor_targets)
            edges[owner].update(uid_targets)
        elif owner in edges:
            edges[owner].update(actor_targets | uid_targets)
        else:
            marked.update(actor_targets | uid_targets)

    def walk(value, owner, key=None, *, proof=False, conservative=False):
        if type(value) is int:
            link(
                owner,
                () if proof else (value,),
                (value,) if key in _UID_FIELDS or conservative else (),
                operative=(
                    conservative
                    or key in ("effect_uid", "native_running_uid", "native_delayed_uid")
                ),
                proof=proof,
                source_areas=key == "area_uid",
            )
        elif type(value) in (str, bool, float, type(None)):
            if type(value) is str and key == "native_context_hex":
                try:
                    fields = _fields(bytes.fromhex(value)) if value else {}
                    if set(fields) - {1, 2, 4, 5, 6, 7, 8, 9} or any(
                        w != 0 for w, _ in fields.values()
                    ):
                        raise ValueError("Unknown execution context")
                except (ValueError, TypeError):
                    uncertain(owner, "execution_context")
        elif type(value) in (list, tuple):
            for item in value:
                walk(item, owner, key, proof=proof, conservative=conservative)
        elif type(value) is dict:
            if key == "child_effect_uids":
                # Qs stores recipient hints -> already-created runner UIDs.
                # The actor remains for hints; only extant runners can execute
                # removal callbacks. Removed historical UIDs are not new roots.
                for recipient, children in value.items():
                    if type(children) not in (list, tuple) or any(
                        type(uid) is not int for uid in children
                    ):
                        uncertain(owner, "area_child_registry")
                        return
                    link(
                        owner,
                        (),
                        (uid for uid in children if uid in records),
                        operative=True,
                        proof=proof,
                    )
                return
            for field, item in value.items():
                if type(field) not in (int, str):
                    uncertain(owner, "opaque_key")
                    return
                if key not in _SCALAR_KEY_MAPS:
                    try:
                        numeric_key = int(field)
                    except (ValueError, TypeError):
                        pass
                    else:
                        link(
                            owner,
                            () if proof else (numeric_key,),
                            (numeric_key,),
                            operative=not proof,
                            proof=proof,
                        )
                if (
                    field == "container_id"
                    and type(item) is int
                    and value.get("container_present") is True
                    and type(value.get("container_type")) is int
                    and value["container_type"] == 3
                    and value.get("container_kind") == "effect_area"
                ):
                    # Same admitted PL3 identity as outer wire fields 9/10.
                    # It is not the invocation's recipient or a callback root.
                    link(
                        owner,
                        () if proof else (item,),
                        proof=proof,
                        operative=conservative,
                        source_areas=True,
                    )
                else:
                    walk(item, owner, field, proof=proof, conservative=conservative)
        else:
            uncertain(owner, "opaque_value")

    def queue_walk(value, owner, *, proof=False, actor=False):
        if deferred is not None and owner in edges:
            deferred.setdefault(owner, []).append((value, proof, actor))
        else:
            walk(_actor_reference_fields(value) if actor else value, owner, proof=proof)

    def materialize(identity):
        if deferred is None:
            return
        owner = (
            uid_node(identity[1])
            if type(identity) is tuple and identity[0] == "operative"
            else identity
        )
        for value, proof, actor in deferred.pop(owner, ()):
            walk(_actor_reference_fields(value) if actor else value, owner, proof=proof)
        if type(owner) is tuple and owner[0] == "effect":
            references = wire_by_uid.pop(owner[1], None)
            if references is not None:
                actor_refs, uid_refs, area_refs = references
                link(owner, actor_refs, uid_refs)
                link(owner, area_refs, source_areas=True)

    def uncertain(owner, reason):
        # An opaque component can contain a reference to any manager. Keeping
        # only its own manager would leave its unknown outbound edges dangling.
        marked.update(candidates)
        opaque.append((owner, reason))

    try:
        for identity, row in actors.items():
            queue_walk(row, identity, actor=True)
            for entry in (row.get("state_ledger") or {}).get("entries", ()):
                if (
                    entry.get("timer") is not None
                    or entry.get("realtime_deadline_ms") is not None
                    or entry.get("realtime_duration", 0) > 0
                ):
                    marked.add(identity)
        for identity, row in {**retired_areas, **active_areas}.items():
            queue_walk(row, identity)
            if identity in dormant_areas:
                # Preserve the source's exact parent/PL dependencies, but its old
                # recipient hints are not a new spatial/removal event. A pending
                # invocation roots the full node above instead.
                queue_walk(
                    {
                        key: value
                        for key, value in row.items()
                        if key != "child_effect_uids"
                    },
                    area_source_node(identity),
                    proof=True,
                )
        for key, row in provenance.items():
            # Historical lineage is a UID graph. Only nodes reached from current
            # carriers/children participate; an old row is never a root merely
            # because its target is a live player.
            queue_walk(row, uid_node(int(key)), proof=True)
        for uid, record in records.items():
            queue_walk(record, uid_node(uid))
        for name in _EFFECT_MAPS:
            for key, row in snapshot.get(name, {}).items():
                uid = int(key)
                owner = owners.get(uid, row.get("target_id"))
                references = (
                    _group_listener_reference_fields(row, records.get(uid))
                    if _native_group_trigger_history is True
                    and name == "native_owned_group_effects"
                    else row
                )
                queue_walk(references, uid_node(uid) if uid in owners else owner)
                if (
                    row.get("timer") is not None
                    or row.get("realtime_deadline_ms") is not None
                ):
                    marked.update((owner,) if owner in actors else candidates)
        for uid, record in records.items():
            payload = snapshot.get("state_wire_payloads", {}).get(str(uid))
            if payload is None:
                for name in _EFFECT_MAPS:
                    payload = snapshot.get(name, {}).get(str(uid), {}).get("payload")
                    if payload is not None:
                        break
            try:
                actor_refs, uid_refs, area_refs = _planner_wire_references(
                    payload, record["effect_class"]
                )
                if deferred is None:
                    link(uid_node(uid), actor_refs, uid_refs)
                    link(uid_node(uid), area_refs, source_areas=True)
                else:
                    wire_by_uid[uid] = (actor_refs, uid_refs, area_refs)
            except (ValueError, TypeError, KeyError):
                uncertain(owners[uid], "wire_schema")
        handled = (
            _HISTORY
            | set(_EFFECT_MAPS)
            | {
                "actors",
                "native_retained_records",
                "state_wire_payloads",
                "native_effect_areas",
                "native_retired_area_managers",
            }
        )
        for name, value in snapshot.items():
            if name in handled:
                continue
            if name == "native_delay_queue":
                try:
                    entries = _delay_queue_entries(value)
                except (ValueError, TypeError, KeyError):
                    uncertain(None, "delay_queue_schema")
                else:
                    # Pending registrations retain their previous conservative walk.
                    walk(entries, None, conservative=True)
            elif name in _ACTOR_KEYED_ROOTS:
                if type(value) is not dict:
                    uncertain(None, "actor_keyed_root_schema")
                    continue
                for key, row in value.items():
                    if type(key) not in (int, str):
                        uncertain(None, "actor_keyed_root_identity")
                        continue
                    try:
                        identity = int(key)
                    except ValueError:
                        uncertain(None, "actor_keyed_root_identity")
                        continue
                    if (
                        identity not in actors
                        or type(key) is str
                        and str(identity) != key
                    ):
                        uncertain(None, "actor_keyed_root_identity")
                        continue
                    link(None, (identity,))
                    # Keep all existing nested actor/UID edges; only the outer key
                    # has a producer-proven fighter domain.
                    walk(row, None)
            elif name in ("native_summon_registrations", "native_controller_registry"):
                # Registry rows belong to their actor; a live controller/master
                # edge protects the terminal source even when caster != controller.
                rows = (
                    value.get("fighters", {})
                    if name == "native_controller_registry"
                    else value
                )
                for key, row in rows.items():
                    try:
                        owner = int(key)
                    except (ValueError, TypeError):
                        owner = None
                    queue_walk(row, owner)
            else:
                walk(value, None, conservative=name == "native_delay_queue")
        # OUT fighters can still be explicit fbX/Qs members; status alone does
        # not exclude these alternate native global iterator memberships.
        pv = snapshot.get("native_global_pv_collections", {})
        for name in ("extras", "areas"):
            walk(pv.get(name, {}).get("keys", ()), None)
        # Rift accounting is retained, but its remaining faM identities are
        # explicitly future roots, not historical assignment snapshots.
        for group in (
            snapshot.get("rift_wave_state", {})
            .get("native_artifact_groups", {})
            .values()
        ):
            for identity in group.get("remaining", ()):
                if identity not in active_areas:
                    uncertain(None, "unresolved_future_area")
                else:
                    marked.add(identity)
        walk(pending_roots, None, conservative=True)
        # Immutable operation-local graph: visit every reachable node/edge once.
        # Set order is immaterial; the result is a reachability set, not dispatch.
        pending = deque(marked)
        while pending:
            identity = pending.popleft()
            materialize(identity)
            for target in edges.get(identity, ()):
                if target not in marked:
                    marked.add(target)
                    pending.append(target)
        if opaque:
            return RetainedGCPlan(
                frozenset(),
                frozenset(),
                frozenset(identity for identity in marked if type(identity) is int),
                tuple(opaque),
            )
        swept_uids = {
            uid
            for uid in storage_uids
            if owners[uid] in candidates and uid_node(uid) not in marked
        }
        swept_managers = {owners[uid] for uid in swept_uids}
        orphan_containers = _orphaned_containers(
            (snapshot.get(name, {}) for name in _CHILD_MAPS),
            snapshot.get("native_owned_state_containers", {}),
            swept_uids,
        )
        # Provenance-only leaves have neither a current carrier nor a child
        # whose later source classification can consult them. The same pending,
        # wire and active-source graph above must also prove them unreachable.
        ledger_uids = {
            entry["uid"]
            for row in (
                *actors.values(),
                *active_areas.values(),
                *retired_areas.values(),
            )
            for entry in (row.get("state_ledger") or {}).get("entries", ())
        }
        present_uids = (
            storage_uids
            | ledger_uids
            | {int(key) for key in snapshot.get("state_wire_payloads", {})}
        )
        for name in _EFFECT_MAPS:
            present_uids.update(int(key) for key in snapshot.get(name, {}))
        parent_uids = {row.get("parent_state_uid") for row in provenance.values()}
        validated_provenance = {}
        orphan_provenance = {
            int(key)
            for key, row in provenance.items()
            if row.get("target_id") in candidates
            and int(key) not in present_uids
            and int(key) not in parent_uids
            and uid_node(int(key)) not in marked
            and _valid_provenance_chain(provenance, int(key), validated_provenance)
        }
        return RetainedGCPlan(
            frozenset(swept_managers),
            frozenset(swept_uids),
            frozenset(identity for identity in marked if type(identity) is int),
            tuple(opaque),
            orphan_containers,
            frozenset(orphan_provenance),
        )
    finally:
        # Release the operation-local recursive walker and captured graph.
        walk = None


def _valid_provenance_chain(entries, uid, validated):
    """Validate each ancestor once per phase, never cache mutable authority."""
    from .combat_retained_source_provenance import _validate_record
    from .combat_state_parameters import pack_state_identity

    visited, path, valid = set(), [], True
    try:
        while uid is not None:
            if uid in validated:
                valid = validated[uid]
                break
            if uid in visited:
                valid = False
                break
            visited.add(uid)
            path.append(uid)
            row = entries.get(str(uid))
            _validate_record(row)
            if row["uid"] != uid:
                valid = False
                break
            parent_uid = row["parent_state_uid"]
            if parent_uid is not None:
                parent = entries.get(str(parent_uid))
                if (
                    not row["container_known"]
                    or row["container_present"] is not True
                    or row["container_type"] != 1
                    or parent is None
                    or row["container_id"]
                    != pack_state_identity(
                        parent["state_reference"], parent["state_level"]
                    )
                ):
                    valid = False
                    break
            uid = parent_uid
    except (ValueError, TypeError, KeyError):
        valid = False
    for identity in path:
        validated[identity] = valid
    return valid


def sweep_retired_effects(fight, plan):
    """Apply a freshly prepared plan on the SAME unpublished private preview.

    This deliberately does not execute unapplication: a proven unreachable
    graph has no gameplay recipient. Keep its actor scalar snapshot, accounting
    sources and immutable receipts. Caller validates the complete view before
    planning and after this atomic sweep, and rolls back on any failure.
    """
    uids = plan.effect_uids
    provenance = getattr(fight, "native_state_source_provenance", {}).get("entries", {})
    if plan.orphan_provenance_uids:
        parents = {row.get("parent_state_uid") for row in provenance.values()}
        ledger_uids = {
            entry.uid
            for actor in fight.actors.values()
            for ledger in (getattr(actor, "state_ledger", None),)
            if ledger is not None
            for entry in ledger.entries
        }
        for name in ("native_effect_areas", "native_retired_area_managers"):
            for row in getattr(fight, name, {}).values():
                ledger = row.get("state_ledger")
                if ledger is not None:
                    ledger_uids.update(entry.uid for entry in ledger.entries)
        validated_provenance = {}
        for uid in plan.orphan_provenance_uids:
            if (
                str(uid) not in provenance
                or uid in parents
                or uid in ledger_uids
                or any(
                    uid in getattr(fight, name, {})
                    for name in (
                        *_EFFECT_MAPS,
                        "state_wire_payloads",
                        "native_retained_records",
                    )
                )
                or not _valid_provenance_chain(provenance, uid, validated_provenance)
            ):
                raise ValueError("State source provenance changed after GC planning")
    facts = getattr(fight, "native_owned_state_containers", {})
    expected_orphans = _orphaned_containers(
        (getattr(fight, name, {}) for name in _CHILD_MAPS), facts, uids
    )
    if expected_orphans != plan.orphan_container_uids:
        raise ValueError("Retained container users changed after GC planning")
    for identity in plan.actor_ids:
        ledger = fight.actors[identity].state_ledger
        ledger._entries = tuple(
            entry for entry in ledger.entries if entry.uid not in uids
        )
    for name in (*_EFFECT_MAPS, "state_wire_payloads", "native_retained_records"):
        values = getattr(fight, name, None)
        if values is not None:
            for uid in uids:
                values.pop(uid, None)
    fight.native_retained_order[:] = [
        uid for uid in fight.native_retained_order if uid not in uids
    ]
    for uid in plan.orphan_container_uids:
        facts.pop(uid)

    for uid in plan.orphan_provenance_uids:
        del provenance[str(uid)]
