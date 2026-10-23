"""Owned native citizenship and PvP-rank facts, distinct from ecology/duels.

Missing legacy authority is unknown. Only actual character construction may
initialize the original empty score map/rank zero; no reward policy lives here.
"""
from dataclasses import dataclass, asdict
from hashlib import sha256
import json

SOURCE = "native.bVr.ftp.fto.owned.v1"
NPC_SOURCE = "native.bje.dnJ.ftq.v1"
VERSION = "native-national-component-20261020-v1"
NATIVE_SOURCE_SHA256 = (
    "89bff63987a7fce2806aa85d2851cefe96b08e24ee22e67d9a39ab63de9c4400"
)


def _integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Invalid native national " + name)
    return value


def _digest(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


@dataclass(frozen=True)
class NationalSnapshot:
    actor_id: int
    account_id: int
    nation_id: int
    rank_id: int
    crime_scores: tuple
    rank_thresholds: tuple
    version: str
    provenance: str
    source: str = SOURCE
    source_sha256: str = ""

    def __post_init__(self):
        _integer(self.actor_id, "actor", 1, (1 << 63) - 1)
        _integer(self.account_id, "account", 1, (1 << 63) - 1)
        _integer(self.nation_id, "nation", 0, (1 << 31) - 1)
        _integer(self.rank_id, "rank", 0, 127)
        if (
            self.source != SOURCE
            or type(self.version) is not str
            or not self.version
            or self.provenance
            not in ("native_constructor", "native_import", "wakemu_policy_epoch")
        ):
            raise ValueError("Missing native national progression provenance")
        for rows, label in (
            (self.crime_scores, "crime"),
            (self.rank_thresholds, "rank"),
        ):
            if type(rows) is not tuple or any(
                type(row) is not tuple or len(row) != 2 for row in rows
            ):
                raise ValueError("Invalid native national " + label + " population")
            if rows != tuple(sorted(rows)) or len({row[0] for row in rows}) != len(
                rows
            ):
                raise ValueError(
                    "Duplicate or unordered national " + label + " identity"
                )
        for nation, score in self.crime_scores:
            _integer(nation, "score nation", 0, (1 << 31) - 1)
            _integer(score, "signed crime", -(1 << 31), (1 << 31) - 1)
        for rank, threshold in self.rank_thresholds:
            _integer(rank, "rank identity", 0, 127)
            _integer(threshold, "merit threshold", 0, (1 << 31) - 1)
        if (
            not self.rank_thresholds
            or self.rank_thresholds[0] != (0, 0)
            or self.rank_id not in dict(self.rank_thresholds)
            or tuple(t for _, t in self.rank_thresholds)
            != tuple(sorted(set(t for _, t in self.rank_thresholds)))
        ):
            raise ValueError("Missing indexed native rank authority")
        payload = asdict(self)
        payload.pop("source_sha256")
        expected = _digest(payload)
        if not self.source_sha256:
            object.__setattr__(self, "source_sha256", expected)
        elif self.source_sha256 != expected:
            raise ValueError("Native national snapshot source changed")

    def require_owner(self, actor_id, account_id, nation_id):
        if (self.actor_id, self.account_id, self.nation_id) != (
            actor_id,
            account_id,
            nation_id,
        ):
            raise ValueError("National progression owner or nation mismatch")
        return self

    def record(self):
        return asdict(self)

    @classmethod
    def from_record(cls, record):
        if not isinstance(record, dict) or set(record) != set(cls.__dataclass_fields__):
            raise ValueError("Missing owned native national progression snapshot")
        values = dict(record)
        for key in ("crime_scores", "rank_thresholds"):
            rows = values[key]
            if not isinstance(rows, (tuple, list)) or any(
                not isinstance(row, (tuple, list)) for row in rows
            ):
                raise ValueError("Malformed native national population")
            values[key] = tuple(tuple(row) for row in rows)
        return cls(**values)


def _component(context):
    if context.get("actor_kind") == "native_companion_npc":
        if context.get("native_national_component") != NPC_SOURCE:
            raise ValueError("Missing actual NPC ftq national component")
        return None
    if context.get("actor_kind") != "player":
        raise ValueError("Missing native national actor identity")
    value = NationalSnapshot.from_record(context.get("national_progression"))
    return value.require_owner(
        context.get("actor_id"), context.get("account_id"), context.get("nation_id")
    )


def crime_score(context, nation=None):
    component = _component(context)
    if nation is not None:
        _integer(nation, "query nation", -(1 << 63), (1 << 63) - 1)
        nation = (nation + (1 << 31)) % (1 << 32) - (1 << 31)
    if component is None:
        return 0  # Original bje.dnJ -> ftq.XB, never the owner's component.
    return dict(component.crime_scores).get(
        component.nation_id if nation is None else nation, 0
    )


def has_pvp_rank(context, required):
    _integer(required, "required rank", -(1 << 63), (1 << 63) - 1)
    required = (required + 128) % 256 - 128  # eMB's native long/int/byte cast.
    component = _component(context)
    if component is None:
        # ftq.glV is fxk.RANK_1. Its threshold is zero; invalid enum IDs remain
        # unknown rather than silently clamping to an available rank.
        if not 0 <= required <= 9:
            raise ValueError("Unknown native required PvP rank")
        return required == 0
    thresholds = dict(component.rank_thresholds)
    if required not in thresholds:
        raise ValueError("Unknown native required PvP rank")
    return thresholds[component.rank_id] >= thresholds[required]


def normalized_score(current_nation, nation, score):
    """Original bVr.gp coercion at mutation, never a query-time rewrite."""
    _integer(current_nation, "current nation", 0, (1 << 31) - 1)
    _integer(nation, "changed nation", 0, (1 << 31) - 1)
    _integer(score, "changed signed crime", -(1 << 31), (1 << 31) - 1)
    return 0 if score > 0 and nation != current_nation else score


def nation_identity(context):
    if context.get("actor_kind") == "native_companion_npc":
        _component(context)
        return 0
    if context.get("actor_kind") != "player":
        raise ValueError("Missing native nation identity")
    return _integer(context.get("nation_id"), "owned current nation", 0, (1 << 31) - 1)


def _transaction(db):
    from psycopg.pq import TransactionStatus

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("National authority requires an owned transaction")


def _ranks(db, version):
    rows = db.execute(
        "SELECT r.rank_id,r.merit_threshold,v.source_sha256 FROM native_national_pvp_ranks r "
        "JOIN native_national_progression_versions v USING(version) WHERE r.version=%s ORDER BY r.rank_id",
        (version,),
    ).fetchall()
    if (
        version != VERSION
        or len(rows) != 10
        or any(row["source_sha256"] != NATIVE_SOURCE_SHA256 for row in rows)
    ):
        raise ValueError("Missing qualified native national rank population")
    return tuple((row["rank_id"], row["merit_threshold"]) for row in rows)


def initialize(db, account_id, character_id):
    """Only the real new-character constructor calls this empty-component path."""
    _transaction(db)
    _ranks(db, VERSION)
    if (
        db.execute(
            "SELECT 1 FROM characters WHERE account_id=%s AND id=%s AND deleted_at IS NULL",
            (account_id, character_id),
        ).fetchone()
        is None
    ):
        raise ValueError("Missing national constructor owner")
    db.execute(
        "INSERT INTO character_national_authority(character_id,account_id,version,rank_id,provenance) "
        "VALUES(%s,%s,%s,0,'native_constructor') ON CONFLICT(character_id) DO NOTHING",
        (character_id, account_id, VERSION),
    )


def load(db, account_id, character_id, nation_id):
    """Read durable authority; a missing legacy row is never initialized here."""
    row = db.execute(
        "SELECT a.*,COALESCE(n.nation_id,0) AS nation_id,COALESCE("
        "(SELECT array_agg(ARRAY[s.nation_id,s.score] ORDER BY s.nation_id) "
        "FROM character_national_crime_scores s WHERE s.character_id=a.character_id "
        "AND s.account_id=a.account_id),'{}'::integer[]) AS crime_population "
        "FROM character_national_authority a "
        "JOIN characters c ON c.id=a.character_id AND c.account_id=a.account_id "
        "LEFT JOIN character_chat_nations n ON n.character_id=c.id "
        "WHERE a.character_id=%s AND a.account_id=%s AND c.deleted_at IS NULL",
        (character_id, account_id),
    ).fetchone()
    if row is None:
        return None
    if row["nation_id"] != nation_id:
        raise ValueError("National identity changed during owned snapshot hydration")
    scores = tuple(tuple(entry) for entry in row["crime_population"])
    return NationalSnapshot(
        character_id,
        account_id,
        nation_id,
        row["rank_id"],
        scores,
        _ranks(db, row["version"]),
        row["version"],
        row["provenance"],
    )


def restore_import(db, account_id, character_id, record, *, receipt_key):
    """Restore an accredited native snapshot, never a client-earned reward.

    The caller must accredit its import source and own the player locks. This
    is not exposed by a network request, command, duel or ecological gauge.
    """
    _transaction(db)
    if type(receipt_key) is not str or not 1 <= len(receipt_key) <= 160:
        raise ValueError("Missing national import receipt")
    incoming = NationalSnapshot.from_record(record)
    owner = db.execute(
        "SELECT COALESCE(n.nation_id,0) AS nation_id FROM characters c "
        "LEFT JOIN character_chat_nations n ON n.character_id=c.id "
        "WHERE c.id=%s AND c.account_id=%s AND c.deleted_at IS NULL FOR UPDATE OF c",
        (character_id, account_id),
    ).fetchone()
    if owner is None:
        raise ValueError("Missing national import owner")
    incoming.require_owner(character_id, account_id, owner["nation_id"])
    if incoming.provenance != "native_import" or incoming.rank_thresholds != _ranks(
        db, incoming.version
    ):
        raise ValueError("Unqualified native national import source")
    previous = db.execute(
        "SELECT source_digest FROM character_national_import_receipts "
        "WHERE character_id=%s AND receipt_key=%s",
        (character_id, receipt_key),
    ).fetchone()
    if previous is not None:
        if previous["source_digest"] != incoming.source_sha256:
            raise ValueError("National import source changed on replay")
        return False
    # An accredited replacement supersedes the custom merit epoch's previous
    # numerical baseline. The next earned result starts from the imported rank.
    db.execute(
        "DELETE FROM character_national_merit WHERE character_id=%s AND account_id=%s",
        (character_id, account_id),
    )
    db.execute(
        "INSERT INTO character_national_authority(character_id,account_id,version,rank_id,provenance) "
        "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(character_id) DO UPDATE SET "
        "version=EXCLUDED.version,rank_id=EXCLUDED.rank_id,provenance=EXCLUDED.provenance,"
        "revision=character_national_authority.revision+1",
        (
            character_id,
            account_id,
            incoming.version,
            incoming.rank_id,
            incoming.provenance,
        ),
    )
    db.execute(
        "DELETE FROM character_national_crime_scores WHERE character_id=%s AND account_id=%s",
        (character_id, account_id),
    )
    for nation, score in incoming.crime_scores:
        db.execute(
            "INSERT INTO character_national_crime_scores VALUES(%s,%s,%s,%s)",
            (character_id, account_id, nation, score),
        )
    db.execute(
        "INSERT INTO character_national_import_receipts VALUES(%s,%s,%s,%s)",
        (character_id, account_id, receipt_key, incoming.source_sha256),
    )
    return True


def owned_snapshot(character):
    context = character.get("equipment_criterion_context")
    if not isinstance(context, dict) or context.get("national_progression") is None:
        return None
    return NationalSnapshot.from_record(context["national_progression"]).require_owner(
        character["id"], character["account_id"], character["nation_id"]
    )


def citizen_section(character):
    """qT/qW signed citizenship; unsupported offence-law rows stay neutral.

    Offence-law qX records are a distinct unimplemented producer. They are
    never synthesized from a negative score or an assumed outlaw threshold.
    """
    import struct

    snapshot = owned_snapshot(character)
    if snapshot is None:
        return None  # Preserve the existing empty rendering for unknown legacy.
    if len(snapshot.crime_scores) > 65535:
        raise ValueError("Native citizenship population exceeds unsigned16")
    return (
        struct.pack(">H", len(snapshot.crime_scores))
        + b"".join(
            struct.pack(">ii", nation, score) for nation, score in snapshot.crime_scores
        )
        + bytes(2)
    )
