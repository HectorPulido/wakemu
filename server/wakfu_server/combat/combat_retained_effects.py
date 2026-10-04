"""Explicit complete native Qf view and extensible removal on one preview.

Existing stat/carrier ownership proves those entries only. The caller must
supply native iteration order and attest the full retained-effect population;
this module never infers completeness from the currently implemented families.
"""
from dataclasses import dataclass
from .combat_effect_removal import _identity_fields, running_effect_removal


@dataclass(frozen=True)
class RetainedEffect:
    uid: int
    target_id: int
    effect_class: int
    generic_effect: int
    owner_uid: int | None = None
    manager_id: int | None = None
    definition_type: int | None = None
    definition_dispellable: bool | None = None
    container_present: bool | None = None
    container_type: int | None = None
    container_is_spell: bool | None = None
    spell_protected: bool | None = None
    state_unremovable: bool | None = None
    state_dispellable: bool | None = None


def default_dispel_eligible(entry):
    if entry.definition_type is None:
        raise ValueError("Missing native PK.aZD definition type")
    if entry.definition_type == 2:
        if type(entry.definition_dispellable) is not bool:
            raise ValueError("Missing native eVv.cxq eligibility")
        if not entry.definition_dispellable:
            return False
    if entry.effect_class == 310:
        if (
            type(entry.state_unremovable) is not bool
            or type(entry.state_dispellable) is not bool
        ):
            raise ValueError("Missing native fyW.guN/cxq state eligibility")
        if entry.state_unremovable or not entry.state_dispellable:
            return False
    if type(entry.container_present) is not bool:
        raise ValueError("Missing native container presence")
    if not entry.container_present:
        return False
    if entry.container_type is None:
        raise ValueError("Missing native PL.aZY container type")
    if entry.container_type in (1, 3):
        return entry.effect_class != 421
    if entry.container_type != 11:
        return False
    if type(entry.container_is_spell) is not bool:
        raise ValueError("Missing native fyG container kind")
    if entry.container_is_spell:
        if type(entry.spell_protected) is not bool:
            raise ValueError("Missing native fyF.elO spell protection")
        if entry.spell_protected:
            return False
    return entry.effect_class != 421


class NativeRetainedEffectView:
    def __init__(self, fight, entries, *, population_verified_complete):
        if population_verified_complete is not True:
            raise ValueError(
                "Complete authoritative native running-effect population required"
            )
        self.fight = fight
        self.entries = tuple(entries)
        self.by_uid = {}
        for entry in self.entries:
            if (
                not isinstance(entry, RetainedEffect)
                or type(entry.uid) is not int
                or not 0 < entry.uid < (1 << 63)
            ):
                raise ValueError("Invalid native retained effect record")
            if entry.uid in self.by_uid:
                raise ValueError("Duplicate native retained effect UID")
            if (
                entry.target_id not in fight.actors
                or type(entry.effect_class) is not int
                or entry.effect_class <= 0
            ):
                raise ValueError("Invalid native retained effect owner/family")
            if type(entry.generic_effect) is not int or not (
                entry.generic_effect == -1 or 0 < entry.generic_effect < (1 << 31)
            ):
                raise ValueError("Invalid native retained generic definition ID")
            self.by_uid[entry.uid] = entry
        known = {}
        for uid, row in fight.owned_stat_effects.items():
            fields = _identity_fields(bytes.fromhex(row["payload"]))
            generic = fields.get(3)
            known[uid] = (
                row["target_id"],
                row["effect_class"],
                generic,
                row.get("state_uid"),
            )
        for actor in fight.actors.values():
            for state in actor.state_ledger.entries:
                payload = fight.state_wire_payloads.get(state.uid)
                if payload is None:
                    raise ValueError("Missing native carrier wire ownership")
                fields = _identity_fields(bytes.fromhex(payload))
                generic = fields.get(3)
                if generic == (1 << 64) - 1:
                    generic = -1
                known[state.uid] = (actor.id, 310, generic, None)
        for uid, row in getattr(fight, "native_owned_group_effects", {}).items():
            fields = _identity_fields(bytes.fromhex(row["payload"]))
            known[uid] = (
                row["target_id"],
                row["effect_class"],
                fields.get(3),
                row.get("state_uid"),
            )
        if set(fight.state_wire_payloads) - set(known):
            raise ValueError("Orphan native state payload")
        for uid, identity in known.items():
            entry = self.by_uid.get(uid)
            if entry is None:
                raise ValueError(
                    "Complete native view omitted an owned retained effect"
                )
            if (
                entry.target_id,
                entry.effect_class,
                entry.generic_effect,
                entry.owner_uid,
            ) != identity:
                raise ValueError(
                    "Native retained metadata disagrees with owned identity"
                )
        for entry in self.entries:
            if entry.owner_uid is not None and entry.owner_uid not in self.by_uid:
                raise ValueError(
                    "Native retained child owner missing from complete view"
                )
        self.known = known


class NativeRetainedRemoval:
    def __init__(self, view):
        self.view = view
        self.fight = view.fight
        self.families = {}
        self.removed = set()

    def register(self, effect_class, *, exists, remove, validate):
        if effect_class in self.families:
            raise ValueError("Native removal family already registered")
        if not all(callable(fn) for fn in (exists, remove, validate)):
            raise ValueError("Complete native removal callbacks required")
        for fn in (exists, remove, validate):
            owner = getattr(fn, "__self__", None)
            if (
                owner is not None
                and getattr(owner, "fight", self.fight) is not self.fight
            ):
                raise ValueError("Removal callback belongs to another preview")
        self.families[effect_class] = (exists, remove, validate)

    def plan(self, uids):
        result = []
        seen = set()
        active = set()

        def visit(uid):
            if uid in self.removed or uid in seen:
                return
            if uid in active:
                raise ValueError("Recursive native retained ownership")
            entry = self.view.by_uid.get(uid)
            if entry is None:
                raise ValueError("Missing owned native removal identity")
            active.add(uid)
            for child in self.view.entries:
                if child.owner_uid == uid:
                    visit(child.uid)
            callbacks = self.families.get(entry.effect_class)
            if callbacks is None:
                raise ValueError("Unregistered native retained removal family")
            exists, remove, validate = callbacks
            if exists(uid) is not True:
                raise ValueError("Native retained ownership is stale")
            validate(entry)
            active.remove(uid)
            seen.add(uid)
            result.append(entry)

        for uid in uids:
            visit(uid)
        return tuple(result)

    def remove(self, uids):
        plan = self.plan(
            uids
        )  # Validate ALL families/children before the first mutation.
        for entry in plan:
            exists, remove, validate = self.families[entry.effect_class]
            remove(entry.uid)
            if exists(entry.uid) is not False:
                raise ValueError("Native removal callback retained its owned effect")
            self.removed.add(entry.uid)
        return plan


def register_owned_removals(removal, *, stat_handler, packets, action_id):
    """Wire existing stat reversal and carrier cleanup to the same preview.

    Children are removed by the generic ownership plan, including families
    registered later. No state child can be silently discarded.
    """
    fight = removal.fight
    if stat_handler.fight is not fight:
        raise ValueError("Stat removal belongs to another preview")

    def validate(entry):
        if entry.effect_class == 310:
            payload = fight.state_wire_payloads[entry.uid]
        else:
            payload = fight.owned_stat_effects[entry.uid]["payload"]
        running_effect_removal(
            fight.id,
            action_id,
            effect_class=entry.effect_class,
            target_id=entry.target_id,
            uid=entry.uid,
            running_effect_payload=bytes.fromhex(payload),
        )

    def stat_remove(uid):
        # Explicit view metadata is authoritative even for an external provider.
        entry = removal.view.by_uid[uid]
        stat_handler.remove(uid)
        manager = entry.manager_id if entry.manager_id is not None else entry.target_id
        if manager != entry.target_id:
            import struct

            opcode, payload = packets[-1]
            if opcode != 13560:
                raise ValueError("Native stat removal outbox identity missing")
            packets[-1] = (opcode, payload[:-16] + struct.pack(">qq", manager, uid))

    for kind in {row["effect_class"] for row in fight.owned_stat_effects.values()}:
        removal.register(
            kind,
            exists=lambda uid: uid in fight.owned_stat_effects,
            remove=stat_remove,
            validate=validate,
        )

    def carrier_exists(uid):
        return uid in fight.state_wire_payloads and any(
            e.uid == uid for a in fight.actors.values() for e in a.state_ledger.entries
        )

    def carrier_remove(uid):
        entry = removal.view.by_uid[uid]
        packet = running_effect_removal(
            fight.id,
            action_id,
            effect_class=310,
            target_id=entry.target_id,
            uid=uid,
            running_effect_payload=bytes.fromhex(fight.state_wire_payloads[uid]),
        )
        if fight.actors[entry.target_id].state_ledger.remove(uid) is None:
            raise ValueError("Missing owned native carrier")
        del fight.state_wire_payloads[uid]
        packets.append((13560, packet))
        fight._event(
            "state_removed",
            actor_id=entry.target_id,
            uid=uid,
            reason="native_owned_removal",
        )

    removal.register(
        310, exists=carrier_exists, remove=carrier_remove, validate=validate
    )
