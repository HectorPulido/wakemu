"""Typed native eYa ownership over an actual canonical QI retained runner.

The public mapping is serializable. A JSON copy cannot restore the live runner
or its exact retained target/context, just like the canonical QI checkpoint.
"""
from copy import deepcopy
from .combat_pointer_qi_lifecycle import NativeRunner937
from .combat_effect_removal import _identity_fields


class NativeSpatialRecord(dict):
    def __init__(self, runner, *, caster_id, state_uid, payload):
        if not isinstance(runner, NativeRunner937):
            raise ValueError("Actual native eYa runner required")
        runner.pk.validate()
        target = runner.spatial.target
        if target is None or runner.spatial.context is None or runner.disposed:
            raise ValueError("Missing retained eYa target/context")
        self._runner = runner
        dict.__init__(
            self,
            uid=runner.spatial.uid,
            effect_class=937,
            target_id=target.identity,
            caster_id=caster_id,
            state_uid=state_uid,
            generic_effect=runner.pk.reference,
            payload=payload.hex(),
        )
        self._identity = dict(self)

    def validate(self, fight):
        if dict(self) != self._identity:
            raise ValueError("Native spatial ownership mapping was modified")
        runner = self._runner
        runner.pk.validate()
        target = runner.spatial.target
        qi = runner.spatial.context.qi if runner.spatial.context is not None else None
        if runner.disposed or qi is None or qi.fight is not fight or target is None:
            raise ValueError("Missing actual retained native spatial context")
        canonical = qi.objects if target.kind == "actor" else qi.area_objects
        if canonical.get(target.identity) is not target:
            raise ValueError("Retained spatial target is not the actual canonical QK")
        fields = _identity_fields(bytes.fromhex(self["payload"]))
        expected = dict(
            uid=runner.spatial.uid,
            effect_class=937,
            target_id=target.identity,
            generic_effect=runner.pk.reference,
        )
        if (
            any(self.get(key) != value for key, value in expected.items())
            or fields.get(1) != self["uid"]
            or fields.get(3) != runner.pk.reference
            or fields.get(7) != (target.identity & ((1 << 64) - 1))
            or fields.get(6) != (self["caster_id"] & ((1 << 64) - 1))
        ):
            raise ValueError("Retained eYa wire ownership differs from actual runner")
        return runner

    def __deepcopy__(self, memo):
        clone = type(self).__new__(type(self))
        memo[id(self)] = clone
        dict.__init__(clone, deepcopy(dict(self), memo))
        clone._identity = deepcopy(self._identity, memo)
        clone._runner = deepcopy(self._runner, memo)
        return clone


def validate_spatial_record(fight, row, entry=None):
    if not isinstance(row, NativeSpatialRecord):
        raise ValueError("Missing typed actual eYa ownership")
    runner = row.validate(fight)
    if entry is not None and (
        entry.uid,
        entry.effect_class,
        entry.target_id,
        entry.generic_effect,
        entry.owner_uid,
        entry.manager_id,
    ) != (
        row["uid"],
        937,
        row["target_id"],
        row["generic_effect"],
        row["state_uid"],
        row["target_id"],
    ):
        raise ValueError("Spatial Qf ownership differs from the actual target manager")
    return runner


def register_spatial_removals(removal, *, packets, action_id):
    """Use the actual central complete Qf view's removal order, never a subset."""
    from .combat_effect_removal import running_effect_removal

    fight = removal.fight
    rows = getattr(fight, "native_owned_spatial_effects", {})
    if not rows:
        return

    def validate(entry):
        row = rows[entry.uid]
        validate_spatial_record(fight, row, entry)
        return running_effect_removal(
            fight.id,
            action_id,
            effect_class=937,
            target_id=row["target_id"],
            uid=entry.uid,
            running_effect_payload=bytes.fromhex(row["payload"]),
        )

    def remove(uid):
        row = rows[uid]
        payload = validate(removal.view.by_uid[uid])
        runner = row.validate(fight)
        runner.dispose()  # bbR restores the exact retained QK before release.
        if uid in rows:
            raise ValueError("Actual spatial runner release retained ownership")
        packets.append((13560, payload))

    removal.register(
        937, exists=lambda uid: uid in rows, remove=remove, validate=validate
    )
