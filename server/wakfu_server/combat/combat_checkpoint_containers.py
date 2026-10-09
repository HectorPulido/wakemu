"""Recover legacy PL namespaces only from checkpointed owned fyW objects."""
from copy import deepcopy
from .combat_effects import _integer
from .combat_effect_removal import _identity_fields, _proto_replace
from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS


def reconstruct_state_containers(saved):
    result = deepcopy(saved)
    actors = result.get("actors", {})
    states = {}
    areas = dict(
        result.get("native_effect_areas", {}),
        **result.get("native_retired_area_managers", {}),
    )
    managers = list(actors.values()) + list(areas.values())
    manager_ids = {int(key) for key in actors}
    manager_ids.update(
        int(key)
        for key, row in areas.items()
        if row.get("native_area_contract") in SUPPORTED_AREA_CONTRACTS
        and row.get("state_ledger", {}).get("actor_id") == int(key)
    )
    for manager in managers:
        for state in manager.get("state_ledger", {}).get("entries", ()):
            uid = state.get("uid")
            if uid in states:
                raise ValueError("Checkpoint has duplicate native state UID")
            states[uid] = state
    owned = result.get("native_owned_state_containers", {})
    records = result.get("native_retained_records", {})
    for uid, record in records.items():
        owner = record.get("owner_uid")
        if owner is None or record.get("container_type") != 3:
            continue
        children = [
            collection[uid]
            for name in (
                "owned_stat_effects",
                "native_owned_group_effects",
                "native_owned_area_effects",
            )
            if uid in (collection := result.get(name, {}))
        ]
        if len(children) != 1 or children[0].get("state_uid") != owner:
            raise ValueError("Checkpoint lacks owned child state authority")
        state = owned.get(str(owner), states.get(owner))
        if not isinstance(state, dict) or state.get("uid") != owner:
            raise ValueError("Checkpoint lacks actual fyW container")
        reference, level = state.get("reference"), state.get("level")
        if (
            type(reference) is not int
            or not 0 < reference <= 32767
            or type(level) is not int
            or not 0 <= level <= 32767
            or str(state.get("caster_id")) not in actors
            or state.get("target_id") not in manager_ids
        ):
            raise ValueError("Checkpoint has invalid fyW identity")
        identity = (reference << 16) | level
        if record.get("container_id") not in (None, identity):
            raise ValueError("Checkpoint fyW identity disagrees with ownership")
        child = children[0]
        if child.get("payload") is not None:
            payload = bytes.fromhex(child["payload"])
            fields = _identity_fields(payload, integer_fields=(1, 9, 10))
            if (
                fields.get(1) != int(uid)
                or fields.get(10) not in (None, identity)
                or fields.get(9) not in (None, 3)
            ):
                raise ValueError("Checkpoint child payload disagrees with fyW")
            payload = _proto_replace(payload, 9, 0, _integer(9, 1))
            payload = _proto_replace(payload, 10, 0, _integer(10, identity))
            child["payload"] = payload.hex()
        record.update(container_type=1, container_id=identity, container_kind="state")
    return result
