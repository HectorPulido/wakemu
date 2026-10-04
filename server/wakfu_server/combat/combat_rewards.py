"""Explicit local victory rewards, independent of official reward/drop data.

Schema is an additive, lazy extension to Store schema5. Award keys include
session generation, character and fight ID; a session replacement cannot
replay an old award. No item loot is generated.
"""
from dataclasses import dataclass
from .progression import level_xp, XP_BY_LEVEL


@dataclass(frozen=True)
class Policy:
    xp: int = 0
    kamas: int = 0

    def __post_init__(self):
        for amount in (self.xp, self.kamas):
            if type(amount) is not int or not 0 <= amount < 2**63:
                raise ValueError("Invalid local reward amount")
        if self.kamas >= 2**31:
            raise ValueError("FightReport gainedKamas requires signed32 amount")


def schema(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS character_progression (
        character_id INTEGER PRIMARY KEY REFERENCES characters(id) ON DELETE CASCADE,
        xp INTEGER NOT NULL CHECK(xp>=0), kamas INTEGER NOT NULL DEFAULT 0 CHECK(kamas>=0))"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS account_wallets (
        account_id INTEGER PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE,
        kamas INTEGER NOT NULL DEFAULT 0 CHECK(kamas>=0))"""
    )
    db.execute(
        """CREATE TABLE IF NOT EXISTS fight_rewards (
        generation TEXT NOT NULL, fight_id INTEGER NOT NULL,
        character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
        account_id INTEGER NOT NULL REFERENCES accounts(id),
        xp INTEGER NOT NULL, kamas INTEGER NOT NULL, created_at REAL NOT NULL,
        PRIMARY KEY(generation,fight_id,character_id))"""
    )

    columns = {row["name"] for row in db.execute("PRAGMA table_info(fight_rewards)")}
    for name in ("start_xp", "end_xp", "start_level", "end_level"):
        if name not in columns:
            db.execute(f"ALTER TABLE fight_rewards ADD COLUMN {name} INTEGER")


def load(db, character):
    """Load totals, initializing manual-level characters at their native threshold."""
    schema(db)
    db.execute(
        "INSERT OR IGNORE INTO character_progression(character_id,xp) VALUES(?,?)",
        (character["id"], level_xp(character["level"])),
    )
    row = db.execute(
        "SELECT xp,kamas FROM character_progression WHERE character_id=?",
        (character["id"],),
    ).fetchone()
    # Preserve explicit administrative level changes; never lower level200.
    xp = max(row["xp"], level_xp(character["level"]))
    if xp != row["xp"]:
        db.execute(
            "UPDATE character_progression SET xp=? WHERE character_id=?",
            (xp, character["id"]),
        )
    db.execute(
        "INSERT OR IGNORE INTO account_wallets(account_id,kamas) "
        "SELECT ?,COALESCE(SUM(p.kamas),0) FROM character_progression p "
        "JOIN characters c ON c.id=p.character_id WHERE c.account_id=?",
        (character["account_id"], character["account_id"]),
    )
    wallet = db.execute(
        "SELECT kamas FROM account_wallets WHERE account_id=?",
        (character["account_id"],),
    ).fetchone()
    return dict(xp=xp, kamas=wallet["kamas"])


def award(store, account_id, generation, character_id, fight, policy=Policy()):
    """Award a winning controlled participant once, under the current lease.

    Returns {character, awarded, xp, kamas}; character contains updated total
    xp/kamas and level. xp/kamas at the top level are this fight's amounts.
    HP maximum must be refreshed by health_store when a level changes.
    """
    if not isinstance(policy, Policy):
        raise ValueError("Explicit local reward Policy required")
    actor = fight.actors.get(character_id)
    if (
        fight.phase != "finished"
        or fight.winner not in (0, 1)
        or actor is None
        or not actor.controlled
        or actor.owner_id != account_id
        or actor.team != fight.winner
    ):
        raise ValueError("Rewards require the own winning fight participant")
    if type(fight.id) is not int or not 0 < fight.id < 2**31:
        raise ValueError("Invalid reward fight identity")
    with store.connection() as db:
        db.execute("BEGIN IMMEDIATE")
        schema(db)
        lease = db.execute(
            "SELECT character_id FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
            (account_id, generation, store.clock()),
        ).fetchone()
        if lease is None or lease["character_id"] != character_id:
            raise ValueError("Session or character lease is stale")
        character = store.character(account_id, character_id, db)
        totals = load(db, character)
        existing = db.execute(
            "SELECT * FROM fight_rewards WHERE generation=? AND fight_id=? AND character_id=?",
            (generation, fight.id, character_id),
        ).fetchone()
        if existing is not None:
            return dict(
                character={**character, **totals},
                awarded=False,
                xp=existing["xp"],
                kamas=existing["kamas"],
                xp_info=_xp_info(existing),
            )
        xp, kamas = totals["xp"] + policy.xp, totals["kamas"] + policy.kamas
        if max(xp, kamas) >= 2**63:
            raise ValueError("Reward total exceeds native signed64 storage")
        level = max(
            character["level"],
            max(level for level, threshold in XP_BY_LEVEL.items() if threshold <= xp),
        )
        db.execute(
            "UPDATE character_progression SET xp=? WHERE character_id=?",
            (xp, character_id),
        )
        db.execute(
            "UPDATE account_wallets SET kamas=? WHERE account_id=?", (kamas, account_id)
        )
        db.execute(
            "UPDATE characters SET level=? WHERE account_id=? AND id=?",
            (level, account_id, character_id),
        )
        db.execute(
            "INSERT INTO fight_rewards(generation,fight_id,character_id,account_id,xp,kamas,created_at,start_xp,end_xp,start_level,end_level) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (
                generation,
                fight.id,
                character_id,
                account_id,
                policy.xp,
                policy.kamas,
                store.clock(),
                totals["xp"],
                xp,
                character["level"],
                level,
            ),
        )
        return dict(
            character={
                **store.character(account_id, character_id, db),
                "xp": xp,
                "kamas": kamas,
            },
            awarded=True,
            xp=policy.xp,
            kamas=policy.kamas,
            xp_info=dict(
                end_xp=xp,
                won_xp=policy.xp,
                start_level=character["level"],
                end_level=level,
            ),
        )


def wallet(store, account_id):
    """Current account-wide balance, including login before character selection."""
    with store.connection() as db:
        schema(db)
        if (
            db.execute("SELECT id FROM accounts WHERE id=?", (account_id,)).fetchone()
            is None
        ):
            raise ValueError("Unknown local account")
        db.execute(
            "INSERT OR IGNORE INTO account_wallets(account_id,kamas) "
            "SELECT ?,COALESCE(SUM(p.kamas),0) FROM character_progression p "
            "JOIN characters c ON c.id=p.character_id WHERE c.account_id=?",
            (account_id, account_id),
        )
        return db.execute(
            "SELECT kamas FROM account_wallets WHERE account_id=?", (account_id,)
        ).fetchone()["kamas"]


def _xp_info(receipt):
    if receipt["xp"] == 0:
        return None
    if any(receipt[key] is None for key in ("end_xp", "start_level", "end_level")):
        raise ValueError("Legacy reward has no authoritative XP receipt")
    return dict(
        end_xp=receipt["end_xp"],
        won_xp=receipt["xp"],
        start_level=receipt["start_level"],
        end_level=receipt["end_level"],
    )


def report_metadata(metadata, character_id, reward):
    """Attach a committed award receipt to an existing own player report record."""
    if (
        reward["character"]["id"] != character_id
        or metadata.get(character_id, {}).get("kind") != "player"
    ):
        raise ValueError("Reward receipt does not match report participant")
    result = {identity: dict(record) for identity, record in metadata.items()}
    result[character_id]["gained_kamas"] = reward["kamas"]
    if reward["xp"]:
        if not reward.get("xp_info"):
            raise ValueError("Missing authoritative XP receipt")
        result[character_id]["xp_info"] = dict(reward["xp_info"])
    return result
