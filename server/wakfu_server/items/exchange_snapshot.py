"""Publish native quantity deltas from immutable SQL offer snapshots.

cuJ/cuK add/remove quantities rather than replacing them. The caller keeps
the previous snapshot only after the complete publication succeeds on its
captured connection; a failed write requires disconnect and bootstrap.
"""
from . import exchange_wire


def packets(exchange_id, revision, current, previous=None):
    if type(revision) is not int or not 0 < revision < 2**63:
        raise ValueError("Invalid exchange offer revision")
    if current.get("state") != "active":
        raise ValueError("Exchange offer snapshot is not active")
    participants = {current["inviter_id"], current["invitee_id"]}
    if len(participants) != 2:
        raise ValueError("Invalid exchange snapshot participants")
    if previous is not None and (
        previous.get("state") != "active"
        or {previous["inviter_id"], previous["invitee_id"]} != participants
    ):
        raise ValueError("Exchange snapshot participants changed")

    def offers(snapshot):
        result = {}
        for row in snapshot.get("items", []):
            uid, actor, quantity = row["uid"], row["character_id"], row["quantity"]
            unit = row.get("unit")
            if isinstance(unit, dict):
                from .inventory_shards import item_from_json

                unit = item_from_json(unit)
            if (
                uid in result
                or actor not in participants
                or type(quantity) is not int
                or not 1 <= quantity <= 32767
                or not isinstance(unit, dict)
                or unit.get("uid") != uid
                or unit.get("character_id") != actor
                or unit.get("quantity") != quantity
            ):
                raise ValueError("Invalid hydrated exchange offer")
            result[uid] = dict(row, unit=unit)
        return result

    before, after = offers(previous or {}), offers(current)
    output = []
    for uid in sorted(before.keys() | after.keys()):
        old, new = before.get(uid), after.get(uid)
        if old and new:
            # An offer cannot transfer ownership/reference between revisions.
            if (
                old["character_id"] != new["character_id"]
                or old["unit"]["reference"] != new["unit"]["reference"]
            ):
                raise ValueError("Exchange offer identity changed")
            old_metadata = {k: v for k, v in old["unit"].items() if k != "quantity"}
            new_metadata = {k: v for k, v in new["unit"].items() if k != "quantity"}
            if old_metadata != new_metadata:
                # Remove old representation before publishing updated metadata.
                output.append(
                    exchange_wire.item(
                        exchange_id,
                        old["character_id"],
                        old["unit"],
                        old["quantity"],
                        removed=True,
                    )
                )
                output.append(
                    exchange_wire.item(
                        exchange_id, new["character_id"], new["unit"], new["quantity"]
                    )
                )
                continue
        difference = (new["quantity"] if new else 0) - (old["quantity"] if old else 0)
        if difference:
            row = new if difference > 0 else old
            output.append(
                exchange_wire.item(
                    exchange_id,
                    row["character_id"],
                    row["unit"],
                    abs(difference),
                    removed=difference < 0,
                )
            )
    members = current.get("members", [])
    if len(members) != 2 or {row["character_id"] for row in members} != participants:
        raise ValueError("Invalid exchange snapshot membership")
    prior_members = {
        row["character_id"]: row for row in (previous or {}).get("members", [])
    }
    for member in sorted(members, key=lambda row: row["character_id"]):
        actor = member["character_id"]
        old = prior_members.get(actor)
        if old is None or old["offered_kamas"] != member["offered_kamas"]:
            output.append(
                exchange_wire.cash(exchange_id, actor, member["offered_kamas"])
            )
    for member in sorted(members, key=lambda row: row["character_id"]):
        actor = member["character_id"]
        # Item/cash mutations reset readiness on the native client; always send
        # both authoritative flags after ALL content, including unchanged flags.
        output.append(
            exchange_wire.ready(
                exchange_id, actor, member["confirmed_revision"] == revision
            )
        )
    return output
