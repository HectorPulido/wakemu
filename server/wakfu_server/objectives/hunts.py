"""Public native monster hunts, transactional spawning and once-per-account wins."""
from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
from psycopg.types.json import Jsonb

LOCK = 747117411


@lru_cache(maxsize=16)
def _decode(raw, digest):
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("Hunt native catalog checksum mismatch")
    return json.loads(raw)


def _document(db, path):
    row = db.execute(
        "SELECT d.raw,d.sha256 FROM native_catalog_documents d JOIN native_catalog_active a ON a.revision=d.revision WHERE a.id=1 AND d.path=%s",
        (path,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing public hunt native source: " + path)
    return _decode(bytes(row["raw"]), row["sha256"])


def inventory(db):
    """Match admitted named dominants/bosses to actual public family habitats."""
    monsters = _document(db, "monsters.json")["monsters"]
    plans = _document(db, "initial-monster-population.json")["plans"]
    by_ref = {m["ref"]: m for m in monsters}
    enabled = db.execute(
        "SELECT r.payload FROM native_catalog_records r JOIN native_catalog_active a ON a.revision=r.revision WHERE a.id=1 AND r.path='native-npc-spell-effect-trees.json' AND r.collection='activation_policy' AND r.record_key='enabled_monsters'"
    ).fetchone()["payload"]
    names_row = db.execute(
        "SELECT value FROM settings WHERE name='admin_map_names'"
    ).fetchone()
    names = names_row["value"] if names_row else {}
    candidates = []
    # Named dominants and royal bosses are source-backed classifications. Never
    # infer eligibility from all enabled NPCs (which include utility actors).
    for monster in monsters:
        name = monster.get("name") or ""
        if not any(
            word in name.lower() for word in (" dominante", " real", "archimonstruo")
        ):
            continue
        from wakfu_server.monster_minigame_policy import require_ordinary_spawn

        try:
            require_ordinary_spawn(monster["ref"])
        except ValueError:
            continue
        policy = enabled.get(str(monster["ref"]))
        if not policy or not monster["native_abilities"]:
            continue
        level = max(1, monster["min_level"], policy["min_level"])
        if level > min(200, monster["max_level"], policy["max_level"]):
            continue
        for plan in plans:
            if plan["instance_id"] != 0:
                continue
            seed = by_ref[plan["members"][0]["reference"]]
            if seed["family_id"] == monster["family_id"]:
                anchor = [plan["members"][0][k] for k in ("x", "y", "z")]
                candidates.append(
                    dict(
                        monster_ref=monster["ref"],
                        monster_name=name,
                        level=level,
                        map_id=plan["map_id"],
                        map_name=names.get(
                            str(plan["map_id"]), f"Map {plan['map_id']}"
                        ),
                        region_id=plan["region_id"],
                        anchor=anchor,
                    )
                )
    return candidates


def tick(db, now=None):
    """Service coordinator; native actor construction/publication stays in World."""
    now = now or datetime.now(timezone.utc)
    if not db.execute(
        "SELECT pg_try_advisory_xact_lock(%s) AS locked", (LOCK,)
    ).fetchone()["locked"]:
        return None
    active = db.execute(
        "SELECT h.*,g.status AS group_status,g.fight_id AS group_fight FROM objectives_public_hunts h LEFT JOIN combat_groups g ON g.map_id=h.map_id AND g.instance_id=0 AND g.group_id=h.group_id WHERE h.status IN('pending','alive','in_fight') FOR UPDATE OF h"
    ).fetchone()
    if active:
        if active["group_status"] == "fighting":
            return db.execute(
                "UPDATE objectives_public_hunts SET status='in_fight',fight_id=%s WHERE id=%s RETURNING *",
                (active["group_fight"], active["id"]),
            ).fetchone()
        if active["expires_at"] <= now:
            db.execute(
                "UPDATE objectives_public_hunts SET status='expired',completed_at=%s WHERE id=%s",
                (now, active["id"]),
            )
        else:
            if active["status"] == "in_fight":
                db.execute(
                    "UPDATE objectives_public_hunts SET status='alive',fight_id=NULL WHERE id=%s",
                    (active["id"],),
                )
            return active
    policy_row = db.execute(
        "SELECT value FROM settings WHERE name='objectives_public_hunts'"
    ).fetchone()
    policy = policy_row["value"] if policy_row else {}
    if not policy.get("enabled", False):
        return None
    lifetime = policy.get("lifetime_seconds", 3600)
    if type(lifetime) is not int or not 60 <= lifetime <= 86400:
        raise ValueError("Invalid public hunt lifetime")
    players = db.execute(
        "SELECT DISTINCT s.account_id,c.level FROM sessions s JOIN characters c ON c.id=s.character_id AND c.account_id=s.account_id WHERE s.expires_at>%s AND c.deleted_at IS NULL AND c.level BETWEEN 1 AND %s ORDER BY s.account_id",
        (now, MAX_CHARACTER_LEVEL),
    ).fetchall()
    if not players:
        return None
    previous = db.execute(
        "SELECT monster_ref,map_id FROM objectives_public_hunts ORDER BY id DESC LIMIT 1"
    ).fetchone()
    count = db.execute("SELECT count(*) AS n FROM objectives_public_hunts").fetchone()[
        "n"
    ]
    level = players[count % len(players)]["level"]
    choices = inventory(db)
    if not choices:
        return None
    # Rotate equally close level candidates; avoid repeating one boss/location.
    choices.sort(key=lambda c: (abs(c["level"] - level), c["monster_ref"], c["map_id"]))
    distance = abs(choices[0]["level"] - level)
    choices = [c for c in choices if abs(c["level"] - level) <= distance + 10]
    if previous and len(choices) > 1:
        choices = [
            c
            for c in choices
            if (c["monster_ref"], c["map_id"])
            != (previous["monster_ref"], previous["map_id"])
        ] or choices
    chosen = choices[count % len(choices)]
    reward = db.execute(
        "SELECT key,policy,revision FROM objectives_reward_policies WHERE key='content-v1.dungeon'"
    ).fetchone()
    if not reward:
        raise ValueError("Missing public hunt reward policy")
    row = db.execute(
        "INSERT INTO objectives_public_hunts(monster_ref,monster_name,level,map_id,map_name,region_id,anchor,reward_snapshot,points,created_at,expires_at) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (
            chosen["monster_ref"],
            chosen["monster_name"],
            chosen["level"],
            chosen["map_id"],
            chosen["map_name"],
            chosen["region_id"],
            Jsonb(chosen["anchor"]),
            Jsonb(dict(reward)),
            int(policy.get("points", 100)),
            now,
            now + timedelta(seconds=lifetime),
        ),
    ).fetchone()
    db.execute("SELECT pg_notify('wakemu_objectives_updates','all')")
    return row


def is_hunt(db, key):
    return (
        db.execute(
            "SELECT 1 FROM objectives_public_hunts WHERE map_id=%s AND %s=0 AND group_id=%s",
            key,
        ).fetchone()
        is not None
    )


def settle_group(db, key, fight_id, defeated):
    """Called under the existing exact group lease before native group finish."""
    hunt = db.execute(
        "SELECT * FROM objectives_public_hunts WHERE map_id=%s AND %s=0 AND group_id=%s FOR UPDATE",
        key,
    ).fetchone()
    if hunt is None or hunt["status"] in ("defeated", "expired"):
        return None
    if not defeated:
        return db.execute(
            "UPDATE objectives_public_hunts SET status='alive',fight_id=NULL WHERE id=%s RETURNING *",
            (hunt["id"],),
        ).fetchone()
    from .repository import reserve_rewards
    from .points import award_points

    definition = db.execute(
        "SELECT definition FROM objectives_definitions WHERE key='public-world-hunt'"
    ).fetchone()["definition"]
    period = "hunt:" + str(hunt["id"])
    winners = db.execute(
        "SELECT DISTINCT ON(p.account_id) p.account_id,p.character_id,c.level FROM combat_fight_participants p JOIN characters c ON c.id=p.character_id AND c.account_id=p.account_id WHERE p.fight_id=%s AND p.team=0 AND NOT EXISTS(SELECT 1 FROM combat_pve_withdrawals w WHERE w.fight_id=p.fight_id AND w.character_id=p.character_id) AND NOT EXISTS(SELECT 1 FROM fight_health_exits e WHERE e.fight_id=p.fight_id AND e.character_id=p.character_id AND e.reason='abort') ORDER BY p.account_id,p.character_id",
        (fight_id,),
    ).fetchall()
    for winner in winners:
        inserted = db.execute(
            "INSERT INTO objectives_public_hunt_winners(hunt_id,account_id,character_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING RETURNING account_id",
            (hunt["id"], winner["account_id"], winner["character_id"]),
        ).fetchone()
        if not inserted:
            continue
        db.execute(
            "INSERT INTO objectives_account_progress(account_id,definition_key,period_key,definition_revision,counters,completed_at,reward_character_id) VALUES(%s,'public-world-hunt',%s,1,%s,CURRENT_TIMESTAMP,%s) ON CONFLICT DO NOTHING",
            (winner["account_id"], period, Jsonb({"kill": 1}), winner["character_id"]),
        )
        db.execute(
            "INSERT INTO objectives_progress(character_id,definition_key,period_key,definition_revision,counters,completed_at) VALUES(%s,'public-world-hunt',%s,1,%s,CURRENT_TIMESTAMP) ON CONFLICT DO NOTHING",
            (winner["character_id"], period, Jsonb({"kill": 1})),
        )
        policy = hunt["reward_snapshot"]
        reserve_rewards(
            db,
            winner["character_id"],
            definition,
            period,
            level=winner["level"],
            policies={policy["key"]: policy},
        )
        award_points(
            db,
            winner["account_id"],
            "public-hunt:" + str(hunt["id"]),
            hunt["points"],
            character_id=winner["character_id"],
            level=winner["level"],
            category="public_hunt",
            title="World hunt: " + hunt["monster_name"],
        )
    result = db.execute(
        "UPDATE objectives_public_hunts SET status='defeated',fight_id=%s,completed_at=CURRENT_TIMESTAMP WHERE id=%s RETURNING *",
        (fight_id, hunt["id"]),
    ).fetchone()
    db.execute("SELECT pg_notify('wakemu_objectives_updates','all')")
    return result


def _region_name(db, hunt):
    """Use the exact native-seeded territory binding, never fuzzy map names."""
    key = f"content-v1.region.{hunt['map_id']}.{hunt['region_id']}"
    row = db.execute(
        "SELECT definition FROM objectives_definitions WHERE key=%s", (key,)
    ).fetchone()
    if row is None:
        return None
    definition = row["definition"]
    binding = {"map_id": hunt["map_id"], "region_id": hunt["region_id"]}
    if not any(
        objective.get("event") == "region_entered"
        and objective.get("filters") == binding
        for objective in definition.get("objectives", [])
    ):
        return None
    title = definition.get("title", "")
    prefix, suffix = "Territory: ", f" [{hunt['region_id']}]"
    if not title.startswith(prefix) or not title.endswith(suffix):
        return None
    name = title[len(prefix) : -len(suffix)].strip()
    # Source extraction falls back to the map label if no localization exists.
    return name if name and name != hunt["map_name"] else None


def snapshot(db, identity=None):
    row = db.execute(
        "SELECT * FROM objectives_public_hunts WHERE status IN('alive','in_fight') ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    level = row["level"]
    if identity and identity.get("character_id"):
        actor = db.execute(
            "SELECT level FROM characters WHERE id=%s AND account_id=%s",
            (identity["character_id"], identity["account_id"]),
        ).fetchone()
        if actor:
            level = actor["level"]
    rewards = next(
        b["rewards"]
        for b in row["reward_snapshot"]["policy"]["bands"]
        if b["minimum"] <= level <= b["maximum"]
    )
    region_name = _region_name(db, row)
    location = " · ".join(part for part in (row["map_name"], region_name) if part)
    search_area = (
        f"{region_name} in {row['map_name']}"
        if region_name
        else f"the wild habitats of {row['map_name']}"
    )
    return dict(
        id=row["id"],
        monster_ref=row["monster_ref"],
        monster_name=row["monster_name"],
        level=row["level"],
        map_id=row["map_id"],
        map_name=row["map_name"],
        region_name=region_name,
        location=location,
        clue=f"Search {search_area}. Find {row['monster_name']} roaming in the public world.",
        status=row["status"],
        expires_at=row["expires_at"],
        points=row["points"],
        rewards=rewards,
    )


def _spawn_position(db, hunt):
    from wakfu_server.combat_terrain import map_geometry

    geometry = map_geometry(hunt["map_id"])
    anchor = tuple(hunt["anchor"])
    columns = {}
    for cell in geometry["cells"]:
        columns.setdefault(tuple(cell[:2]), []).append(tuple(cell))
    connected = {tuple(a) for a, b in geometry["edges"]} | {
        tuple(b) for a, b in geometry["edges"]
    }
    blocked = set()
    for row in db.execute(
        "SELECT members FROM combat_groups WHERE map_id=%s AND instance_id=0 AND status<>'defeated'",
        (hunt["map_id"],),
    ):
        blocked.update((m["x"], m["y"]) for m in row["members"])
    for row in db.execute(
        "SELECT x,y FROM planted_resources WHERE map_id=%s AND instance_id=0 UNION SELECT c.x,c.y FROM characters c JOIN sessions s ON s.character_id=c.id WHERE c.map_id=%s AND c.instance_id=0 AND s.expires_at>CURRENT_TIMESTAMP",
        (hunt["map_id"], hunt["map_id"]),
    ):
        blocked.add((row["x"], row["y"]))
    from wakfu_server.planting_cells import surface

    for cell in sorted(
        connected,
        key=lambda c: (
            abs(c[0] - anchor[0]) + abs(c[1] - anchor[1]),
            abs(c[2] - anchor[2]),
            c,
        ),
    ):
        if (
            len(columns[cell[:2]]) != 1
            or cell[:2] in blocked
            or abs(cell[0] - anchor[0]) + abs(cell[1] - anchor[1]) > 12
            or abs(cell[2] - anchor[2]) > 1
        ):
            continue
        if surface(hunt["map_id"], *cell)["region_id"] != hunt["region_id"]:
            continue
        return cell
    return None


def publish(store, groups, world):
    """World dispatcher outbox: commit native actor first, then broadcast once.

    The groups lock serializes publication against a concurrent player claiming
    this group; PostgreSQL fencing makes independent dispatchers idempotent.
    Players entering later receive the normal authoritative world snapshot.
    """
    from wakfu_server.monsters import owned_instance
    from wakfu_server.monster_minigame_policy import require_ordinary_spawn
    from wakfu_server.npc_actor_identity import allocate_block
    from wakfu_server.combat_monster_world import spawn_group, remove_message

    packets = []
    acknowledge = []
    removed = []
    with groups.lock:
        with store.connection() as db, db.transaction():
            if not db.execute(
                "SELECT pg_try_advisory_xact_lock(%s) AS locked", (LOCK,)
            ).fetchone()["locked"]:
                return []
            # A previously queued request is not permission to create actors
            # after the last real World character has disconnected. Web tokens
            # never count as presence. Hold the selected session through commit.
            if (
                db.execute(
                    "SELECT s.account_id FROM sessions s JOIN characters c "
                    "ON c.id=s.character_id AND c.account_id=s.account_id "
                    "WHERE s.expires_at>CURRENT_TIMESTAMP AND c.deleted_at IS NULL "
                    "ORDER BY s.account_id LIMIT 1 FOR SHARE OF s"
                ).fetchone()
                is None
            ):
                return []
            for hunt in db.execute(
                "SELECT * FROM objectives_public_hunts WHERE status='expired' AND removed_at IS NULL FOR UPDATE"
            ).fetchall():
                if hunt["group_id"] is not None:
                    group = db.execute(
                        "SELECT * FROM combat_groups WHERE map_id=%s AND instance_id=0 AND group_id=%s FOR UPDATE",
                        (hunt["map_id"], hunt["group_id"]),
                    ).fetchone()
                    if group and group["status"] == "fighting":
                        continue
                    db.execute(
                        "UPDATE combat_groups SET status='defeated',defeated_at=CURRENT_TIMESTAMP,revision=revision+1 WHERE map_id=%s AND instance_id=0 AND group_id=%s AND status='available'",
                        (hunt["map_id"], hunt["group_id"]),
                    )
                    if group:
                        packets.append(
                            (
                                hunt["map_id"],
                                *remove_message([m["id"] for m in group["members"]]),
                            )
                        )
                removed.append(hunt["id"])
            hunt = db.execute(
                "SELECT * FROM objectives_public_hunts WHERE status='pending' FOR UPDATE"
            ).fetchone()
            if hunt and hunt["expires_at"] > datetime.now(timezone.utc):
                require_ordinary_spawn(hunt["monster_ref"])
                position = _spawn_position(db, hunt)
                if position is None:
                    db.execute(
                        "UPDATE objectives_public_hunts SET status='expired',completed_at=CURRENT_TIMESTAMP,removed_at=CURRENT_TIMESTAMP WHERE id=%s",
                        (hunt["id"],),
                    )
                else:
                    base = allocate_block(db, 1)
                    member = owned_instance(
                        hunt["monster_ref"],
                        hunt["level"],
                        -base,
                        map_id=hunt["map_id"],
                        instance_id=0,
                        x=position[0],
                        y=position[1],
                        z=position[2],
                    )
                    groups.register_transaction(db, hunt["map_id"], 0, base, [member])
                    db.execute(
                        "UPDATE objectives_public_hunts SET status='alive',group_id=%s,monster_id=%s,anchor=%s WHERE id=%s",
                        (base, -base, Jsonb(list(position)), hunt["id"]),
                    )
                db.execute("SELECT pg_notify('wakemu_objectives_updates','all')")
            # Replay an interrupted publication by removing its exact identity
            # first. This keeps the native actor registry free of duplicates.
            for pending in db.execute(
                "SELECT h.id,h.map_id,h.group_id,g.members FROM objectives_public_hunts h JOIN combat_groups g ON g.map_id=h.map_id AND g.instance_id=0 AND g.group_id=h.group_id WHERE h.status='alive' AND h.published_at IS NULL AND g.status='available' ORDER BY h.id FOR UPDATE OF h"
            ).fetchall():
                packets.append(
                    (
                        pending["map_id"],
                        *remove_message([m["id"] for m in pending["members"]]),
                    )
                )
                packets.append(
                    (
                        pending["map_id"],
                        12608,
                        spawn_group(pending["members"], group_id=pending["group_id"]),
                    )
                )
                acknowledge.append(pending["id"])
        for map_id, opcode, body in packets:
            world.emit_location(map_id, 0, opcode, body)
        if acknowledge or removed:
            with store.connection() as db:
                if acknowledge:
                    db.execute(
                        "UPDATE objectives_public_hunts SET published_at=CURRENT_TIMESTAMP WHERE id=ANY(%s) AND published_at IS NULL",
                        (acknowledge,),
                    )
                if removed:
                    db.execute(
                        "UPDATE objectives_public_hunts SET removed_at=CURRENT_TIMESTAMP WHERE id=ANY(%s) AND removed_at IS NULL",
                        (removed,),
                    )
    return packets
