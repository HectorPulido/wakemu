"""Native mercenary UI admission from a fresh authenticated board offer.

The client opens the UI locally. Opcode12864 contains no board ID; it is never
accepted without an unexpired offer bound to this selected owner and scene.
Only the separately reviewed playable whitelist is offered by this adapter.
"""

from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import struct

from wakfu_server.achievements import storage, wire, native_effective_eligibility
from wakfu_server.dungeon_achievement_authority import queries_from_state
from wakfu_server import dungeon_criteria

SETTING = "native_mercenary_board_contracts"
SOURCE = Path(__file__).with_name("native_mercenary_board_contracts.json")
OFFER_TTL_MS = 60000


@dataclass(frozen=True)
class BoardOffer:
    account_id: int
    generation: object
    character_id: int
    map_id: int
    instance_id: int
    board_id: int
    source_sha256: str
    offered: tuple
    expires_at_ms: int


@lru_cache(maxsize=1)
def _object_ids():
    if not SOURCE.is_file():
        return frozenset()
    return frozenset(
        b["source"]["id"] for b in json.loads(SOURCE.read_bytes())["boards"]
    )


def recognizes(body):
    """Cheap static identity lookup; recognition grants no interaction authority."""
    return (
        type(body) is bytes
        and len(body) == 12
        and struct.unpack_from(">q", body)[0] in _object_ids()
    )


def _publication(db):
    saved = db.execute(
        "SELECT value FROM settings WHERE name=%s", (SETTING,)
    ).fetchone()
    if saved is None:
        return None
    raw = SOURCE.read_bytes()
    document = json.loads(raw)
    if (
        saved["value"] != document
        or document.get("schema") != "reviewed-native-mercenary-boards-v1"
    ):
        raise ValueError("Mercenary board publication differs from reviewed source")
    return document, hashlib.sha256(raw).hexdigest()


def install(db, document):
    """Publish only the packaged reviewed source, preserving previous offers."""
    from psycopg.pq import TransactionStatus
    from psycopg.types.json import Jsonb

    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Mercenary board publication requires an active transaction")
    expected = json.loads(SOURCE.read_bytes())
    if (
        document != expected
        or document.get("schema") != "reviewed-native-mercenary-boards-v1"
    ):
        raise ValueError("Mercenary publication differs from reviewed source")
    previous = db.execute(
        "SELECT value FROM settings WHERE name=%s FOR UPDATE", (SETTING,)
    ).fetchone()
    if previous is not None:
        old = previous["value"]
        if old.get("schema") != document["schema"] or any(
            d not in document["definitions"] for d in old["definitions"]
        ):
            raise ValueError(
                "Mercenary publication would replace an existing definition"
            )
        current = {b["source"]["id"]: b for b in document["boards"]}
        for board in old["boards"]:
            new = current.get(board["source"]["id"])
            if (
                new is None
                or any(
                    new.get(k) != v for k, v in board.items() if k != "playable_quests"
                )
                or not set(board["playable_quests"]) <= set(new["playable_quests"])
            ):
                raise ValueError(
                    "Mercenary publication would replace an existing board"
                )
    db.execute(
        "INSERT INTO settings(name,value) VALUES(%s,%s) ON CONFLICT(name) DO UPDATE SET value=EXCLUDED.value",
        (SETTING, Jsonb(document)),
    )
    return dict(
        boards=len(document["boards"]), definitions=len(document["definitions"])
    )


def _position(character, board):
    source = board["source"]
    anchor = board["interaction_anchor"]
    if (
        character["instance_id"] != 0
        or character["map_id"] != source["map_id"]
        or abs(character["z"] - anchor["z"]) > 1
        or abs(character["x"] - anchor["x"]) + abs(character["y"] - anchor["y"]) > 4
    ):
        raise ValueError("Character is too far from the native mercenary board")
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    actual = native_catalog.record(
        DATA_ROOT / "native-map-objects.json", "$", str(source["id"])
    )
    with native_catalog._database().connection() as db:
        geometry = db.execute(
            "SELECT sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
            (native_catalog.release(), f"combat-maps/{source['map_id']}.json"),
        ).fetchone()
    if geometry is None or geometry["sha256"] != board["geometry_sha256"]:
        raise ValueError("Mercenary board floor differs from reviewed native geometry")
    if actual is None or any(
        actual.get(k) != source[k]
        for k in ("map_id", "type", "x", "y", "z", "payload_hex")
    ):
        raise ValueError("Mercenary board differs from native physical source")


def _authority(state):
    return queries_from_state(state)


def _eligible(store, current, state, definition):
    identity = definition["d"]
    return (
        identity not in state["running"]
        and identity not in state["completed"]
        and dungeon_criteria.evaluate(
            store,
            native_effective_eligibility.criterion(definition),
            character=current,
            queries=_authority(state),
        )
    )


def open_board(store, account_id, generation, character, body):
    """Return None for other objects; recognized boards require exact cpF0."""
    if type(body) is not bytes or len(body) != 12:
        raise ValueError("Invalid native board interactive request")
    identity, action, parameter = struct.unpack(">qHH", body)
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.environment_interactions import _guard

    with store.connection() as db:
        published = _publication(db)
        if published is None:
            return None
        document, digest = published
        board = next(
            (b for b in document["boards"] if b["source"]["id"] == identity), None
        )
        if board is None:
            return None
        _leased_owner(store, db, account_id, generation, character)
        _guard(db, character["id"])
        current = store.character(account_id, character["id"], db)
        if action != 0 or parameter != 0:
            raise ValueError("Not a native mercenary board ACTIVATE action")
        _position(current, board)
        state = storage.load_locked(db, current["id"])
        for criterion in (
            board["native_action"]["criterion"],
            board["native_effect"]["criterion"],
        ):
            if not dungeon_criteria.evaluate(
                store, criterion, character=current, queries=_authority(state)
            ):
                raise ValueError("Native mercenary board access is not met")
        definitions = {d["d"]: d for d in document["definitions"]}
        offered = tuple(
            q
            for q in board["playable_quests"]
            if _eligible(store, current, state, definitions[q])
        )
        return BoardOffer(
            account_id,
            generation,
            current["id"],
            current["map_id"],
            current["instance_id"],
            identity,
            digest,
            offered,
            int(store.now().timestamp() * 1000) + OFFER_TTL_MS,
        )


def select(store, account_id, generation, character, offer, body):
    """Accept native cnH12864 only from this still-live leased board UI."""
    if type(body) is not bytes or len(body) != 13:
        raise ValueError("Invalid native mercenary selection")
    identity, target, accepting = struct.unpack(">iqB", body)
    now_ms = int(store.now().timestamp() * 1000)
    if (
        type(offer) is not BoardOffer
        or (offer.account_id, offer.generation, offer.character_id)
        != (account_id, generation, character["id"])
        or offer.expires_at_ms < now_ms
        or target != -1
        or accepting != 1
        or identity not in offer.offered
    ):
        raise ValueError("Mercenary selection was not offered to this owner")
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.environment_interactions import _guard
    from wakfu_server.achievements.mission_progress import auto_track, seed_counters

    with store.connection() as db:
        _leased_owner(store, db, account_id, generation, character)
        _guard(db, character["id"])
        current = store.character(account_id, character["id"], db)
        published = _publication(db)
        if published is None or published[1] != offer.source_sha256:
            raise ValueError("Mercenary board publication changed since offer")
        document, _digest = published
        board = next(
            b for b in document["boards"] if b["source"]["id"] == offer.board_id
        )
        if (current["map_id"], current["instance_id"]) != (
            offer.map_id,
            offer.instance_id,
        ):
            raise ValueError("Mercenary offer belongs to another scene")
        _position(current, board)
        if identity not in board["playable_quests"]:
            raise ValueError("Mercenary quest is outside the published board")
        definition = next(
            (d for d in document["definitions"] if d["d"] == identity), None
        )
        if definition is None:
            raise ValueError("Mercenary quest lacks its native definition")
        before = storage.load_locked(db, current["id"])
        for criterion in (
            board["native_action"]["criterion"],
            board["native_effect"]["criterion"],
        ):
            if not dungeon_criteria.evaluate(
                store, criterion, character=current, queries=_authority(before)
            ):
                raise ValueError("Native mercenary board access changed")
        if identity not in board["playable_quests"] or not _eligible(
            store, current, before, definition
        ):
            raise ValueError("Native mercenary quest eligibility changed")
        fact = dict(
            kind="native_mercenary_board_acceptance_v1",
            quest_id=identity,
            board_id=offer.board_id,
            category=board["category"],
            source_sha256=offer.source_sha256,
        )
        if not storage.record_event(
            db, current["id"], f"native-mercenary-board-acceptance:{identity}", fact
        ):
            raise ValueError("Mercenary acceptance receipt lacks its active state")
        after = deepcopy(before)
        after["running"] = sorted(set(after["running"]) | {identity})
        auto_track(after, identity)
        seed_counters(after, definition)
        storage.store(db, current["id"], after)
        return wire.changes(current["id"], before, after, [], [], now_ms)
