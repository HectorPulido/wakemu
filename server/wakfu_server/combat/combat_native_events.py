"""Native eZX/Qi subscription selection; event production stays explicit.

The integer delivery channel is a Qf/Qi byte, not an effect/event ID.
Selection does not evaluate conditions, clone Qe, or execute its children.
"""
CHANNEL_MASK_INDEX = {1: 0, 2: 1, 3: 3, 4: 2, 5: 4, 6: 5}
REVERSED_CHANNEL_MASK_INDEX = {10: 0, 20: 1, 30: 3, 40: 2, 60: 5}
GLOBAL_CHANNEL_MASK_INDEX = {11: 0, 21: 1, 31: 3, 41: 2, 61: 5}


def activation_order_key(*, priority, generic_effect, uid):
    """eZY sorts queued listeners by priority descending, generic and UID ascending."""
    if type(priority) is not int or not -(1 << 31) <= priority < (1 << 31):
        raise ValueError("Native signed priority required")
    if (
        type(generic_effect) is not int
        or type(uid) is not int
        or not 0 < uid < (1 << 63)
    ):
        raise ValueError("Native listener definition and UID required")
    return -priority, generic_effect, uid


def subscription_actor_ids(
    *,
    target_code,
    caster_code,
    original_caster,
    original_target,
    manager_actor,
    source_caster,
    source_target,
    source_present,
):
    """Actual eZR.l/m enum rebinding, preserving native nullable actor IDs."""
    if type(source_present) is not bool:
        raise ValueError("Explicit native event source presence required")
    if not source_present:
        return original_caster, original_target
    if type(target_code) is not int or target_code not in range(6):
        raise ValueError("Missing native Qd target selector")
    if caster_code is not None and (
        type(caster_code) is not int or caster_code not in range(6)
    ):
        raise ValueError("Unknown native Qb caster selector")
    target = (
        original_target,
        original_target,
        manager_actor,
        original_caster,
        source_caster,
        source_target,
    )[target_code]
    caster = (
        original_caster
        if caster_code is None
        else (
            original_caster,
            original_caster,
            manager_actor,
            original_target,
            source_caster,
            source_target,
        )[caster_code]
    )
    return caster, target


def subscription_selection(
    *,
    masks,
    event_ids,
    channel,
    global_subscription,
    reversed_subscription,
    flags,
    source_present,
    source_suppresses_level_one=False,
    source_suppresses_all=False,
    source_is_self=False,
    source_parent_is_self=False,
    source_suppressed=False,
):
    """Return activate/remove/None according to eZX.b + Qi.a/b.

    Inputs describe an already existing source running effect. Callers must
    obtain real event IDs from the native caller, never from effect IDs.
    """
    if type(channel) is not int or len(masks) != 7:
        raise ValueError("Native channel and seven subscription masks required")
    if any(
        type(x) is not bool
        for x in (
            global_subscription,
            reversed_subscription,
            source_present,
            source_suppresses_level_one,
            source_suppresses_all,
            source_is_self,
            source_parent_is_self,
            source_suppressed,
        )
    ):
        raise ValueError("Explicit native event source flags required")
    if any(type(x) is not int or x < 0 for x in event_ids):
        raise ValueError("Native event IDs must be nonnegative integers")
    if source_present and (
        source_suppresses_all
        or source_is_self
        or source_parent_is_self
        or source_suppressed
    ):
        return None
    if source_present and source_suppresses_level_one and 1 not in flags:
        return None
    mapping = (
        GLOBAL_CHANNEL_MASK_INDEX
        if global_subscription
        else (
            REVERSED_CHANNEL_MASK_INDEX if reversed_subscription else CHANNEL_MASK_INDEX
        )
    )
    index = mapping.get(channel)
    if index is None or not set(masks[index] or ()).intersection(event_ids):
        return None
    return "remove" if index == 2 else "activate"


def validate_group_registration_flags(
    flags, *, active, constructor=False, effect=None, reference=None
):
    """Flags1 affects eZX event selection only;17 is not read by eYg.

    Jar-wide reference audit finds eVl.rwy consumed only by eZX, outside
    registration/execution arithmetic. Flags14/26 are handled by the native
    target ordering resolver before execution; single-target event clones have
    no target list to reorder. Flag3 is consumed only by aJs zone preview,
    with no execution arithmetic/event effect. Flag15 is the KO bypass in eZR.bcd; eYg overrides bcd to true
    regardless of that flag, so it changes no group arithmetic. Actor KO
    eligibility still needs authoritative runtime support. Unknown flags remain rejected.
    Flag5 is eZR.aZB source level-one event suppression, already preserved
    by Ordinary*Events and the shared eZX replay guard; it does not block
    group arithmetic or child execution.
    Flag16 is executed by the shared child-level/eVt transmission contract;
    registration preserves it for that later execution step.
    Flag9 KEEP_WHEN_OFF_PLAY is consumed only by eZV.a(PV,boolean,
    boolean,boolean) during manager cleanup: it skips unapplication when
    the third argument is true. It does not modify group registration,
    child execution or event subscription. Preserve it in retained metadata.
    Flag24 RANGED_EFFECT is consumed only by eXt.bbx (damage event2217)
    and eYE range classification. It does not change group registration;
    damage and range consumers retain their own native authority.
    Flag8 is accepted only with the exact source-qualified faI ordering
    definition. Target PA lookup and ordering remain the resolver's job;
    flags-only callers cannot attest this additional native contract.
    """
    if (
        type(active) is not bool
        or type(constructor) is not bool
        or any(type(x) is not int for x in flags)
    ):
        raise ValueError("Explicit native group flags/combat context required")
    unknown = set(flags) - {1, 3, 5, 9, 14, 15, 16, 17, 24, 26}
    if 8 in unknown and effect is not None and reference is not None:
        if set(effect.get("native_effect_flags", ())) != set(flags):
            raise ValueError("Native group ordering flags differ from definition")
        from .combat_target_ordering import validate_native_target_ordering_identity

        validate_native_target_ordering_identity(effect, reference)
        unknown.remove(8)
    if 22 in unknown and effect is not None and reference is not None:
        # eXt owns SINGLE_TARGET_EFFECT mastery and event2216. Its fresh
        # subscribed listener reaches central retention before activation;
        # eZR registration itself has no rwS consumer.
        if (
            type(effect.get("effect_class")) is int
            and effect["effect_class"] in (1, 2, 3, 4, 5)
            and type(reference) is int
            and reference > 0
            and set(effect.get("native_effect_flags", ())) == set(flags)
        ):
            unknown.remove(22)
    if unknown:
        raise ValueError(f"Unaudited native group execution flags: {sorted(unknown)}")
    # eYg.bcd returns true unconditionally; no active-phase predicate is
    # introduced by group construction (native eYg bytecode). ID17/rwN
    # is BUFF_BYPASS_OUT_FIGHT_MAX; neither eYg nor eZR reads it. Actual
    # characteristic consumers retain their own cap/context requirements.
    if not active and not constructor:
        raise ValueError("Native group execution requires active combat")
