"""Native eWh1038 live PA links over explicitly owned characteristic snapshots."""
import copy
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_delivery
from .combat_effects import _integer, _varint
from .combat_effect_removal import running_effect_removal


def _int32(value):
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def link_contribution(source, percent=100, upper=0, lower=-(1 << 31)):
    if any(
        type(v) is not int or not -(1 << 31) <= v < (1 << 31)
        for v in (source, percent, upper, lower)
    ):
        raise ValueError("Missing signed native characteristic link parameters")
    product = _int32(source * percent)
    value = (abs(product) // 100) * (-1 if product < 0 else 1)
    if upper > 0:
        value = min(upper, value)
    if lower > -(1 << 31):
        value = max(lower, value)
    return value


class ObservableCharacteristicStats(dict):
    def __init__(self, values, fight, identity):
        dict.__init__(self, values)
        self._fight, self._identity = fight, identity

    def __deepcopy__(self, memo):
        clone = type(self).__new__(type(self))
        memo[id(self)] = clone
        dict.__init__(clone, copy.deepcopy(dict(self), memo))
        clone._identity = self._identity
        clone._fight = copy.deepcopy(self._fight, memo)
        return clone

    def __setitem__(self, stat, value):
        before = self.get(stat)
        dict.__setitem__(self, stat, value)
        if before != value:
            records = getattr(self._fight, "native_characteristic_links", {})
            for row in tuple(records.values()):
                if row["source_id"] == self._identity and row["source_stat"] == stat:
                    _refresh(self._fight, row)

    def update(self, *args, **kwargs):
        for stat, value in dict(*args, **kwargs).items():
            self[stat] = value


def bind_characteristic_stats(fight):
    records = getattr(fight, "native_characteristic_links", {})
    for identity, actor in fight.actors.items():
        stats = actor.effect_stats
        if not isinstance(stats, dict):
            raise ValueError(
                "Missing native PA characteristic snapshots for live links"
            )
        if isinstance(stats, ObservableCharacteristicStats):
            if stats._fight is not fight or stats._identity != identity:
                raise ValueError("Stale native PA listener snapshot binding")
        else:
            if any(
                identity in (row["source_id"], row["destination_id"])
                for row in records.values()
            ):
                raise ValueError(
                    "Live PA links require pre-mutation restored listener registration"
                )
            actor.effect_stats = ObservableCharacteristicStats(stats, fight, identity)


def characteristic_adoption_bindings(candidate):
    """Validate live PA listeners before publishing a candidate into a Fight."""
    records = getattr(candidate, "native_characteristic_links", {})
    bindings = []
    for identity, actor in candidate.actors.items():
        stats = getattr(actor, "effect_stats", None)
        if isinstance(stats, ObservableCharacteristicStats):
            if stats._fight is not candidate or stats._identity != identity:
                raise ValueError("Stale native PA listener snapshot binding")
            bindings.append(stats)
        elif any(
            identity in (row["source_id"], row["destination_id"])
            for row in records.values()
        ):
            raise ValueError("Missing native PA listener at publication boundary")
    return tuple(bindings)


def _characteristic(fight, identity, stat):
    if stat in (1, 2, 3, 4):
        raise ValueError(
            "Resource PA link requires separate native resource notification contract"
        )
    from .combat_actor_snapshot import native_actor_catalog

    profile = native_actor_catalog()["characteristics"].get(str(stat))
    if profile is None or profile.get("expandable") is not False:
        raise ValueError(
            "Native link requires proven non-expandable fff PA characteristic"
        )
    actor = fight.actors.get(identity)
    if actor is None:
        raise ValueError("Missing native characteristic link actor")
    for name in ("effect_stats", "effect_minima", "effect_maxima"):
        values = getattr(actor, name, None)
        if not isinstance(values, dict) or type(values.get(stat)) is not int:
            raise ValueError("Missing actual native link PA current/bounds")
    if not isinstance(actor.effect_frozen, frozenset):
        raise ValueError("Missing native PA link mutability")
    current, minimum, maximum = (
        getattr(actor, name)[stat]
        for name in ("effect_stats", "effect_minima", "effect_maxima")
    )
    if not minimum <= current <= maximum:
        raise ValueError("Native link PA raw/current snapshot mismatch")
    return actor, current, minimum, maximum


def _change(fight, identity, stat, amount, *, remove=False):
    actor, before, minimum, maximum = _characteristic(fight, identity, stat)
    if stat in actor.effect_frozen:
        return 0
    if remove:
        requested = minimum if amount > before - minimum else _int32(before - amount)
    else:
        requested = maximum if amount > maximum - before else _int32(before + amount)
    after = max(minimum, min(maximum, requested))
    actor.effect_stats[stat] = after
    return _int32(before - after if remove else after - before)


def _refresh(fight, row):
    # Dependency cycles are rejected at registration, not silently suppressed.
    _change(
        fight,
        row["destination_id"],
        row["destination_stat"],
        row["actual"],
        remove=True,
    )
    _, source, _, _ = _characteristic(fight, row["source_id"], row["source_stat"])
    amount = link_contribution(source, row["percent"], row["upper"], row["lower"])
    row["actual"] = _change(
        fight, row["destination_id"], row["destination_stat"], amount
    )


def _check_dependency(records, source, destination):
    edges = {}
    for row in records.values():
        edges.setdefault((row["source_id"], row["source_stat"]), set()).add(
            (row["destination_id"], row["destination_stat"])
        )
    pending, seen = [destination], set()
    while pending:
        node = pending.pop()
        if node == source:
            raise ValueError(
                "Cyclic native characteristic PA listener contract unsupported"
            )
        if node not in seen:
            seen.add(node)
            pending.extend(edges.get(node, ()))


class NativeCharacteristicLinkHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )

    def __call__(self, effect, values, invocation):
        raw = effect.get("parameters")
        if (
            effect.get("effect_class") != 1038
            or not isinstance(raw, (list, tuple))
            or len(raw) < 4
            or len(raw) % 2
        ):
            raise ValueError("Missing native eWh characteristic definition")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing native eWh execution authority")
        if not context.executable:
            return False
        params = [
            parameter_value(raw, i, invocation.level) for i in range(len(raw) // 2)
        ]
        from .combat_value_transfer import apply_context_value

        source_parameter = apply_context_value(
            params[0],
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        source_stat, destination_stat = source_parameter & 255, params[1] & 255
        reverse = len(params) > 2 and params[2] == 1
        source_id = invocation.caster_id if reverse else invocation.target_id
        destination_id = invocation.target_id if reverse else invocation.caster_id
        _characteristic(self.fight, source_id, source_stat)
        _characteristic(self.fight, destination_id, destination_stat)
        records = getattr(self.fight, "native_characteristic_links", {})
        _check_dependency(
            records, (source_id, source_stat), (destination_id, destination_stat)
        )
        bind_characteristic_stats(self.fight)
        uid = self.allocate_uid()
        row = dict(
            uid=uid,
            source_id=source_id,
            source_stat=source_stat,
            destination_id=destination_id,
            destination_stat=destination_stat,
            percent=params[3] if len(params) > 3 else 100,
            upper=params[4] if len(params) > 4 else 0,
            lower=params[5] if len(params) > 5 else -(1 << 31),
            actual=0,
        )
        self.fight.native_characteristic_links = records
        records[uid] = row
        try:
            _refresh(self.fight, row)
        except Exception:
            records.pop(uid, None)
            raise
        # eWh aSg remains the source characteristic ID, not its contribution.
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            value=source_parameter,
            timing_payload=context.timing_payload,
        )
        additional = (
            _integer(17, int(reverse))
            + _integer(19, row["percent"])
            + _integer(12, params[1])
            + _integer(10, row["upper"])
            + _integer(20, row["lower"])
        )
        payload += b"\x42" + _varint(len(additional)) + additional
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=invocation.target_id,
                caster_id=invocation.caster_id,
                effect_class=1038,
                family="eWh",
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        self.packets.append(
            owned_effect_delivery(
                self.fight.id,
                self.action_id,
                effect_class=1038,
                target_id=invocation.target_id,
                uid=uid,
                running_effect_payload=payload,
            )
        )
        return True


def remove_characteristic_link(handler, uid):
    row = handler.fight.native_characteristic_links.pop(uid)
    _change(
        handler.fight,
        row["destination_id"],
        row["destination_stat"],
        row["actual"],
        remove=True,
    )
    entry = handler.fight.owned_stat_effects.pop(uid)
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=1038,
        target_id=entry["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    handler.packets.append((13560, packet))
