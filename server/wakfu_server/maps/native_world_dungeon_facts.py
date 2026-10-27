"""Original WorldInfoManager.eyd facts; loaded once, never inferred from combat."""

from functools import lru_cache
import hashlib
import json
from types import MappingProxyType

SOURCE = "native-worlds-eyd-v1"
SCHEMA = "native.eNL.eII.n.eGj.arM.WorldInfoManager.mP.eyd.v1"
CLIENT_SHA = "e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd"
MAP_JAR_SHA = "caf937e29fcba5847a43caeb6cf564236864bc6612d4f64198032bc577ba1201"
WORLDS_SHA = "53d7ab151bd51b175d654a63d9e2cc1acd29f7895a7ac7c1b3258c6a74ff5024"
PAYLOAD_SHA = "02a60defaebe708ec14ed31b0ca26ad2fd07857e94fc99b92ceb90efc8c33b21"
FLAGS_SHA = "84b99235eedb9922b7b9272fe6923650ad1a5610ea4747c87dfddc53608049c0"


def _database():
    from wakfu_server import native_catalog

    return native_catalog._database()


@lru_cache(maxsize=1)
def dungeon_world_flags():
    """Read complete immutable original facts, including known false worlds."""
    from psycopg import Error

    try:
        with _database().connection() as db:
            source = db.execute(
                "SELECT * FROM native_world_dungeon_sources WHERE source_key=%s",
                (SOURCE,),
            ).fetchone()
            rows = db.execute(
                "SELECT native_instance_id,is_dungeon FROM native_world_dungeon_flags "
                "WHERE source_key=%s",
                (SOURCE,),
            ).fetchall()
    except (Error, RuntimeError) as error:
        raise ValueError(
            "Original native dungeon world facts are unavailable"
        ) from error
    expected = dict(
        source_key=SOURCE,
        schema_tag=SCHEMA,
        client_jar_sha256=CLIENT_SHA,
        map_data_jar_sha256=MAP_JAR_SHA,
        worlds_lib_sha256=WORLDS_SHA,
        payload_sha256=PAYLOAD_SHA,
        flags_sha256=FLAGS_SHA,
        world_count=720,
        dungeon_count=169,
    )
    if source is None or any(
        source.get(key) != value for key, value in expected.items()
    ):
        raise ValueError("Original native dungeon world provenance differs")
    flags = {}
    for row in rows:
        identity, flag = row["native_instance_id"], row["is_dungeon"]
        if type(identity) is not int or type(flag) is not bool or identity in flags:
            raise ValueError("Malformed original native dungeon world fact")
        flags[identity] = flag
    canonical = json.dumps(
        {str(key): value for key, value in flags.items()},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    if (
        len(flags) != source["world_count"]
        or sum(flags.values()) != source["dungeon_count"]
        or hashlib.sha256(canonical).hexdigest() != source["flags_sha256"]
    ):
        raise ValueError(
            "Original native dungeon world facts are incomplete or changed"
        )
    return MappingProxyType(flags)


def is_dungeon(native_instance_id):
    if type(native_instance_id) is not int or not -(1 << 63) <= native_instance_id < (
        1 << 63
    ):
        raise ValueError("Missing actual native dungeon world identity")
    flags = dungeon_world_flags()
    if native_instance_id not in flags:
        raise ValueError("Native dungeon world identity is outside the original source")
    return flags[native_instance_id]
