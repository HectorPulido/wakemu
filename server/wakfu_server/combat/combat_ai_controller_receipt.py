"""Read-only forecast authority from an actual published eWD207 controller book."""


def controller_forecast_receipt(fight, actor):
    from .combat_controller_registry import _row, SOURCE

    book = getattr(fight, "native_controller_action_books", {}).get(actor.id)
    if book is None:
        return affiliation_forecast_receipt(fight, actor)
    if isinstance(book, dict) and not {
        "effect_reference",
        "caster_id",
        "applied_team",
    } <= set(book):
        return None  # Historical books provide no new team-transition authority.
    row = _row(fight, actor.id)
    if (
        not isinstance(book, dict)
        or book.get("producer") != "eWD207.eZd.fQM.actual"
        or type(book.get("running_uid")) is not int
        or not 0 < book["running_uid"] < 1 << 63
        or type(book.get("effect_reference")) is not int
        or book["effect_reference"] <= 0
        or book.get("controller_id") != row["current_controller"]
        or book.get("applied_team") != row["current_team"]
        or type(book.get("caster_id")) is not int
        or book["caster_id"] not in fight.actors
        or row["current_controller"] not in fight.actors
    ):
        raise ValueError("Missing actual eWD207 forecast controller authority")
    return dict(
        source=SOURCE,
        producer=book["producer"],
        effect_class=207,
        effect_reference=book["effect_reference"],
        running_uid=book["running_uid"],
        target_id=actor.id,
        caster_id=book["caster_id"],
        controller_id=row["current_controller"],
        current_team=row["current_team"],
        original_team=row["original_team"],
        original_controller=row["original_controller"],
    )


def affiliation_forecast_receipt(fight, actor):
    """An actual retained eYV1030 PA owns the signed team mutation and payload."""
    from .combat_controller_registry import _row, SOURCE
    from .combat_affiliation_effect import signed_affiliation
    from .combat_effect_removal import _identity_fields

    candidates = [
        row
        for row in getattr(fight, "owned_stat_effects", {}).values()
        if row.get("family") == "eYV"
        and row.get("effect_class") == 1030
        and row.get("target_id") == actor.id
    ]
    if not candidates:
        return None
    registry = _row(fight, actor.id)
    for row in reversed(candidates):
        if signed_affiliation(row["actual"]) != registry["current_team"]:
            continue
        uid = row.get("uid")
        fields = _identity_fields(bytes.fromhex(row["payload"]))
        if (
            type(uid) is not int
            or not 0 < uid < 1 << 63
            or fields.get(1) != uid
            or fields.get(6) != row["caster_id"] & ((1 << 64) - 1)
            or fields.get(7) != actor.id & ((1 << 64) - 1)
            or type(fields.get(3)) is not int
            or fields[3] <= 0
            or row["caster_id"] not in fight.actors
        ):
            raise ValueError("Missing actual eYV1030 forecast affiliation authority")
        return dict(
            source=SOURCE,
            producer="eYV1030.fdy.au.actual",
            effect_class=1030,
            effect_reference=fields[3],
            running_uid=uid,
            target_id=actor.id,
            caster_id=row["caster_id"],
            controller_id=registry["current_controller"],
            current_team=registry["current_team"],
            original_team=registry["original_team"],
            original_controller=registry["original_controller"],
        )
    return None
