"""Refresh owned guild modifiers at exploration boundaries, preserving wounds."""


def synchronize(store, account_id, generation, character, *, in_combat):
    if type(in_combat) is not bool:
        raise ValueError("Invalid guild modifier combat boundary")
    if in_combat:
        return character, False
    from wakfu_server.guild_member_effects import load_from_records

    records = character.get("guild_member_bonus_records", {})
    if not isinstance(records, dict) or any(
        not isinstance(row, dict) for row in records.values()
    ):
        raise ValueError("Invalid owned guild member bonus records")
    model = character.get("guild_native")
    signature = (
        None if model is None else model["guildId"],
        tuple(
            (key, row.get("active"), row.get("activated_at_ms"))
            for key, row in sorted(records.items())
        ),
    )
    now_ms = int(store.now().timestamp() * 1000)
    previous = character.get("guild_member_effects", ())
    expired = any(
        source.get("expires_at_ms") is not None and source["expires_at_ms"] <= now_ms
        for source in previous
    )
    if character.get("_guild_member_refresh_signature") == signature and not expired:
        return character, False
    candidate = dict(character)
    load_from_records(candidate, records, now_ms)
    candidate["_guild_member_refresh_signature"] = signature
    if candidate["guild_member_effects"] == previous:
        return candidate, False
    from wakfu_server.health_store import initialize

    # The database reload rechecks membership and active bonuses. Native HP
    # reconciliation retains canonical wounds, death and equipment receipts.
    updated = initialize(
        store, account_id, generation, character["id"], exploration=True
    )
    updated["_guild_member_refresh_signature"] = signature
    return updated, True
