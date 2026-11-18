"""Reviewed owned-scene interpretation of zero-range global abilities.

The installed client still sends its real SELF cell in cpm. A declared scene
may interpret that input through fcj's existing null-aBn validation branch.
This is an explicit server reconstruction, not a claimed nullable wire format.
Effect execution retains the actual input anchor and original selectors.
"""

from hashlib import sha256
import json


def source_record(reference, level, *, zero_casting=None):
    from .combat_native_spell_casting import native_casting_table
    from .combat_casting_context import casting_root_catalog

    table, index = native_casting_table(reference, level, zero_casting=zero_casting)
    roots = list(table["levels"][index][2])
    record = {k: v for k, v in table.items() if k not in ("levels", "costs")}
    record.update(level=list(table["levels"][index]), costs=list(table["costs"][index]))
    root_catalog = casting_root_catalog()["roots"]
    return dict(
        reference=reference,
        level=level,
        table=record,
        roots={str(r): root_catalog[str(r)] for r in roots},
    )


def source_digest(reference, level, *, zero_casting=None):
    return sha256(
        json.dumps(
            source_record(reference, level, zero_casting=zero_casting),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def declarations(descriptor):
    rows = descriptor.get("reviewed_cellless_casts", ())
    if type(rows) not in (list, tuple):
        raise ValueError("Invalid reviewed cell-less casting declaration")
    seen = set()
    for row in rows:
        if (
            type(row) is not dict
            or set(row)
            != {
                "spell_id",
                "level",
                "state_id",
                "form_reference",
                "source_sha256",
                "evidence",
            }
            or any(
                type(row.get(k)) is not int or row[k] <= 0
                for k in ("spell_id", "state_id", "form_reference")
            )
            or type(row.get("level")) is not int
            or row["level"] < 0
            or row["spell_id"] in seen
            or type(row.get("source_sha256")) is not str
            or len(row["source_sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in row["source_sha256"])
            or type(row.get("evidence")) is not str
            or not row["evidence"].strip()
            or descriptor.get("full_room_scope") is not True
        ):
            raise ValueError("Cell-less casting lacks its exact reviewed native source")
        seen.add(row["spell_id"])
    return rows


def authorized(context):
    fight, actor = context.fight, context.source
    record = getattr(fight, "native_encounter_scene", None)
    if (
        record is None
        or record.get("descriptor", {}).get("reviewed_cellless_casts") is None
    ):
        return False
    if not context.normal_mode:
        return False
    from .combat_encounter_scene_policy import frozen_scene
    from .combat_morph_spellbook import morph_record

    rows = [
        r
        for r in declarations(frozen_scene(fight))
        if r["spell_id"] == context.plan.get("spell_id")
    ]
    if not rows:
        return False
    row = rows[0]
    if tuple(context.cell) != tuple(actor.position):
        return False
    receipt = getattr(fight, "native_controlled_scene_state_receipt", None)
    morph = morph_record(fight, actor.id)
    if (
        actor.controlled is not True
        or actor.owner_id is None
        or getattr(actor, "native_summon_source", None) is not None
        or type(receipt) is not dict
        or receipt.get("actor_id") != actor.id
        or receipt.get("scene_sha256") != record["sha256"]
        or not any(
            p["state_id"] == row["state_id"] for p in receipt.get("programs", ())
        )
        or not any(
            e.reference == row["state_id"] and e.uid in receipt.get("state_uids", ())
            for e in actor.state_ledger.entries
        )
        or morph is None
        or morph.get("profile_id") != row["form_reference"]
        or context.plan.get("evaluation_level") != row["level"]
        or context.rule["minimum"] != 0
        or context.rule["maximum"] != 0
        or source_digest(row["spell_id"], row["level"]) != row["source_sha256"]
    ):
        raise ValueError("Reviewed cell-less cast lost its original player/form/source")
    source = source_record(row["spell_id"], row["level"])
    if source["table"]["level"][:2] != [0, 0] or not source["roots"]:
        raise ValueError("Cell-less reconstruction requires native zero-range roots")
    for root in source["roots"].values():
        selector = root.get("native_target_selector")
        if (
            root.get("native_casting_collision_area") is not None
            or root.get("native_selector_present") is not True
            or type(selector) is not dict
            or selector.get("class") != "fcE"
            or type(selector.get("mask")) is not int
            or selector["mask"] & 2
            or not selector["mask"] & (64 | 8 | 128 | 256)
        ):
            raise ValueError(
                "Cell-less reconstruction cannot bypass a native SELF actor root"
            )
    return True
