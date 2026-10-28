"""eXs/Qe lifecycle delivery for the owned ordinary actor creation path.

Qe.d emits L1 before calculation; bbJ emits L2 after criteria/probability;
Qe.a emits L3/L4 after application. Ordinary actors have no carrier chain.
Global recipients require an audited native iterator order when more than one
manager has a matching global listener. No lifecycle event ID is synthesized.
"""
from dataclasses import replace
from .combat_native_actor_lookup import native_actor
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

        from .combat_summon import ordinary_roster_authority

        if not ordinary_roster_authority(adapter.actor_authority):
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

    def register_applied(self, effect, invocation, uid):
        self.retention.register_applied_stat(effect, invocation, uid)

    def death(self, actor_id, *, effect, invocation, uid, value):
        from .combat_death_events import deliver_owned_death

        definition = self.definition(effect, invocation)
        flags = effect["native_effect_flags"]
        parent = (
            None
            if invocation.native_trigger_context is None
            else invocation.native_trigger_context["uid"]
        )
        source = NativeEventSource(
            uid,
            invocation.reference,
            value,
            invocation.caster_id,
            actor_id,
            invocation.cell,
            (1013,),
            6,
            actor_id,
            parent,
            definition["event_suppresses_level_one"] or 5 in flags,
            6 in flags,
            False,
            True,
            cost_source=source_cost_descriptor(self.retention, invocation),
            **self.identifiers(effect, invocation),
        )
        return deliver_owned_death(
            self.preview,
            actor_id,
            source=source,
            replay=self.replay,
            authority=self.authority,
            retention=self.retention,
            finisher_cleanup=self._queue_finisher_cleanup,
        )

    def _queue_finisher_cleanup(self, source):
        pending = getattr(self, "_pending_finisher_cleanup", None)
        if pending is None:
            pending = {}
            self._pending_finisher_cleanup = pending
        pending.setdefault(source.uid, []).append(source)

    def _finish_finisher_cleanup(self, uid):
        from .combat_finisher_events import finish_owned_finisher

        pending = getattr(self, "_pending_finisher_cleanup", {})
        for source in pending.pop(uid, ()):
            packets = self.retention.packets
            start = len(packets)
            finish_owned_finisher(source, replay=self.replay, authority=self.authority)
            cleanup = packets[start:]
            del packets[start:]
            # The native death action reads PI after lethal damage. Preserve
            # the evaluated cleanup bytes until that action has been emitted.
            queued = getattr(self.preview, "native_finisher_after_death_packets", {})
            key = str(source.target_id)
            queued[key] = list(queued.get(key, ())) + [
                [opcode, payload.hex()] for opcode, payload in cleanup
            ]
            self.preview.native_finisher_after_death_packets = queued

    def executable(self, effect, invocation, source):
        from .combat_state_managers import registered_area_pv
        from .combat_area_authority import area_guards

        def require_area(identity):
            area = registered_area_pv(self.preview, identity)
            if area is None:
                raise ValueError("Native clone PV absent from preview")
            return area

        if effect["effect_class"] == 400:
            # eXE.bcd() is always true: both native corpse gates are bypassed.
            for identity in (invocation.caster_id, invocation.target_id):
                if identity is not None and identity not in self.preview.actors:
                    require_area(identity)
            return True
        from .combat_ordinary_death import (
            corpse_gate_bypassed,
        )

        for identity in (invocation.caster_id, invocation.target_id):
            if identity is None:
                continue
            from .combat_native_actor_lookup import native_actor

            actor = native_actor(self.preview, identity)
            if actor is None:
                require_area(identity)
                continue  # PV exists; fighter HP/death authority does not apply.
            authority = self.adapter.actor_authority(self.preview, actor)
            if (
                type(authority.targeting.get("baG")) is not bool
                or type(authority.targeting.get("baK")) is not bool
            ):
                raise ValueError("Native clone corpse/wrapped guards are not ordinary")
        # eZR.i tests the retained ORIGINAL target's baG before I(source).
        row = self.preview.native_owned_group_effects.get(invocation.base_uid)
        if row is None:
            raise ValueError("Missing original native listener for clone guard")
        original_target = row["invocation"]["target_id"]
        if original_target is not None:
            actor = native_actor(self.preview, original_target)
            if actor is None:
                require_area(original_target)
                if area_guards(self.preview, original_target)["baG"]:
                    return corpse_gate_bypassed(
                        effect, fight=self.preview, invocation=invocation
                    )
                return True
            authority = self.adapter.actor_authority(self.preview, actor)
            if type(authority.targeting.get("baG")) is not bool:
                raise ValueError("Unknown original listener native corpse guard")
            if authority.targeting["baG"]:
                if not corpse_gate_bypassed(
                    effect, fight=self.preview, invocation=invocation
                ):
                    return False
        return True

    def conditions(self, effect, invocation, source):
        # eZR.I rebinds criterion actors but eKc reads this.bbc (the retained
        # listener), not those arguments or its rIV triggering source.
        row = self.preview.native_owned_group_effects.get(invocation.base_uid)
        if (
            row is None
            or not {"target_id", "caster_id"} <= row.get("invocation", {}).keys()
        ):
            raise ValueError("Missing original native listener target for criteria")
        return self.adapter.condition(
            self.preview,
            self.plan,
            effect,
            invocation,
            native_original_target_id=row["invocation"]["target_id"],
            native_original_caster_id=row["invocation"]["caster_id"],
        )

    def definition(self, effect, invocation):
        return self.retention.definition(effect, invocation)

    def identifiers(self, effect, invocation):
        from .combat_trigger_identifiers import source_identifiers

        return source_identifiers(self.retention, effect, invocation)

    def phase(
        self,
        effect,
        invocation,
        *,
        uid,
        value,
        channel,
        _event_ids=None,
        final_modifier=None,
        runner_modifier=None,
        _nullable_target=False,
        _execution_blocked=None,
        _execution_status=None,
        _cost_source=None,
    ):
        if channel not in (1, 2, 3, 4):
            raise ValueError("Unknown native healing lifecycle phase")
        if (
            _event_ids is None
            and effect["effect_class"] != 24
            and effect["effect_class"] not in HEALING_ELEMENT_EVENT_IDS
        ):
            raise ValueError("Native source is not eXs")
        from .combat_state_managers import registered_area_pv

        def verify_recipient(identity):
            actor = native_actor(self.preview, identity)
            if actor is not None:
                # eGj forwards local events to its own Qf, including summons.
                # The registered authority validates current controller, master,
                # carry relations and snapshots; never redirect to the master.
                self.adapter.actor_authority(self.preview, actor)
                return actor
            # Qe.L delivers through PV.a; faV/Qq forwards to its actual Qf.
            # Explicit generic state/stat events may address a registered area.
            # Healing/eXs still requires a fighter and its characteristics.
            manager = registered_area_pv(self.preview, identity)
            if manager is None or getattr(manager, "native_is_area", False) is not True:
                raise ValueError(
                    f"Ordinary event recipient absent: identity={identity}, phase={channel}, family={effect['effect_class']}"
                )
            return manager

        for identity in (invocation.caster_id, invocation.target_id):
            if identity is None and _nullable_target:
                continue
            verify_recipient(identity)
        definition = self.definition(effect, invocation)
        suppressed = definition.get("event_suppresses_level_one")
        if type(suppressed) is not bool:
            raise ValueError("Native PK.aZB metadata required")
        # Qe.aWr clears bfQ; ordinary registry eXs fresh prototypes have bfQ=false.
        # This path exposes no mutator of a source running effect's bfQ/bfA.
        flags = effect["native_effect_flags"]
        # eXs.bbw returns shared EMPTY BitSet for sdQ(undead), even flag33.
        undead = (
            _event_ids is None
            and invocation.target_id in self.preview.actors
            and 20
            in self.adapter.actor_authority.properties(
                self.preview, self.preview.actors[invocation.target_id]
            )
        )
        if _event_ids is None and effect["effect_class"] == 24:
            from .combat_life_steal import life_steal_event_ids

            _event_ids = (
                ()
                if undead
                else tuple(
                    sorted(
                        set(life_steal_event_ids(self.retention, invocation))
                        | set(effect["target_masks"][6] or ())
                    )
                )
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
        base = NativeEventSource(
            uid,
            invocation.reference,
            value,
            invocation.caster_id,
            invocation.target_id,
            invocation.cell,
            event_ids,
            channel,
            invocation.target_id
            if invocation.target_id is not None
            else invocation.caster_id,
            parent,
            suppressed or 5 in flags,
            6 in flags,
            False,
            True,
            final_modifier=final_modifier,
            runner_modifier=runner_modifier,
            native_execution_blocked=_execution_blocked,
            native_execution_status=_execution_status,
            cost_source=(
                source_cost_descriptor(self.retention, invocation)
                if _cost_source is None
                else _cost_source
            ),
            **self.identifiers(effect, invocation),
        )
        base.validate()
        # Qe.L routes caster first (reversed), target second; same actor receives both.
        sources = []
        if invocation.caster_id is not None:
            sources.append(
                replace(
                    base, channel=channel * 10, manager_actor_id=invocation.caster_id
                )
            )
        if invocation.target_id is not None:
            sources.append(base)
        outcomes = []
        for source in sources:
            recipient = verify_recipient(source.manager_actor_id)
            if getattr(recipient, "native_is_area", False):
                # Keep the actual Qq object across reactions that unregister it.
                from .combat_state_managers import retained_area_pv_row

                area_row = retained_area_pv_row(self.preview, source.manager_actor_id)
                if recipient.native_running_effect_manager:
                    outcomes.append(self.replay(source, authority=self.authority))
                if source.channel == 1:
                    callbacks = getattr(self.retention, "area_events", None)
                    from .combat_effect_area import native_effect_areas

                    area_definition = native_effect_areas()[str(area_row["reference"])]
                    masks = (
                        set(recipient.native_entry_masks)
                        | set(area_definition.get("exit_masks", ()))
                        | set(area_row.get("native_removal_masks", ()))
                    )
                    if callbacks is None and masks.intersection(event_ids):
                        raise ValueError(
                            "Missing native area lifecycle callback authority"
                        )
                    if callbacks is not None:
                        outcomes.extend(
                            callbacks.running_source(
                                effect,
                                invocation,
                                uid=uid,
                                value=value,
                                channel=1,
                                source=source,
                                area_row=area_row,
                                qf_delivered=True,
                            )
                        )
                continue  # Actual null bax skips Qf, never its own Qq callbacks.
            outcomes.append(self.replay(source, authority=self.authority))
        # eZR.L invokes PN.bab().m(caster) AFTER local deliveries. Determine whether
        # any complete tracked manager can observe it before requiring roster order.
        global_channel = channel * 10 + 1
        from .combat_summon_initialization import detached_actor

        construction = detached_actor(self.preview, invocation.caster_id)
        if construction is not None:
            # Actual fresh eZQ/PO.bab().m: constructor's beg contains SELF.
            # Do not substitute fcb's battle-wide registered PV iterator.
            verify_recipient(construction.id)
            outcomes.append(
                self.replay(
                    replace(
                        base, channel=global_channel, manager_actor_id=construction.id
                    ),
                    authority=self.authority,
                )
            )
            if channel == 3:
                self._finish_finisher_cleanup(uid)
            return tuple(outcomes)
        if hasattr(self.preview, "native_global_pv_collections"):
            from .combat_global_pv_collections import global_pv_iterator
            from .combat_event_replay import NativeEventReplay
            from .combat_retained_runtime import NativeRetainedRuntime
            from .combat_ordinary_authority import (
                OrdinaryActorAuthority,
                _immutable_property_catalog,
            )
            from .combat_summon import RegisteredSummonAuthority
            from .combat_npc_spellbook import ordinary_npc_spellbook
            from contextlib import nullcontext

            authority = self.adapter.actor_authority
            if type(authority) is RegisteredSummonAuthority:
                authority = authority.ordinary
            pure_reads = (
                type(self.replay) is NativeEventReplay
                and type(self.replay.retention) is NativeRetainedRuntime
                and type(authority) is OrdinaryActorAuthority
                and authority.catalog is _immutable_property_catalog()
                and (
                    authority.npc_spellbook is None
                    or authority.npc_spellbook is ordinary_npc_spellbook
                )
            )
            read_pass = self.replay.read_pass() if pure_reads else nullcontext()

            # Native m(caster) constructs its iterator after local delivery.
            # Visit every eligible PV, not a cached set of matching listeners:
            # earlier reactions can register subscriptions on later managers.
            with read_pass:
                for identity in global_pv_iterator(
                    self.preview, caster_id=invocation.caster_id
                ):
                    # Area lookup refreshes live geometry, unlike the audited
                    # ordinary fighter authority. Never carry a view across it.
                    if pure_reads and identity not in self.preview.actors:
                        self.replay.invalidate_read_pass()
                    recipient = verify_recipient(identity)
                    if (
                        getattr(recipient, "native_is_area", False)
                        and not recipient.native_running_effect_manager
                    ):
                        continue  # Qq forwards to its actual nullable Qf.
                    outcomes.append(
                        self.replay(
                            replace(
                                base, channel=global_channel, manager_actor_id=identity
                            ),
                            authority=self.authority,
                        )
                    )
                    if pure_reads and getattr(recipient, "native_is_area", False):
                        self.replay.invalidate_read_pass()
            if channel == 3:
                self._finish_finisher_cleanup(uid)
            return tuple(outcomes)
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
            if any(identity not in self.preview.actors for identity in relevant):
                raise ValueError(
                    "Global native event requires audited fighter/area iterator order"
                )
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
            recipient = verify_recipient(identity)
            if (
                getattr(recipient, "native_is_area", False)
                and not recipient.native_running_effect_manager
            ):
                raise ValueError("Global listener belongs to a native null-Qf area")
            outcomes.append(
                self.replay(
                    replace(base, channel=global_channel, manager_actor_id=identity),
                    authority=self.authority,
                )
            )
        if channel == 3:
            # All owned writers append their lethal delivery before Qe L3.
            self._finish_finisher_cleanup(uid)
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

    def phase(
        self,
        effect,
        invocation,
        *,
        uid,
        value,
        channel,
        blocked,
        localization,
        final_modifier=None,
        runner_modifier=None,
    ):
        from .combat_damage_events import damage_event_ids
        from .combat_ordinary_authority import (
            ordinary_container_type,
            native_facing,
            native_damage_target,
        )

        # fOF uses actual Sl.o even when definition arithmetic localization is disabled.
        target = native_damage_target(self.preview, invocation.target_id)
        if target is None:
            raise ValueError("Missing native eXt actor or fbd PV event target")
        from .combat_native_actor_lookup import native_actor, detached_authority

        from .combat_damage_source import native_damage_source

        caster = native_damage_source(self.preview, invocation.caster_id)
        actual_location = native_facing(caster, target)
        from .combat_area_damage_guard import area_damage_has_no_resources

        calculation_skipped = area_damage_has_no_resources(
            self.preview, invocation.target_id
        )
        events = damage_event_ids(
            effect,
            container_type=ordinary_container_type(self.preview, self.plan, invocation),
            phase=channel,
            blocked=blocked,
            localization=actual_location,
            # Detached initial children receive eZQ/PO, not eVw. eXt's
            # blocked2233 branch tests the real PN type, even with a battle
            # preview available around that independent constructor context.
            context_is_native_fight=detached_authority(self.preview, caster) is None,
            calculation_skipped=calculation_skipped,
        )
        return super().phase(
            effect,
            invocation,
            uid=uid,
            value=value,
            channel=channel,
            _event_ids=events,
            final_modifier=final_modifier,
            runner_modifier=runner_modifier,
            _execution_blocked=False if channel == 1 else blocked,
        )


class OrdinaryResourceLossEvents(OrdinaryHealingEvents):
    """eWR/eVZ characteristic masks; no elemental healing events."""

    synthetic_authority = None

    def definition(self, effect, invocation):
        if self.synthetic_authority is None:
            return self.retention.definition(effect, invocation)
        from .combat_collision_source import NativeCollisionSourceAuthority

        if type(self.synthetic_authority) is not NativeCollisionSourceAuthority:
            raise ValueError("Unverified native synthetic lifecycle authority")
        return self.synthetic_authority.definition(effect, invocation)

    def identifiers(self, effect, invocation):
        from .combat_trigger_identifiers import source_identifiers

        return source_identifiers(
            self.retention,
            effect,
            invocation,
            synthetic_authority=self.synthetic_authority,
        )

    @classmethod
    def from_healing(cls, healing):
        return cls(
            adapter=healing.adapter,
            preview=healing.preview,
            plan=healing.plan,
            replay=healing.replay,
            retention=healing.retention,
        )

    def events(self, effect, channel, plan, invocation=None):
        from .combat_resource_loss import resource_loss_event_ids

        stat = {48: 3, 55: 2}[effect["effect_class"]]
        extra = tuple(effect["target_masks"][6] or ())
        if self.synthetic_authority is not None:
            extra += self.synthetic_authority.runtime_events(effect, invocation)
        if plan is None:
            if channel != 1:
                raise ValueError("Native eVZ calculation required after L1")
            return tuple(sorted({0, 79 if stat == 3 else 77, *extra}))
        return resource_loss_event_ids(
            stat_id=stat, phase=channel, plan=plan, extra_event_ids=extra
        )

    def source(self, effect, invocation, *, uid, value, channel, plan):
        from .combat_trigger_identifiers import source_identifiers

        definition = self.definition(effect, invocation)
        suppressed = definition.get("event_suppresses_level_one")
        if type(suppressed) is not bool:
            raise ValueError("Native eVZ source suppression metadata required")
        flags = effect["native_effect_flags"]
        source = NativeEventSource(
            uid,
            invocation.reference,
            value,
            invocation.caster_id,
            invocation.target_id,
            invocation.cell,
            self.events(effect, channel, plan, invocation),
            channel,
            invocation.target_id,
            None
            if invocation.native_trigger_context is None
            else invocation.native_trigger_context["uid"],
            suppressed or 5 in flags,
            6 in flags,
            False,
            True,
            cost_source=source_cost_descriptor(self.retention, invocation),
            **self.identifiers(effect, invocation),
        )
        source.validate()
        return source

    def phase(
        self, effect, invocation, *, uid, value, channel, plan, runner_modifier=None
    ):
        return super().phase(
            effect,
            invocation,
            uid=uid,
            value=value,
            channel=channel,
            _event_ids=self.events(effect, channel, plan, invocation),
            runner_modifier=runner_modifier,
        )


class OrdinaryArmorEvents(OrdinaryDamageEvents):
    """eWW constructor/fNk call Qe.bbx (event0); bbw adds PK.aZO."""

    def phase(
        self,
        effect,
        invocation,
        *,
        uid,
        value,
        channel,
        final_modifier=None,
        runner_modifier=None,
    ):
        if effect["effect_class"] != 1013:
            raise ValueError("Native armor source requires eWx")
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) < 7:
            raise ValueError("Missing native armor source event masks")
        events = tuple(sorted({0, *(masks[6] or ())}))
        return OrdinaryHealingEvents.phase(
            self,
            effect,
            invocation,
            uid=uid,
            value=value,
            channel=channel,
            _event_ids=events,
            final_modifier=final_modifier,
            runner_modifier=runner_modifier,
        )


class OrdinaryDisplacementEvents(OrdinaryDamageEvents):
    """Qe.L routes original running caster/target, not the displaced substitute."""

    def phase(self, effect, invocation, *, uid, value, channel):
        from .combat_displacement_events import displacement_event_ids

        return OrdinaryHealingEvents.phase(
            self,
            effect,
            invocation,
            uid=uid,
            value=value,
            channel=channel,
            _event_ids=displacement_event_ids(effect),
            _nullable_target=True,
        )

    def displacement_completed(self, effect, invocation, *, uid, value, moved):
        """Do not invent events in addition to native displacement reactions.

        Original caster listener 416001 observes eVi phase3 and executes
        null runner416114, whose published emission mask contains2128.
        Shared cast boundaries now install that listener before the roots.
        The former synthetic2128 fallback duplicated its actual delivery.
        """
        return ()
