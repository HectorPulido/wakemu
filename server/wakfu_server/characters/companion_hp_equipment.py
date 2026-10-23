"""Owned sidekick HP equipment replay, sharing the native eWO PA interpreter."""
from wakfu_server.equipment_hp_lifecycle import NativeHPActor, OwnedEwoHPReplay


def project(record, baseline, operations, *, equip_rng=None):
    """Reconcile a read-only projection; callers persist only in owner transactions."""
    checkpoint = record.get("equipment_hp_projection") if record else None
    if not operations and not checkpoint:
        return None
    operations = OwnedEwoHPReplay.resolved_operations(
        operations, checkpoint.get("receipts", ()) if checkpoint else (), rng=equip_rng
    )
    replay = OwnedEwoHPReplay.restore(checkpoint) if checkpoint else None
    if replay is not None:
        # Combat recovery owns durable visible HP. Preserve the hidden raw
        # current when it still agrees; otherwise reflect that explicit change.
        if replay.actor.max_hp == record["max_hp"] and replay.actor.hp != record["hp"]:
            raw = replay.actor.plain()
            raw["raw_current"] = (
                raw["raw_maximum"] if record["hp"] == record["max_hp"] else record["hp"]
            )
            replay = OwnedEwoHPReplay(NativeHPActor(**raw), replay.plain_receipts())
        stripped = OwnedEwoHPReplay.restore(replay.checkpoint())
        for key in sorted(
            tuple(stripped.receipts),
            key=lambda value: (stripped._order(stripped.receipts[value]), value),
            reverse=True,
        ):
            stripped.remove(key)
        if any(
            stripped.actor.plain()[key] != baseline[key]
            for key in ("raw_maximum", "raw_minimum", "percentage", "frozen")
        ):
            replay = None
    if replay is None:
        raw = dict(baseline)
        if record:
            missing = record["max_hp"] - record["hp"]
            raw["raw_current"] = max(raw["raw_minimum"], raw["raw_maximum"] - missing)
        replay = OwnedEwoHPReplay(NativeHPActor(**raw))
    replay.reconcile(operations)
    return replay
