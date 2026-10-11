"""Persistent active-zone maturation, receipts and publication recovery.

A restart, absent player, combat or harvest never charges offline time.
Spell definitions and combat execution are outside this module's scope.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
import math
import secrets
from contextlib import nullcontext
from .paths import DATA_ROOT

CATALOG = protocol_catalog.load(DATA_ROOT / "monster-growth-catalog.json")
GROWABLE = {
    candidate["reference"]
    for family in CATALOG["families"]
    for tier in family["tiers"][:-1]
    for candidate in tier["candidates"]
}
STAGES = {
    candidate["reference"]: (family, tier["rank"])
    for family in CATALOG["families"]
    for tier in family["tiers"]
    for candidate in tier["candidates"]
}


def policy(store):
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name='monster_maturation'"
        ).fetchone()
    value = None if row is None else row["value"]
    return validate_policy(value)


def validate_policy(value):
    keys = {"interval_ms", "base_probability", "stage_decay", "boss_probability"}
    if type(value) is not dict or set(value) != keys:
        raise ValueError("Invalid monster maturation policy")
    if (
        type(value["interval_ms"]) is not int
        or not 1000 <= value["interval_ms"] <= 86400000
    ):
        raise ValueError("Invalid monster maturation interval")
    for key in keys - {"interval_ms"}:
        number = value[key]
        if (
            type(number) not in (int, float)
            or not 0 <= number <= 1
            or not math.isfinite(number)
        ):
            raise ValueError("Invalid monster maturation probability")
    if value["base_probability"] + value["boss_probability"] > 1:
        raise ValueError("Monster maturation outcome probabilities exceed one")
    return value


def choose_next(reference, configuration, *, draw, choose=secrets.choice):
    """One categorical draw; a boss is never a uniform ordinary alternative.

    Boss probability is per attempt for the whole next-tier boss set, rather
    than multiplied by the number of boss references. No skipped level tiers.
    """
    if type(draw) not in (int, float) or not 0 <= draw < 1 or not math.isfinite(draw):
        raise ValueError("Invalid monster maturation draw")
    stage = STAGES.get(reference)
    if stage is None:
        return None
    family, rank = stage
    if rank + 1 >= len(family["tiers"]):
        return None
    candidates = family["tiers"][rank + 1]["candidates"]
    bosses = [
        row
        for row in candidates
        if row["boss_classification"] in ("boss", "ultimate_boss", "raid_boss")
    ]
    ordinary = [row for row in candidates if row not in bosses]
    boss_probability = configuration["boss_probability"] if bosses else 0
    ordinary_probability = (
        configuration["base_probability"] * configuration["stage_decay"] ** rank
        if ordinary
        else 0
    )
    if draw < boss_probability:
        return choose(bosses)
    if draw < boss_probability + ordinary_probability:
        return choose(ordinary)
    return None


def observe(
    store,
    map_id,
    instance_id,
    *,
    present,
    generation,
    now_ms,
    excluded_ids=(),
    configuration=None,
):
    from .monster_active_clocks import observe as observe_clocks

    return observe_clocks(
        store,
        map_id,
        instance_id,
        present=present,
        generation=generation,
        now_ms=now_ms,
        excluded_ids=excluded_ids,
        table="monster_maturation_timers",
        eligible_refs=GROWABLE,
        policy_provider=policy
        if configuration is None
        else lambda _: validate_policy(configuration),
    )


def attempt(
    store,
    ticket,
    *,
    present,
    excluded_ids=(),
    draw=None,
    choose=secrets.choice,
    configuration=None,
    prepared=None,
):
    """Commit one pending cycle under the same group lock used by fight claims.

    Caller holds its live harvest/group locks. Invalid/stale/occupied members
    never draw. Replaying a committed cycle returns its stored outcome.
    """
    from psycopg.types.json import Jsonb
    from .monsters import owned_instance
    from .combat_monster_world import spawn_group

    if type(present) is not bool:
        raise ValueError("Invalid monster maturation presence")
    if not present:
        return None
    configuration = (
        policy(store) if configuration is None else validate_policy(configuration)
    )
    key = (
        ticket["map_id"],
        ticket["instance_id"],
        ticket["monster_id"],
        ticket["cycle"],
    )
    group_key = (ticket["map_id"], ticket["instance_id"], ticket["group_id"])
    with store.connection() as db:
        db.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            ("monster-population:" + ":".join(map(str, key[:2])),),
        )
        group = db.execute(
            "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=%s "
            "AND group_id=%s FOR UPDATE",
            group_key,
        ).fetchone()
        old = db.execute(
            "SELECT * FROM monster_maturation_receipts WHERE map_id=%s "
            "AND instance_id=%s AND monster_id=%s AND cycle=%s",
            key,
        ).fetchone()
        if old is not None:
            if (
                old["group_id"] != ticket["group_id"]
                or old["from_reference"] != ticket["reference"]
            ):
                raise ValueError("Foreign monster maturation cycle")
            return dict(old, duplicate=True)
        if (
            group is None
            or group["status"] != "available"
            or ticket["monster_id"] in excluded_ids
        ):
            return None
        if (
            prepared is not None
            and list(group["members"]) != prepared["expected_members"]
        ):
            return None
        timer = db.execute(
            "SELECT * FROM monster_maturation_timers WHERE map_id=%s "
            "AND instance_id=%s AND monster_id=%s FOR UPDATE",
            key[:3],
        ).fetchone()
        members = list(group["members"])
        index = next(
            (
                index
                for index, member in enumerate(members)
                if member["id"] == ticket["monster_id"]
            ),
            None,
        )
        if (
            timer is None
            or not timer["due"]
            or timer["cycle"] != ticket["cycle"]
            or timer["reference"] != ticket["reference"]
            or index is None
            or members[index]["ref"] != ticket["reference"]
        ):
            return None
        sample = secrets.randbelow(1 << 53) / (1 << 53) if draw is None else draw
        if prepared is None:
            candidate = choose_next(
                ticket["reference"], configuration, draw=sample, choose=choose
            )
            grown = None
            if candidate is not None:
                member = members[index]
                grown = owned_instance(
                    candidate["reference"],
                    candidate["min_level"],
                    member["id"],
                    map_id=member["map_id"],
                    x=member["x"],
                    y=member["y"],
                    z=member["z"],
                    team=member["team"],
                    instance_id=ticket["instance_id"],
                )
        else:
            grown = prepared["grown"]
        to_reference = None
        if grown is not None:
            members[index] = grown
            # Validate complete native roster before changing durable state.
            spawn_group(members, group_id=ticket["group_id"])
            to_reference = grown["ref"]
            revision = db.execute(
                "UPDATE combat_groups SET members=%s,revision=revision+1 "
                "WHERE map_id=%s AND instance_id=%s AND group_id=%s RETURNING revision",
                (Jsonb(members), *group_key),
            ).fetchone()["revision"]
        receipt = db.execute(
            "INSERT INTO monster_maturation_receipts(map_id,instance_id,monster_id,cycle,"
            "group_id,from_reference,to_reference,draw,policy) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                *key,
                ticket["group_id"],
                ticket["reference"],
                to_reference,
                sample,
                Jsonb(configuration),
            ),
        ).fetchone()
        if to_reference is not None:
            db.execute(
                "INSERT INTO monster_maturation_outbox(map_id,instance_id,monster_id,cycle,group_id,revision) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (*key, ticket["group_id"], revision),
            )
        db.execute(
            "UPDATE monster_maturation_timers SET reference=%s,remaining_ms=%s,"
            "last_active_ms=NULL,due=false WHERE map_id=%s AND instance_id=%s AND monster_id=%s",
            (
                to_reference or ticket["reference"],
                configuration["interval_ms"],
                *key[:3],
            ),
        )
        return dict(receipt, duplicate=False)


def pending(store, map_id, instance_id):
    """Recover pending cycles after restart without replaying wall-clock time."""
    with store.connection() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT t.map_id,t.instance_id,t.monster_id,t.reference,t.cycle,m.group_id "
                "FROM monster_maturation_timers t JOIN combat_group_members m "
                "USING(map_id,instance_id,monster_id) "
                "WHERE t.map_id=%s AND t.instance_id=%s AND t.due ORDER BY t.monster_id",
                (map_id, instance_id),
            )
        ]


def unpublished(store, map_id, instance_id, *, group_id=None):
    """Read committed publications with the latest durable group snapshot.

    Several growth events may share a group. Publish its current revision,
    never an older roster captured before a movement or another maturation.
    Caller must hold the group lock through publication and acknowledgement.
    """
    with store.connection() as db:
        return [
            dict(row)
            for row in db.execute(
                "SELECT o.*,g.members,g.status,g.revision AS current_revision "
                "FROM monster_maturation_outbox o JOIN combat_groups g "
                "USING(map_id,instance_id,group_id) "
                "WHERE o.map_id=%s AND o.instance_id=%s AND NOT o.published "
                + ("AND o.group_id=%s " if group_id is not None else "")
                + "ORDER BY o.group_id,o.revision,o.monster_id,o.cycle",
                (map_id, instance_id)
                if group_id is None
                else (map_id, instance_id, group_id),
            )
        ]


def acknowledge(store, event):
    """Ack only this event if its published group revision is still current."""
    with store.connection() as db:
        return (
            db.execute(
                "UPDATE monster_maturation_outbox o SET published=true "
                "FROM combat_groups g WHERE o.map_id=%s AND o.instance_id=%s "
                "AND o.monster_id=%s AND o.cycle=%s AND o.revision=%s "
                "AND g.map_id=o.map_id AND g.instance_id=o.instance_id "
                "AND g.group_id=o.group_id AND g.revision=%s "
                "AND g.status='available' AND NOT o.published RETURNING o.cycle",
                (
                    event["map_id"],
                    event["instance_id"],
                    event["monster_id"],
                    event["cycle"],
                    event["revision"],
                    event["current_revision"],
                ),
            ).fetchone()
            is not None
        )


def reconcile_seed(store, key, seeds, persisted):
    """Validate seed drift only through committed native maturation receipts.

    This does not write or reset a group. Positions may wander independently;
    every other field must match the exact native member reached by receipts.
    """
    from .monsters import owned_instance
    from .npc_actor_identity_repair import actor_aliases, aliased_members

    with store.connection() as db:
        aliases = actor_aliases(db, key)
    seeds = aliased_members(seeds, aliases)

    if len(seeds) != len(persisted):
        from .monster_reproduction import expanded_seeds

        seeds = expanded_seeds(store, key, seeds, persisted)
    if len(seeds) != len(persisted):
        raise ValueError("Conflicting existing group seed roster")
    with store.connection() as db:
        receipts = db.execute(
            "SELECT * FROM monster_maturation_receipts WHERE map_id=%s "
            "AND instance_id=%s AND group_id=%s ORDER BY monster_id,cycle",
            key,
        ).fetchall()
    by_id = {}
    for receipt in receipts:
        identity = aliases.get(receipt["monster_id"], receipt["monster_id"])
        by_id.setdefault(identity, []).append(receipt)
    for seed, current in zip(seeds, persisted):
        if seed["id"] != current["id"]:
            raise ValueError("Conflicting existing group seed identity")
        expected = dict(seed)
        for receipt in by_id.get(seed["id"], ()):
            if receipt["from_reference"] != expected["ref"]:
                raise ValueError("Broken monster maturation receipt chain")
            target = receipt["to_reference"]
            if target is None:
                continue
            stage = STAGES.get(expected["ref"])
            if stage is None or stage[1] + 1 >= len(stage[0]["tiers"]):
                raise ValueError("Invalid monster maturation receipt transition")
            candidate = next(
                (
                    row
                    for row in stage[0]["tiers"][stage[1] + 1]["candidates"]
                    if row["reference"] == target
                ),
                None,
            )
            if candidate is None:
                raise ValueError("Invalid monster maturation receipt transition")
            expected = owned_instance(
                target,
                candidate["min_level"],
                expected["id"],
                map_id=expected["map_id"],
                x=expected["x"],
                y=expected["y"],
                z=expected["z"],
                team=expected["team"],
                instance_id=key[1],
            )
        identity = lambda member: {
            k: v for k, v in member.items() if k not in ("x", "y", "z")
        }
        if identity(expected) != identity(current):
            raise ValueError("Conflicting existing group seed identity or stats")
    return key


def tick(
    store,
    locations,
    previous_locations,
    *,
    generation,
    now_ms,
    excluded_ids,
    emit,
    coordination=None,
):
    """Refresh authority per operation instead of fencing a complete zone cycle.

    The optional coordinator yields current players and harvest exclusions while
    holding group/harvest fences. Legacy callers retain their outer fence.
    """
    from .combat_monster_world import remove_message, spawn_group

    def guarded(stage, map_id, instance_id):
        if coordination is None:
            return nullcontext(((), excluded_ids))
        return coordination(stage, map_id, instance_id)

    def present(players, map_id, instance_id):
        return coordination is None or any(
            (player["map_id"], player["instance_id"]) == (map_id, instance_id)
            for player in players
        )

    locations = set(locations)
    configuration = policy(store) if locations else None
    for map_id, instance_id in set(previous_locations) - locations:
        with guarded("absent", map_id, instance_id):
            observe(
                store,
                map_id,
                instance_id,
                present=False,
                generation=generation,
                now_ms=now_ms,
            )
    for map_id, instance_id in sorted(locations):
        with guarded("observe", map_id, instance_id) as (players, current_excluded):
            observe(
                store,
                map_id,
                instance_id,
                present=present(players, map_id, instance_id),
                generation=generation,
                now_ms=now_ms,
                excluded_ids=current_excluded,
                configuration=configuration,
            )
        for ticket in pending(store, map_id, instance_id):
            with guarded("attempt", map_id, instance_id) as (players, current_excluded):
                attempt(
                    store,
                    ticket,
                    present=present(players, map_id, instance_id),
                    excluded_ids=current_excluded,
                    configuration=configuration,
                )
        group_ids = dict.fromkeys(
            event["group_id"] for event in unpublished(store, map_id, instance_id)
        )
        for group_id in group_ids:
            with guarded("publish", map_id, instance_id) as (_, current_excluded):
                # Enumeration is advisory: a claim or harvest can start before
                # this fence. Reload the authoritative roster before delivery.
                batch = unpublished(store, map_id, instance_id, group_id=group_id)
                if not batch:
                    continue
                current = batch[-1]
                if current["status"] != "available" or any(
                    member["id"] in current_excluded for member in current["members"]
                ):
                    continue
                remove = remove_message([member["id"] for member in current["members"]])
                spawn = spawn_group(current["members"], group_id=group_id)
                emit(map_id, instance_id, *remove)
                emit(map_id, instance_id, 12608, spawn)
                for event in batch:
                    acknowledge(store, event)
    return locations
