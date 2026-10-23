"""Typed native company publication and original table138 rank lookup.

A missing company and a registered company with score zero are distinct:
original eJD returns -1 for absence; eSO's out-of-range fallback is rank12.
The original company.rank.tuto and live native deltas define account player
real levels times three plus linked, unlocked companion levels times one.
"""
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import struct

SOURCE_SHA256 = "2230321abc52940c8b1c4dec0485e37668fd253392598465baaa430329c242b0"


@lru_cache(maxsize=1)
def ranks():
    raw = Path(__file__).with_name("native_company_ranks.json").read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Conflicting original company rank authority")
    document = json.loads(raw)
    if document["table_id"] != 138 or document["record_class"] != "aKK":
        raise ValueError("Invalid original company rank table")
    return tuple(document["rows"])


def rank_for_score(score):
    if type(score) is not int or not -(1 << 31) <= score < (1 << 31):
        raise ValueError("Invalid native company score")
    rows = ranks()
    for row in rows:
        if row["minimum_score"] <= score <= row["maximum_score"]:
            return row["rank"]
    # Original eSN.fIR selects the row with greatest upper bound, including
    # scores below the first interval. Absence must never become score zero.
    return max(rows, key=lambda row: row["maximum_score"])["rank"]


@dataclass(frozen=True)
class CompanySnapshot:
    account_id: int
    chief_id: int
    nation_id: int
    guild_id: int
    score: int
    active: bool

    def __post_init__(self):
        if any(
            type(value) is not int or not 0 < value < (1 << 63)
            for value in (self.account_id, self.chief_id)
        ):
            raise ValueError("Invalid native company ownership")
        if type(self.guild_id) is not int or not 0 <= self.guild_id < (1 << 63):
            raise ValueError("Invalid native company guild")
        from wakfu_server.nation_state import nation_id

        nation_id(dict(nation_id=self.nation_id))
        rank_for_score(self.score)
        if type(self.active) is not bool:
            raise ValueError("Invalid native company activation")

    def require_owner(self, account_id):
        if type(account_id) is not int or account_id != self.account_id:
            raise ValueError("Foreign native company authority")
        return self

    def require_chief(self, character_id):
        if type(character_id) is not int or character_id != self.chief_id:
            raise ValueError("Foreign native company chief")
        return self

    def record(self):
        return dict(
            source=SOURCE_SHA256,
            account_id=self.account_id,
            chief_id=self.chief_id,
            nation_id=self.nation_id,
            guild_id=self.guild_id,
            score=self.score,
            active=self.active,
        )

    @classmethod
    def from_record(cls, value):
        if (
            not isinstance(value, dict)
            or set(value)
            != {
                "source",
                "account_id",
                "chief_id",
                "nation_id",
                "guild_id",
                "score",
                "active",
            }
            or value["source"] != SOURCE_SHA256
        ):
            raise ValueError("Missing typed native company snapshot")
        return cls(**{key: value[key] for key in value if key != "source"})

    @property
    def rank(self):
        return rank_for_score(self.score)

    def packet(self):
        # One eDS.COMPANY member; eSJ has an empty optional company name.
        return 13873, struct.pack(
            ">IIqqiqIiB",
            1,
            1,
            self.account_id,
            self.chief_id,
            self.nation_id,
            self.guild_id,
            0,
            self.score,
            int(self.active),
        )


def rank_for_snapshot(snapshot):
    if snapshot is None:
        return -1
    if not isinstance(snapshot, CompanySnapshot):
        raise ValueError("Missing typed native company authority")
    return snapshot.rank


def load(db, character):
    """Derive one current company from durable owned real progression only.

    One bounded aggregate row avoids hydrating every character or companion
    equipment tree. Deleted players, unlinked/relocked companions and another
    account's rows cannot contribute. Native eSy.cmZ uses the uncapped MP XP
    level; its temporary fighter/controller cap does not change company points.
    """
    from wakfu_server.companions import level_for_xp
    from wakfu_server.owned_social_context import OwnedSocialContext

    social = OwnedSocialContext.from_record(character.get("native_social_context"))
    social.require_owner(character["id"], character["account_id"])

    row = db.execute(
        "SELECT (SELECT SUM(p.level) FROM characters p WHERE p.account_id=c.account_id "
        "AND p.deleted_at IS NULL) AS player_levels, "
        "(SELECT COALESCE(array_agg(p.xp ORDER BY p.id),ARRAY[]::bigint[]) "
        "FROM account_companions p WHERE p.account_id=c.account_id "
        "AND p.linked AND p.unlocked) AS companion_xp "
        "FROM characters c WHERE c.id=%s AND c.account_id=%s AND c.deleted_at IS NULL",
        (character["id"], character["account_id"]),
    ).fetchone()
    if row is None:
        raise ValueError("Unavailable owned native company chief")
    levels, experience = row["player_levels"], row["companion_xp"]
    if type(levels) is not int or levels <= 0 or not isinstance(experience, list):
        raise ValueError("Invalid durable native company progression")
    score = 3 * levels + sum(level_for_xp(xp) for xp in experience)
    return CompanySnapshot(
        character["account_id"],
        character["id"],
        social.nation_id,
        0 if social.guild_id is None else social.guild_id,
        score=score,
        active=True,
    )


def preselection_packet(account_id):
    """Preserve the inactive login placeholder without owned rank authority.

    Its historical score1 sentinel avoids eSO's out-of-range score0 fallback;
    this wire-only record is not an earned or absent-company predicate receipt.
    """
    if type(account_id) is not int or not 0 < account_id < (1 << 63):
        raise ValueError("Invalid preselection company account")
    return 13873, struct.pack(">IIqqiqIiB", 1, 1, account_id, 0, 0, 0, 0, 1, 0)
