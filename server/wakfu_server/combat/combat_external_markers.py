"""Scoped world markers for ordinary and owned-instance fights.

Markers are presentation-only. They are derived from the current shared fight
and are published only to the exact server map/instance audience. Duels remain
ineligible; private fights are never visible in another owned instance.
"""

from dataclasses import dataclass
from threading import RLock
import struct
import time

from .combat_multiplayer_wire import external, external_marker_actor_id
from .combat_wire import decode_topology, topology


def _native_map_partitions(cells):
    """Convert public world cells to the native 18x18 scene partition grid.

    cuY.mys is consumed by cdE.l()/cdz.aQc() as partition x/y keys. The
    client builds those keys with Ve.qb/qc, which floor-divide world
    coordinates by 18 (including negative coordinates).
    """
    partitions = []
    seen = set()
    for x, y in cells:
        key = (x // 18, y // 18)
        if key not in seen:
            if not all(-32768 <= value <= 32767 for value in key):
                raise ValueError("Native marker partition is out of bounds")
            seen.add(key)
            partitions.append(key)
    return tuple(partitions)


def _topology_partitions(value):
    """Return native partitions intersecting the whole QI rectangle.

    Official 13753 samples show that ``mys`` is the set of 18x18 partitions
    touched by the QI bounds, not just the fight starter's cell. Captures
    disagree on the ordering for equivalent rectangles, so this function uses
    stable row-major order rather than treating one observed order as a rule.
    """
    if not isinstance(value, dict):
        raise ValueError("Invalid marker topology")
    x, y, width, height = (value.get(k) for k in ("x", "y", "width", "height"))
    if (
        any(type(v) is not int for v in (x, y, width, height))
        or width < 1
        or height < 1
    ):
        raise ValueError("Invalid marker topology bounds")
    min_x, max_x = x // 18, (x + width - 1) // 18
    min_y, max_y = y // 18, (y + height - 1) // 18
    columns, rows = max_x - min_x + 1, max_y - min_y + 1
    if columns * rows > 127:
        raise ValueError("Native marker partition list is too long")
    if not all(-32768 <= n <= 32767 for n in (min_x, max_x, min_y, max_y)):
        raise ValueError("Native marker partition is out of bounds")

    return tuple(
        (partition_x, partition_y)
        for partition_y in range(min_y, max_y + 1)
        for partition_x in range(min_x, max_x + 1)
    )


def _marker_topology(arena, world_origin):
    """Center the external swords on the initiator's public map cell.

    Native aII.d(buG) places swords using QI.bdT(): origin plus half the
    width/height, then resolves ground height through VF.y. The fbm created
    by ckM at the QI origin is a separate terrain presentation, not a sword.
    Translate only this 13753 envelope; the participant bootstrap and its
    private arena remain unchanged.
    """
    if (
        not isinstance(world_origin, (tuple, list))
        or len(world_origin) != 3
        or any(type(value) is not int for value in world_origin)
        or any(not -32768 <= value <= 32767 for value in world_origin)
    ):
        raise ValueError("Invalid public marker origin")
    native = topology(arena)
    value = decode_topology(native)
    dz = world_origin[2] - value["min_z"]
    value["x"] = world_origin[0] - value["width"] // 2
    value["y"] = world_origin[1] - value["height"] // 2
    # Exploration bootstrap uses native scene instance zero, including owned
    # dungeons. Durable server instance IDs isolate delivery, but cannot enter
    # this signed-int16 field. Participant arena instances are separate scenes.
    value["instance_id"] = 0
    translated_min_z = value["min_z"] + dz
    translated_max_z = value["max_z"] + dz
    if not all(-32768 <= z <= 32767 for z in (translated_min_z, translated_max_z)):
        raise ValueError("Translated public marker Z range is out of bounds")
    value["min_z"] = translated_min_z
    value["max_z"] = translated_max_z
    return topology(value)


@dataclass(frozen=True)
class Marker:
    fight_id: int
    map_id: int
    instance_id: int
    participant_character_ids: frozenset
    actor_body: bytes
    body: bytes
    phase_code: int


class ExternalFightMarkers:
    def __init__(self):
        self.lock = RLock()
        self.markers = {}
        self.started_at_ms = {}

    @staticmethod
    def _actor_snapshot(shared):
        """Build the owned NPC world actors referenced by the marker.

        A public marker's myr roster may contain the fight's monster leader.
        That actor must exist in the recipient's world registry first. The
        only authoritative public appearance is the original leased NPC
        group from join_context plus its group lease; never derive a group ID
        or appearance from the combat actor alone.
        """
        fight = getattr(shared, "fight", None)
        context = getattr(shared, "join_context", None)
        lease = getattr(shared, "group_lease", None)
        monsters = context.get("monsters") if isinstance(context, dict) else None
        if (
            fight is None
            or not isinstance(context, dict)
            or not isinstance(monsters, dict)
            or not monsters
            or not isinstance(lease, (tuple, list))
            or len(lease) != 4
        ):
            return None
        key, generation, leased_fight_id, revision = lease
        if (
            not isinstance(key, (tuple, list))
            or len(key) != 3
            or tuple(key[:2]) != (shared.map_id, shared.instance_id)
            or type(key[2]) is not int
            or key[2] <= 0
            or not isinstance(generation, str)
            or not generation
            or type(leased_fight_id) is not int
            or leased_fight_id != fight.id
            or type(revision) is not int
            or revision <= 0
        ):
            return None
        leaders = context.get("leaders")
        if not isinstance(leaders, dict) or leaders.get(1) not in monsters:
            return None
        try:
            from wakfu_server.combat_monster_world import spawn_group

            members = tuple(monsters.values())
            if any(
                not isinstance(member, dict)
                or member.get("map_id") != shared.map_id
                or member.get("instance_id", 0) != shared.instance_id
                for member in members
            ):
                return None
            return 12608, spawn_group(members, group_id=key[2])
        except (KeyError, TypeError, ValueError, OverflowError, struct.error):
            return None

    @staticmethod
    def _body(shared, *, started_at_ms):
        fight = getattr(shared, "fight", None)
        context = getattr(shared, "join_context", None)
        if (
            fight is None
            or getattr(shared, "is_duel", False)
            or type(getattr(shared, "instance_id", None)) is not int
            or shared.instance_id < 0
            or getattr(fight, "phase", None) not in ("placement", "active")
            or not isinstance(context, dict)
        ):
            return None

        arena = context.get("arena")
        terrain_effect_id = context.get("terrain_effect_id")
        leaders = context.get("leaders")
        monsters = context.get("monsters")
        participants = getattr(shared, "participants", None)
        if (
            not isinstance(arena, dict)
            or arena.get("map_id") != shared.map_id
            # cuY.eHc is passed to fbr.iU(long), which looks up the native
            # terrain/effect-area template (faP). It is not the public map ID.
            # Reusing shared.map_id here makes ckM log that the effect area
            # for map 1134 does not exist and abort marker creation.
            or type(terrain_effect_id) is not int
            or terrain_effect_id <= 0
            or not isinstance(leaders, dict)
            or not isinstance(monsters, dict)
            or not participants
        ):
            return None

        actors = getattr(fight, "actors", None)
        if not isinstance(actors, dict) or len(actors) < 2 or len(actors) > 32767:
            return None
        leader_ids = (leaders.get(0), leaders.get(1))
        if (
            any(
                type(actor_id) is not int or actor_id not in actors
                for actor_id in leader_ids
            )
            or leader_ids[0] == leader_ids[1]
        ):
            return None

        # Capture the starter's authoritative world cell at fight
        # registration; synthetic combat fixtures can have no world XY.
        cells = context.get("world_marker_cells")
        world_origin = context.get("world_marker_origin")
        if not isinstance(cells, (tuple, list)):
            return None
        cells = tuple(tuple(cell) for cell in cells)
        if (
            not cells
            or len(cells) > 127
            or len(set(cells)) != len(cells)
            or any(
                len(cell) != 2
                or any(
                    type(coord) is not int or not -32768 <= coord <= 32767
                    for coord in cell
                )
                for cell in cells
            )
        ):
            return None
        if (
            not isinstance(world_origin, (tuple, list))
            or len(world_origin) != 3
            or any(
                type(coord) is not int or not -32768 <= coord <= 32767
                for coord in world_origin
            )
            or (world_origin[0], world_origin[1]) not in cells
        ):
            return None

        teams = []
        for actor_id, actor in actors.items():
            if (
                type(actor_id) is not int
                or actor.id != actor_id
                or actor.team not in (0, 1)
            ):
                return None
            teams.append((actor_id, actor.team))
        if (
            actors[leader_ids[0]].team != 0
            or actors[leader_ids[1]].team != 1
            or any(
                type(monster_id) is not int
                or not isinstance(monster, dict)
                or monster.get("id") != monster_id
                or monster.get("map_id") != shared.map_id
                or monster.get("instance_id", 0) != shared.instance_id
                or monster_id not in actors
                or actors[monster_id].team != 1
                for monster_id, monster in monsters.items()
            )
            or not monsters
        ):
            return None

        turn = getattr(fight, "native_table_turn", None)
        if type(turn) is not int or not -32768 <= turn <= 32767:
            return None

        native_topology = _marker_topology(arena, world_origin)
        phase_code = 1 if fight.phase == "placement" else 2
        payload = {
            "fight_id": fight.id,
            "kind": 2,
            "myo": terrain_effect_id,
            "myp": external_marker_actor_id(fight.id),
            "jqi": turn,
            "myu": started_at_ms,
            "myr": leader_ids,
            "teams": tuple(teams),
            "phase_code": phase_code,
            "flags": (False, False, False, False),
            # Native cdE.l()/cdz.aQc() associate every partition crossed by
            # the QI rectangle; ordering is stable and does not imply a
            # native ordering contract that the captures do not establish.
            "mys": _topology_partitions(decode_topology(native_topology)),
            "topology": native_topology,
        }
        return external(payload)

    def update(self, shared, *, now_ms=None, now_monotonic=None):
        """Publish a marker once; retain later state for new map entrants.

        Ineligible fights remove a previously visible marker. A marker is never
        created from a partial or guessed world snapshot.
        """
        now_ms = int(time.time() * 1000) if now_ms is None else now_ms
        now_monotonic = time.monotonic() if now_monotonic is None else now_monotonic
        if type(now_ms) is not int or now_ms < 0:
            raise ValueError("Invalid marker timestamp")
        fight = getattr(shared, "fight", None)
        if fight is None:
            return None
        fight_id = getattr(fight, "id", None)
        if type(fight_id) is not int or fight_id <= 0:
            return None
        with self.lock:
            current = self.markers.get(fight_id)
            if getattr(fight, "phase", None) not in ("placement", "active"):
                self.markers.pop(fight_id, None)
                self.started_at_ms.pop(fight_id, None)
                return (12238, _remove_body(fight_id)) if current is not None else None
            try:
                started_at_ms = self.started_at_ms.get(fight_id)
                if started_at_ms is None:
                    context = getattr(shared, "join_context", None)
                    started = (
                        context.get("fight_started_at")
                        if isinstance(context, dict)
                        else None
                    )
                    if type(started) not in (int, float) or isinstance(started, bool):
                        return None
                    started_at_ms = now_ms - max(
                        0, int((now_monotonic - started) * 1000)
                    )
                    self.started_at_ms[fight_id] = started_at_ms
                encoded = self._body(shared, started_at_ms=started_at_ms)
            except (KeyError, TypeError, ValueError, OverflowError, struct.error):
                encoded = None
            if encoded is None:
                self.markers.pop(fight_id, None)
                self.started_at_ms.pop(fight_id, None)
                return (12238, _remove_body(fight_id)) if current is not None else None
            actor_packet = self._actor_snapshot(shared)
            if actor_packet is None:
                self.markers.pop(fight_id, None)
                self.started_at_ms.pop(fight_id, None)
                return (12238, _remove_body(fight_id)) if current is not None else None
            opcode, body = encoded
            phase_code = 1 if fight.phase == "placement" else 2
            sessions = tuple(getattr(shared, "participants", {}).values())
            if not sessions:
                return None
            marker = Marker(
                fight_id,
                shared.map_id,
                shared.instance_id,
                frozenset(session.character_id for session in sessions),
                actor_packet[1],
                body,
                phase_code,
            )
            if current is not None:
                phase_changed_to_action = current.phase_code == 1 and phase_code == 2
                # Keep phase, turn, and roster fresh for a later join without
                # re-sending 13753 to clients that already registered this
                # fight ID. The native 12233 END_PLACEMENT message moves an
                # existing external model to ACTION; send it exactly once when
                # the authoritative shared fight crosses that boundary.
                self.markers[fight_id] = marker
                if phase_changed_to_action:
                    return 12233, struct.pack(">i", fight_id)
                return None
            self.markers[fight_id] = marker
            return opcode, body

    def remove(self, fight_id):
        if type(fight_id) is not int or fight_id <= 0:
            raise ValueError("Invalid marker fight ID")
        with self.lock:
            marker = self.markers.pop(fight_id, None)
            self.started_at_ms.pop(fight_id, None)
            return (12238, _remove_body(fight_id)) if marker is not None else None

    def location(self, fight_id):
        """Return the last published map scope, for a matching native removal."""
        with self.lock:
            marker = self.markers.get(fight_id)
            return None if marker is None else (marker.map_id, marker.instance_id)

    def actor_packet(self, fight_id):
        """Return the authoritative 12608 group dependency for one marker."""
        if type(fight_id) is not int or fight_id <= 0:
            raise ValueError("Invalid marker fight ID")
        with self.lock:
            marker = self.markers.get(fight_id)
            return None if marker is None else (12608, marker.actor_body)

    def snapshots(self, map_id, instance_id, *, exclude_character_id=None):
        if (
            type(map_id) is not int
            or map_id <= 0
            or type(instance_id) is not int
            or instance_id < 0
            or (
                exclude_character_id is not None
                and (type(exclude_character_id) is not int or exclude_character_id <= 0)
            )
        ):
            raise ValueError("Invalid public marker snapshot scope")
        with self.lock:
            return tuple(
                (13753, marker.body)
                for _, marker in sorted(self.markers.items())
                if marker.map_id == map_id
                and marker.instance_id == instance_id
                and exclude_character_id not in marker.participant_character_ids
            )

    def world_snapshots(self, map_id, instance_id, *, exclude_character_id=None):
        """Return actor registrations immediately before their 13753 markers.

        Both packets are captured under one lock, so a late entrant cannot get
        a marker body from one roster revision and the NPC group from another.
        Existing ``snapshots`` remains marker-only for explicit marker replay.
        """
        if (
            type(map_id) is not int
            or map_id <= 0
            or type(instance_id) is not int
            or instance_id < 0
            or (
                exclude_character_id is not None
                and (type(exclude_character_id) is not int or exclude_character_id <= 0)
            )
        ):
            raise ValueError("Invalid public marker snapshot scope")
        with self.lock:
            packets = []
            for _, marker in sorted(self.markers.items()):
                if (
                    marker.map_id != map_id
                    or marker.instance_id != instance_id
                    or exclude_character_id in marker.participant_character_ids
                ):
                    continue
                packets.extend(((12608, marker.actor_body), (13753, marker.body)))
            return tuple(packets)


def _remove_body(fight_id):
    # Native cvF cleanup; huN=true denotes a map marker removal without a
    # fight-result presentation. These IDs are never reused for another fight.
    return struct.pack(">iiiB", fight_id, 1, -1, 1)
