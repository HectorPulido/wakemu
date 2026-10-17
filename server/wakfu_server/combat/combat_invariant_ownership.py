"""Read existing native ownership facts without executing lifecycle helpers.

No catalog, QI rebinding, state-manager refresh, callback, clock or deepcopy is
used. Completeness assertions require the engine's actual tracking flag; legacy
or absent authority is reported separately from contradictory supplied facts.
"""

PV_SOURCE = "fresh.fdt_saq.Qs_bhs.fbX_rRc.default_Trove"
LISTENER_SOURCE = "eWq.c_AP.a_eWr_fff.aZk"
RELATION_SOURCE = "big.new_bje.fdt_initial_registration"
LIMIT = 16384


def check_ownership(fight, state, actors, issue, unknown, checked):
    """Inspect completed-boundary native participation and retained ownership."""
    from .combat_state import Actor
    from .combat_state_ledger import StateLedger, RunningState
    from .combat_state_timing import StateTimer
    from .combat_pointer_qi_spatialowned import NativeSpatialRecord
    from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS
    from .combat_summon_initialization import _construction, DetachedSummonConstruction
    from .combat_pending_state import _PENDING

    work = 0

    def bounded(values, path):
        nonlocal work
        if type(values) not in (dict, list, tuple, set, frozenset):
            issue("ownership.population", path, "Unsupported owned population type")
            return False
        work += len(values)
        if work > LIMIT:
            unknown("coverage.limit", path, "Ownership inspection work limit reached")
            return False
        return True

    actor_rows = {
        identity: vars(actor)
        for identity, actor in dict.items(actors)
        if type(identity) is int and type(actor) is Actor
    }
    # These exact ContextVar facts are the only detached/pending exceptions.
    # Read them directly: owner getters can refresh area geometry.
    all_actor_rows = dict(actor_rows)
    constructions = _construction.get()
    if type(constructions) is tuple and bounded(
        constructions, "scope.detached_summons"
    ):
        for construction in constructions:
            if type(construction) is not DetachedSummonConstruction:
                continue
            facts = vars(construction)
            child = facts.get("actor")
            if facts.get("fight") is fight and type(child) is Actor:
                row = vars(child)
                identity = row.get("id")
                if type(identity) is int and identity not in all_actor_rows:
                    all_actor_rows[identity] = row
    pending = set()
    scopes = _PENDING.get()
    if type(scopes) is tuple and bounded(scopes, "scope.pending_states"):
        for scope in scopes:
            if (
                type(scope) is tuple
                and len(scope) == 2
                and scope[0] is fight
                and type(scope[1]) is int
            ):
                pending.add(scope[1])
    # Native statuses are independent of HP and timeline suppression.
    pv = state.get("native_global_pv_collections")
    registered, statuses, retired = None, {}, set()
    if pv is None:
        unknown(
            "timeline.participation",
            "fight.native_global_pv_collections",
            "Native participation producer unavailable",
        )
    elif type(pv) is not dict or pv.get("source") != PV_SOURCE:
        unknown(
            "timeline.participation",
            "fight.native_global_pv_collections",
            "Unsupported native participation producer",
        )
    else:
        topology, statuses, removed = (
            pv.get("fighters"),
            pv.get("fighter_status"),
            pv.get("retired_fighters"),
        )
        if (
            type(topology) is not dict
            or type(statuses) is not dict
            or type(removed) is not list
        ):
            issue(
                "timeline.population",
                "fight.native_global_pv_collections",
                "Incomplete source-attested participation population",
            )
        else:
            keys, slots = topology.get("keys"), topology.get("states")
            if (
                type(keys) is not list
                or type(slots) is not list
                or len(keys) != len(slots)
                or not bounded(keys, "fight.native_global_pv_collections.fighters")
                or not bounded(
                    statuses, "fight.native_global_pv_collections.fighter_status"
                )
                or not bounded(
                    removed, "fight.native_global_pv_collections.retired_fighters"
                )
            ):
                unknown(
                    "timeline.topology",
                    "fight.native_global_pv_collections.fighters",
                    "Participation topology unavailable or exceeds budget",
                )
            elif (
                any(type(uid) is not int for uid in keys)
                or any(type(slot) is not int or slot not in (0, 1, 2) for slot in slots)
                or any(type(uid) is not int for uid in removed)
            ):
                issue(
                    "timeline.population",
                    "fight.native_global_pv_collections.fighters",
                    "Malformed source-attested fighter topology",
                )
            else:
                live = [uid for uid, slot in zip(keys, slots) if slot == 1]
                registered, retired = set(live), set(removed)
                if (
                    len(live) != len(registered)
                    or len(removed) != len(retired)
                    or topology.get("size") != len(live)
                    or registered & retired
                ):
                    issue(
                        "timeline.population",
                        "fight.native_global_pv_collections.fighters",
                        "Duplicate, retired or size-inconsistent native registration",
                    )
                if set(statuses) != {str(uid) for uid in registered}:
                    issue(
                        "timeline.status",
                        "fight.native_global_pv_collections.fighter_status",
                        "Status population differs from registered fighters",
                    )
                if any(
                    type(value) is not str
                    or value not in ("IN_PLAY", "OFF_PLAY", "OUT_OF_PLAY")
                    for value in statuses.values()
                ):
                    issue(
                        "timeline.status",
                        "fight.native_global_pv_collections.fighter_status",
                        "Unknown native fighter status",
                    )
                if registered - set(actor_rows):
                    issue(
                        "timeline.owner",
                        "fight.native_global_pv_collections.fighters",
                        "Registered native fighter has no owned roster actor",
                    )
                order = state.get("order")
                if (
                    state.get("phase") == "active"
                    and type(order) is list
                    and bounded(order, "fight.order")
                ):
                    for uid in order:
                        if type(uid) is not int:
                            continue
                        if uid not in registered or statuses.get(str(uid)) != "IN_PLAY":
                            issue(
                                "timeline.participation",
                                "fight.order",
                                "Activation references a nonparticipating native fighter",
                            )
                    # Repeated actor activations remain valid native extra turns.
                checked.extend(
                    ("timeline.population", "timeline.status", "timeline.participation")
                )
    # SU/Tc membership snapshots, rather than IN_PLAY alone, prove that an
    # otherwise participating actor is missing its actual activation.
    counters = state.get("native_timeline_member_counters")
    if state.get("native_timeline_snapshot_source") == "owned-tc-sy-v1":
        if type(counters) is not dict or not bounded(
            counters, "fight.native_timeline_member_counters"
        ):
            issue(
                "timeline.membership",
                "fight.native_timeline_member_counters",
                "Incomplete native SY member snapshot",
            )
        else:
            order = state.get("order")
            activation_ids = (
                set(uid for uid in order if type(uid) is int)
                if type(order) is list and len(order) <= LIMIT
                else None
            )
            for key, progress in dict.items(counters):
                if (
                    type(key) is not str
                    or len(key) > 20
                    or not key.lstrip("-").isdigit()
                    or type(progress) is not int
                    or not -32768 <= progress < 32768
                ):
                    issue(
                        "timeline.membership",
                        "fight.native_timeline_member_counters",
                        "Malformed native SY identity or progress",
                    )
                    continue
                identity = int(key)
                if str(identity) != key or identity not in actor_rows:
                    issue(
                        "timeline.membership",
                        "fight.native_timeline_member_counters",
                        "Native SY member has no canonical roster identity",
                    )
                elif (
                    state.get("phase") == "active"
                    and activation_ids is not None
                    and identity not in activation_ids
                    and (registered is None or statuses.get(key) == "IN_PLAY")
                ):
                    issue(
                        "timeline.membership",
                        "fight.order",
                        "Native SY member is missing its timeline activation",
                    )
            checked.append("timeline.membership")
    else:
        unknown(
            "timeline.membership",
            "fight.native_timeline_member_counters",
            "Native SU/SY membership snapshot unavailable",
        )
    for identity, row in actor_rows.items():
        bits = row.get("native_turn_suppression_bits")
        if bits is None:
            unknown(
                "timeline.suppression",
                "fight.actors.native_turn_suppression_bits",
                "Native phase-suppression authority unavailable",
            )
        elif type(bits) is not int or bits < 0:
            issue(
                "timeline.suppression",
                "fight.actors.native_turn_suppression_bits",
                "Native phase-suppression BitSet is malformed",
            )
        else:
            checked.append("timeline.suppression")
        properties = row.get("native_fight_properties")
        if type(properties) in (set, frozenset) and bounded(
            properties, "fight.actors.native_fight_properties"
        ):
            order = state.get("order")
            if (
                state.get("phase") == "active"
                and type(order) is list
                and len(order) <= LIMIT
                and 114 in properties
                and identity in order
                and state.get("native_base_turn_order") is None
            ):
                issue(
                    "timeline.property114",
                    "fight.order",
                    "NOT_PRESENT_IN_TIMELINE actor has an activation",
                )
            checked.append("timeline.property114")
        elif properties is None:
            unknown(
                "timeline.properties",
                "fight.actors.native_fight_properties",
                "Native timeline property authority unavailable",
            )
        else:
            unknown(
                "timeline.properties",
                "fight.actors.native_fight_properties",
                "Unsupported native property population",
            )

    # Read active and retained retired-area managers directly, never refresh faN.
    managers = dict(all_actor_rows)
    area_populations = []
    for name in ("native_effect_areas", "native_retired_area_managers"):
        population = state.get(name)
        if type(population) is not dict or not bounded(population, "fight." + name):
            unknown(
                "retained.manager_authority",
                "fight." + name,
                "Area manager population unavailable",
            )
            continue
        area_populations.append(set(population))
        for uid, row in dict.items(population):
            if type(uid) is not int or type(row) is not dict:
                issue(
                    "retained.manager",
                    "fight." + name,
                    "Malformed area manager identity",
                )
                continue
            if row.get("uid") != uid or uid in managers:
                issue(
                    "retained.manager",
                    "fight." + name,
                    "Area manager identity collides or disagrees",
                )
            if type(row.get("state_ledger")) is StateLedger:
                if row.get("native_area_contract") not in SUPPORTED_AREA_CONTRACTS:
                    unknown(
                        "retained.manager_authority",
                        "fight." + name,
                        "Area manager constructor contract unavailable",
                    )
                elif row.get("native_running_effect_manager") is not False:
                    managers[uid] = row
    if len(area_populations) == 2 and area_populations[0] & area_populations[1]:
        issue(
            "retained.manager",
            "fight.native_retired_area_managers",
            "Area manager is both active and retired",
        )
    state_uids = set()
    for identity, row in managers.items():
        ledger = row.get("state_ledger")
        if type(ledger) is not StateLedger:
            continue
        facts = vars(ledger)
        entries = facts.get("_entries")
        if facts.get("actor_id") != identity:
            issue(
                "retained.manager",
                "fight.state_managers",
                "Ledger belongs to another manager",
            )
        if type(entries) is not tuple or not bounded(
            entries, "fight.state_managers.entries"
        ):
            continue
        for entry in entries:
            if type(entry) is not RunningState:
                continue  # Core checker reports unsupported actor ledger entries.
            values = vars(entry)
            uid = values.get("uid")
            if type(uid) is int:
                if uid in state_uids:
                    issue(
                        "retained.identity",
                        "fight.state_managers.entries",
                        "Running-state UID has multiple managers",
                    )
                state_uids.add(uid)
            if values.get("target_id") != identity:
                issue(
                    "retained.owner",
                    "fight.state_managers.entries",
                    "State target differs from ledger owner",
                )
            timer = values.get("timer")
            if timer is not None:
                if type(timer) is not StateTimer:
                    issue(
                        "timer.state",
                        "fight.state_managers.entries.timer",
                        "Unsupported state timer type",
                    )
                else:
                    clock = vars(timer)
                    if (
                        type(clock.get("actor_id")) is not int
                        or clock["actor_id"] == 0
                        or type(clock.get("expiration_round")) is not int
                        or not -32768 <= clock["expiration_round"] < 32768
                        or clock.get("phase") not in ("start", "end")
                    ):
                        issue(
                            "timer.state",
                            "fight.state_managers.entries.timer",
                            "Malformed native state clock",
                        )
                    # A dead or no-turn actor may be a native clock; never require HP or timeline membership.
    checked.extend(("retained.manager", "timer.state"))

    tracking = state.get("native_retained_tracking") is True
    records, order = state.get("native_retained_records"), state.get(
        "native_retained_order"
    )
    if (
        type(records) is not dict
        or type(order) is not list
        or not bounded(records, "fight.native_retained_records")
        or not bounded(order, "fight.native_retained_order")
    ):
        unknown(
            "retained.completeness",
            "fight.native_retained_records",
            "Retained registry unavailable or oversized",
        )
        return
    if not tracking:
        unknown(
            "retained.completeness",
            "fight.native_retained_tracking",
            "Complete native retained population is not attested",
        )
    if (
        any(type(uid) is not int for uid in order)
        or len(order) != len(set(uid for uid in order if type(uid) is int))
        or set(uid for uid in order if type(uid) is int) != set(records)
    ):
        issue(
            "retained.order",
            "fight.native_retained_order",
            "Retained ordering differs from its registered population",
        )
    owned, children, collections = set(state_uids), {}, {}
    for name in (
        "owned_stat_effects",
        "native_owned_group_effects",
        "native_owned_area_effects",
        "native_owned_spatial_effects",
        "state_wire_payloads",
    ):
        population = state.get(name)
        if type(population) is not dict or not bounded(population, "fight." + name):
            unknown(
                "retained.population",
                "fight." + name,
                "Owned retained population unavailable",
            )
            tracking = False
            continue
        collections[name] = population
        owned.update(uid for uid in population if type(uid) is int)
        if name == "state_wire_payloads":
            continue
        for uid, row in dict.items(population):
            if type(uid) is not int or type(row) not in (dict, NativeSpatialRecord):
                issue(
                    "retained.identity",
                    "fight." + name,
                    "Unsupported owned runner identity",
                )
                continue
            target, owner = dict.get(row, "target_id"), dict.get(row, "state_uid")
            if target is not None and (
                type(target) is not int or target not in managers
            ):
                issue(
                    "retained.owner",
                    "fight." + name,
                    "Retained target has no existing state manager",
                )
            if owner is not None:
                if type(owner) is not int:
                    issue(
                        "retained.container",
                        "fight." + name,
                        "Malformed retained container identity",
                    )
                else:
                    children.setdefault(owner, set()).add(uid)
    payloads = collections.get("state_wire_payloads", {})
    # An exact pending eZk scope is valid only for its owned ledger/payload and
    # before Qf registration, just as pending_state_registration requires.
    for uid in pending:
        if uid not in state_uids or uid not in payloads or uid in records:
            issue(
                "retained.pending_scope",
                "scope.pending_states",
                "Pending carrier lacks its exact pre-registration ownership",
            )
    owned.difference_update(pending)
    nonpayload = set(state_uids)
    for name, population in collections.items():
        if name != "state_wire_payloads":
            nonpayload.update(uid for uid in population if type(uid) is int)
    if tracking and set(payloads) - nonpayload - pending:
        issue(
            "retained.payload_owner",
            "fight.state_wire_payloads",
            "Carrier payload has no owned runner or ledger entry",
        )
    containers = state.get("native_owned_state_containers")
    if type(containers) is not dict or not bounded(
        containers, "fight.native_owned_state_containers"
    ):
        unknown(
            "retained.container_authority",
            "fight.native_owned_state_containers",
            "Owned container snapshots unavailable",
        )
        containers = {}
    for uid, record in dict.items(records):
        if type(uid) is not int or type(record) is not dict or record.get("uid") != uid:
            issue(
                "retained.identity",
                "fight.native_retained_records",
                "Retained metadata key and UID disagree",
            )
            continue
        target, owner = record.get("target_id"), record.get("owner_uid")
        if target is not None and (type(target) is not int or target not in managers):
            issue(
                "retained.owner",
                "fight.native_retained_records",
                "Retained metadata targets an absent manager",
            )
        manager = record.get("manager_id")
        if target is None and (type(manager) is not int or manager not in managers):
            issue(
                "retained.owner",
                "fight.native_retained_records",
                "Target-less runner has no registered native manager",
            )
        if owner is not None and (
            type(owner) is not int or owner not in records and owner not in containers
        ):
            issue(
                "retained.container",
                "fight.native_retained_records",
                "Retained child has no registered or captured PL owner",
            )
    for owner, users in children.items():
        if owner not in state_uids and owner not in containers:
            issue(
                "retained.container",
                "fight.native_owned_state_containers",
                "Owned child lost its live or captured state container",
            )
    for uid, row in dict.items(containers):
        if type(uid) is not int or type(row) is not dict or row.get("uid") != uid:
            issue(
                "retained.container",
                "fight.native_owned_state_containers",
                "Container snapshot key and UID disagree",
            )
        elif not children.get(uid):
            issue(
                "retained.container",
                "fight.native_owned_state_containers",
                "Captured PL snapshot has no owned retained child",
            )
        elif (
            type(row.get("target_id")) is not int
            or row["target_id"] not in managers
            or type(row.get("caster_id")) is not int
            or row["caster_id"] not in all_actor_rows
        ):
            issue(
                "retained.container",
                "fight.native_owned_state_containers",
                "Captured PL target or caster has no retained manager/actor",
            )
    if tracking:
        if owned != set(records):
            issue(
                "retained.completeness",
                "fight.native_retained_records",
                "Complete retained registry differs from actual owned runners",
            )
        checked.append("retained.completeness")
    checked.extend(("retained.order", "retained.owner", "retained.container"))
    queue = state.get("native_delay_queue")
    if (
        type(queue) is dict
        and type(queue.get("entries")) is list
        and bounded(queue["entries"], "fight.native_delay_queue.entries")
    ):
        for row in queue["entries"]:
            if type(row) is not dict:
                continue
            uid = row.get("uid")
            if (
                tracking
                and type(uid) is int
                and uid not in collections.get("native_owned_group_effects", {})
            ):
                issue(
                    "timer.owner",
                    "fight.native_delay_queue.entries",
                    "Delayed runner has no owned retained group",
                )
        checked.append("timer.owner")
    listeners = state.get("native_resource_pa_listeners")
    if listeners is not None:
        if type(listeners) is not dict or not bounded(
            listeners, "fight.native_resource_pa_listeners"
        ):
            unknown(
                "subscription.authority",
                "fight.native_resource_pa_listeners",
                "Unsupported listener population",
            )
        else:
            for actor_id, rows in dict.items(listeners):
                if type(actor_id) is not int or actor_id not in actor_rows:
                    issue(
                        "subscription.owner",
                        "fight.native_resource_pa_listeners",
                        "Listener owner is not an existing actor",
                    )
                if type(rows) is not list or not bounded(
                    rows, "fight.native_resource_pa_listeners.rows"
                ):
                    continue
                seen = set()
                for row in rows:
                    if type(row) is not dict:
                        issue(
                            "subscription.registration",
                            "fight.native_resource_pa_listeners",
                            "Malformed listener record",
                        )
                        continue
                    uid = row.get("uid")
                    if (
                        row.get("source") != LISTENER_SOURCE
                        or row.get("actor_id") != actor_id
                        or type(uid) is not int
                        or uid in seen
                        or any(
                            type(row.get(key)) is not int
                            or not -(1 << 31) <= row[key] < (1 << 31)
                            for key in ("rBe", "rBf", "rBg")
                        )
                    ):
                        issue(
                            "subscription.registration",
                            "fight.native_resource_pa_listeners",
                            "Listener provenance, identity or operand disagrees",
                        )
                    if type(uid) is int:
                        seen.add(uid)
                        if tracking and uid not in collections.get(
                            "owned_stat_effects", {}
                        ):
                            issue(
                                "subscription.runner",
                                "fight.native_resource_pa_listeners",
                                "AP listener lost its owned stat runner",
                            )
            checked.extend(
                (
                    "subscription.owner",
                    "subscription.registration",
                    "subscription.runner",
                )
            )
    _summons(state, actor_rows, registered, statuses, issue, unknown, checked, bounded)


def _summons(state, actors, registered, statuses, issue, unknown, checked, bounded):
    registrations = state.get("native_summon_registrations")
    if registrations is None:
        if any(row.get("native_summon_source") is not None for row in actors.values()):
            unknown(
                "summon.authority",
                "fight.native_summon_registrations",
                "Summon relationship registry unavailable",
            )
        return
    if type(registrations) is not dict or not bounded(
        registrations, "fight.native_summon_registrations"
    ):
        unknown(
            "summon.authority",
            "fight.native_summon_registrations",
            "Unsupported summon registration population",
        )
        return
    for uid, row in dict.items(registrations):
        actor = actors.get(uid) if type(uid) is int else None
        if type(row) is not dict or actor is None or row.get("actor_id") != uid:
            issue(
                "summon.owner",
                "fight.native_summon_registrations",
                "Registered summon identity has no actor",
            )
            continue
        source, authority = actor.get("native_summon_source"), row.get("authority")
        if (
            type(source) is not dict
            or source.get("native_relation_source") != RELATION_SOURCE
        ):
            unknown(
                "summon.authority",
                "fight.native_summon_registrations",
                "Supported native relationship producer unavailable",
            )
            continue
        controller = row.get("controller_id")
        if (
            type(controller) is not int
            or controller not in actors
            or source.get("controller_id") != controller
            or source.get("caster_id") != row.get("caster_id")
            or actor.get("native_master_id") != controller
            or actor.get("native_controller_id") != controller
        ):
            issue(
                "summon.owner",
                "fight.native_summon_registrations",
                "Summon controller/master/source relationships disagree",
            )
        if type(authority) is not dict:
            unknown(
                "summon.authority",
                "fight.native_summon_registrations.authority",
                "Summon authority snapshot unavailable",
            )
        elif (
            authority.get("is_summon") is not True
            or authority.get("native_controller_id") != controller
            or authority.get("breed_id") != source.get("ref")
            or authority.get("native_real_level") != source.get("level")
        ):
            issue(
                "summon.authority",
                "fight.native_summon_registrations.authority",
                "Summon native snapshot contradicts creation facts",
            )
    retirements = state.get("native_summon_retirements")
    if type(retirements) is dict and bounded(
        retirements, "fight.native_summon_retirements"
    ):
        for uid, row in dict.items(retirements):
            actor = actors.get(uid) if type(uid) is int else None
            if (
                type(row) is not dict
                or row.get("source")
                not in (
                    "wakemu.summon_retirement.ko_zero_after_settlement.v1",
                    "wakemu.summon_retirement.protected_332_boundary.v1",
                )
                or row.get("actor_id") != uid
                or actor is None
                or uid not in registrations
            ):
                issue(
                    "summon.retirement",
                    "fight.native_summon_retirements",
                    "Retirement lost its registered source or actor",
                )
                continue
            if actor.get("native_obstacle_id") != -1:
                issue(
                    "summon.retirement",
                    "fight.native_summon_retirements",
                    "Retired summon still owns a live obstacle byte",
                )
            if registered is not None and (
                uid not in registered or statuses.get(str(uid)) != "OUT_OF_PLAY"
            ):
                issue(
                    "summon.retirement",
                    "fight.native_summon_retirements",
                    "Retired summon lacks registered OUT_OF_PLAY status",
                )
    checked.extend(("summon.owner", "summon.authority", "summon.retirement"))
