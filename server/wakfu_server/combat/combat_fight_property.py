"""eWt447 property counters, native retained ownership and exact resource writes."""
import json
from functools import lru_cache
from .paths import DATA_ROOT
from .combat_property_stack import add_property, remove_property
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload
from .combat_effect_removal import running_effect_removal
from .combat_effects import _integer, _varint
from .combat_displacement import position_payload


@lru_cache(maxsize=1)
def property_registry():
    return {
        r["id"]: r
        for r in json.loads((DATA_ROOT / "native-fight-properties.json").read_text())[
            "properties"
        ]
    }


def visibility_additional(actor):
    direction = getattr(actor, "direction", None)
    if type(direction) is not int or not 0 <= direction <= 7:
        raise ValueError("Missing native property visibility direction")
    position = position_payload(actor.position)
    return (
        b"\x7a"
        + _varint(len(position))
        + position
        + _integer(16, direction)
        + _integer(33, 1)
    )


def _side_effect(fight, actor, property_id, *, applying, authority):
    # Native bbR does not restore consumed AP/MP or recalculate HASTE/EXTRA_TURN.
    if property_id in (31, 34) and applying:
        stat = 2 if property_id == 31 else 3
        if not isinstance(actor.effect_minima, dict) or stat not in actor.effect_minima:
            raise ValueError("Missing native PA current minimum")
        minimum = actor.effect_minima[stat]
        if type(minimum) is not int:
            raise ValueError("Invalid native PA current minimum")
        return lambda: (
            actor.effect_stats.__setitem__(stat, minimum),
            setattr(actor, "ap" if stat == 2 else "mp", minimum),
        )
    if property_id in (5, 18) or (applying and property_id in (10, 25, 37)):
        callback = getattr(authority, "property_side_effect", None)
        if not callable(callback):
            raise ValueError(
                "Missing native property timeline/occupancy/listener authority"
            )
        # Callback returns a preflighted application; unknown branches reject now.
        result = callback(fight, actor, property_id, applying=applying)
        if not callable(result):
            raise ValueError("Missing native property side-effect executor")
        return result
    return lambda: None


class NativeFightPropertyHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context, authority):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context, self.authority = (
            action_id,
            allocate_uid,
            context,
            authority,
        )

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 447:
            raise ValueError("Wrong native property runner")
        if invocation.native_running_uid is not None:
            raise ValueError("Native property event clone lifecycle remains unaudited")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Missing native property execution authority")
        if not ctx.executable:
            return False
        p = values["parameters"]
        if not p or type(p[0]) is not int:
            raise ValueError("Missing native evaluated property")
        prop = p[0]
        # eWt rejects null/non-eGj targets and enum lookup failures with mu(true).
        actor = self.fight.actors.get(invocation.target_id)
        if actor is None or prop not in property_registry():
            return False
        native = self.authority(self.fight, actor)
        if native.targeting.get("is_eGj") is not True:
            return False
        counts_provider = getattr(self.authority, "property_counts", None)
        if not callable(counts_provider):
            raise ValueError("Missing complete native PB property counter authority")
        counts = counts_provider(self.fight, actor)
        side = _side_effect(
            self.fight, actor, prop, applying=True, authority=self.authority
        )
        uid = self.allocate_uid()
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=prop,
            timing_payload=ctx.timing_payload,
            execution_status=0,
            executed=True,
        )
        if prop in (5, 18):
            extra = visibility_additional(actor)
            payload += b"\x42" + _varint(len(extra)) + extra
        packet = running_effect_removal(
            self.fight.id,
            self.action_id,
            effect_class=447,
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )[:-16]
        add_property(counts, prop)
        actor.native_fight_property_counts = counts
        actor.native_fight_properties = frozenset(
            k for k, v in counts.items() if v != 0
        )
        side()
        if ctx.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                effect_class=447,
                family="eWt",
                caster_id=invocation.caster_id,
                target_id=actor.id,
                property_id=prop,
                actual=0,
                stat_id=None,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
                collision_affiliation=native.targeting.get("bcN"),
            )
        self.packets.append((13497, packet))
        return True


def remove_fight_property(handler, uid):
    row = handler.fight.owned_stat_effects[uid]
    actor = handler.fight.actors[row["target_id"]]
    counts = getattr(actor, "native_fight_property_counts", None)
    if counts is None:
        raise ValueError("Missing native retained property counters")
    prop = row["property_id"]
    # Native removal of invisibility has a separate QI/restoration callback.
    side = lambda: None
    payload = bytes.fromhex(row["payload"])
    if prop in (5, 18):
        affiliation = row.get("collision_affiliation")
        los = getattr(handler.fight, "native_los_ignored_affiliations", None)
        walk = getattr(handler.fight, "native_walk_ignored_affiliations", None)
        if (
            type(affiliation) is not int
            or not isinstance(los, frozenset)
            or not isinstance(walk, frozenset)
        ):
            raise ValueError("Missing native retained QI affiliation ownership")
        # Server fresh eWt has rBj=null. At serialization it writes current
        # position; the client then restores these current authoritative coords.
        from .wire import proto_fields, proto_field

        extra = visibility_additional(actor)
        payload = b"".join(
            proto_field(tag, value) for tag, value in proto_fields(payload) if tag != 66
        )
        payload += b"\x42" + _varint(len(extra)) + extra

        def side():
            handler.fight.native_los_ignored_affiliations = los - {affiliation}
            handler.fight.native_walk_ignored_affiliations = walk - {affiliation}

    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=447,
        target_id=actor.id,
        uid=uid,
        running_effect_payload=payload,
    )
    remove_property(counts, prop)
    actor.native_fight_properties = frozenset(k for k, v in counts.items() if v != 0)
    side()
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
    return True
