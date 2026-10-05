"""eXA802 reciprocal pGN relation; no invented movement of its partner."""
from dataclasses import replace
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_force_characteristic import remove_forced_characteristic


def link_allowed(
    source, target, source_properties, target_properties, *, ignore_stabilization
):
    if ignore_stabilization:
        return True
    if source_properties.get(11, 0) or target_properties.get(11, 0):
        return False
    blocked = 111 if source.team == target.team else 110
    return not (source_properties.get(blocked, 0) or target_properties.get(blocked, 0))


class NativeMovementLinkHandler:
    native_runner_value_verified = True

    def __init__(self, fight, packets, *, action_id, allocate_uid, context, authority):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.authority = context, authority
        self.event_lifecycle = None

    def _phase(self, effect, invocation, uid, channel):
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=0,
                channel=channel,
                _event_ids=tuple(sorted({0, 2123, *(effect["target_masks"][6] or ())})),
            )

    def prepare(self, effect, values, invocation):
        invocation = replace(invocation, native_running_uid=self.allocate_uid())
        self._phase(effect, invocation, invocation.native_running_uid, 1)
        return invocation

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 802 or values["parameters"]:
            raise ValueError("Native eXA has no parameters")
        source = self.fight.actors.get(invocation.caster_id)
        target = self.fight.actors.get(invocation.target_id)
        if source is None or target is None:
            raise ValueError("Native eXA requires two authoritative eGj actors")
        flags = effect.get("native_effect_flags")
        if flags is None or any(type(f) is not int for f in flags):
            raise ValueError("Native eXA flags required")
        if set(flags) - {3, 5, 6, 15, 17, 36}:
            raise ValueError("Unsupported native eXA flags")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Native movement-link execution authority required")
        if not ctx.executable:
            return False
        provider = getattr(self.authority, "property_counts", None)
        if not callable(provider):
            raise ValueError("Native movement-link property authority required")
        counts = [provider(self.fight, a) for a in (source, target)]
        if any(
            not isinstance(p, dict)
            or any(type(k) is not int or type(v) is not int for k, v in p.items())
            for p in counts
        ):
            raise ValueError("Native movement-link counters required")
        if not link_allowed(source, target, *counts, ignore_stabilization=36 in flags):
            return False
        uid = invocation.native_running_uid
        if uid is None:
            uid = self.allocate_uid()
        self._phase(effect, invocation, uid, 2)
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=source.id,
            target_id=target.id,
            value=0,
            timing_payload=ctx.timing_payload,
            execution_status=0,
            executed=True,
        )
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=802,
            target_id=target.id,
            uid=uid,
            running_effect_payload=payload,
        )
        links = dict(getattr(self.fight, "native_movement_links", {}))
        # frw clears only each selected actor's pGN; old third-party links
        # are not silently normalized or restored by this native runner.
        links[source.id] = target.id
        links[target.id] = source.id
        self.fight.native_movement_links = links
        self.fight._event("movement_link", source_id=source.id, target_id=target.id)
        self.packets.append((13497, packet))
        for channel in (3, 4):
            self._phase(effect, invocation, uid, channel)
        # Qf registration follows application deliveries; the current Qe is
        # not part of the retained population while its L3/L4 are replayed.
        if ctx.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                effect_class=802,
                family="eXA",
                target_id=target.id,
                caster_id=source.id,
                stat_id=None,
                actual=0,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                executed=True,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, 0)
        return True


def remove_movement_link(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    links = dict(getattr(handler.fight, "native_movement_links", {}))
    links.pop(entry["caster_id"], None)
    links.pop(entry["target_id"], None)
    handler.fight.native_movement_links = links
    remove_forced_characteristic(handler, uid)


def movement_link_removal_dependencies(fight, entry, entries):
    """eXA.bbR calls the other actor's Qf.a(actualPL,true).

    Return explicit dependencies for the validated central removal plan;
    arbitrary callbacks never delete unvalidated sibling effects mid-loop.
    """
    row = fight.owned_stat_effects.get(entry.uid)
    if row is None or row.get("executed") is not True:
        raise ValueError("Native link removal execution identity required")
    source, target = row["caster_id"], row["target_id"]
    if (
        entry.manager_id not in (source, target)
        or type(entry.container_present) is not bool
    ):
        raise ValueError("Native link removal manager/container authority required")
    other = target if entry.manager_id == source else source
    return tuple(
        candidate.uid
        for candidate in entries
        if candidate.uid != entry.uid
        and candidate.manager_id == other
        and candidate.container_present == entry.container_present
        and candidate.container_type == entry.container_type
        and candidate.container_id == entry.container_id
    )
