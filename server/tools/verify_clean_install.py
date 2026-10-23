"""One actual account/dispatcher/World TLS flow in the NEW disposable install.

No client, JAR, gameplay gifts, direct ticket minting or existing fixture reuse.
Credentials and tokens remain in memory and are never included in the receipt.
"""
import argparse
import hashlib
import json
import re
import os
from pathlib import Path
import secrets
import socket
import ssl
import struct
import subprocess
import tempfile
import time
import urllib.request

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from wakfu_server.store import Store
from wakfu_server.social_wire import decode_friend_lists


def post(path, payload, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        ACCESS["http_url"] + path,
        data=json.dumps(payload).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def text(value):
    raw = value.encode()
    return struct.pack(">I", len(raw)) + raw


class Peer:
    def __init__(self, port):
        self.connection = ssl._create_unverified_context().wrap_socket(
            socket.create_connection((ACCESS["world_host"], port), timeout=10),
            server_hostname="localhost",
        )
        self.connection.settimeout(20)
        self.tls = self.connection.version()

    def send(self, opcode, body=b""):
        self.connection.sendall(struct.pack(">IBH", 7 + len(body), 3, opcode) + body)

    def exact(self, length):
        result = bytearray()
        while len(result) < length:
            part = self.connection.recv(length - len(result))
            if not part:
                raise AssertionError("TLS peer disconnected before expected packet")
            result.extend(part)
        return bytes(result)

    def until(self, opcode):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            length = struct.unpack(">I", self.exact(4))[0]
            if not 6 <= length <= 327670:
                raise AssertionError("Invalid native frame length")
            payload = self.exact(length - 4)
            if struct.unpack(">H", payload[:2])[0] == opcode:
                return payload[2:]
        raise AssertionError("Expected native packet missing")

    def close(self):
        self.connection.close()


def dispatcher_ticket(game_token):
    peer = Peer(ACCESS["dispatcher_port"])
    try:
        peer.send(574)
        public = peer.until(400)
        challenge = struct.unpack(">q", public[:8])[0]
        token = game_token.encode()
        if len(token) > 255:
            raise AssertionError("Native authentication token exceeds short text field")
        authentication = struct.pack(">qB", challenge, len(token)) + token
        with tempfile.TemporaryDirectory(prefix="clean-native-auth-") as temporary:
            key = Path(temporary) / "public.der"
            key.write_bytes(public[8:])
            encrypted = subprocess.run(
                [
                    "openssl",
                    "pkeyutl",
                    "-encrypt",
                    "-pubin",
                    "-keyform",
                    "DER",
                    "-inkey",
                    str(key),
                    "-pkeyopt",
                    "rsa_padding_mode:pkcs1",
                ],
                input=authentication,
                capture_output=True,
                check=True,
            ).stdout
        peer.send(584, struct.pack(">I", len(encrypted)) + encrypted)
        peer.until(472)
        peer.send(402)
        peer.until(453)
        peer.send(575, struct.pack(">iB", 10, 0))
        payload = peer.until(466)
        assert payload[0] == 0
        length = struct.unpack(">I", payload[1:5])[0]
        ticket = payload[5 : 5 + length].decode()
        assert len(payload) == 5 + length and ticket
        return ticket, peer.tls
    finally:
        peer.close()


def join(ticket, character):
    peer = Peer(ACCESS["world_port"])
    try:
        peer.send(426, text(ticket) + text("clean-install-19-headless"))
        peer.until(13873)
        peer.send(23664, struct.pack(">q", character["id"]) + text(character["name"]))
        assert decode_friend_lists(peer.until(630)) == {"friends": [], "ignored": []}
        peer.until(711)
        peer.send(12449)
        peer.until(12436)
        assert peer.until(711) == b"\x01"
        peer.send(12449)
        assert peer.until(711) == b"\x00"
        return peer.tls
    finally:
        peer.close()


IDENTITY_KEYS = ("id", "level", "map_id", "instance_id", "x", "y", "z")
HEALTH_KEYS = ("hp", "max_hp", "hp_damage", "health_dead", "hp_zero_valid")


def character_observation(character):
    result = {key: character[key] for key in IDENTITY_KEYS + HEALTH_KEYS}
    projection = character.get("territory_health_projection")
    result["territory_health_projection"] = (
        None
        if projection is None
        else {
            key: projection[key]
            for key in (
                "applied_flat",
                "state_id",
                "map_id",
                "instance_id",
                "region_id",
                "revision",
            )
        }
    )
    return result


def compare_selected_character(before, selected):
    """Accept only the real selected reducer, preserving identity and wounds."""
    from wakfu_server.equipment_stats import effective_character
    from wakfu_server.health_policy import visible

    require(
        all(before[key] == selected[key] for key in IDENTITY_KEYS),
        "Selected character identity, level or location changed",
    )
    require(
        selected["health_dead"] == before["health_dead"],
        "Selection changed the canonical death state",
    )
    maximum = effective_character(selected, include_consumable_buffs=True)["max_hp"]
    require(
        selected["max_hp"] == maximum,
        "Selected HP maximum differs from the canonical reducer",
    )
    # The fixture is created without equipped gear/food. Reconstruct the same
    # selected cap before territory application, then its preserve-current/cap
    # transition. A positive territory cap rebases wounds; it never heals.
    prior_territory = dict(
        selected, territory_health_projection=before.get("territory_health_projection")
    )
    prior_maximum = effective_character(prior_territory, include_consumable_buffs=True)[
        "max_hp"
    ]
    prior_hp = visible(
        prior_maximum,
        before["hp_damage"],
        before["health_dead"],
        before.get("hp_zero_valid", False) and before["hp_damage"] >= prior_maximum,
    )
    expected_hp = min(prior_hp, maximum)
    expected_damage = (
        before["hp_damage"] + maximum - prior_maximum + prior_hp - expected_hp
    )
    require(
        selected["hp_damage"] == expected_damage,
        "Selection changed canonical wounds outside the territory transition",
    )
    require(
        selected["hp_zero_valid"] == before["hp_zero_valid"],
        "Selection changed the canonical zero marker",
    )
    require(
        selected["hp"]
        == expected_hp
        == visible(
            maximum,
            selected["hp_damage"],
            selected["health_dead"],
            selected["hp_zero_valid"],
        ),
        "Selected current HP differs from canonical wounds",
    )


def access_diagnostic(path, stage, observations, error=None):
    """Bounded health/identity evidence only; credentials/tokens never enter it."""
    differences = {}
    for left, right in (("before", "first"), ("first", "after")):
        if left in observations and right in observations:
            differences[left + "_to_" + right] = {
                key: [observations[left].get(key), observations[right].get(key)]
                for key in observations[left].keys() | observations[right].keys()
                if observations[left].get(key) != observations[right].get(key)
            }
    payload = dict(
        status="IN_PROGRESS" if error is None else "FAIL",
        stage=stage,
        observations=observations,
        differences=differences,
    )
    if error is not None:
        payload["error_type"] = type(error).__name__
    Path(path).write_text(json.dumps(payload, indent=2) + "\n")


def run_access(receipt_path, installation_proof, *, baseline_fixture_counts=None):
    database = os.environ["WAKFU_DATABASE_URL"]
    started = time.monotonic()
    username = "clean19_" + secrets.token_hex(5)
    credential = secrets.token_urlsafe(24)
    account = post("/register", {"username": username, "password": credential})
    login = post("/login", {"username": username, "password": credential})
    assert login["account"]["id"] == account["id"]
    character = post(
        "/characters",
        {
            "name": "Clean"
            + "".join(secrets.choice("abcdefghijklmnop") for _ in range(8)),
            "breed": 8,
        },
        login["api_token"],
    )
    store = Store(database, password_file=os.environ["WAKFU_DATABASE_PASSWORD_FILE"])
    diagnostic = Path(receipt_path).with_suffix(".failure.json")
    observations = {}
    stage = "before-first-selection"
    try:
        keys = ("id", "level", "map_id", "instance_id", "x", "y", "z", "hp", "max_hp")
        before = store.character(account["id"], character["id"])
        observations["before"] = character_observation(before)
        access_diagnostic(diagnostic, stage, observations)
        ticket, auth_tls = dispatcher_ticket(login["game_token"])
        world_tls = join(ticket, character)
        first = store.character(account["id"], character["id"])
        observations["first"] = character_observation(first)
        stage = "first-selected-canonical-health"
        access_diagnostic(diagnostic, stage, observations)
        compare_selected_character(before, first)
        login = post("/login", {"username": username, "password": credential})
        ticket, again_auth = dispatcher_ticket(login["game_token"])
        again_world = join(ticket, character)
        after = store.character(account["id"], character["id"])
        observations["after"] = character_observation(after)
        stage = "reconnect-preservation"
        access_diagnostic(diagnostic, stage, observations)
        compare_selected_character(first, after)
        require(
            {k: first[k] for k in keys} == {k: after[k] for k in keys},
            "Reconnect changed the first selected canonical baseline",
        )
        with store.connection() as db:
            counts = {
                "accounts": db.execute("SELECT count(*) AS n FROM accounts").fetchone()[
                    "n"
                ],
                "characters": db.execute(
                    "SELECT count(*) AS n FROM characters"
                ).fetchone()["n"],
            }
        baseline_fixture_counts = baseline_fixture_counts or dict(
            accounts=0, characters=0
        )
        require(
            counts
            == {key: value + 1 for key, value in baseline_fixture_counts.items()},
            "Unexpected accounts or characters appeared during the probe",
        )
        receipt = {
            "status": "PASS",
            "installation": installation_proof,
            "http_registration": True,
            "http_login": True,
            "http_character_creation_response": True,
            "character_creation_committed": True,
            "native_dispatcher_rsa_authentication": True,
            "native_realm_ticket": True,
            "world_tls_selection": True,
            "contacts630": True,
            "cached_join": True,
            "dnd_toggle_roundtrip": True,
            "new_login_reconnect": True,
            "initial_tls": [auth_tls, world_tls],
            "reconnect_tls": [again_auth, again_world],
            "before": {k: before[k] for k in keys},
            "first_selected": observations["first"],
            "after": {k: after[k] for k in keys},
            "initial_health_reconciliation": observations,
            "baseline_fixture_counts": baseline_fixture_counts,
            "fixture_counts": counts,
            "seconds": time.monotonic() - started,
            "scope": "Clean server installation, no client/JAR or gameplay/combat completion claim",
        }
        destination = Path(receipt_path)
        destination.write_text(json.dumps(receipt, indent=2) + "\n")
        print(json.dumps(receipt), flush=True)
        diagnostic.unlink(missing_ok=True)
    except BaseException as error:
        access_diagnostic(diagnostic, stage, observations, error)
        raise
    finally:
        store.close()


# These are explicitly named installation semantics, never SQL supplied by a
# manifest. Exact table row counts use separately validated SQL identifiers.
SEMANTIC_QUERIES = {
    "xp_active_rate_bp": "SELECT v.xp_rate_bp FROM combat_reward_policy_active a JOIN combat_reward_policy_versions v USING(version) WHERE a.singleton",
    "environmental_profiles_sealed": "SELECT count(*) FROM environmental_runtime_profiles WHERE sealed",
    "environmental_profiles_enabled": "SELECT count(*) FROM environmental_runtime_profiles WHERE enabled",
    "environmental_profiles_enabled_sealed": "SELECT count(*) FROM environmental_runtime_profiles WHERE enabled AND sealed",
    "environmental_scenarios": "SELECT count(DISTINCT native_scenario_id) FROM environmental_runtime_profiles",
    "regional_v9_enabled": "SELECT count(*) FROM environmental_regional_schedule_policies WHERE version=9 AND enabled",
    "regional_enabled_candidates": "SELECT count(*) FROM environmental_regional_schedule_candidates c JOIN environmental_regional_schedule_policies p USING(policy_key,version) WHERE p.enabled",
    "random_genesis_enabled": "SELECT enabled FROM environmental_random_roster_active WHERE singleton",
    "archmonster_enabled": "SELECT enabled FROM archmonster_spawn_active WHERE singleton",
    "archmonster_eligible_sources": "SELECT count(*) FROM archmonster_spawn_sources WHERE NOT blocked_by_membership",
    "archmonster_blocked_sources": "SELECT count(*) FROM archmonster_spawn_sources WHERE blocked_by_membership",
    "dungeon_routes": "SELECT jsonb_array_length(value->'routes') FROM settings WHERE name='dungeon_runtime_routes'",
    "shop_enabled_articles": "SELECT count(*) FROM shop_articles a JOIN shop_categories c ON c.key=a.category WHERE a.enabled AND c.enabled",
    "shop_enabled_categories": "SELECT count(*) FROM shop_categories WHERE enabled",
    "shop_11387_disabled": "SELECT NOT enabled FROM shop_articles WHERE item_ref=11387",
}
ACCESS = {}
IDENTIFIER = re.compile(r"[a-z][a-z0-9_]*\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def official_migrations(directory):
    result = {}
    for path in sorted(Path(directory).glob("*.sql")):
        match = re.match(r"([0-9]{3})_", path.name)
        require(match is not None, "Unsupported official migration filename")
        version = int(match.group(1))
        require(version not in result, "Duplicate official migration version")
        result[version] = hashlib.sha256(path.read_bytes()).hexdigest()
    require(
        bool(result) and sorted(result) == list(range(1, len(result) + 1)),
        "Official migration versions are not contiguous",
    )
    return result


def migration_manifest(rows):
    require(
        isinstance(rows, list) and bool(rows), "Missing expected migration manifest"
    )
    result = {}
    for row in rows:
        require(isinstance(row, dict), "Invalid migration entry")
        version = row.get("version")
        if type(version) is int:
            parsed = version
        else:
            require(isinstance(version, str), "Invalid migration version")
            match = re.fullmatch(r"([0-9]{1,3})(?:_[A-Za-z0-9_]+(?:\.sql)?)?", version)
            require(match is not None, "Invalid migration version filename")
            parsed = int(match.group(1))
        checksum = row.get("sha256")
        require(
            isinstance(checksum, str) and SHA256.fullmatch(checksum),
            "Invalid migration SHA256",
        )
        require(parsed not in result, "Duplicate expected migration version")
        result[parsed] = checksum
    return result


def table_identifier(name):
    require(
        isinstance(name, str) and IDENTIFIER.fullmatch(name),
        "Invalid manifest table identifier",
    )
    return sql.Identifier(name)


def validate_zero_witness(recheck_witness, database, zeros):
    require(
        isinstance(recheck_witness, dict)
        and recheck_witness.get("database") == database
        and recheck_witness.get("zero_player_state") is True
        and isinstance(recheck_witness.get("counts"), dict)
        and set(zeros).issubset(recheck_witness["counts"])
        and all(
            type(value) is int and value == 0
            for value in recheck_witness["counts"].values()
        ),
        "Recheck requires the original matching zero-player witness",
    )


def existing_probe_fixtures(db):
    accounts = db.execute("SELECT id,username FROM accounts ORDER BY id").fetchall()
    characters = db.execute(
        "SELECT account_id,name,breed,deleted_at FROM characters ORDER BY id"
    ).fetchall()
    require(
        bool(accounts)
        and all(
            isinstance(row[1], str) and re.fullmatch(r"clean19_[0-9a-f]{10}", row[1])
            for row in accounts
        ),
        "Recheck found a non-probe account",
    )
    owners = {row[0] for row in accounts}
    require(
        len(characters) == len(accounts)
        and {row[0] for row in characters} == owners
        and all(
            isinstance(row[1], str)
            and re.fullmatch(r"Clean[a-p]{8}", row[1])
            and row[2] == 8
            and row[3] is None
            for row in characters
        ),
        "Recheck found a non-probe, duplicate or deleted character",
    )
    return dict(accounts=len(accounts), characters=len(characters))


def check_installation(db, manifest, migrations, *, recheck_witness=None):
    expected_schema = migration_manifest(manifest.get("schema_versions"))
    require(
        expected_schema == official_migrations(migrations),
        "Expected migrations differ from the complete current server checkout",
    )
    installed_schema = dict(
        db.execute("SELECT version,checksum FROM schema_migrations").fetchall()
    )
    require(
        installed_schema == expected_schema,
        "Installed migration checksums do not match expected manifest",
    )
    identity = manifest.get("installation")
    require(
        isinstance(identity, dict)
        and isinstance(identity.get("project"), str)
        and bool(identity["project"]),
        "Missing dedicated installation identity",
    )
    require(
        db.execute("SELECT current_database()").fetchone()[0]
        == identity.get("database"),
        "Database differs from the dedicated installation manifest",
    )
    zeros = manifest.get("required_zero_tables")
    mandatory = {
        "accounts",
        "characters",
        "sessions",
        "inventory_items",
        "inventory_containers",
    }
    require(
        isinstance(zeros, list)
        and mandatory.issubset(zeros)
        and len(zeros) == len(set(zeros)),
        "Incomplete pre-account zero-state contract",
    )
    zero_state = {}
    for table in zeros:
        zero_state[table] = db.execute(
            sql.SQL("SELECT count(*) FROM {}").format(table_identifier(table))
        ).fetchone()[0]
    baseline_fixture_counts = None
    if recheck_witness is None:
        require(
            all(value == 0 for value in zero_state.values()),
            "Fresh installation already contains player state",
        )
    else:
        validate_zero_witness(recheck_witness, identity["database"], zeros)
        baseline_fixture_counts = existing_probe_fixtures(db)
        zero_state = dict(recheck_witness["counts"])

    expected_counts = manifest.get("expected_counts")
    require(
        isinstance(expected_counts, dict) and bool(expected_counts),
        "Missing expected public content counts",
    )
    counts = {}
    for table, expected in expected_counts.items():
        require(type(expected) is int and expected >= 0, "Invalid expected table count")
        counts[table] = db.execute(
            sql.SQL("SELECT count(*) FROM {}").format(table_identifier(table))
        ).fetchone()[0]
        require(counts[table] == expected, "Public content count mismatch: " + table)
    semantics = {}
    for name, expected in manifest.get("expected_semantics", {}).items():
        require(
            name in SEMANTIC_QUERIES and type(expected) in (int, bool),
            "Unknown or malformed installation semantic: " + str(name),
        )
        row = db.execute(SEMANTIC_QUERIES[name]).fetchone()
        actual = None if row is None else row[0]
        require(
            type(actual) is type(expected) and actual == expected,
            "Installed public semantic mismatch: " + name,
        )
        semantics[name] = actual
    catalog = manifest.get("native_catalog")
    require(isinstance(catalog, dict), "Missing native catalog expectation")
    active = db.execute(
        "SELECT revision FROM native_catalog_active WHERE id=1"
    ).fetchone()
    require(
        active is not None and active[0] == catalog.get("active_revision"),
        "Native active release mismatch",
    )
    releases = db.execute(
        "SELECT revision,document_count,source_bytes,complete FROM native_catalog_releases ORDER BY revision"
    ).fetchall()
    expected_releases = catalog.get("releases")
    require(isinstance(expected_releases, list), "Missing native release inventory")
    actual_release_rows = [
        dict(revision=row[0], document_count=row[1], source_bytes=row[2])
        for row in releases
    ]
    require(
        all(row[3] is True for row in releases)
        and actual_release_rows
        == sorted(expected_releases, key=lambda row: row["revision"]),
        "Native catalog release metadata mismatch",
    )
    documents = db.execute("SELECT count(*) FROM native_catalog_documents").fetchone()[
        0
    ]
    require(
        type(catalog.get("documents")) is int and documents == catalog["documents"],
        "Native document count mismatch",
    )
    for release in actual_release_rows:
        count, size = db.execute(
            "SELECT count(*),coalesce(sum(source_bytes),0) FROM native_catalog_documents WHERE revision=%s",
            (release["revision"],),
        ).fetchone()
        require(
            (count, size) == (release["document_count"], release["source_bytes"]),
            "Native catalog document totals differ from their release",
        )
    seed_inputs = manifest.get(
        "declared_seed_inputs", manifest.get("installed_seed_receipts", [])
    )
    require(isinstance(seed_inputs, list), "Invalid declared seed input inventory")
    seed_keys = set()
    for entry in seed_inputs:
        require(
            isinstance(entry, dict)
            and isinstance(entry.get("key"), str)
            and entry["key"] not in seed_keys
            and isinstance(entry.get("sha256"), str)
            and SHA256.fullmatch(entry["sha256"]),
            "Invalid declared seed input hash",
        )
        seed_keys.add(entry["key"])
    return dict(
        installation=identity,
        latest_schema=max(expected_schema),
        migration_count=len(expected_schema),
        zero_state=zero_state,
        content_counts=counts,
        semantics=semantics,
        native_catalog=dict(
            active_revision=active[0], documents=documents, releases=actual_release_rows
        ),
        declared_seed_inputs=seed_inputs,
        recheck_baseline=baseline_fixture_counts,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument(
        "--recheck-after-failed-probe",
        type=Path,
        help="Original zero-player witness; permit only preserved synthetic QA fixtures",
    )
    parser.add_argument(
        "--migrations",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "migrations",
    )
    parser.add_argument("--http-url", default="http://127.0.0.1:18081")
    parser.add_argument("--world-host", default="127.0.0.1")
    parser.add_argument("--world-port", type=int, default=15556)
    parser.add_argument("--dispatcher-port", type=int, default=15558)
    args = parser.parse_args()
    require(
        not args.receipt.exists(),
        "Verification receipt already exists; do not create duplicate QA fixtures",
    )
    raw = args.manifest.read_bytes()
    manifest = json.loads(raw)
    require(
        isinstance(manifest, dict), "Expected installation manifest must be an object"
    )
    password = Path(os.environ["WAKFU_DATABASE_PASSWORD_FILE"]).read_text().strip()
    # Plain SQL precedes Store construction and every account API request.
    with psycopg.connect(os.environ["WAKFU_DATABASE_URL"], password=password) as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        witness_raw = (
            None
            if args.recheck_after_failed_probe is None
            else args.recheck_after_failed_probe.read_bytes()
        )
        witness = None if witness_raw is None else json.loads(witness_raw)
        proof = check_installation(
            db, manifest, args.migrations, recheck_witness=witness
        )
        if witness_raw is not None:
            proof["original_zero_witness_sha256"] = hashlib.sha256(
                witness_raw
            ).hexdigest()
    proof["verification_manifest_sha256"] = hashlib.sha256(raw).hexdigest()
    ACCESS.update(
        http_url=args.http_url,
        world_host=args.world_host,
        world_port=args.world_port,
        dispatcher_port=args.dispatcher_port,
    )
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    run_access(args.receipt, proof, baseline_fixture_counts=proof["recheck_baseline"])


if __name__ == "__main__":
    main()
