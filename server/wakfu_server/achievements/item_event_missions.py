"""Reviewed mission starts attached to successful, server-owned item actions.

The binding is reconstructed from the item's text and matching mission; it is
not an original server script. Its caller owns the inventory transaction.
"""
from copy import deepcopy

from . import storage, wire
from .mission_progress import auto_track
from .service import _owner

# A reusable table of independently reviewed item-action facts. The tuple is
# (action class, action id, source reference, output reference).
BINDINGS = {
    ("bHS", 3614, 15985, 15986): {
        "definition_id": 1217,
        "revision": "3d1e48353eef085e9d2159340ea170ac51d6a878093e90f1214a60ab2eed4a06",
        "objective_ids": (2178,),
        "minimum_real_level": 105,
        "criterion": "GetRealLevel() >= 105",
        "source": "reconstructed_item_description_and_quest_text_v1",
    },
}


def activate_for_output(
    db,
    store,
    character,
    *,
    native_class,
    action_id,
    source_reference,
    output_reference,
    source_uid,
):
    """Start one mapped mission on a successful conversion, in its transaction."""
    binding = BINDINGS.get(
        (native_class, action_id, source_reference, output_reference)
    )
    if binding is None:
        return []
    _owner(db, character)
    identity = binding["definition_id"]
    native = db.execute(
        "SELECT data FROM native_quest_metadata_definitions "
        "WHERE definition_id=%s AND revision=%s",
        (identity, binding["revision"]),
    ).fetchone()
    if native is None:
        raise ValueError("Missing reconstructed item mission metadata")
    definition = native["data"]["native"]
    if (
        definition.get("native_class") != "aJM"
        or definition.get("d") != identity
        or definition.get("aqb") is not False
        or definition.get("cjI") != binding["criterion"]
        or {obj["d"] for obj in definition["cjJ"]} != set(binding["objective_ids"])
        or character["level"] < binding["minimum_real_level"]
    ):
        raise ValueError("Reconstructed item mission definition changed")
    before = storage.load_locked(db, character["id"])
    if identity in before["running"] or identity in before["completed"]:
        return []
    fact = {
        "kind": "reconstructed_item_action_mission_v1",
        "mission_id": identity,
        "action_id": action_id,
        "source_reference": source_reference,
        "source_uid": source_uid,
        "output_reference": output_reference,
        "reconstruction": binding["source"],
    }
    if not storage.record_event(
        db, character["id"], f"item-action-mission:{identity}", fact
    ):
        raise ValueError("Item mission receipt exists without progress")
    after = deepcopy(before)
    after["running"] = sorted(set(after["running"]) | {identity})
    auto_track(after, identity)
    storage.store(db, character["id"], after)
    return wire.changes(
        character["id"], before, after, [], [], int(store.now().timestamp() * 1000)
    )
