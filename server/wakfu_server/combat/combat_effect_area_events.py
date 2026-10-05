"""Explicit emulated-server Qq callbacks, separate from the fighter roster.

Native Qq mask routing/c(amP)/e(amP)/activation charges and PL(type3, UID)
are preserved. Executing installed child definitions is server policy: client
faZ callbacks are visual no-ops. Turn-start event10000 is an explicit
emulated-server policy supported by installed glyph descriptions; native Qs
creation does not emit it. Unknown event producers are rejected.
"""
from .combat_effect_dispatch import EffectInvocation
from .combat_effect_area_queries import _rows
from .combat_effect_area_geometry import contains_area_cell
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
        masks = set(definition.get("entry_masks", ())) | set(
            definition.get("exit_masks", ())
        )
        unsupported = masks - (SUPPORTED_AREA_EVENTS | {2251})
        if unsupported:
            raise ValueError(
                f"Unaudited native effect-area callback masks: {sorted(unsupported)}"
            )
        return definition

    def _activate(self, row, definition, target, *, trigger=None):
        if row.get("executing"):
            return False
        if definition["type"] == "HOUR" and (
            target is None or target.id != row["owner_id"]
        ):
            return False  # Original faZ.e(amP) compares the actual owner.
        if target is not None and 1 in definition.get("native_area_properties", ()):
            owner = self.fight.actors.get(row["owner_id"])
            if owner is None:
                raise ValueError("Missing native area affiliation owner")
            affiliation = lambda actor: getattr(
                actor, "native_fight_affiliation", actor.team
            )
            if affiliation(owner) == affiliation(target):
                return False
        remaining = row["remaining_activations"]
        if remaining == 0:
            return False
        if remaining > 0 and definition["type"] != "HOUR":
            # Qq.a decrements only !bcv(); native faZ.bcv is always true.
            row["remaining_activations"] -= 1
        if target is None:
            # faY.e(null) true, faY.c(null) null: consumes a finite charge but
            # supplies no coordinates to execute child definitions.
            return True
        if row["owner_id"] not in self.fight.actors:
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
                        row["owner_id"],
                        target.id,
                        tuple(target.position),
                        native_retained_container=dict(
                            present=True,
                            type=3,
                            id=row["uid"],
                            level=row["level"],
                            is_spell=False,
                            protected=None,
                            native_kind="effect_area",
                        ),
                        native_explicit_target=False,
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
        return True

    def _exit(self, row, target):
        # faV.g: target Qf removes effects whose PL is this area. Recorded
        # roots/descendants are owned by this exact UID, never by prototype.
        if row.get("native_area_contract") == "faZ":
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
        """Qs move order: entry10001, internal10008, exit10002."""
        return tuple(
            self.event(event, target_id, from_cell=from_cell, to_cell=to_cell)
            for event in (10001, 10008, 10002)
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

    def running_source(self, effect, invocation, *, uid, value, channel):
        """Qq.a(BitSet,Qe,byte): native recipient channel1 uses Qe.bbb caster.

        Only an actual Qq target receives this route. Definition mask6 is the
        producer, not a server-inferred event ID. Other channels still visit Qf
        first; nonempty area subscriptions require their clone authority.
        """
        row = self.fight.native_effect_areas.get(invocation.target_id)
        if row is None:
            raise ValueError("Missing native Qq source recipient")
        if any(
            record.get("manager_id") == row["uid"]
            for record in self.fight.native_owned_group_effects.values()
        ):
            raise ValueError("Native Qq subscriber clone authority is unaudited")
        if channel != 1:
            return ()
        event_ids = set(effect["target_masks"][6] or ())
        definition = self._definition(row)
        enter = bool(event_ids.intersection(definition["entry_masks"]))
        exit = bool(event_ids.intersection(definition["exit_masks"]))
        remove = removal_mask_matches(definition, event_ids)
        if not enter and not exit and not remove:
            return ()
        target = self.fight.actors.get(invocation.caster_id)
        if target is None:
            raise ValueError("Missing actual Qe.bbb area source caster")
        from dataclasses import asdict
        from .combat_event_replay import NativeEventSource
        from .combat_trigger_identifiers import source_identifiers

        retention = self.dispatcher.native_retention
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
