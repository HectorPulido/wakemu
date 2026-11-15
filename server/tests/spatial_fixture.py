"""Test setup through the real native spatial transaction commands.

These helpers supply explicit persisted/lease facts. They do not validate,
advance, checkpoint, or mirror a second position state in Python.
"""

POSITION_KEYS = ("map_id", "instance_id", "x", "y", "z", "direction")


def seed_position(positions, key, current, *, persisted=None, mirror=False):
    """Install a clean baseline, then admit an explicitly supplied movement."""
    key = tuple(key)
    current = dict(current)
    current.setdefault("id", key[2])
    current.setdefault("account_id", key[0])
    baseline = {
        name: (current if persisted is None else persisted)[name]
        for name in POSITION_KEYS
    }
    positions.native.bind_character(key, current, domain="positions")
    positions.native.call(
        "positions.attach",
        key=list(key),
        current=baseline,
        persisted=baseline,
        selected_character_id=key[2],
        skip_stale_selection=False,
    )
    target = {name: current[name] for name in POSITION_KEYS}
    if target != baseline:
        plan = positions.native.call(
            "positions.prepare_move",
            key=list(key),
            start=baseline,
            end=target,
            lease_active=True,
        )
        try:
            encoded = (
                positions.journal.put(key, plan, expected=plan["expected"])
                if mirror
                else None
            )
        except BaseException:
            positions.native.call("positions.abort", token=plan["token"])
            raise
        positions.native.call(
            "positions.commit_move", token=plan["token"], encoded=encoded
        )
    elif mirror:
        # Returning to the same baseline creates a legitimate clean mirror.
        for end in (dict(target, x=target["x"] + 1), target):
            old = positions.entry_state(key)["current"]
            plan = positions.native.call(
                "positions.prepare_move",
                key=list(key),
                start=old,
                end=end,
                lease_active=True,
            )
            try:
                encoded = positions.journal.put(key, plan, expected=plan["expected"])
            except BaseException:
                positions.native.call("positions.abort", token=plan["token"])
                raise
            positions.native.call(
                "positions.commit_move", token=plan["token"], encoded=encoded
            )
    return key


def commit_checkpoint(positions, keys, *, selected=True):
    """Supply the successful SQL result for an explicitly selected fixture set."""
    keys = [tuple(key) for key in keys]
    if not keys:
        raise AssertionError("A checkpoint fixture requires at least one owner")
    accounts = {key[0] for key in keys}
    if len(accounts) != 1:
        raise AssertionError("Checkpoint fixtures commit one account at a time")
    plan = positions.native.call(
        "positions.prepare_checkpoint",
        account_id=keys[0][0],
        leases=[
            dict(
                key=list(key),
                selected_character_id=key[2] if selected else None,
                lease_active=True,
            )
            for key in keys
        ],
    )
    return positions.native.call("positions.commit_checkpoint", token=plan["token"])
