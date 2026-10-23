"""Durable company entry/return and pending native scene delivery."""
import uuid
from psycopg.types.json import Jsonb

KEYS = ("map_id", "instance_id", "x", "y", "z")


def _pending(db, character_id):
    return db.execute(
        "SELECT * FROM haven_world_transitions WHERE character_id=%s "
        "AND delivered_at IS NULL FOR UPDATE",
        (character_id,),
    ).fetchone()


def _result(store, db, account_id, character_id, row):
    return dict(
        character=store.character(account_id, character_id, db),
        transition=dict(
            token=row["token"],
            kind=row["kind"],
            source=row["source"],
            destination=row["destination"],
            cohort=row["cohort"],
        ),
    )


def travel(store, positions, account_id, generation, character_id, *, leave=False):
    """World owns final scene publication; movement is fenced and atomic."""
    if type(leave) is not bool:
        raise ValueError("Invalid Haven World travel direction")
    if positions is not None:
        from wakfu_server.dungeon_position_barrier import run_account_exit

        return run_account_exit(
            store,
            positions,
            account_id,
            transition=lambda: travel(
                store, None, account_id, generation, character_id, leave=leave
            ),
        )
    from wakfu_server.console_relocation import (
        lock_relocation_company,
        relocate_in_transaction,
    )
    from wakfu_server.simple_item_actions import _idle
    from wakfu_server.guild_service import GuildService

    with store.connection() as db:
        cohort = lock_relocation_company(store, db, account_id, character_id)
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        store.lock_character(db, account_id, generation, character_id)
        current = store.character(account_id, character_id, db)
        source = {key: current[key] for key in KEYS}
        prior = _pending(db, character_id)
        if prior is not None:
            if any(current[key] != prior["destination"][key] for key in KEYS):
                raise ValueError("Haven World transition destination changed")
            return _result(store, db, account_id, character_id, prior)
        for member in cohort:
            _idle(db, member, store.now())
        if leave:
            visit = db.execute(
                "SELECT v.source,w.map_id,w.instance_id FROM haven_world_visits v "
                "JOIN guild_haven_worlds w ON w.guild_id=v.guild_id "
                "WHERE v.character_id=%s AND v.returned_at IS NULL FOR UPDATE OF v,w",
                (character_id,),
            ).fetchone()
            if visit is None or any(
                current[key] != visit[key] for key in ("map_id", "instance_id")
            ):
                raise ValueError("No current owned Haven World visit to return from")
            destination = dict(visit["source"])
            if destination.get("instance_id") != 0:
                raise ValueError("Haven World return has no exterior authority")
            # Return remains possible after leaving a guild or disabling entry.
            store.transition_map_in_transaction(
                db, account_id, generation, character_id, source, destination
            )
        else:
            if current["instance_id"] != 0:
                raise ValueError(
                    "Leave the current private scene before entering a Haven World"
                )
            service = GuildService(store)
            policy = service._start(db, account_id, generation, character_id)
            if (
                not isinstance(policy.get("haven_world"), dict)
                or policy["haven_world"].get("enabled") is not True
            ):
                raise ValueError("Guild Haven World access is disabled")
            guild = service._guild(db, character_id)
            binding = db.execute(
                "SELECT * FROM guild_haven_worlds WHERE guild_id=%s FOR UPDATE",
                (guild["id"],),
            ).fetchone()
            if binding is None:
                raise ValueError("This guild has no assigned Haven World")
            from wakfu_server.haven_world_terrain import TEMPLATE_MAP_ID

            if binding["map_id"] != TEMPLATE_MAP_ID:
                raise ValueError("Assigned Haven World has no published native layout")
            destination = dict(
                map_id=binding["map_id"],
                instance_id=binding["instance_id"],
                x=binding["entry_x"],
                y=binding["entry_y"],
                z=binding["entry_z"],
            )
            for member in cohort:
                visit = db.execute(
                    "SELECT returned_at FROM haven_world_visits WHERE character_id=%s FOR UPDATE",
                    (member,),
                ).fetchone()
                if visit is not None and visit["returned_at"] is None:
                    raise ValueError("Company retains an unresolved Haven World visit")
                db.execute(
                    "INSERT INTO haven_world_visits(character_id,guild_id,source) VALUES(%s,%s,%s) "
                    "ON CONFLICT(character_id) DO UPDATE SET guild_id=EXCLUDED.guild_id,source=EXCLUDED.source,"
                    "entered_at=CURRENT_TIMESTAMP,returned_at=NULL",
                    (member, guild["id"], Jsonb(source)),
                )
            relocate_in_transaction(
                store,
                db,
                account_id,
                generation,
                character_id,
                source,
                destination,
                cohort=cohort,
            )
        row = db.execute(
            "INSERT INTO haven_world_transitions(token,account_id,character_id,kind,source,destination,cohort) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                uuid.uuid4().hex,
                account_id,
                character_id,
                "return" if leave else "entry",
                Jsonb(source),
                Jsonb(destination),
                Jsonb(list(cohort)),
            ),
        ).fetchone()
        return _result(store, db, account_id, character_id, row)


def external_departure(db, account_id):
    """Finish actual departed visits after company SQL relocation, including !tp.

    A private scene change never silently retains membership or a stale pending
    transition. Characters still physically inside their assigned world remain.
    """
    departed = list(
        db.execute(
            "UPDATE haven_world_visits v SET returned_at=CURRENT_TIMESTAMP "
            "FROM guild_haven_worlds w,characters c WHERE v.guild_id=w.guild_id "
            "AND c.id=v.character_id AND c.account_id=%s AND v.returned_at IS NULL "
            "AND (c.map_id!=w.map_id OR c.instance_id!=w.instance_id) RETURNING v.character_id",
            (account_id,),
        )
    )
    if departed:
        db.execute(
            "UPDATE haven_world_transitions SET delivered_at=CURRENT_TIMESTAMP "
            "WHERE character_id=ANY(%s) AND delivered_at IS NULL",
            ([row["character_id"] for row in departed],),
        )


def pending(store, account_id, generation, character_id):
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        row = _pending(db, character_id)
        if row is None:
            return None
        current = store.character(account_id, character_id, db)
        if any(current[key] != row["destination"][key] for key in KEYS):
            raise ValueError(
                "Pending Haven World delivery does not match actual location"
            )
        return _result(store, db, account_id, character_id, row)


def acknowledge(store, account_id, generation, character_id, token):
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        row = _pending(db, character_id)
        if row is None:
            return
        if row["token"] != token or row["account_id"] != account_id:
            raise ValueError("Invalid Haven World transition receipt")
        current = store.character(account_id, character_id, db)
        if any(current[key] != row["destination"][key] for key in KEYS):
            raise ValueError("Haven World acknowledgment location changed")
        db.execute(
            "UPDATE haven_world_transitions SET delivered_at=CURRENT_TIMESTAMP WHERE token=%s",
            (token,),
        )


def owned_scope(db, source, *, character_id=None):
    if source.get("instance_id", 0) <= 0:
        return False
    if character_id is None:
        return (
            db.execute(
                "SELECT 1 FROM guild_haven_worlds WHERE map_id=%s AND instance_id=%s",
                (source["map_id"], source["instance_id"]),
            ).fetchone()
            is not None
        )
    return (
        db.execute(
            "SELECT 1 FROM guild_haven_worlds w JOIN haven_world_visits v ON v.guild_id=w.guild_id "
            "WHERE w.map_id=%s AND w.instance_id=%s AND v.character_id=%s AND v.returned_at IS NULL",
            (source["map_id"], source["instance_id"], character_id),
        ).fetchone()
        is not None
    )


def follow_company_visit(db, main_id, hero_ids):
    """Reuse the main's real exterior for newly following owned company members."""
    if not hero_ids:
        return
    visit = db.execute(
        "SELECT v.* FROM haven_world_visits v JOIN guild_haven_worlds w ON w.guild_id=v.guild_id "
        "JOIN characters c ON c.id=v.character_id WHERE c.id=%s AND v.returned_at IS NULL "
        "AND c.map_id=w.map_id AND c.instance_id=w.instance_id",
        (main_id,),
    ).fetchone()
    if visit is None:
        return
    for hero_id in hero_ids:
        previous = db.execute(
            "SELECT guild_id,returned_at FROM haven_world_visits "
            "WHERE character_id=%s FOR UPDATE",
            (hero_id,),
        ).fetchone()
        if previous is not None and previous["returned_at"] is None:
            if previous["guild_id"] != visit["guild_id"]:
                raise ValueError("Following hero retains another Haven World visit")
            continue
        db.execute(
            "INSERT INTO haven_world_visits(character_id,guild_id,source) VALUES(%s,%s,%s) "
            "ON CONFLICT(character_id) DO UPDATE SET guild_id=EXCLUDED.guild_id,source=EXCLUDED.source,"
            "entered_at=CURRENT_TIMESTAMP,returned_at=NULL",
            (hero_id, visit["guild_id"], Jsonb(visit["source"])),
        )
