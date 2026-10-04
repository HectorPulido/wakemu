"""Persisted central fresh-cast retention registry, including native groups."""
from dataclasses import asdict
from contextlib import contextmanager
from .combat_native_container import state_container_scope, resolve_state_container
from functools import lru_cache
import json
import struct
from .paths import DATA_ROOT
from .combat_parameters import _float32
from .combat_effects import _integer, _varint
from .combat_native_timing_context import native_definition_timing
from .combat_retained_effects import (
    RetainedEffect,
    NativeRetainedEffectView,
    NativeRetainedRemoval,
    register_owned_removals,
)
from .combat_effect_removal import running_effect_removal, _identity_fields
from .combat_stat_effects import owned_effect_application


@lru_cache(maxsize=1)
def native_retained_metadata():
    return json.loads((DATA_ROOT / "native-retained-effect-metadata.json").read_text())


def _blob(field, data):
    return _varint(field << 3 | 2) + _varint(len(data)) + data


def native_retained_condition_effects(fight, actor_id):
    """Read the complete tracked Qf population without storing runtime objects on Fight."""
    if fight.native_retained_tracking is not True or actor_id not in fight.actors:
        raise ValueError("Unverified native retained condition population")
    live = (
        set(fight.owned_stat_effects)
        | set(fight.state_wire_payloads)
        | set(fight.native_owned_group_effects)
    )
    live.update(e.uid for a in fight.actors.values() for e in a.state_ledger.entries)
    if (
        live != set(fight.native_retained_records)
        or live != set(fight.native_retained_order)
        or len(live) != len(fight.native_retained_order)
    ):
        raise ValueError("Incomplete native retained condition population")
    view = NativeRetainedEffectView(
        fight,
        [
            RetainedEffect(**fight.native_retained_records[uid])
            for uid in fight.native_retained_order
        ],
        population_verified_complete=True,
    )
    return tuple(
        (entry.generic_effect, entry.effect_class, entry.uid)
        for entry in view.entries
        if entry.manager_id == actor_id
    )


def group_payload(
    *,
    uid,
    base_uid,
    generic_effect,
    caster_id,
    target_id,
    cell,
    container_type,
    container_id,
    timing_payload,
    context_payload=None
):
    if base_uid is None:
        base_uid = uid
    if (
        type(uid) is not int
        or not 0 < uid < (1 << 63)
        or type(base_uid) is not int
        or not 0 <= base_uid < (1 << 63)
    ):
        raise ValueError("Invalid retained group UID")
    if any(
        type(v) is not int or v == 0 or not -(1 << 63) <= v < (1 << 63)
        for v in (caster_id, target_id)
    ):
        raise ValueError("Invalid retained group actors")
    if not isinstance(timing_payload, bytes):
        raise ValueError("Missing native group TimeDatas")
    position = b"".join(_integer(k, v) for k, v in enumerate(cell, 1))
    return (
        b"".join(
            _integer(k, v)
            for k, v in ((1, uid), (2, base_uid), (3, generic_effect), (4, 0))
        )
        + _blob(5, position)
        + _integer(6, caster_id)
        + _integer(7, target_id)
        + _integer(9, container_type)
        + _integer(10, container_id)
        + _blob(11, timing_payload)
        + (b"" if context_payload is None else _blob(12, context_payload))
    )


class NativeRetainedRuntime:
    def __init__(
        self, fight, packets, *, plan, state_catalog, action_id, timing, metadata=None
    ):
        self.fight, self.packets, self.plan, self.states = (
            fight,
            packets,
            plan,
            state_catalog,
        )
        self.action_id, self.timing = action_id, timing
        self.metadata = native_retained_metadata() if metadata is None else metadata
        self.stat_handler = None
        self._carrier_parents = []
        self._container_scopes = []
        if fight.native_retained_tracking is not True:
            raise ValueError(
                "Native retained population has an untracked execution history"
            )
        self.synchronize()
        if set(self._live()) != set(fight.native_retained_records):
            raise ValueError("Native retained population contains unregistered effects")
        self.container(None)

    def _live(self):
        return (
            set(self.fight.owned_stat_effects)
            | set(self.fight.state_wire_payloads)
            | set(self.fight.native_owned_group_effects)
            | {
                e.uid
                for a in self.fight.actors.values()
                for e in a.state_ledger.entries
            }
        )

    def synchronize(self):
        live = self._live()
        for uid in tuple(self.fight.native_retained_records):
            if uid not in live:
                del self.fight.native_retained_records[uid]
        self.fight.native_retained_order[:] = [
            uid for uid in self.fight.native_retained_order if uid in live
        ]

    def container(self, invocation):
        if invocation is not None and invocation.state_uid is not None:
            state = resolve_state_container(self.fight, invocation.state_uid)
            return (
                dict(
                    container_present=True,
                    container_type=3,
                    container_is_spell=False,
                    spell_protected=None,
                ),
                (state.reference << 16) | state.level,
            )
        direct = self.plan.get("native_retained_container")
        if direct is not None:
            if type(direct.get("present")) is not bool:
                raise ValueError("Native direct container presence required")
            if not direct["present"]:
                return (
                    dict(
                        container_present=False,
                        container_type=None,
                        container_is_spell=None,
                        spell_protected=None,
                    ),
                    None,
                )
            kind, identity = direct.get("type"), direct.get("id")
            if (
                type(kind) is not int
                or type(identity) is not int
                or not -(1 << 63) <= identity < (1 << 63)
                or type(direct.get("is_spell")) is not bool
            ):
                raise ValueError("Native direct container identity/kind required")
            if direct["is_spell"] and type(direct.get("protected")) is not bool:
                raise ValueError("Native direct spell protection required")
            return (
                dict(
                    container_present=True,
                    container_type=kind,
                    container_is_spell=direct["is_spell"],
                    spell_protected=direct.get("protected"),
                ),
                identity,
            )
        spell = self.plan.get("spell_id")
        level = self.plan.get("evaluation_level")
        row = self.metadata.get("spells", {}).get(str(spell))
        if row is None or type(level) is not int or not 0 <= level <= 32767:
            raise ValueError("Missing native spell container metadata")
        protected = row["protected"]
        if type(protected) is not bool:
            raise ValueError("Missing native fyF.elO")
        return dict(
            container_present=True,
            container_type=25 if protected else 11,
            container_is_spell=True,
            spell_protected=protected,
        ), (spell << 16) + (level & 255)

    @contextmanager
    def applied_state_scope(self, entry):
        """Bind the fyW just constructed by StateHandler for its full iterator.

        Includes non-retained instant carriers; this trusted entry comes from
        Fight.apply_state, never an event's unresolved external UID.
        """
        from .combat_state_ledger import RunningState

        if not isinstance(entry, RunningState):
            raise ValueError("Missing authoritative applied state container")
        self._container_scopes.append({entry.uid: entry})
        try:
            with state_container_scope(self.fight, self._container_scopes[-1]):
                yield
        finally:
            self._container_scopes.pop()

    @contextmanager
    def container_scope(self, invocation):
        """Qe receives the actual fyW object, even if a child replaces its state.

        Resolve only a live or already executing container. The snapshot expires
        with the synchronous call; a stale UID in a later event still rejects.
        """
        scope = {}
        if invocation is not None and invocation.state_uid is not None:
            uid = invocation.state_uid
            state = resolve_state_container(self.fight, uid)
            scope[uid] = state
        self._container_scopes.append(scope)
        try:
            with state_container_scope(self.fight, self._container_scopes[-1]):
                yield
        finally:
            self._container_scopes.pop()

    def definition(self, effect, invocation):
        row = self.metadata["effects"].get(str(invocation.reference))
        if row is None:
            raise ValueError("Missing native retained definition metadata")
        for name in ("effect_class", "variant", "minimum_level", "maximum_level"):
            if row[name] != effect.get(name):
                raise ValueError(
                    "Native retained definition identity differs from execution catalog"
                )
        if list(map(_float32, row["parameters"])) != list(
            map(_float32, effect["parameters"])
        ):
            raise ValueError(
                "Native retained definition parameters differ from execution catalog"
            )
        if row["definition_type"] != effect.get("native_execution_mode"):
            raise ValueError("Native retained definition mode differs from catalog")
        return row

    def record(self, entry):
        uid = entry.uid
        if uid in self.fight.native_retained_records:
            raise ValueError("Native effect already registered")
        self.fight.native_retained_records[uid] = asdict(entry)
        self.fight.native_retained_order.append(uid)

    def _record_stat(self, uid, effect, invocation):
        row = self.fight.owned_stat_effects[uid]
        definition = self.definition(effect, invocation)
        container, _ = self.container(invocation)
        self.record(
            RetainedEffect(
                uid,
                row["target_id"],
                row["effect_class"],
                invocation.reference,
                owner_uid=row.get("state_uid"),
                manager_id=row["caster_id"]
                if definition["owner_on_caster"]
                else row["target_id"],
                definition_type=definition["definition_type"],
                definition_dispellable=definition["definition_dispellable"],
                **container
            )
        )

    def _record_carrier(self, uid, invocation):
        state = next(
            e
            for a in self.fight.actors.values()
            for e in a.state_ledger.entries
            if e.uid == uid
        )
        flags = self.metadata["states"].get(str(state.reference))
        if flags is None:
            raise ValueError("Missing native fyW removal metadata")
        parent = self._carrier_parents[-1] if self._carrier_parents else invocation
        container, _ = self.container(parent)
        self.record(
            RetainedEffect(
                uid,
                state.target_id,
                310,
                -1,
                manager_id=state.target_id,
                definition_type=0,
                state_unremovable=flags["unremovable"]
                if state.protected is None
                else state.protected,
                state_dispellable=flags["dispellable"],
                **container
            )
        )

    def open_state(self, invocation):
        self._carrier_parents.append(invocation)

    def close_state(self, invocation):
        if not self._carrier_parents or self._carrier_parents[-1] != invocation:
            raise ValueError("Native state registration scope mismatch")
        try:
            self.synchronize()
            for uid in self.fight.state_wire_payloads:
                if uid not in self.fight.native_retained_records:
                    self._record_carrier(uid, invocation)
        finally:
            self._carrier_parents.pop()

    def apply_state_reference(
        self, handler, invocation, reference, level, *, carrier_context, protected=None
    ):
        if handler.fight is not self.fight:
            raise ValueError("Direct native state handler belongs to another preview")
        self.open_state(invocation)
        try:
            result = handler.apply_reference(
                None,
                invocation,
                reference,
                level,
                carrier_context=carrier_context,
                protected=protected,
            )
        except BaseException:
            self._carrier_parents.pop()
            raise
        self.close_state(invocation)
        return result

    def probability_bypassed(self, invocation):
        if invocation.native_context_hex is None:
            return False
        fields = _identity_fields(
            bytes.fromhex(invocation.native_context_hex),
            integer_fields=(1, 2, 4, 5, 6, 7, 8, 9),
        )
        if any(fields.get(key) not in (0, 1) for key in (1, 2, 5, 7, 8)):
            raise ValueError("Invalid native eVt probability context")
        return fields[1] == 1

    def wrap(self, handler, *, state=False):
        def execute_scoped(effect, values, invocation):
            self.synchronize()
            before = self._live()
            definition = self.definition(effect, invocation)
            if not state:
                native = native_definition_timing(effect, invocation.level)
                if native["retained"] and not (
                    effect["effect_class"]
                    in (31, 41, 56, 57, 191, 192, 321, 421, 877, 986, 1013, 1065, 1201, 1202)
                    or str(effect["effect_class"]) in self.stat_handler.registry
                ):
                    raise ValueError(
                        "Retained native effect family lacks central ownership machinery"
                    )
            if state:
                self._carrier_parents.append(invocation)
            try:
                result = handler(effect, values, invocation)
            finally:
                if state:
                    self._carrier_parents.pop()
            # Nested children can encounter a new carrier before the applying
            # state's outer call completes. Register it before the child.
            self.synchronize()
            for uid in self.fight.state_wire_payloads:
                if uid not in self.fight.native_retained_records:
                    self._record_carrier(uid, invocation)
            for uid in self.fight.owned_stat_effects:
                if uid not in self.fight.native_retained_records:
                    if uid not in before:
                        self._record_stat(uid, effect, invocation)
                    else:
                        raise ValueError(
                            "Previously unregistered retained native stat effect"
                        )
            return result

        def execute(effect, values, invocation):
            with self.container_scope(invocation):
                return execute_scoped(effect, values, invocation)

        return execute

    def is_subscription(self, effect, invocation):
        if effect["effect_class"] not in (
            330,
            400,
            844,
            910,
            912,
            913,
            999,
            1020,
            1047,
        ):
            return False
        row = self.definition(effect, invocation)
        expected = any(effect["target_masks"][index] for index in (0, 1, 3, 4, 5))
        if row["subscription"] is not expected:
            raise ValueError("Native subscription metadata differs from catalog masks")
        return expected

    def child_context(self, effect, values, invocation, *, event_activation=False):
        from .combat_state_level_group import child_level
        from .combat_level_group import level_group_override

        override = -1
        if effect["effect_class"] == 844:
            override = child_level(
                effect,
                values,
                invocation,
                self.fight.actors,
                return_native_override=True,
            )
        elif effect["effect_class"] == 999:
            parameters = values["parameters"]
            caster, target = invocation.caster_id, invocation.target_id
            rebind = ((parameters[5] + 128) % 256) - 128
            if rebind == 1:
                caster = target
            elif rebind == 2:
                caster, target = target, caster
            actor = self.fight.actors.get(caster if parameters[6] == 1 else target)
            if actor is None:
                raise ValueError("Native eYm requires authoritative level actor")
            override = level_group_override(
                effect,
                invocation.level,
                actor.effective_level,
                return_native_override=True,
            )
        elif effect["effect_class"] == 1047:
            from .combat_hp_level_group import runtime_group_level

            override = runtime_group_level(
                effect,
                values,
                invocation,
                self.fight.actors,
                return_native_override=True,
            )
        elif effect["effect_class"] == 913:
            from .combat_characteristic_level_group import runtime_group_level

            override = runtime_group_level(
                effect,
                values,
                invocation,
                self.fight.actors,
                return_native_override=True,
            )
        elif effect["effect_class"] in (910, 912):
            from .combat_cost_level_group import runtime_group_level

            override = runtime_group_level(
                effect,
                values,
                invocation,
                self.fight.actors,
                return_native_override=True,
                cost_resolver=getattr(self, "cost_resolver", None),
            )
        elif effect["effect_class"] == 1020:
            from .combat_trigger_level_group import runtime_group_level

            override = runtime_group_level(
                effect,
                values,
                invocation,
                self.fight.actors,
                return_native_override=True,
            )
        # eYg.d(nonrelative) native eVt: flags false, SP default-1,
        # mb(false), count0, origin kindiu0. fLP is not serialized here.
        return b"".join(
            _integer(k, v)
            for k, v in (
                (1, int(event_activation)),
                (2, 0),
                (4, override),
                (5, 0),
                (6, 0),
                (7, 0),
                (8, 0),
                (9, 0),
            )
        )

    def begin_group(self, effect, values, invocation):
        definition = self.definition(effect, invocation)
        for uid in self.fight.state_wire_payloads:
            if uid not in self.fight.native_retained_records:
                self._record_carrier(uid, invocation)
        native = native_definition_timing(effect, invocation.level)
        # This entry is a fresh cast/application. Event copies use Qe.bbL and
        # must provide a separate suppression context before reuse.
        from .combat_native_events import validate_group_registration_flags

        validate_group_registration_flags(
            effect["native_effect_flags"], active=self.fight.phase == "active"
        )
        if not native["retained"]:
            return None
        if invocation.target_id is None:
            raise ValueError(
                "Retained native cell group requires target-less owner/wire machinery"
            )
        container, identity = self.container(invocation)
        context = self.timing.stat(self.fight, self.plan, effect, invocation)
        uid = self.fight.allocate_effect_uid()
        payload = group_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            cell=invocation.cell,
            container_type=container["container_type"],
            container_id=identity,
            timing_payload=context.timing_payload,
            context_payload=None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        if effect["effect_class"] == 400:
            from .combat_stat_effects import owned_effect_payload

            # Qe.d subscription branch skips eXE.C: constructor status remains -1.
            payload = owned_effect_payload(
                uid=uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=invocation.target_id,
                value=0,
                timing_payload=context.timing_payload,
                execution_status=-1,
                executed=False,
            )
            if container["container_present"]:
                payload += _integer(9, container["container_type"]) + _integer(
                    10, identity
                )
            if invocation.native_context_hex is not None:
                payload += _blob(12, bytes.fromhex(invocation.native_context_hex))
        record = RetainedEffect(
            uid,
            invocation.target_id,
            effect["effect_class"],
            invocation.reference,
            owner_uid=invocation.state_uid,
            manager_id=invocation.caster_id
            if definition["owner_on_caster"]
            else invocation.target_id,
            definition_type=definition["definition_type"],
            definition_dispellable=definition["definition_dispellable"],
            **container
        )
        return dict(
            execution_count=definition.get("event_execution_count"),
            uid=uid,
            target_id=invocation.target_id,
            effect_class=effect["effect_class"],
            state_uid=invocation.state_uid,
            payload=payload.hex(),
            timer=None if context.timer is None else dict(vars(context.timer)),
            invocation=dict(vars(invocation)),
            native_subscription_masks=effect["target_masks"],
            native_selector=effect["native_target_selector"],
            native_effect_flags=list(effect["native_effect_flags"]),
            children=list(effect["children"]),
            variant=effect["variant"],
            record=record,
        )

    def finish_group(self, pending):
        if pending is None:
            return
        row = dict(pending)
        record = row.pop("record")
        uid = row["uid"]
        self.fight.native_owned_group_effects[uid] = row
        self.record(record)  # Native Qf.p happens AFTER the group's child calls.
        self.packets.append(
            (
                13497,
                owned_effect_application(
                    self.fight.id,
                    self.action_id,
                    effect_class=row["effect_class"],
                    target_id=row["target_id"],
                    uid=uid,
                    running_effect_payload=bytes.fromhex(row["payload"]),
                ),
            )
        )

    def view(self):
        self.synchronize()
        if set(self._live()) != set(self.fight.native_retained_records):
            raise ValueError(
                "Unregistered native retained effects prevent complete view"
            )
        if set(self.fight.native_retained_order) != set(
            self.fight.native_retained_records
        ) or len(self.fight.native_retained_order) != len(
            set(self.fight.native_retained_order)
        ):
            raise ValueError("Native retained insertion order is inconsistent")
        return NativeRetainedEffectView(
            self.fight,
            [
                RetainedEffect(**self.fight.native_retained_records[uid])
                for uid in self.fight.native_retained_order
            ],
            population_verified_complete=self.fight.native_retained_tracking,
        )

    def condition_effects(self, actor_id):
        """Qf-ordered (generic definition ID, action class, running UID) for one actor.

        Completeness is checked against this preview's tracked central population,
        never attested by an external condition caller. Ownership follows the Qf
        manager actor rather than the serialized effect target.
        """
        self.synchronize()
        return native_retained_condition_effects(self.fight, actor_id)

    def remove_group(self, uid):
        remove_owned_group(self.fight, self.packets, action_id=self.action_id, uid=uid)
        self.synchronize()

    def removal(self, view):
        removal = NativeRetainedRemoval(view)
        register_owned_removals(
            removal,
            stat_handler=self.stat_handler,
            packets=self.packets,
            action_id=self.action_id,
        )
        for family in (330, 400, 844, 910, 912, 913, 999, 1020, 1047):
            previous = removal.families.pop(family, None)

            def validate(entry):
                row = self.fight.native_owned_group_effects[entry.uid]
                running_effect_removal(
                    self.fight.id,
                    self.action_id,
                    effect_class=row["effect_class"],
                    target_id=row["target_id"],
                    uid=entry.uid,
                    running_effect_payload=bytes.fromhex(row["payload"]),
                )

            removal.register(
                family,
                exists=lambda uid, old=previous: uid
                in self.fight.native_owned_group_effects
                or (old is not None and old[0](uid)),
                remove=lambda uid, old=previous: self.remove_group(uid)
                if uid in self.fight.native_owned_group_effects
                else old[1](uid),
                validate=lambda entry, old=previous, group_validate=validate: group_validate(
                    entry
                )
                if entry.uid in self.fight.native_owned_group_effects
                else old[2](entry),
            )
        return removal


def remove_owned_group(fight, packets, *, action_id, uid):
    """Common group removal for dispel, state replacement and timer expiry.

    Group removal does not undo its separately owned executed child effects.
    """
    row = fight.native_owned_group_effects.get(uid)
    metadata = fight.native_retained_records.get(uid)
    if row is None or metadata is None:
        raise ValueError("Missing centrally owned native group")
    entry = RetainedEffect(**metadata)
    payload = running_effect_removal(
        fight.id,
        action_id,
        effect_class=row["effect_class"],
        target_id=row["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    manager = entry.manager_id if entry.manager_id is not None else entry.target_id
    packets.append((13560, payload[:-16] + struct.pack(">qq", manager, uid)))
    del fight.native_owned_group_effects[uid]
    del fight.native_retained_records[uid]
    fight.native_retained_order.remove(uid)


def remove_owned_stat(handler, uid):
    """Reverse the payload target's stat and address the manager's native Qf."""
    row = handler.fight.owned_stat_effects.get(uid)
    if row is None:
        raise ValueError("Missing owned native stat removal")
    metadata = handler.fight.native_retained_records.get(uid)
    manager = row["target_id"] if metadata is None else metadata.get("manager_id")
    if manager is None:
        raise ValueError("Missing native retained stat manager identity")
    handler.remove(uid)
    if manager != row["target_id"]:
        opcode, payload = handler.packets[-1]
        if opcode != 13560 or struct.unpack(">q", payload[-8:])[0] != uid:
            raise ValueError("Native stat removal outbox identity differs")
        handler.packets[-1] = (opcode, payload[:-16] + struct.pack(">qq", manager, uid))
