"""Private installed eXW982: passive PL25 then flagged natural eZk carriers.

Qm compares PL.aZY and PL.QF, not Java object identity. The authority below
uses the existing complete central retained view and original state bindings.
No monster, spell, or state reference is special-cased.
"""
from .combat_state_parameters import pack_state_identity
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class NativeContainerKey:
    kind: int
    identity: int

    def __post_init__(self):
        if (
            type(self.kind) is not int
            or type(self.identity) is not int
            or not -(1 << 31) <= self.kind < (1 << 31)
            or not -(1 << 63) <= self.identity < (1 << 63)
        ):
            raise ValueError("Missing actual PL.aZY/QF container facts")


def identity_hashset_order(entries, identity_hash):
    """Default HashSet<eZk> order, only with same-JVM identity hash authority.

    Empty/singleton sets need no hashes. Tree/collision-driven resizing remains
    unsupported, rather than borrowing UID hashes or Python identity values.
    """
    entries = tuple(entries)
    if len({entry.uid for entry in entries}) != len(entries):
        raise ValueError("Duplicate actual carrier identity")
    if len(entries) <= 1:
        return entries
    if not callable(identity_hash):
        raise ValueError(
            "Multiple natural states require actual native identity hashes"
        )
    capacity = 16
    while len(entries) > capacity * 3 // 4:
        capacity *= 2
    buckets = {}
    for entry in entries:
        value = identity_hash(entry)
        if type(value) is not int or not 0 <= value < (1 << 32):
            raise ValueError("Missing same-JVM eZk identity hash")
        bucket = (value ^ (value >> 16)) & (capacity - 1)
        chain = buckets.setdefault(bucket, [])
        chain.append(entry)
        if len(chain) > 8:
            raise ValueError("Native identity HashSet collision domain is unsupported")
    return tuple(entry for bucket in sorted(buckets) for entry in buckets[bucket])


class RetainedCleanupAuthority:
    def __init__(self, retention, target_id, *, identity_hash=None):
        self.retention, self.fight, self.target_id = (
            retention,
            retention.fight,
            target_id,
        )
        self.identity_hash = identity_hash
        self.containers = {}
        self.removing = set()

    def _entries(self):
        view = self.retention.view()
        if view.fight is not self.fight:
            raise ValueError("Cleanup retained view belongs to another preview")
        return tuple(
            entry
            for entry in view.entries
            if (entry.manager_id if entry.manager_id is not None else entry.target_id)
            == self.target_id
        )

    def _payload(self, entry):
        if entry.effect_class == 310:
            return bytes.fromhex(self.fight.state_wire_payloads[entry.uid])
        owners = [
            rows
            for rows in (
                self.fight.owned_stat_effects,
                self.fight.native_owned_group_effects,
                self.fight.native_owned_area_effects,
                getattr(self.fight, "native_owned_spatial_effects", {}),
            )
            if entry.uid in rows
        ]
        if len(owners) != 1:
            raise ValueError("Missing unique native cleanup payload owner")
        return bytes.fromhex(owners[0][entry.uid]["payload"])

    def container(self, entry):
        from .combat_effect_removal import _identity_fields

        fields = _identity_fields(self._payload(entry), integer_fields=(9, 10))
        if type(entry.container_present) is not bool:
            raise ValueError("Missing native PL presence authority")
        if not entry.container_present:
            if fields:
                raise ValueError(
                    "Native PL absence disagrees with original running payload"
                )
            return None
        key = NativeContainerKey(entry.container_type, entry.container_id)
        signed = lambda value: value - (1 << 64) if value >= (1 << 63) else value
        if (
            set(fields) != {9, 10}
            or signed(fields[9]) != key.kind
            or signed(fields[10]) != key.identity
        ):
            raise ValueError(
                "Native PL key differs from original registered running payload"
            )
        if key.kind == 1:
            from .combat_native_container import resolve_state_container

            if type(entry.owner_uid) is not int:
                raise ValueError("State-owned effect lacks actual PL binding")
            state = resolve_state_container(self.fight, entry.owner_uid)
            if key.identity != (pack_state_identity(state.reference, state.level)):
                raise ValueError(
                    "Retained state PL differs from its actual owned snapshot"
                )
        return self.containers.setdefault(key, key)

    def cleanup_flag(self, entry):
        if entry.effect_class != 310:
            raise ValueError("fNh only belongs to actual eZk")
        from .combat_state_managers import state_manager
        from .combat_effect_removal import _identity_fields

        manager = state_manager(self.fight, self.target_id)
        states = [
            state for state in manager.state_ledger.entries if state.uid == entry.uid
        ]
        if len(states) != 1:
            raise ValueError("Missing unique owned carrier")
        state = states[0]
        payload = bytes.fromhex(self.fight.state_wire_payloads[entry.uid])
        messages = {}
        fields = _identity_fields(payload, messages=messages)
        additional = messages.get(8)
        if additional is None:
            raise ValueError("Missing native carrier AdditionalDatas")
        flags = _identity_fields(additional, integer_fields=(10, 13, 18))
        packed = pack_state_identity(state.reference, state.level)
        signed = lambda value: value - (1 << 64) if value >= (1 << 63) else value
        if (
            fields.get(1) != state.uid
            or fields.get(4) != packed
            or 6 not in fields
            or signed(fields[6]) != state.caster_id
            or 7 not in fields
            or signed(fields[7]) != state.target_id
            or flags.get(10) != packed
            or flags.get(13) != state.uid
            or flags.get(18, 0) not in (0, 1)
        ):
            raise ValueError(
                "State cleanup operand differs from registered native carrier"
            )
        return bool(flags.get(18, 0))  # ij.Me protobuf default is false.

    def _notify_forced(self, entry):
        from .combat_effect_removal import _read_varint, _identity_fields

        payload = bytes.fromhex(self.fight.state_wire_payloads[entry.uid])
        offset, timing = 0, None
        while offset < len(payload):
            tag, offset = _read_varint(payload, offset)
            wire = tag & 7
            if wire == 0:
                _, offset = _read_varint(payload, offset)
            elif wire == 2:
                length, offset = _read_varint(payload, offset)
                if tag >> 3 == 11:
                    if timing is not None:
                        raise ValueError("Duplicate native TimeDatas")
                    timing = payload[offset : offset + length]
                offset += length
            elif wire in (1, 5):
                offset += 8 if wire == 1 else 4
            else:
                raise ValueError("Unsupported native carrier wire type")
            if offset > len(payload):
                raise ValueError("Truncated native carrier")
        fields = _identity_fields(timing or b"", integer_fields=(1,))
        if fields.get(1, 0) not in (0, 1):
            raise ValueError("Invalid native notify-unapplication flag")
        return bool(fields.get(1, 0))

    def preflight(self):
        from .combat_state_managers import state_manager

        if state_manager(self.fight, self.target_id) is None:
            raise ValueError("Missing actual eZV recipient manager")
        entries = self._entries()
        selected = []
        for entry in entries:
            key = self.container(entry)
            if (key is not None and key.kind == 25) or (
                entry.effect_class == 310 and self.cleanup_flag(entry)
            ):
                selected.append(entry.uid)
        view = self.retention.view()
        removal = self.retention.removal(view)
        if removal.view is not view:
            raise ValueError("Native cleanup removal/view mismatch")
        removal.plan(selected)
        # No irreversible mutation before current multi-state order is attested.
        identity_hashset_order(
            (
                e
                for e in entries
                if e.effect_class == 310
                and self.cleanup_flag(e)
                and not (self.container(e) is not None and self.container(e).kind == 25)
            ),
            self.identity_hash,
        )

    def _set_forced(self, entry):
        from .combat_effect_removal import state_unapplication_payload

        if entry.effect_class == 310:
            collection, field = self.fight.state_wire_payloads, None
        else:
            collections = (
                self.fight.owned_stat_effects,
                self.fight.native_owned_group_effects,
                self.fight.native_owned_area_effects,
                getattr(self.fight, "native_owned_spatial_effects", {}),
            )
            owners = [rows for rows in collections if entry.uid in rows]
            if len(owners) != 1:
                raise ValueError("Missing unique owned cleanup payload")
            collection, field = owners[0], "payload"
        original = (
            collection[entry.uid] if field is None else collection[entry.uid][field]
        )
        replacement = state_unapplication_payload(bytes.fromhex(original)).hex()
        if field is None:
            collection[entry.uid] = replacement
        else:
            collection[entry.uid][field] = replacement

    def _remove_exact(self, entry):
        # Invoke the actual registered family's validate/remove callback directly.
        # Generic owner_uid recursion would choose a different population from Qm.
        view = self.retention.view()
        actual = view.by_uid.get(entry.uid)
        if actual is None:
            return
        removal = self.retention.removal(view)
        callbacks = removal.families.get(actual.effect_class)
        if callbacks is None:
            raise ValueError("Unregistered native cleanup removal family")
        exists, remove, validate = callbacks
        if exists(actual.uid) is not True:
            raise ValueError("Stale native cleanup owner")
        validate(actual)
        remove(actual.uid)
        if exists(actual.uid) is not False:
            raise ValueError("Cleanup callback retained its owned effect")
        self.retention.synchronize()

    def _remove_state(self, entry, *, forced):
        if entry.uid in self.removing:
            return
        self.removing.add(entry.uid)
        try:
            from .combat_native_container import resolve_state_container

            state = resolve_state_container(self.fight, entry.uid)
            state_key = NativeContainerKey(
                1, pack_state_identity(state.reference, state.level)
            )
            # Installed eZk.fRd calls fbX.a1046, whose only implementation returns
            # false; buH does not override. Do not invent a server event here.
            children = tuple(
                e
                for e in self._entries()
                if e.effect_class != 310 and self.container(e) == state_key
            )
            for child in children:
                if forced:
                    self._set_forced(child)
                self._remove_exact(child)
            self._remove_exact(entry)
        finally:
            self.removing.remove(entry.uid)

    def execute(self):
        self.preflight()
        # Qm compares type+QF: duplicate actual PL objects with equal keys yield
        # only empty later scans, so retaining the first key preserves removals.
        containers = tuple(
            dict.fromkeys(
                key
                for entry in self._entries()
                if (key := self.container(entry)) is not None and key.kind == 25
            )
        )
        for key in containers:
            states = []
            for entry in tuple(e for e in self._entries() if self.container(e) == key):
                self._set_forced(entry)
                if entry.effect_class == 310:
                    states.append(entry)
                else:
                    self._remove_exact(entry)
            for entry in states:
                self._remove_state(entry, forced=True)
        remaining = tuple(
            e for e in self._entries() if e.effect_class == 310 and self.cleanup_flag(e)
        )
        for entry in identity_hashset_order(remaining, self.identity_hash):
            self._remove_state(entry, forced=self._notify_forced(entry))


class NativeStateCleanupHandler:
    family = 982

    def __init__(
        self, retention, *, allocate_uid, rng, event_lifecycle, identity_hash=None
    ):
        self.retention, self.allocate_uid, self.rng = retention, allocate_uid, rng
        self.event_lifecycle, self.identity_hash = event_lifecycle, identity_hash
        self.prepared, self.activated = {}, set()

    def _validate(self, effect, values):
        if effect["effect_class"] != 982 or values["parameters"]:
            raise ValueError("Installed eXW982 has no parameters")
        if self.event_lifecycle is None:
            raise ValueError("Cleanup requires actual Qe event lifecycle")

    def _phase(self, effect, invocation, runner, channel):
        self.event_lifecycle.phase(
            effect,
            invocation,
            uid=runner.uid,
            value=runner.value,
            channel=channel,
            runner_modifier=runner,
            _event_ids=tuple(sorted({0, *(effect["target_masks"][6] or ())})),
        )

    def prepare(self, effect, values, invocation):
        from .combat_trigger_value_modifier import NativeRunnerAmount

        self._validate(effect, values)
        if invocation.native_running_uid is not None:
            raise ValueError("Unaudited restored eXW runner")
        runner = NativeRunnerAmount(self.allocate_uid(), self.family, rng=self.rng)
        invocation = replace(invocation, native_running_uid=runner.uid)
        self._phase(effect, invocation, runner, 1)
        self.prepared[runner.uid] = runner
        return invocation

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)
        self.activated.discard(invocation.native_running_uid)

    def prepare_activation(self, effect, values, invocation, *, clone_uid):
        from .combat_trigger_value_modifier import NativeRunnerAmount

        self._validate(effect, values)
        if invocation.native_running_uid is not None or clone_uid in self.prepared:
            raise ValueError("Invalid actual eXW clone identity")
        runner = NativeRunnerAmount(clone_uid, self.family, rng=self.rng)
        self.prepared[clone_uid] = runner
        self.activated.add(clone_uid)
        return replace(invocation, native_running_uid=clone_uid)

    def _authority(self, target_id):
        return RetainedCleanupAuthority(
            self.retention, target_id, identity_hash=self.identity_hash
        )

    def __call__(self, effect, values, invocation):
        from .combat_native_timing_context import native_definition_timing
        from .combat_runner_callbacks import notify_runner_value

        self._validate(effect, values)
        native_definition_timing(effect, invocation.level)
        runner = self.prepared.pop(invocation.native_running_uid, None)
        activated = invocation.native_running_uid in self.activated
        self.activated.discard(invocation.native_running_uid)
        if runner is None:
            raise ValueError("Missing actual prepared cleanup runner")
        if not activated:
            self._phase(effect, invocation, runner, 2)
        self._authority(invocation.target_id).execute()
        runner.finish_application()
        self._phase(effect, invocation, runner, 3)
        self._phase(effect, invocation, runner, 4)
        notify_runner_value(invocation, runner.value)
        return True
