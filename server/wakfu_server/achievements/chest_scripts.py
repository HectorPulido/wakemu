"""Original GenericActivable PLAY_SCRIPT publication after a committed action.

The normalized programs are bound to the original type7 leaf and action. They
carry original criteria and archive provenance; scripts never grant progress.
"""
import struct


def programs(db, rule):
    if rule["emote_id"] is None:
        return []
    rows = db.execute(
        "SELECT * FROM native_generic_chest_script_sources WHERE descriptor_id=%s "
        "AND wire_action=%s AND emote_effect_reference=%s ORDER BY effect_order",
        (rule["native_definition"], rule["native_action"], rule["effect_reference"]),
    ).fetchall()
    if not rows:
        raise ValueError("Native emote chest lacks its original visual program")
    for row in rows:
        if (
            row["catalog_revision"] != rule["catalog_revision"]
            or row["source_sha256"] != rule["source_sha256"]
            or row["effect_type"] != 1
            or row["group_clx"] == 0
        ):
            raise ValueError("Native chest visual program source changed")
    return [dict(row) for row in rows]


def packets(rule, actor_id, *, evaluate):
    result = []
    for program in rule.get("scripts", ()):
        if evaluate(program["effect_criterion"]):
            # cwh13270 / ffK.GENERIC_IE. bBH supplies only elementId, the
            # actual interactive-element UID; no synthetic user/cell fields.
            name = b"elementId"
            payload = struct.pack(">qiBi", actor_id, program["effect_reference"], 1, 1)
            payload += (
                struct.pack(">i", len(name))
                + name
                + struct.pack(">q", rule["object_id"])
            )
            result.append((13270, payload))
    return result
