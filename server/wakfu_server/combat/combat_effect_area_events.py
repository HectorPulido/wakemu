"""Explicit emulated-server Qq callbacks, separate from the fighter roster.

Native Qq mask routing/c(amP)/e(amP)/activation charges and PL(type3, UID)
are preserved. Executing installed child definitions is server policy: client
faZ callbacks are visual no-ops. Turn-start event10000 is an explicit
emulated-server policy supported by installed glyph descriptions; native Qs
creation does not emit it. Unknown event producers are rejected.
"""
from .combat_effect_dispatch import EffectInvocation
from .combat_effect_area_queries import _rows
from .combat_effect_area_geometry import contains_area_cell, contains_area_actor
from .combat_area_removal_masks import area_removal_masks, removal_mask_matches

SUPPORTED_AREA_EVENTS = frozenset({10000, 10001, 10002, 10006, 10008, 10011})


class NativeAreaEventRuntime:
    def __init__(self, fight, dispatcher, *, definitions):
        self.fight, self.dispatcher, self.definitions = fight, dispatcher, definitions

    def _definition(self, row):
        definition = self.definitions.get(str(row["reference"]))
        if definition is None:
            raise ValueError("Missing installed effect-area prototype")
        removal_masks = area_removal_masks(definition)
        if (
            "native_removal_masks" in row
            and frozenset(row["native_removal_masks"]) != removal_masks
        ):
            raise ValueError("Owned faV removal masks disagree with native prototype")
        # Qq stores native BitSets without an event-producer whitelist. A
        # subscription does not attest that the server can emit its event.
        # In particular, creation must preserve10016 without inventing a
        # callback; an actual Qe mask6 may deliver it through running_source.
        for name in ("entry_masks", "exit_masks"):
            masks = definition.get(name)
            if not isinstance(masks, (tuple, list)) or any(
                type(event) is not int or not 0 <= event < (1 << 31) for event in masks
            ):
                raise ValueError("Invalid installed native area BitSet masks")
        return definition

    def _target_affiliation(self, target):
        """faV filters actual amO targets; its ebh never follows owner changes."""
        from .combat_effect_area_targets import NativeAreaTarget

        if isinstance(target, NativeAreaTarget):
            rows = getattr(self.fight, "native_effect_areas", {})
            row = rows.get(target.id)
            if row is None:
                raise ValueError("Missing actual native area activation target")
            if row.get("native_fight_affiliation_source") != "faV.j(PV).bcM":
                raise ValueError("Missing native area target captured affiliation")
            value = row.get("native_fight_affiliation")
        elif getattr(target, "native_is_amO", None) is False:
            return None
        elif getattr(target, "native_is_amO", None) is True:
            value = getattr(target, "native_fight_affiliation", None)
        else:
            provider = getattr(
                getattr(self.dispatcher, "contexts", None), "area_affiliation", None
            )
            if not callable(provider) or self.fight.actors.get(target.id) is not target:
                raise ValueError("Missing native activation target amO authority")
            adapter = getattr(provider, "__self__", None)
            actor_authority = getattr(adapter, "_actor", None)
            if not callable(actor_authority):
                raise ValueError("Missing native activation target amO type authority")
            targeting = actor_authority(self.fight, target).targeting
            is_amO = targeting.get("is_amO")
            if type(is_amO) is not bool:
                raise ValueError("Missing native activation target amO type authority")
            if not is_amO:
                return None
            # faV.j's existing producer copies bcM only for actual eGj.
            # Other amO kinds need their own explicit affiliation producer.
            if targeting.get("is_eGj") is not True:
                raise ValueError("Missing non-fighter amO activation bcM authority")
            value = provider(self.fight, target.id)
        if type(value) is not int or not -128 <= value <= 127:
            raise ValueError("Missing native activation target bcM authority")
        return value

    def _activate(self, row, definition, target, *, trigger=None):
        if row.get("executing"):
            return False
        if definition["type"] == "TRAP":
            from .combat_trap_area import verified_trap_characteristics

            verified_trap_characteristics(row, definition)
        if definition["type"] == "WALL":
            from .combat_wall_area import verified_wall_constructor

            verified_wall_constructor(row, definition)
            return False  # Actual fbd.e(amP) is false, before charge handling.
        if definition["type"] == "FAKE_FIGHTER":
            from .combat_fake_fighter import verified_fake_fighter

            constructor = verified_fake_fighter(row, definition)
            own = target is not None and target.id == row["owner_id"]
            if not constructor["owner_activation" if own else "other_activation"]:
                return False  # faW.e compares actual target identity with bgZ.
        if definition["type"] == "HOUR" and (
            target is None or target.id != row["owner_id"]
        ):
            return False  # Original faZ.e(amP) compares the actual owner.
        from .combat_area_property import area_properties

        if target is not None and 1 in area_properties(row, definition):
            affiliation = self._target_affiliation(target)
            if affiliation is not None:
                captured = row.get("native_fight_affiliation")
                if (
                    type(captured) is not int
                    or not -128 <= captured <= 127
                    or row.get("native_fight_affiliation_source") != "faV.j(PV).bcM"
                ):
                    raise ValueError(
                        "Missing native area captured activation affiliation"
                    )
                if captured == affiliation:
                    return False
        remaining = row["remaining_activations"]
        if remaining == 0:
            return False
        if remaining > 0 and definition["type"] != "HOUR":
            # Qq.a decrements only !bcv(); native faZ.bcv is always true.
            row["remaining_activations"] -= 1
        if target is None and row.get("native_area_contract") != "fbc":
            # faY.e(null) true, faY.c(null) null: consumes a finite charge but
            # supplies no coordinates to execute child definitions.
            return True
        border = row.get("native_area_contract") == "faP"
        environment = row.get("native_environment_source") is not None
        if environment:
            from .combat_environment_glyphs import verify_environment_glyph

            verify_environment_glyph(self.fight, row)
        if border:
            from .combat_battleground_border import SOURCE

            if (
                row.get("owner_id") is not None
                or row.get("native_border_source") != SOURCE
            ):
                raise ValueError("Missing native faP null-owner constructor")
        elif not environment and row["owner_id"] not in self.fight.actors:
            raise ValueError("Missing registered area owner")
        self.dispatcher.native_retention.synchronize()
        before = set(self.fight.native_retained_records)
        row["executing"] = True
        try:
            for reference in definition["effect_ids"]:
                self.dispatcher.execute(
                    EffectInvocation(
                        reference,
                        row["level"],
                        row["uid"] if border or environment else row["owner_id"],
                        None if target is None else target.id,
                        tuple(row["cell"])
                        if row.get("native_area_contract") == "fbc"
                        else tuple(target.position),
                        native_retained_container=dict(
                            present=True,
                            type=3,
                            id=row["uid"],
                            level=row["level"],
                            is_spell=False,
                            protected=None,
                            native_kind="effect_area",
                        ),
                        # The border callback owns an actual amP recipient;
                        # preserve it instead of selecting another PV at the
                        # same QI-minimum cell (including the border itself).
                        native_explicit_target=border or environment,
                        native_trigger_context=trigger,
                    )
                )
        finally:
            row["executing"] = False
        self.dispatcher.native_retention.synchronize()
        new = set(self.fight.native_retained_records) - before
        children = row.setdefault("child_effect_uids", {})
        for uid in new:
            record = self.fight.native_retained_records[uid]
            if (
                record.get("container_kind") != "effect_area"
                or record.get("container_id") != row["uid"]
            ):
                continue  # Reactive fyW/fyG children do not belong to this Qq PL.
            manager = record["manager_id"]
            key = str(manager)
            children[key] = sorted(set(children.get(key, ())) | {uid})
        if row.get("native_area_contract") == "fbc":
            from .combat_trap_area import retire_exhausted_trap

            retire_exhausted_trap(self.fight, row, callbacks=self)
        return True

    def _exit(self, row, target):
        # faV.g: target Qf removes effects whose PL is this area. Recorded
        # roots/descendants are owned by this exact UID, never by prototype.
        if row.get("native_area_contract") == "fbc":
            return False  # Actual fbc.n(amP) is null: no exit recipients.
        if row.get("native_area_contract") == "fbd":
            from .combat_effect_area import native_effect_areas
            from .combat_wall_area import verified_wall_constructor

            verified_wall_constructor(row, native_effect_areas()[str(row["reference"])])
            return False  # fbd.d/n supplies its actual empty recipient list.
        if row.get("native_area_contract") in ("faZ", "faW"):
            # faZ.d(amP) always returns the actual owner, including null/other.
            target = self.fight.actors.get(row["owner_id"])
            if target is None:
                raise ValueError("Missing native HOUR cleanup owner")
        children = row.get("child_effect_uids", {})
        uids = children.get(str(target.id), ())
        live = [uid for uid in uids if uid in self.fight.native_retained_records]
        if live:
            retention = self.dispatcher.native_retention
            retention.removal(retention.view()).remove(live)
            retention.synchronize()
        children.pop(str(target.id), None)
        return bool(live)

    def _remove_on_masks(self, row, definition, event_ids):
        """faV.a calls Qq callbacks first, then rLR -> Qf.q or Qs.b."""
        if not removal_mask_matches(definition, event_ids):
            return False
        uid = row["effect_uid"]
        owned = getattr(self.fight, "native_owned_area_effects", {})
        if uid in owned:
            if owned[uid].get("removing"):
                return False  # Qf.q is already unapplying this parent.
            retention = self.dispatcher.native_retention
            retention.synchronize()
            if uid not in self.fight.native_retained_records:
                raise ValueError("Missing actual faV parent eYQ in Qf")
            retention.removal(retention.view()).remove(uid)
            retention.synchronize()
        else:
            from .combat_effect_area import remove_owned_hour_area

            remove_owned_hour_area(self.fight, row["uid"], callbacks=self)
        return True

    def event(
        self, event_id, target_id, *, area_uid=None, from_cell=None, to_cell=None
    ):
        if event_id not in SUPPORTED_AREA_EVENTS:
            raise ValueError(f"Unknown native effect-area event producer: {event_id}")
        target = self.fight.actors.get(target_id)
        if target is None:
            raise ValueError("Missing native area-event target")
        result = []
        for row in tuple(_rows(self.fight)):
            if area_uid is not None and row["uid"] != area_uid:
                continue
            definition = self._definition(row)
            if (
                row.get("native_area_contract") == "faN"
                and target.id == row["owner_id"]
                and event_id in (10001, 10002)
            ):
                continue  # Native faN suppresses its owner's movement entry/exit.
            before = contains_area_cell(row, from_cell)
            after = contains_area_cell(
                row, target.position if to_cell is None else to_cell
            )
            if event_id == 10001 and (before or not after):
                continue
            if event_id == 10002 and (not before or after):
                continue
            if event_id == 10008 and not (before and after):
                continue
            if event_id in (10000, 10006, 10008) and not after:
                continue
            result.extend(self._deliver_event(row, definition, target, event_id))
        return tuple(result)

    def _deliver_event(self, row, definition, target, event_id):
        if row.get("native_area_contract") == "fbc":
            from .combat_trap_area import trap_owner_movement_allowed

            current = self.fight.current
            if not trap_owner_movement_allowed(
                row,
                definition,
                target_id=target.id,
                current_id=None if current is None else current.id,
                event_ids=(event_id,),
            ):
                return ()
        if (
            row.get("native_area_contract") == "faN"
            and target.id == row["owner_id"]
            and event_id in (10001, 10002)
        ):
            return ()  # faN suppresses its owner's entire movement delivery.
        result = []
        if event_id in definition["entry_masks"]:
            result.append(self._activate(row, definition, target))
        if event_id in definition["exit_masks"]:
            result.append(self._exit(row, target))
        if removal_mask_matches(definition, (event_id,)):
            result.append(self._remove_on_masks(row, definition, (event_id,)))
        return tuple(result)

    def created(self, row):
        """Register only: native Qs.a -> Qq.bcH does not activate glyphs."""
        self._definition(row)
        return ()

    def turn_start(self, target_id):
        """Server policy: glyphs activate at turn start (content.67.234).

        Event10000 mapping is inferred from installed glyph entry masks, not
        claimed to be a producer recovered from the unavailable server code.
        """
        current = self.fight.current
        if self.fight.phase != "active" or current is None or current.id != target_id:
            raise ValueError(
                "Effect-area turn start requires the current active fighter"
            )
        return self.event(10000, target_id)

    def movement(self, target_id, *, from_cell, to_cell):
        """Qs freezes three actual-object lists before delivering any callback."""
        target = self.fight.actors.get(target_id)
        if target is None:
            raise ValueError("Missing native area-event target")
        lists = {event: [] for event in (10001, 10008, 10002)}
        for row in _rows(self.fight):
            definition = self._definition(row)
            before = contains_area_cell(row, from_cell)
            after = contains_area_actor(row, to_cell, target.physical_radius)
            event = (
                (10008 if before else 10001) if after else (10002 if before else None)
            )
            if event is not None:
                lists[event].append((row, definition))
        return tuple(
            tuple(
                outcome
                for row, definition in rows
                for outcome in self._deliver_event(row, definition, target, event)
            )
            for event, rows in lists.items()
        )

    def removed(self, row, *, target_id=None):
        """Qs unregisters first, then faV entry/exit and rLR event10011."""
        definition = self._definition(row)
        result = []
        target = None if target_id is None else self.fight.actors.get(target_id)
        if target_id is not None and target is None:
            raise ValueError("Missing actual Qs removal-event target")
        if 10011 in definition["entry_masks"]:
            result.append(self._activate(row, definition, target))
        if 10011 in definition["exit_masks"]:
            if definition["type"] == "HOUR":
                owner = self.fight.actors.get(row["owner_id"])
                if owner is None:
                    raise ValueError("Missing native HOUR cleanup owner")
                result.append(self._exit(row, owner))
            elif target is not None:
                result.append(self._exit(row, target))
            else:
                for key in tuple(row.get("child_effect_uids", {})):
                    target = self.fight.actors.get(int(key))
                    if target is None:
                        raise ValueError("Missing owned area cleanup manager")
                    result.append(self._exit(row, target))
        if removal_mask_matches(definition, (10011,)):
            result.append(self._remove_on_masks(row, definition, (10011,)))
        return tuple(result)

    def running_source(
        self,
        effect,
        invocation,
        *,
        uid,
        value,
        channel,
        source=None,
        area_row=None,
        qf_delivered=False,
    ):
        """Qq.a(BitSet,Qe,byte): native recipient channel1 uses Qe.bbb caster.

        Only an actual Qq target receives this route. Definition mask6 is the
        producer, not a server-inferred event ID. Other channels still visit Qf
        first; nonempty area subscriptions require their clone authority.
        """
        row = (
            self.fight.native_effect_areas.get(invocation.target_id)
            if area_row is None
            else area_row
        )
        if row is None:
            raise ValueError("Missing native Qq source recipient")
        if row.get("uid") != invocation.target_id:
            raise ValueError("Native Qq source recipient identity mismatch")
        if not qf_delivered and any(
            record.get("manager_id") == row["uid"]
            for record in self.fight.native_owned_group_effects.values()
        ):
            raise ValueError("Native Qq subscriber clone authority is unaudited")
        if channel != 1:
            return ()
        event_ids = (
            set(effect["target_masks"][6] or ())
            if source is None
            else set(source.event_ids)
        )
        definition = self._definition(row)
        enter = bool(event_ids.intersection(definition["entry_masks"]))
        exit = bool(event_ids.intersection(definition["exit_masks"]))
        remove = removal_mask_matches(definition, event_ids)
        if not enter and not exit and not remove:
            return ()
        target = self.fight.actors.get(invocation.caster_id)
        if row.get("native_area_contract") == "fbc":
            from .combat_trap_area import trap_owner_movement_allowed

            current = self.fight.current
            if not trap_owner_movement_allowed(
                row,
                definition,
                target_id=None if target is None else target.id,
                current_id=None if current is None else current.id,
                event_ids=event_ids,
            ):
                return ()
        if (
            row.get("native_area_contract") == "faN"
            and target is not None
            and target.id == row["owner_id"]
            and event_ids.intersection((10001, 10002))
        ):
            return ()  # faN's BitSet override skips the entire own movement delivery.
        if target is None:
            raise ValueError("Missing actual Qe.bbb area source caster")
        from dataclasses import asdict
        from .combat_event_replay import NativeEventSource
        from .combat_trigger_identifiers import source_identifiers

        retention = self.dispatcher.native_retention
        if source is not None:
            source.validate()
            if (
                source.uid != uid
                or source.value != value
                or source.channel != channel
                or source.manager_actor_id != row["uid"]
                or source.caster_id != invocation.caster_id
                or source.target_id != invocation.target_id
            ):
                raise ValueError("Mismatched actual Qq running source")
        else:
            source = NativeEventSource(
                uid,
                invocation.reference,
                value,
                invocation.caster_id,
                invocation.target_id,
                tuple(invocation.cell),
                tuple(sorted(event_ids)),
                channel,
                row["uid"],
                source_parent_uid=None
                if invocation.native_trigger_context is None
                else invocation.native_trigger_context["uid"],
                suppresses_level_one=retention.definition(effect, invocation)[
                    "event_suppresses_level_one"
                ]
                or 5 in effect["native_effect_flags"],
                suppresses_all=6 in effect["native_effect_flags"],
                suppressed=False,
                native_events_verified=True,
                **source_identifiers(retention, effect, invocation),
            )
        source.validate()
        result = []
        if enter:
            result.append(
                self._activate(row, definition, target, trigger=asdict(source))
            )
        if exit:
            result.append(self._exit(row, target))
        if remove:
            result.append(self._remove_on_masks(row, definition, event_ids))
        return tuple(result)
