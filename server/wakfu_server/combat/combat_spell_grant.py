"""Native eWn649 temporary spell registry and shortcut, independent of breed."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_effect_removal import running_effect_removal
from .combat_observation_delivery import evaluated_application_from_observation
from .combat_effects import _integer, _varint


@lru_cache(maxsize=1)
def native_spell_references():
    return frozenset(
        protocol_catalog.load(DATA_ROOT / "native-spell-references.json")["references"]
    )


def granted_spells(fight, actor_id):
    from .combat_morph_spellbook import morph_record

    morph = morph_record(fight, actor_id)
    if morph is not None:
        return morph["grants"]
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
        if reference not in native_spell_references() or not 0 <= level <= 32767:
            raise ValueError("Unknown native eWn spell or level")
        # bPS.i -> bPO constructor applies Math.min(requested, bPK.Fq()).
        from .combat_native_spell_casting import catalog as casting_catalog

        level = min(level, casting_catalog()[str(reference)]["maximum_level"])
        # A fresh controlled actor already has raw-reference UIDs. eWn.fMO
        # keeps that exact existing fyG object instead of replacing its level.
        from .combat_morph_spellbook import morph_record

        morph = morph_record(self.fight, actor.id)
        object_present = True
        if morph is not None:
            # eWn.fMO sees current dok(), including an existing form bPO.
            existing = granted_spells(self.fight, actor.id).get(reference)
            if existing is not None:
                level = existing["level"]
            elif (
                reference in morph["levels"]
                and reference not in morph["removed_raw_uids"]
            ):
                level = morph["levels"][reference]
            else:
                actual_uids = (set(morph["levels"]) - morph["removed_raw_uids"]) | set(
                    morph["grants"]
                )
                # eWn.fMO catches fyR capacity failure and clears rAY. Its
                # application still delivers; bbR then has no object to remove.
                object_present = len(actual_uids) < 80
        elif actor.id in getattr(self.fight, "native_summon_registrations", {}):
            from .combat_summon_spellbook import actor_action_book
            from .combat_spell_grant_book import removed_raw_uids

            existing = granted_spells(self.fight, actor.id).get(reference)
            if existing is not None:
                level = existing["level"]
            elif reference not in removed_raw_uids(self.fight, actor.id):
                for action in actor_action_book(actor)["actions"]:
                    if action["uid"] == reference:
                        level = action["level"]
                        break
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
        pool = (
            morph["grants"]
            if morph is not None
            else self.fight.native_spell_grants.setdefault(actor.id, {})
        )
        # fyR.f tests UID: repeated grants retain the existing native spell object.
        if object_present:
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
                native_spell_object_present=object_present,
                spell_id=reference,
                spell_level=level,
                bar=bar,
                slot=slot,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        # Original eWn.f(iN) restores the spell object; only c()/fMO installs
        # it in fyR and creates the native shortcut. cvX/eIK=false retains Ty
        # and executes non-subscribed runners without recalculating C().
        self.packets.append((12613, evaluated_application_from_observation(packet)))
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
    if entry.get("native_spell_object_present", True):
        granted_spells(handler.fight, entry["target_id"]).pop(entry["spell_id"], None)
        from .combat_spell_grant_book import register_raw_removal

        register_raw_removal(handler.fight, entry["target_id"], entry["spell_id"])
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
