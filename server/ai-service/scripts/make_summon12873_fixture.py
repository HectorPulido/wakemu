"""Create one positive-UID eHj body fixture using the SDK snapshot serializer."""
import hashlib
import struct
import sys
import types
from pathlib import Path

# This checkout omits equipment_damage.py, imported only for _float by the
# snapshot catalog module. Catalog curve values are numeric in the installed
# fixture, so this isolated probe supplies the equivalent float conversion.
equipment_damage = types.ModuleType("wakfu_server.combat.equipment_damage")
equipment_damage._float = float
sys.modules[equipment_damage.__name__] = equipment_damage
combat_paths = types.ModuleType("wakfu_server.combat.paths")
from wakfu_server.paths import DATA_ROOT as ROOT_DATA  # noqa: E402

combat_paths.DATA_ROOT = ROOT_DATA
sys.modules[combat_paths.__name__] = combat_paths

from wakfu_server.combat.combat_actor_snapshot import (  # noqa: E402
    build_npc_snapshot,
    native_npc_creation_values,
)
from wakfu_server.combat.combat_actor import monster_actor_stats  # noqa: E402
from wakfu_server.combat.combat_snapshot_wire import (
    snapshot_characteristics,
)  # noqa: E402
from wakfu_server.combat.combat_state import Actor  # noqa: E402


def main():
    actor_id, reference, level = 901, 1153, 20
    values = native_npc_creation_values(reference, level)
    actor = Actor(
        actor_id,
        0,
        (9, 10, 0),
        17,
        4,
        2,
        17,
        level,
        max_hp=values[1]["maximum"],
    )
    snapshot = build_npc_snapshot(
        {"id": actor_id, "ref": reference},
        actor,
        wp_current=2,
        wp_maximum=max(2, values[4]["maximum"]),
        running_effects=(),
    )
    snapshot.install(actor)
    payload = snapshot_characteristics(actor)
    descriptor = dict(
        id=-actor_id,
        ref=reference,
        level=level,
        team=actor.team,
        hp=actor.hp,
        max_hp=actor.max_hp,
        ap=actor.ap,
        max_ap=actor.max_ap,
        mp=actor.mp,
        max_mp=actor.max_mp,
        wp=2,
        max_wp=max(2, values[4]["maximum"]),
        initiative=actor.initiative,
        x=actor.position[0],
        y=actor.position[1],
        z=actor.position[2],
        map_id=123,
    )
    body = bytearray(
        monster_actor_stats(
            descriptor,
            1,
            direction=0,
            obstacle_id=4,
            characteristics_payload=payload,
        )
    )
    # Current NPC serializer guards on negative identity. Keep all its format2
    # bytes and replace only the repeated terminal identity with the registered UID.
    struct.pack_into(">q", body, len(body) - 20, actor_id)
    packet = struct.pack(">iqh", 1, actor_id, len(body)) + body
    Path(".runtime/summon-12873-eHj-body.bin").write_bytes(body)
    Path(".runtime/summon-12873-body.bin").write_bytes(packet)
    print(
        f"format=2 stats={len(payload)} body={len(body)} packet={len(packet)} "
        f"actor={actor_id} ref={reference} level={level} hp={actor.hp} ap={actor.ap} "
        f"mp={actor.mp} wp=2 body_sha256={hashlib.sha256(body).hexdigest()} "
        f"packet_sha256={hashlib.sha256(packet).hexdigest()}"
    )


if __name__ == "__main__":
    main()
