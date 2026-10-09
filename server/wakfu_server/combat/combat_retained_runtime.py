"""Persisted central fresh-cast retention registry, including native groups."""
from wakfu_server import native_catalog as protocol_catalog
from .combat_state_managers import state_manager, state_managers
from dataclasses import asdict
from contextlib import contextmanager
from .combat_native_container import (
    state_container_scope,
    resolve_state_container,
    capture_owned_state_container,
    owned_container_users,
)
from functools import lru_cache
import json
import struct
from wakfu_server.paths import DATA_ROOT
from .combat_parameters import _float32
from .combat_running_context import running_context_payload
from .combat_effects import _integer, _varint
from .combat_native_timing_context import native_definition_timing
from .combat_retained_effects import (
    RetainedEffect,
    NativeRetainedEffectView,
    NativeRetainedRemoval,
    register_owned_removals,
)
from .combat_effect_removal import running_effect_removal, _identity_fields
from .combat_stat_effects import owned_effect_delivery
from .combat_pending_state import pending_state_registration, pending_state_uids
from .combat_subscription_runners import (
    SUBSCRIPTION_FAMILIES,
    GROUP_SUBSCRIPTION_FAMILIES,
    DEFERRED_RUNNERS,
    deferred_payload,
)


def _set_current_families():
    from .combat_set_current_characteristic import FAMILIES

    return FAMILIES


@lru_cache(maxsize=1)
def native_retained_metadata():
    return protocol_catalog.load(DATA_ROOT / "native-retained-effect-metadata.json")


def _blob(field, data):
    return _varint(field << 3 | 2) + _varint(len(data)) + data


def native_retained_condition_effects(fight, actor_id):
    """Read the complete tracked Qf population without storing runtime objects on Fight."""
    if (
        fight.native_retained_tracking is not True
        or state_manager(fight, actor_id) is None
    ):
        raise ValueError("Unverified native retained condition population")
    live = (
        set(fight.owned_stat_effects)
        | set(fight.state_wire_payloads)
        | set(fight.native_owned_group_effects)
        | set(getattr(fight, "native_owned_area_effects", {}))
    )
    live.update(e.uid for a in state_managers(fight) for e in a.state_ledger.entries)
    live.difference_update(pending_state_uids(fight))
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
    context_payload=None,
    initial_value=0,
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
        for v in ((caster_id,) if target_id is None else (caster_id, target_id))
    ):
        raise ValueError("Invalid retained group actors")
    if not isinstance(timing_payload, bytes):
        raise ValueError("Missing native group TimeDatas")
    # Qe.a(iP) only sets fields9/10 when its actual PL/bfq is non-null.
    # Lifecycle event copies can legitimately have no container. Preserve
    # that absence; neither zero IDs nor a guessed parent encode the same fact.
    if container_type is None and container_id is None:
        container_payload = b""
    elif (
        type(container_type) is not int
        or type(container_id) is not int
        or not -(1 << 31) <= container_type < (1 << 31)
        or not -(1 << 63) <= container_id < (1 << 63)
    ):
        raise ValueError("Missing paired native group container kind/identity")
    else:
        container_payload = _integer(9, container_type) + _integer(10, container_id)
    position = b"".join(_integer(k, v) for k, v in enumerate(cell, 1))
    return (
        b"".join(
            _integer(k, v)
            for k, v in (
                (1, uid),
                (2, base_uid),
                (3, generic_effect),
                (4, initial_value),
            )
        )
        + _blob(5, position)
        + _integer(6, caster_id)
        + (b"" if target_id is None else _integer(7, target_id))
        + container_payload
        + _blob(11, timing_payload)
        + running_context_payload(context_payload=context_payload)
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
            | set(getattr(self.fight, "native_owned_area_effects", {}))
            | {
                e.uid
                for a in state_managers(self.fight)
                for e in a.state_ledger.entries
            }
        ) - pending_state_uids(self.fight)

    def synchronize(self):
        live = self._live()
        for uid in tuple(self.fight.native_retained_records):
            if uid not in live:
                del self.fight.native_retained_records[uid]
        self.fight.native_retained_order[:] = [
            uid for uid in self.fight.native_retained_order if uid in live
        ]
        facts = getattr(self.fight, "native_owned_state_containers", {})
        for uid in tuple(facts):
            if not owned_container_users(self.fight, uid):
                del facts[uid]
        from .combat_state_managers import prune_retired_state_managers

        prune_retired_state_managers(self.fight)

    def container(self, invocation):
        if invocation is not None and invocation.state_uid is not None:
            state = resolve_state_container(self.fight, invocation.state_uid)
            return (
                dict(
                    container_present=True,
                    container_type=1,
                    container_id=(state.reference << 16) | state.level,
                    container_kind="state",
                    container_is_spell=False,
                    spell_protected=None,
                ),
                (state.reference << 16) | state.level,
            )
        direct = None if invocation is None else invocation.native_retained_container
        if direct is None:
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
                    container_id=identity,
                    container_kind=direct.get("native_kind"),
                    container_is_spell=direct["is_spell"],
                    spell_protected=direct.get("protected"),
                ),
                identity,
            )
        spell = self.plan.get("spell_id")
        level = self.plan.get("evaluation_level")
        row = self.metadata.get("spells", {}).get(str(spell))
        if row is None:
            # Same installed fyF.elO used by the class inventory; granted aliases
            # are native spells too, with the same fyG/QF container semantics.
            from .combat_native_spell_casting import catalog as casting_catalog

            row = casting_catalog().get(str(spell))
        if row is None or type(level) is not int or not 0 <= level <= 32767:
            raise ValueError("Missing native spell container metadata")
        protected = row["protected"]
        if type(protected) is not bool:
            raise ValueError("Missing native fyF.elO")
        identity = (spell << 16) + (level & 255)
        return (
            dict(
                container_present=True,
                container_type=25 if protected else 11,
                container_id=identity,
                container_is_spell=True,
                spell_protected=protected,
            ),
            identity,
        )

    @contextmanager
    def applied_state_scope(self, entry):
        """Bind the fyW just constructed by StateHandler for its full iterator.

        Includes non-retained instant carriers; this trusted entry comes from
        Fight.apply_state, never an event's unresolved external UID.
        """
        from .combat_state_ledger import RunningState

        if not isinstance(entry, RunningState):
            raise ValueError("Missing authoritative applied state container")
        parents = getattr(self, "_carrier_parents", ())
        parent = parents[-1] if parents else None
        if entry.retained and parent is None:
            raise ValueError("Missing native applying carrier parent authority")
        if entry.retained:
            self.synchronize()  # Replacement removed old Qf carriers before iteration.
        self._container_scopes.append({entry.uid: entry})
        try:
            with pending_state_registration(self.fight, entry):
                with state_container_scope(self.fight, self._container_scopes[-1]):
                    yield
            # Qe.d registers after eZk.c finishes its child iterator. Nested
            # outer carriers remain pending, and are not inserted here.
            if entry.retained:
                self.synchronize()
            if (
                entry.retained
                and entry.uid in self.fight.state_wire_payloads
                and entry.uid not in self.fight.native_retained_records
            ):
                self._record_carrier(entry.uid, parent)
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
            from .combat_running_container import running_container_scope

            with state_container_scope(self.fight, self._container_scopes[-1]):
                container, identity = self.container(invocation)
                with running_container_scope(container, identity):
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
        if entry.owner_uid is not None:
            capture_owned_state_container(self.fight, entry.owner_uid)
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
                **container,
            )
        )

    def register_applied_stat(self, effect, invocation, uid):
        """Qe.a/PT inserts this exact applied effect before L3/L4 replay."""
        row = self.fight.owned_stat_effects.get(uid)
        if (
            row is None
            or row.get("uid") != uid
            or row.get("effect_class") != effect["effect_class"]
            or row.get("target_id") != invocation.target_id
        ):
            raise ValueError(
                "Missing exact owned stat application for native registration"
            )
        if uid in self.fight.native_retained_records:
            raise ValueError("Applied native stat effect already registered")
        self._record_stat(uid, effect, invocation)

    def register_applied_target_aura(self, effect, invocation, uid):
        """Register the actual eYJ Qf owner before Qs creation callbacks."""
        row = getattr(self.fight, "native_owned_area_effects", {}).get(uid)
        definition = self.definition(effect, invocation)
        if (
            effect.get("effect_class") != 338
            or row is None
            or row.get("uid") != uid
            or row.get("effect_class") != 338
            or row.get("target_id") != invocation.target_id
            or type(definition.get("owner_on_caster")) is not bool
            or invocation.target_id is None
        ):
            raise ValueError("Missing exact owned native eYJ application")
        if uid in self.fight.native_retained_records:
            raise ValueError("Applied native target aura already registered")
        container, _ = self.container(invocation)
        row["native_manager_id"] = (
            invocation.caster_id
            if definition["owner_on_caster"]
            else invocation.target_id
        )
        row["native_manager_source"] = "eYJ.PK.owner_on_caster"
        self.record(
            RetainedEffect(
                uid,
                row["target_id"],
                338,
                invocation.reference,
                owner_uid=row.get("state_uid"),
                manager_id=row["native_manager_id"],
                definition_type=definition["definition_type"],
                definition_dispellable=definition["definition_dispellable"],
                **container,
            )
        )

    def _record_carrier(self, uid, invocation):
        state = next(
            e
            for a in state_managers(self.fight)
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
                **container,
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
                if (
                    uid not in self.fight.native_retained_records
                    and uid not in pending_state_uids(self.fight)
                ):
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
            first_packet = len(self.packets)
            definition = self.definition(effect, invocation)
            if not state:
                native = native_definition_timing(effect, invocation.level)
                if native["retained"] and not (
                    effect["effect_class"]
                    in (
                        20,
                        28,
                        31,
                        41,
                        47,
                        48,
                        55,
                        56,
                        57,
                        191,
                        192,
                        196,
                        808,
                        303,
                        308,
                        321,
                        325,
                        332,
                        314,
                        315,
                        316,
                        338,
                        339,
                        402,
                        421,
                        426,
                        430,
                        446,
                        320,
                        309,
                        447,
                        451,
                        649,
                        667,
                        666,
                        668,
                        802,
                        877,
                        923,  # eXm always cancels itself; synthetic eWf30 is non-retained.
                        986,
                        1001,
                        1000,
                        933,
                        1008,
                        1013,
                        1038,
                        1030,
                        1065,
                        1066,
                        1099,
                        1201,
                        1202,
                    )
                    or effect["effect_class"] in _set_current_families()
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
            # Register only finished carriers; native Qe.d inserts a carrier
            # after its eZk child iterator, not during that iterator.
            self.synchronize()
            for uid in self.fight.state_wire_payloads:
                if (
                    uid not in self.fight.native_retained_records
                    and uid not in pending_state_uids(self.fight)
                ):
                    self._record_carrier(uid, invocation)
            for uid in self.fight.owned_stat_effects:
                if uid not in self.fight.native_retained_records:
                    if uid not in before:
                        self._record_stat(uid, effect, invocation)
                    else:
                        raise ValueError(
                            "Previously unregistered retained native stat effect"
                        )
            for uid, row in getattr(
                self.fight, "native_owned_area_effects", {}
            ).items():
                if uid not in self.fight.native_retained_records:
                    if uid in before:
                        raise ValueError("Previously unregistered retained area effect")
                    container, _ = self.container(invocation)
                    self.record(
                        RetainedEffect(
                            uid,
                            row["target_id"],
                            row["effect_class"],
                            invocation.reference,
                            owner_uid=row.get("state_uid"),
                            manager_id=row["caster_id"],
                            definition_type=definition["definition_type"],
                            definition_dispellable=definition["definition_dispellable"],
                            **container,
                        )
                    )
            self.normalize_owned_delivery(effect, invocation, first_packet)
            return result

        def execute(effect, values, invocation):
            with self.container_scope(invocation):
                return execute_scoped(effect, values, invocation)

        execute.native_runner_value_verified = getattr(
            handler, "native_runner_value_verified", False
        )
        eligibility = getattr(handler, "native_eligibility", None)
        if callable(eligibility):
            execute.native_eligibility = eligibility
        prepare = getattr(handler, "prepare", None)
        if callable(prepare):
            # Runtime preparation can address the registered wrapper after
            # handler installation. Preserve the original runner owner.
            execute.prepare = prepare
        prepare_activation = getattr(handler, "prepare_activation", None)
        if callable(prepare_activation):
            execute.prepare_activation = prepare_activation
        cancel = getattr(handler, "cancel_prepared", None)
        if callable(cancel):
            # Dispatcher rejection happens before execute() is called. Keep
            # cleanup attached to the registered wrapper, not only its owner.
            execute.cancel_prepared = cancel
        return execute

    def is_subscription(self, effect, invocation):
        if effect["effect_class"] not in SUBSCRIPTION_FAMILIES:
            return False
        row = self.definition(effect, invocation)
        expected = any(effect["target_masks"][index] for index in (0, 1, 3, 4, 5))
        if row["subscription"] is not expected:
            raise ValueError("Native subscription metadata differs from catalog masks")
        return expected

    def container_level(self, invocation):
        """The actual PL/eVo level; never infer it from child evaluation level."""
        if invocation.state_uid is not None:
            return True, resolve_state_container(self.fight, invocation.state_uid).level
        direct = None if invocation is None else invocation.native_retained_container
        if direct is None:
            direct = self.plan.get("native_retained_container")
        if direct is not None:
            present = direct.get("present")
            if type(present) is not bool:
                raise ValueError("Explicit native container presence required")
            return present, direct.get("level") if present else None
        # This is the explicit fyF instance level constructed by the spell plan.
        self.container(invocation)  # Validate identity and native spell metadata.
        return True, self.plan.get("evaluation_level")

    def replay_container(self, row, entry, invocation):
        """Validate and return the PL snapshot required by an event clone.

        A checkpoint predating the snapshot is reconstructed only from its
        serialized native PL, original parent-root invocation and matching
        native spell tree. Otherwise replay fails closed; it never borrows a
        level from its generic dispatcher or guesses from a child/container ID.
        """
        if invocation.state_uid is not None:
            if row.get("native_retained_container") is not None:
                raise ValueError("State-owned listener has an unexpected PL snapshot")
            return None
        context = row.get("native_retained_container")
        if context is None:
            if entry.container_present is False:
                return {"present": False}
            if entry.container_present is True:
                context = self._legacy_spell_container(row, entry, invocation)
            if context is not None:
                return self._validate_replay_container(
                    context, entry, allow_missing_id=True
                )
            raise ValueError("Missing retained PL snapshot for event replay")
        return self._validate_replay_container(context, entry)

    @staticmethod
    def _validate_replay_container(context, entry, *, allow_missing_id=False):
        if not isinstance(context, dict) or type(context.get("present")) is not bool:
            raise ValueError("Malformed retained PL snapshot")
        if context["present"] is not entry.container_present:
            raise ValueError("Retained PL snapshot differs from registered container")
        if not context["present"]:
            return {"present": False}
        if (
            type(context.get("type")) is not int
            or not -(1 << 31) <= context["type"] < (1 << 31)
            or type(context.get("id")) is not int
            or not -(1 << 63) <= context["id"] < (1 << 63)
            or type(context.get("is_spell")) is not bool
            or type(entry.container_is_spell) is not bool
            or (entry.container_is_spell and type(context.get("protected")) is not bool)
        ):
            raise ValueError("Malformed retained PL identity types")
        for key, value in (
            ("type", entry.container_type),
            ("id", entry.container_id),
            ("is_spell", entry.container_is_spell),
            ("protected", entry.spell_protected),
        ):
            if key == "id" and value is None and allow_missing_id:
                continue
            if context.get(key) != value:
                raise ValueError("Retained PL snapshot identity mismatch")
        if entry.container_kind is not None and context.get("native_kind") not in (
            None,
            entry.container_kind,
        ):
            raise ValueError("Retained PL snapshot kind mismatch")
        if entry.container_is_spell:
            spell, level = context.get("spell_id"), context.get("level")
            identity = context.get("id")
            if (
                type(spell) is not int
                or spell <= 0
                or type(level) is not int
                or not 0 <= level <= 32767
                or type(identity) is not int
                or identity != (spell << 16) | (level & 0xFF)
                or entry.container_id not in (None, identity)
            ):
                raise ValueError("Invalid retained spell PL level authority")
        elif "level" in context and (
            type(context["level"]) is not int or not -32768 <= context["level"] <= 32767
        ):
            raise ValueError("Invalid retained direct PL level")
        return dict(context)

    def _legacy_spell_container(self, row, entry, invocation):
        """Migrate a trusted older group checkpoint from its native PL bytes.

        The spell identity comes from Qe's serialized container fields. The
        level comes from the stored *parent root invocation*, and is accepted
        only when its exact identity formula and native spell-effect tree agree.
        A child level or the container ID's low byte is never used as a source.
        """
        if entry.container_is_spell is not True or entry.container_type not in (11, 25):
            return None
        try:
            payload = bytes.fromhex(row["payload"])
            fields = _identity_fields(payload, integer_fields=(9, 10))
        except (KeyError, TypeError, ValueError):
            return None
        if 9 not in fields or 10 not in fields:
            return None
        container_type, identity = fields[9], fields[10]
        if (
            container_type != entry.container_type
            or entry.container_id not in (None, identity)
            or type(identity) is not int
            or identity <= 0
        ):
            return None
        spell = identity >> 16
        level = invocation.level
        if (
            type(spell) is not int
            or spell <= 0
            or type(level) is not int
            or not 1 <= level <= 200
            or identity != (spell << 16) | (level & 0xFF)
        ):
            return None
        owner = self.fight.actors.get(invocation.caster_id)
        if owner is None or owner.effective_level < level:
            return None
        from wakfu_server.spell_audit import catalog as spell_catalog
        from .combat_native_spell_casting import catalog as casting_catalog

        tree = spell_catalog()
        spell_tree = tree["spells"].get(str(spell))
        casting = casting_catalog().get(str(spell))
        if spell_tree is None or casting is None or level > len(spell_tree["levels"]):
            return None
        protected = casting.get("protected")
        if type(protected) is not bool or entry.container_type != (
            25 if protected else 11
        ):
            return None
        roots = spell_tree["levels"][level - 1][2]
        pending = list(roots)
        visited = set()
        while pending:
            reference = pending.pop()
            if reference == invocation.reference:
                return {
                    "present": True,
                    "type": container_type,
                    "id": identity,
                    "is_spell": True,
                    "protected": protected,
                    "spell_id": spell,
                    "level": level,
                }
            if reference in visited:
                continue
            visited.add(reference)
            effect = tree["effects"].get(str(reference))
            if effect is not None:
                pending.extend(effect.get("children", ()))
        return None

    def transmit_child_override(self, effect, invocation, override):
        from .combat_group_level_transmission import transmitted_child_override

        flags = effect["native_effect_flags"]
        if 16 not in flags or override != -1:
            return override
        parent = None
        if invocation.native_context_hex is not None:
            fields = _identity_fields(
                bytes.fromhex(invocation.native_context_hex), integer_fields=(4,)
            )
            if 4 not in fields:
                raise ValueError("Missing native parent eVt level override")
            raw = fields[4]
            parent = raw & 0xFFFFFFFF
            if parent >= (1 << 31):
                parent -= 1 << 32
        # fRR returns immediately for a non-sentinel parent override.
        present, level = (
            (None, None)
            if parent not in (None, -1)
            else self.container_level(invocation)
        )
        return transmitted_child_override(
            flags=flags,
            child_override=override,
            parent_override=parent,
            container_present=present,
            container_level=level,
        )

    def child_level_context(
        self,
        effect,
        values,
        invocation,
        *,
        default_level,
        event_activation=False,
        native_override=None,
    ):
        """One native SP for both child evaluation and serialized eVt.

        Shared by eYg and eZM; family-specific overrides are calculated first.
        """
        context = self.child_context(
            effect,
            values,
            invocation,
            event_activation=event_activation,
            native_override=native_override,
        )
        raw = _identity_fields(context, integer_fields=(4,))[4]
        override = raw & 0xFFFFFFFF
        if override >= (1 << 31):
            override -= 1 << 32
        # A new PS resets SP unless the group explicitly writes/transmits it.
        # Parent evaluation/default_level may itself be a previous SP override.
        # With the sentinel the child reads its actual PL instead of inheriting
        # that previous runner's evaluation level.
        from .combat_group_level_transmission import child_evaluation_level

        present, level = (
            self.container_level(invocation) if override == -1 else (None, None)
        )
        return (
            child_evaluation_level(
                override=override, container_present=present, container_level=level
            ),
            context,
        )

    def child_context(
        self,
        effect,
        values,
        invocation,
        *,
        event_activation=False,
        native_override=None,
    ):
        from .combat_state_level_group import runtime_child_level
        from .combat_level_group import level_group_override

        override = -1
        if effect["effect_class"] in (1076, 1080):
            if type(native_override) is not int:
                raise ValueError("Native eYx child context requires calculated value")
            override = native_override
        elif effect["effect_class"] == 844:
            override = runtime_child_level(
                effect,
                values,
                invocation,
                self.fight,
                return_native_override=True,
            )
        elif effect["effect_class"] == 999:
            parameters = values["parameters"]
            caster, target = invocation.caster_id, invocation.target_id
            rebind = ((parameters[5] + 128) % 256) - 128
            if rebind == 1 and target is not None:
                caster = target
            elif rebind == 2 and target is not None:
                caster, target = target, caster
            identity = caster if parameters[6] == 1 else target
            from .combat_group_pv import resolve_group_level_pv

            actor = resolve_group_level_pv(self.fight, identity)
            if actor is not None and not getattr(actor, "native_is_area", False):
                override = level_group_override(
                    effect,
                    invocation.level,
                    actor.effective_level,
                    return_native_override=True,
                )
            # eYm.d returns the parent-produced context unchanged for null
            # or non-eGj PV. Preserve SP=-1 and the common flag16 transmission.

        elif effect["effect_class"] == 1047:
            from .combat_hp_level_group import runtime_group_level

            from .combat_group_pv import scoped_group_actors, group_pa

            override = runtime_group_level(
                effect,
                values,
                invocation,
                scoped_group_actors(self.fight),
                return_native_override=True,
                resolve_pa=lambda identity, stat: group_pa(self.fight, identity, stat),
            )
        elif effect["effect_class"] == 913:
            from .combat_characteristic_level_group import runtime_group_level

            from .combat_group_pv import scoped_group_actors, group_pa

            override = runtime_group_level(
                effect,
                values,
                invocation,
                scoped_group_actors(self.fight),
                return_native_override=True,
                resolve_pa=lambda identity, stat: group_pa(self.fight, identity, stat),
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
        if effect["effect_class"] not in (1076, 1080):
            override = self.transmit_child_override(effect, invocation, override)
        # eYg.d(nonrelative) native eVt: flags false, SP default-1,
        # mb(false), count0, origin kindiu0. fLP is not serialized here.
        context = b"".join(
            _integer(k, v)
            for k, v in (
                (
                    1,
                    int(
                        event_activation
                        and effect["effect_class"] not in (345, 349, 1076, 1080)
                    ),
                ),
                (2, 0),
                (4, override),
                (5, int(effect["effect_class"] in (1076, 1080))),
                (6, 0),
                (7, 0),
                (8, 0),
                (9, 0),
            )
        )
        if effect["effect_class"] == 1103:
            from .combat_trigger_value_group import trigger_value_context

            context = trigger_value_context(effect, invocation, context)
        return context

    def begin_group(self, effect, values, invocation, *, initial_value=0):
        definition = self.definition(effect, invocation)
        for uid in self.fight.state_wire_payloads:
            if (
                uid not in self.fight.native_retained_records
                and uid not in pending_state_uids(self.fight)
            ):
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
        if (
            invocation.target_id is None
            and effect["effect_class"] not in GROUP_SUBSCRIPTION_FAMILIES
        ):
            raise ValueError("Unaudited target-less retained native runner")
        manager_id = (
            invocation.caster_id
            if invocation.target_id is None or definition["owner_on_caster"]
            else invocation.target_id
        )
        if state_manager(self.fight, manager_id) is None:
            from .combat_state_managers import registered_area_pv

            manager = registered_area_pv(self.fight, manager_id)
            if (
                manager is None
                or manager.native_running_effect_manager is not False
                or definition.get("subscription") is not True
            ):
                raise ValueError("Missing actual retained group manager")
            # Qe.d(Collection), 284..289/486..642/759..795: a subscribed
            # clone skips n(); null bax() enters release rather than Qf.p/PR.
            return {
                "native_null_qf": True,
                "uid": self.fight.allocate_effect_uid(),
            }
        container, identity = self.container(invocation)
        replay_container = None
        if invocation.state_uid is None:
            # Event replay uses a fight-scoped dispatcher, whose plan has no
            # relation to the spell that registered this listener. Preserve
            # the exact PL authority at registration so the replayed clone can
            # construct children with the same parent container level.
            direct = invocation.native_retained_container
            if direct is None:
                direct = self.plan.get("native_retained_container")
            if direct is not None:
                replay_container = dict(direct)
            elif container["container_present"]:
                spell = self.plan.get("spell_id")
                level = self.plan.get("evaluation_level")
                if (
                    type(spell) is not int
                    or spell <= 0
                    or type(level) is not int
                    or not 0 <= level <= 32767
                    or container["container_is_spell"] is not True
                ):
                    raise ValueError(
                        "Missing authoritative retained spell container level"
                    )
                replay_container = {
                    "present": True,
                    "type": container["container_type"],
                    "id": identity,
                    "is_spell": True,
                    "protected": container["spell_protected"],
                    "spell_id": spell,
                    "level": level,
                }
            else:
                replay_container = {"present": False}
        context = self.timing.stat(self.fight, self.plan, effect, invocation)
        uid = (
            invocation.native_running_uid
            if effect["effect_class"] == 1080
            and invocation.native_running_uid is not None
            else self.fight.allocate_effect_uid()
        )
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
            initial_value=initial_value,
            context_payload=None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        if effect["effect_class"] in DEFERRED_RUNNERS:
            payload = deferred_payload(
                family=effect["effect_class"],
                uid=uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=invocation.target_id,
                cell=invocation.cell,
                timing_payload=context.timing_payload,
                container_type=container["container_type"],
                container_id=identity,
                context_payload=None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        record = RetainedEffect(
            uid,
            invocation.target_id,
            effect["effect_class"],
            invocation.reference,
            owner_uid=invocation.state_uid,
            manager_id=manager_id,
            definition_type=definition["definition_type"],
            definition_dispellable=definition["definition_dispellable"],
            **container,
        )
        return dict(
            _delivery_effect=effect,
            _delivery_invocation=invocation,
            execution_count=definition.get("event_execution_count"),
            uid=uid,
            target_id=invocation.target_id,
            effect_class=effect["effect_class"],
            state_uid=invocation.state_uid,
            native_retained_container=replay_container,
            payload=payload.hex(),
            timer=None if context.timer is None else dict(vars(context.timer)),
            invocation=dict(
                vars(invocation),
                native_value_scope=None,
                native_cast_boundary_context=None,
            ),
            native_subscription_masks=effect["target_masks"],
            native_selector=effect["native_target_selector"],
            native_effect_flags=list(effect["native_effect_flags"]),
            children=list(effect["children"]),
            variant=effect["variant"],
            record=record,
        )

    def normalize_owned_delivery(self, effect, invocation, first_packet):
        """Match already evaluated owned UIDs to the original aTR/aVo guards."""
        from .combat_effect_removal import _identity_fields
        from .combat_observation_delivery import (
            choose_delivery,
            evaluated_application_from_observation,
        )
        from .combat_effect_groups import native_group_route
        from .combat_delivery_owners import native_owner_flags

        definition = self.definition(effect, invocation)
        for index in range(first_packet, len(self.packets)):
            opcode, body = self.packets[index]
            if opcode != 13497 or not isinstance(body, bytes) or len(body) < 18:
                continue
            family = struct.unpack_from(">i", body, 12)[0]
            length = struct.unpack_from(">h", body, 16)[0]
            if (
                family != effect["effect_class"]
                or length < 0
                or len(body) != 18 + length
            ):
                continue
            fields = _identity_fields(body[18:], integer_fields=(1, 3))
            if fields.get(3) != invocation.reference:
                continue  # A nested child has its own PK and wrapper.
            record = self.fight.native_retained_records.get(fields.get(1))
            if record is None:
                continue  # Ty=false runners must not be forced into Qf.
            manager = record["manager_id"]
            if state_manager(self.fight, manager) is None:
                raise ValueError(
                    "Missing actual retained delivery manager "
                    f"(uid={fields.get(1)}, manager={manager!r}, "
                    f"reference={invocation.reference})"
                )
            caster, target = invocation.caster_id, invocation.target_id
            if definition["owner_on_caster"] or caster == target:
                observation_owner = full_owner = caster
            else:
                actor_mode, cell_mode = native_owner_flags(effect)
                observation_owner = caster if cell_mode else target
                full_owner = caster if cell_mode and not actor_mode else target
            native = native_definition_timing(effect, invocation.level)
            if native["retained"] is not True:
                # Arithmetic ownership is not native Ty; preserve observation.
                continue
            # Current verified timing rejects scheduled positive-delay execution;
            # eo below retains the native negative/nonzero bbW distinction.
            delayed = False
            if record["container_present"] and effect["native_execution_mode"] == 2:
                from .combat_delivery_owners import native_delay_nonzero

                delayed = native_delay_nonzero(effect, invocation.level)
            chosen = choose_delivery(
                native_ty=True,
                subscribed=definition["subscription"],
                native_delayed=delayed,
                manager_id=manager,
                observation_owner=observation_owner,
                full_owner=full_owner,
            )
            if chosen == 12613:
                self.packets[index] = (
                    12613,
                    evaluated_application_from_observation(body),
                )

    def finish_group(self, pending, *, notify=True):
        if type(notify) is not bool:
            raise ValueError("Explicit native group PR notification decision required")
        if pending is None:
            return
        if pending.get("native_null_qf") is True:
            return
        row = dict(pending)
        record = row.pop("record")
        effect = row.pop("_delivery_effect")
        invocation = row.pop("_delivery_invocation")
        first_packet = len(self.packets)
        uid = row["uid"]
        self.fight.native_owned_group_effects[uid] = row
        self.record(record)  # Native Qf.p happens AFTER the group's child calls.
        if not notify:
            return  # eYC.c fRS: Qf ownership survives, its own PR does not fire.
        self.packets.append(
            owned_effect_delivery(
                self.fight.id,
                self.action_id,
                effect_class=row["effect_class"],
                target_id=record.manager_id
                if row["target_id"] is None
                else row["target_id"],
                uid=uid,
                running_effect_payload=bytes.fromhex(row["payload"]),
            )
        )

        self.normalize_owned_delivery(effect, invocation, first_packet)

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
            area_events=getattr(self, "area_events", None),
        )
        from .combat_subscription_runners import SUBSCRIPTION_FAMILIES

        for family in SUBSCRIPTION_FAMILIES:
            previous = removal.families.pop(family, None)

            def validate(entry):
                row = self.fight.native_owned_group_effects[entry.uid]
                running_effect_removal(
                    self.fight.id,
                    self.action_id,
                    effect_class=row["effect_class"],
                    target_id=entry.manager_id
                    if row["target_id"] is None
                    else row["target_id"],
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
        target_id=entry.manager_id if row["target_id"] is None else row["target_id"],
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
