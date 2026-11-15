"""Publish reviewed mission profiles and settle authenticated producer events.

This is not a client command API. The gameplay producer owns authentication,
its event identity, the character lock and the surrounding transaction. Native
metadata and immutable profiles are queried by their event index, never scanned
from a full catalogue at each operation.
"""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from threading import RLock

from psycopg.types.json import Jsonb

from . import mission_dependencies, mission_toolkit_contract as contract
from . import mission_toolkit_planner as planner, storage

_CACHE = {}
_CACHE_LOCK = RLock()
RII_PROFILE = Path(__file__).with_name("mission_profiles") / "rii.json"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _revision(db):
    row = db.execute(
        "SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        raise ValueError("Missing native quest metadata publication")
    return row["revision"]


def _identities(profile):
    ids = {row["quest_id"] for row in profile.get("bindings", ())}
    for row in profile.get("links", ()):
        ids.update((row["parent_quest_id"], row["child_quest_id"]))
    for row in profile.get("activations", ()):
        ids.add(row["quest_id"])
        ids.update(row.get("requires_completed", ()))
    if any(type(identity) is not int or identity <= 0 for identity in ids):
        raise ValueError("Invalid profile native quest identity")
    return ids


def definitions(db, profile, revision=None):
    """Read only this declaration's referenced, immutable native definitions."""
    try:
        identities = _identities(profile)
    except (KeyError, TypeError, AttributeError) as error:
        raise ValueError("Malformed mission profile declarations") from error
    if not identities:
        return {}
    revision = _revision(db) if revision is None else revision
    rows = db.execute(
        "SELECT definition_id,data FROM native_quest_metadata_definitions "
        "WHERE revision=%s AND definition_id=ANY(%s)",
        (revision, sorted(identities)),
    ).fetchall()
    result = {row["definition_id"]: row["data"]["native"] for row in rows}
    if set(result) != identities:
        raise ValueError("Profile references missing native mission definitions")
    return result


def _metadata(row):
    return dict(
        id=row["profile_id"],
        version=row["version"],
        sha256=row["sha256"],
        native_revision=row["native_revision"],
        active=bool(row.get("active", False)),
    )


def installed(db):
    """List publication metadata; bodies are available through get_profile."""
    return [
        _metadata(row)
        for row in db.execute(
            "SELECT p.*,a.version IS NOT NULL AS active FROM mission_toolkit_profiles p "
            "LEFT JOIN mission_toolkit_active a USING(profile_id,version) "
            "ORDER BY p.profile_id,p.version"
        ).fetchall()
    ]


def get_profile(db, profile_id, version=None):
    if version is not None and (type(version) is not int or version <= 0):
        raise ValueError("Invalid mission profile publication version")
    row = db.execute(
        "SELECT p.document FROM mission_toolkit_profiles p "
        "LEFT JOIN mission_toolkit_active a USING(profile_id,version) "
        "WHERE p.profile_id=%s AND (%s::integer IS NULL OR p.version=%s) "
        "ORDER BY a.version IS NOT NULL DESC,p.version DESC LIMIT 1",
        (profile_id, version, version),
    ).fetchone()
    if row is None:
        raise ValueError("Unknown mission profile publication")
    return deepcopy(row["document"])


def install(db, profile, *, activate=False):
    """Validate and publish a new immutable version; never enable by inference.

    JSON version1 is the format version. The returned database version advances
    independently when a reviewed document or native metadata release changes.
    """
    if type(activate) is not bool:
        raise ValueError("Invalid mission profile activation flag")
    revision = _revision(db)
    native = definitions(db, profile, revision)
    profile = contract.validate(profile, native)
    digest = sha256(_canonical(profile).encode()).hexdigest()
    identity = profile["id"]
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("mission-toolkit-publish:" + identity,),
    )
    row = db.execute(
        "SELECT p.*,EXISTS(SELECT 1 FROM mission_toolkit_active a "
        "WHERE a.profile_id=p.profile_id AND a.version=p.version) AS active "
        "FROM mission_toolkit_profiles p WHERE profile_id=%s AND native_revision=%s AND sha256=%s",
        (identity, revision, digest),
    ).fetchone()
    if row is None:
        version = db.execute(
            "SELECT coalesce(max(version),0)+1 AS next FROM mission_toolkit_profiles WHERE profile_id=%s",
            (identity,),
        ).fetchone()["next"]
        row = db.execute(
            "INSERT INTO mission_toolkit_profiles(profile_id,version,native_revision,sha256,document) "
            "VALUES(%s,%s,%s,%s,%s) RETURNING *,false AS active",
            (identity, version, revision, digest, Jsonb(profile)),
        ).fetchone()
        events = {
            (entry["event"]["kind"], entry["event"].get("reference"))
            for entry in profile["bindings"] + profile["activations"]
        }
        events.update(
            ("quest_completed", row["child_quest_id"]) for row in profile["links"]
        )
        for kind, reference in sorted(events, key=lambda item: (item[0], item[1] or 0)):
            db.execute(
                "INSERT INTO mission_toolkit_event_index(profile_id,version,kind,reference) VALUES(%s,%s,%s,%s)",
                (identity, version, kind, reference),
            )
    if activate:
        return _activate_profile(db, identity, row["version"])
    return _metadata(row)


def _overlap(first, second):
    return contract.overlapping(first, second)


def _activate_profile(db, profile_id, version):
    if type(version) is not int or version <= 0:
        raise ValueError("Invalid mission profile publication version")
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("mission-toolkit-activation",),
    )
    row = db.execute(
        "SELECT * FROM mission_toolkit_profiles WHERE profile_id=%s AND version=%s",
        (profile_id, version),
    ).fetchone()
    if row is None or row["native_revision"] != _revision(db):
        raise ValueError(
            "Profile publication is missing or belongs to an older native release"
        )
    current = row["document"]
    others = db.execute(
        "SELECT p.document FROM mission_toolkit_profiles p JOIN mission_toolkit_active a USING(profile_id,version) "
        "WHERE p.profile_id<>%s AND p.native_revision=%s",
        (profile_id, row["native_revision"]),
    ).fetchall()
    for other in others:
        edges = {
            (link["parent_quest_id"], link["objective_id"]): link["child_quest_id"]
            for link in other["document"]["links"]
        }
        for link in current["links"]:
            previous = edges.get((link["parent_quest_id"], link["objective_id"]))
            if previous is not None and previous != link["child_quest_id"]:
                raise ValueError(
                    "Active profiles disagree on a native child quest dependency"
                )
        for left in current["bindings"]:
            for right in other["document"]["bindings"]:
                same_objective = (left["quest_id"], left["objective_id"]) == (
                    right["quest_id"],
                    right["objective_id"],
                )
                same_variable = "variable_id" in left and left.get(
                    "variable_id"
                ) == right.get("variable_id")
                if (same_objective or same_variable) and _overlap(left, right):
                    raise ValueError(
                        "Active mission profiles contain overlapping event counters/objectives"
                    )
    db.execute(
        "INSERT INTO mission_toolkit_active(profile_id,version) VALUES(%s,%s) "
        "ON CONFLICT(profile_id) DO UPDATE SET version=EXCLUDED.version",
        (profile_id, version),
    )
    return _metadata(dict(row, active=True))


def activate(db, profile_id, version):
    """Select an installed immutable publication without changing progress."""
    return _activate_profile(db, profile_id, version)


def install_rii(db, *, activate=False):
    """Explicit compatibility publication of already implemented Rii bindings."""
    return install(db, json.loads(RII_PROFILE.read_text()), activate=activate)


def _load(db, row):
    context = tuple(
        getattr(db.info, name, None) for name in ("host", "port", "dbname", "options")
    )
    key = (
        *context,
        row["profile_id"],
        row["version"],
        row["native_revision"],
        row["sha256"],
    )
    with _CACHE_LOCK:
        found = _CACHE.get(key)
    if found is not None:
        return found
    native = definitions(db, row["document"], row["native_revision"])
    profile = contract.validate(row["document"], native)

    def index(entries):
        result = {}
        for entry in entries:
            event = entry["event"]
            result.setdefault((event["kind"], event.get("reference")), []).append(entry)
        return result

    children, parents = {}, {}
    for link in profile["links"]:
        children.setdefault(link["child_quest_id"], []).append(link)
        parents.setdefault(link["parent_quest_id"], []).append(link)
    found = dict(
        profile=profile,
        native=native,
        bindings=index(profile["bindings"]),
        activations=index(profile["activations"]),
        children=children,
        parents=parents,
    )
    with _CACHE_LOCK:
        if len(_CACHE) >= 64:
            _CACHE.pop(next(iter(_CACHE)))
        _CACHE[key] = found
    return found


def _selected(index, event, character):
    entries = list(index.get((event["kind"], event.get("reference")), ()))
    if event.get("reference") is not None:
        entries.extend(index.get((event["kind"], None), ()))
    return [entry for entry in entries if contract.matches(entry, event, character)]


def _project(loaded, event, character):
    """Select only the event's indexed bindings and reachable dependency graph."""
    base = loaded["profile"]
    selected = _selected(loaded["bindings"], event, character)
    activations = {
        row["id"]: row for row in _selected(loaded["activations"], event, character)
    }
    child = event.get("reference") if event["kind"] == "quest_completed" else None
    if not selected and not activations and child not in loaded["children"]:
        return None
    touched = {row["quest_id"] for row in selected} | {
        row["quest_id"] for row in activations.values()
    }
    if child in loaded["children"]:
        touched.add(child)
    pending = list(touched)
    links = {}
    while pending:
        identity = pending.pop()
        for link in loaded["children"].get(identity, ()):
            links[(link["parent_quest_id"], link["objective_id"])] = link
            parent = link["parent_quest_id"]
            if parent not in touched:
                touched.add(parent)
                pending.append(parent)
        # An objective on this parent can unlock a child already completed
        # earlier. Include siblings for reconciliation without traversing them.
        for link in loaded["parents"].get(identity, ()):
            links[(link["parent_quest_id"], link["objective_id"])] = link
        completion = dict(kind="quest_completed", reference=identity, quantity=1)
        for row in _selected(loaded["activations"], completion, character):
            activations[row["id"]] = row
            if row["quest_id"] not in touched:
                touched.add(row["quest_id"])
                pending.append(row["quest_id"])
    profile = dict(
        base,
        bindings=selected,
        links=list(links.values()),
        activations=list(activations.values()),
    )
    native = {identity: loaded["native"][identity] for identity in _identities(profile)}
    return profile, native


def _legacy(profile, event, token, character):
    """One explicit conversion adapter; ordinary profiles have no legacy IDs."""
    if profile["id"] != "rii":
        return []
    kind, reference = event["kind"], event.get("reference")
    if kind in ("monster_harvest", "resource_harvest", "planting"):
        candidates = [
            row
            for row in profile["bindings"]
            if contract.matches(row, event, character)
        ]
        if len(candidates) == 1 and "variable_id" in candidates[0]:
            return [
                (
                    "rii-ecosystem:" + kind + ":" + sha256(token.encode()).hexdigest(),
                    dict(
                        kind=kind, item=reference, variable=candidates[0]["variable_id"]
                    ),
                )
            ]
    if kind == "craft_completed" and reference == 9445:
        return [
            (
                "rii-craft:" + token,
                dict(
                    kind="reconstructed_rii_craft",
                    recipe_id=9445,
                    station_id=34659,
                    item_id=31159,
                ),
            )
        ]
    return []


def effective_character(db, store, character):
    """Refresh earned stats while retaining the producer's private scene pose."""
    current = store.character(character["account_id"], character["id"], db)
    if current is None or (current.get("id"), current.get("account_id")) != (
        character["id"],
        character["account_id"],
    ):
        raise ValueError("Mission toolkit character ownership changed")
    current = dict(character, **current)
    for key in ("map_id", "instance_id", "x", "y", "z"):
        if key in character:
            current[key] = character[key]
    return current


def _settle(
    db,
    store,
    character,
    token,
    kind,
    reference,
    quantity=1,
    *,
    excluded=(),
    applied=None
):
    """Settle a trusted committed gameplay operation in its producer transaction.

    The producer authenticates and locks its account BEFORE its character;
    the shared settlement/reward pipeline retains that order. Receipts commit or
    roll back together. Calls from client-supplied generic event messages are
    deliberately unsupported.
    """
    if not isinstance(token, str) or not token or len(token) > 4096:
        raise ValueError("Invalid authenticated mission event token")
    event = dict(kind=kind, quantity=quantity)
    if reference is not None:
        event["reference"] = reference
    contract.validate_event(event)
    rows = db.execute(
        "SELECT DISTINCT p.* FROM mission_toolkit_event_index i "
        "JOIN mission_toolkit_active a USING(profile_id,version) "
        "JOIN mission_toolkit_profiles p USING(profile_id,version) "
        "WHERE i.kind=%s AND (i.reference=%s OR i.reference IS NULL) "
        "AND p.native_revision=(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "ORDER BY p.profile_id",
        (kind, reference),
    ).fetchall()
    loaded = [_project(_load(db, row), event, character) for row in rows]
    loaded = [
        profile
        for profile in loaded
        if profile is not None and profile[0]["id"] not in excluded
    ]
    if not loaded:
        return []
    before = storage.load_locked(db, character["id"])
    receipt = (
        "mission-toolkit:"
        + kind
        + ":"
        + str(reference)
        + ":"
        + sha256(token.encode()).hexdigest()
    )
    facts = dict(event, map_id=character["map_id"])
    aliases = [
        alias
        for profile, _ in loaded
        for alias in _legacy(profile, event, token, character)
    ]
    expected = dict([(receipt, facts), *aliases])
    prior = db.execute(
        "SELECT event_key,payload FROM character_achievement_events WHERE character_id=%s AND event_key=ANY(%s)",
        (character["id"], list(expected)),
    ).fetchall()
    if prior:
        for row in prior:
            if row["payload"] != expected[row["event_key"]]:
                raise ValueError(
                    "Mission producer event identity conflicts with stored facts"
                )
        return []
    character = effective_character(db, store, character)
    now_ms = int(store.now().timestamp() * 1000)
    after = before
    intents, objectives, completed, native, links = [], [], [], {}, []
    for profile, definitions_by_id in loaded:
        prior_state = after
        after, extra_intents, extra_objectives, extra_completed = planner.plan(
            after,
            definitions_by_id,
            profile,
            event,
            character=character,
            store=store,
            now_ms=now_ms,
        )
        if applied is not None and (
            after != prior_state or extra_intents or extra_objectives or extra_completed
        ):
            applied.add(profile["id"])
        intents.extend(extra_intents)
        objectives.extend(extra_objectives)
        completed.extend(extra_completed)
        native.update(definitions_by_id)
        for row in profile["links"]:
            link = row["parent_quest_id"], row["objective_id"], row["child_quest_id"]
            if link not in links:
                links.append(link)
    if after == before and not intents and not objectives and not completed:
        return []
    for key, payload in expected.items():
        if not storage.record_event(db, character["id"], key, payload):
            return []
    return mission_dependencies.settle(
        db,
        store,
        character,
        before,
        (after, intents, objectives, completed),
        native,
        links,
        now_ms=now_ms,
    )["packets"]


def settle(db, store, character, token, kind, reference, quantity=1):
    """Settle a trusted event; caller owns account-first authentication/locks."""
    return _settle(db, store, character, token, kind, reference, quantity)


def settle_combat(db, store, character, *, fight_id, breeds):
    """Publish actual defeated original breeds, retaining old Rii battle receipts.

    This adapter accepts only an authenticated settled victory supplied by the
    combat producer. Summons and client-authored target lists do not qualify.
    A legacy aggregate receipt skips only Rii; other profiles still receive each
    actual breed. New Rii conversion writes its aggregate once after the batch.
    """
    from collections import Counter

    if (
        type(fight_id) is not int
        or fight_id <= 0
        or not isinstance(breeds, list)
        or any(type(breed) is not int or breed <= 0 for breed in breeds)
    ):
        raise ValueError("Invalid authenticated mission combat event")
    legacy_key = "rii-wodent-victory:" + str(fight_id)
    amount = sum(breed in (5455, 5456, 5525) for breed in breeds)
    legacy = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], legacy_key),
    ).fetchone()
    legacy_facts = dict(kind="rii_wodent_victory", fight_id=fight_id, count=amount)
    if legacy is not None and legacy["payload"] != legacy_facts:
        raise ValueError(
            "Legacy Rii combat identity conflicts with original defeated breeds"
        )
    packets, applied = [], set()
    for breed, quantity in sorted(Counter(breeds).items()):
        packets.extend(
            _settle(
                db,
                store,
                character,
                str(fight_id) + ":" + str(breed),
                "monster_defeat",
                breed,
                quantity,
                excluded=("rii",) if legacy is not None else (),
                applied=applied,
            )
        )
    if "rii" in applied and amount:
        storage.record_event(db, character["id"], legacy_key, legacy_facts)
    return packets
