"""eXs/Qe lifecycle delivery for the owned ordinary actor creation path.

Qe.d emits L1 before calculation; bbJ emits L2 after criteria/probability;
Qe.a emits L3/L4 after application. Ordinary actors have no carrier chain.
Global recipients require an audited native iterator order when more than one
manager has a matching global listener. No lifecycle event ID is synthesized.
"""
from dataclasses import replace
from .combat_event_replay import (
    NativeEventSource,
    NativeCloneAuthority,
    HEALING_ELEMENT_EVENT_IDS,
)
from .combat_native_events import subscription_selection
from .combat_event_costs import source_cost_descriptor


class OrdinaryHealingEvents:
    def __init__(self, *, adapter, preview, plan, replay, retention):
        from .combat_ordinary_authority import OrdinaryActorAuthority

        if not isinstance(adapter.actor_authority, OrdinaryActorAuthority):
            raise ValueError(
                "Ordinary native event production requires exact creation authority"
            )
        self.adapter, self.preview, self.plan, self.replay, self.retention = (
            adapter,
            preview,
            plan,
            replay,
            retention,
        )
        self.authority = NativeCloneAuthority(self.executable, self.conditions)

    def executable(self, effect, invocation, source):
        if effect["effect_class"] == 400:
            # eXE.bcd() is always true: both native corpse gates are bypassed.
            if any(
                identity is not None and identity not in self.preview.actors
                for identity in (invocation.caster_id, invocation.target_id)
            ):
                raise ValueError("Native eXE clone actor absent")
            return True
        for identity in (invocation.caster_id, invocation.target_id):
            if identity is None:
                continue
            actor = self.preview.actors.get(identity)
            if actor is None:
                raise ValueError("Native clone actor absent from preview")
            authority = self.adapter.actor_authority(self.preview, actor)
            if (
                authority.targeting.get("baG") is not False
                or authority.targeting.get("baK") is not False
            ):
                raise ValueError("Native clone corpse/wrapped guards are not ordinary")
            if actor.hp <= 0:
                raise ValueError(
                    "Ordinary creation authority cannot attest post-death native corpse flags"
                )
        # eZR.i checks the retained ORIGINAL target before I(source) rebinds
        # criterion actors. The later Qe.k guard checks the rebound target baK.
        row = self.preview.native_owned_group_effects.get(invocation.base_uid)
        if row is None:
            raise ValueError("Missing original native listener for clone guard")
        original_target = row["invocation"]["target_id"]
        if original_target is not None:
            actor = self.preview.actors.get(original_target)
            if actor is None or actor.hp <= 0:
                raise ValueError(
                    "Original listener corpse context is not ordinary/alive"
                )
            authority = self.adapter.actor_authority(self.preview, actor)
            if authority.targeting.get("baG") is not False:
                raise ValueError("Unknown original listener native corpse guard")
        return True

    def conditions(self, effect, invocation, source):
        return self.adapter.condition(self.preview, self.plan, effect, invocation)

    def phase(self, effect, invocation, *, uid, value, channel, _event_ids=None):
        if channel not in (1, 2, 3, 4):
            raise ValueError("Unknown native healing lifecycle phase")
        if (
            _event_ids is None
            and effect["effect_class"] not in HEALING_ELEMENT_EVENT_IDS
        ):
            raise ValueError("Native source is not eXs")
        for identity in (invocation.caster_id, invocation.target_id):
            actor = self.preview.actors.get(identity)
            if actor is None:
                raise ValueError("Ordinary healing actor absent")
            self.adapter.actor_authority(self.preview, actor)
        definition = self.retention.definition(effect, invocation)
        suppressed = definition.get("event_suppresses_level_one")
        if type(suppressed) is not bool:
            raise ValueError("Native PK.aZB metadata required")
        # Qe.aWr clears bfQ; ordinary registry eXs fresh prototypes have bfQ=false.
        # This path exposes no mutator of a source running effect's bfQ/bfA.
        flags = effect["native_effect_flags"]
        # eXs.bbw returns shared EMPTY BitSet for sdQ(undead), even flag33.
        undead = 20 in self.adapter.actor_authority.properties(
            self.preview, self.preview.actors[invocation.target_id]
        )
        event_ids = (
            _event_ids
            if _event_ids is not None
            else (
                ()
                if undead
                else tuple(
                    sorted(
                        {
                            0,
                            1,
                            HEALING_ELEMENT_EVENT_IDS[effect["effect_class"]],
                            *(effect["target_masks"][6] or ()),
                        }
                    )
                )
            )
        )
        parent = (
            None
            if invocation.native_trigger_context is None
            else invocation.native_trigger_context["uid"]
        )
        from .combat_trigger_identifiers import source_identifiers

        base = NativeEventSource(
            uid,
            invocation.reference,
            value,
            invocation.caster_id,
            invocation.target_id,
            invocation.cell,
            event_ids,
            channel,
            invocation.target_id,
            parent,
            suppressed or 5 in flags,
            6 in flags,
            False,
            True,
            cost_source=source_cost_descriptor(self.retention, invocation),
            **source_identifiers(self.retention, effect, invocation),
        )
        base.validate()
        # Qe.L routes caster first (reversed), target second; same actor receives both.
        sources = [
            replace(base, channel=channel * 10, manager_actor_id=invocation.caster_id),
            base,
        ]
        outcomes = [self.replay(source, authority=self.authority) for source in sources]
        # eZR.L invokes PN.bab().m(caster) AFTER local deliveries. Determine whether
        # any complete tracked manager can observe it before requiring roster order.
        global_channel = channel * 10 + 1
        relevant = set()
        for entry in self.retention.view().entries:
            row = self.preview.native_owned_group_effects.get(entry.uid)
            if row is None:
                continue
            meta = self.retention.metadata["effects"][str(entry.generic_effect)]
            if not meta["event_global_subscription"]:
                continue
            if subscription_selection(
                masks=row["native_subscription_masks"],
                event_ids=event_ids,
                channel=global_channel,
                global_subscription=True,
                reversed_subscription=meta["event_reverse_subscription"],
                flags=row["native_effect_flags"],
                source_present=True,
                source_suppresses_level_one=base.suppresses_level_one,
                source_suppresses_all=base.suppresses_all,
                source_suppressed=False,
                source_is_self=uid == entry.uid,
                source_parent_is_self=parent == entry.uid,
            ):
                relevant.add(entry.manager_id)
        if len(relevant) > 1:
            order = getattr(self.preview, "native_event_actor_order", None)
            if (
                not isinstance(order, tuple)
                or len(order) != len(set(order))
                or set(order) != set(self.preview.actors)
            ):
                raise ValueError(
                    "Global native event requires audited fcb.m actor iterator order"
                )
            relevant = [identity for identity in order if identity in relevant]
        for identity in relevant:
            self.adapter.actor_authority(self.preview, self.preview.actors[identity])
            outcomes.append(
                self.replay(
                    replace(base, channel=global_channel, manager_actor_id=identity),
                    authority=self.authority,
                )
            )
        return tuple(outcomes)


class OrdinaryDamageEvents(OrdinaryHealingEvents):
    @classmethod
    def from_healing(cls, healing):
        return cls(
            adapter=healing.adapter,
            preview=healing.preview,
            plan=healing.plan,
            replay=healing.replay,
            retention=healing.retention,
        )

    def phase(self, effect, invocation, *, uid, value, channel, blocked, localization):
        from .combat_damage_events import damage_event_ids
        from .combat_ordinary_authority import ordinary_container_type, native_facing

        # fOF uses actual Sl.o even when definition arithmetic localization is disabled.
        actual_location = native_facing(
            self.preview.actors[invocation.caster_id],
            self.preview.actors[invocation.target_id],
        )
        events = damage_event_ids(
            effect,
            container_type=ordinary_container_type(self.preview, self.plan, invocation),
            phase=channel,
            blocked=blocked,
            localization=actual_location,
            context_is_native_fight=True,
        )
        return super().phase(
            effect, invocation, uid=uid, value=value, channel=channel, _event_ids=events
        )
