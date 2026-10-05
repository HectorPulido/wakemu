"""Native eWn649 temporary spell registry and shortcut, independent of breed."""
import json
from functools import lru_cache
from .paths import DATA_ROOT
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_effect_removal import running_effect_removal
from .combat_effects import _integer, _varint


@lru_cache(maxsize=1)
def native_spell_references():
    return frozenset(
        json.loads((DATA_ROOT / "native-spell-references.json").read_text())[
            "references"
        ]
    )


def granted_spells(fight, actor_id):
    return getattr(fight, "native_spell_grants", {}).get(actor_id, {})


class NativeSpellGrantHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 649 or len(effect["parameters"]) != 8:
            raise ValueError("Unsupported native eWn parameters")
        actor = self.fight.actors.get(invocation.target_id)
        if (
            actor is None
            or invocation.caster_id not in self.fight.actors
            or self.fight.phase != "active"
        ):
            raise ValueError("Invalid native eWn actor")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Unverified native eWn context")
        if not ctx.executable:
            return False
        bar, slot, reference, raw_level = [
            parameter_value(effect["parameters"], i, invocation.level) for i in range(4)
        ]
        bar = ((bar + 128) % 256) - 128
        slot = ((slot + 32768) % 65536) - 32768
        raw_level = ((raw_level + 32768) % 65536) - 32768
        level = actor.effective_level if raw_level == -1 else raw_level
        if reference not in native_spell_references() or not 1 <= level <= 32767:
            raise ValueError("Unknown native eWn spell or level")
        # bPS.i -> bPO constructor applies Math.min(requested, bPK.Fq()).
        from .combat_native_spell_casting import catalog as casting_catalog

        level = min(level, casting_catalog()[str(reference)]["maximum_level"])
        uid = self.allocate_uid()
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=0,
            timing_payload=ctx.timing_payload,
        )
        extra = b"".join(
            _integer(k, v)
            for k, v in ((10, reference), (14, raw_level), (19, bar), (20, slot))
        )
        payload += b"\x42" + _varint(len(extra)) + extra
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=649,
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        if not hasattr(self.fight, "native_spell_grants"):
            self.fight.native_spell_grants = {}
        pool = self.fight.native_spell_grants.setdefault(actor.id, {})
        # fyR.f tests UID: repeated grants retain the existing native spell object.
        pool.setdefault(
            reference, dict(uid=reference, reference=reference, level=level)
        )
        if ctx.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=649,
                family="eWn",
                spell_id=reference,
                spell_level=level,
                bar=bar,
                slot=slot,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        self.packets.append((13497, packet))
        return True


def remove_spell_grant(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=649,
        target_id=entry["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    # Native fyR.c and fzf.aX remove by object UID/ref, not reference counting.
    granted_spells(handler.fight, entry["target_id"]).pop(entry["spell_id"], None)
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
