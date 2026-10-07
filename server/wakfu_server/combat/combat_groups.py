"""Shared own NPC groups, leased atomically by map/instance/group.

No spectator protocol is invented. Observers obtain only available world groups;
caller broadcasts native removals on claim and own spawns on abort/respawn.
Defeated groups remain absent until an explicit local respawn policy restores them.
"""
from copy import deepcopy
from threading import RLock


class Groups:
    def __init__(self):
        self.lock = RLock()
        self.groups = {}
        self.sequence = 0

    def register(self, map_id, instance_id, group_id, members):
        from .combat_monster_world import spawn_group

        members = tuple(deepcopy(list(members)))
        if any(m["map_id"] != map_id for m in members):
            raise ValueError("Group belongs to another map")
        if any(m["instance_id"] != instance_id for m in members):
            raise ValueError("Group belongs to another instance")
        spawn_group(
            members, group_id=group_id
        )  # Enforce native ownership/roster constraints.
        key = (map_id, instance_id, group_id)
        if type(instance_id) is not int or instance_id < 0:
            raise ValueError("Invalid instance")
        with self.lock:
            if key in self.groups:
                if self.groups[key]["members"] != members:
                    raise ValueError("Conflicting existing group")
                return key
            ids = {m["id"] for m in members}
            if any(
                k[:2] == key[:2] and ids & {m["id"] for m in g["members"]}
                for k, g in self.groups.items()
            ):
                raise ValueError("NPC identity already exists in this map instance")
            self.groups[key] = dict(members=members, status="available", claim=None)
            return key

    def available(self, map_id, instance_id):
        with self.lock:
            return [
                dict(key=k, members=deepcopy(g["members"]))
                for k, g in self.groups.items()
                if k[:2] == (map_id, instance_id) and g["status"] == "available"
            ]

    def claim(self, key, generation, fight_id):
        if not generation or type(fight_id) is not int or not 0 < fight_id < 2**31:
            raise ValueError("Invalid fight lease")
        with self.lock:
            group = self.groups.get(key)
            if group is None or group["status"] != "available":
                raise ValueError("Group is unavailable")
            self.sequence += 1
            lease = (key, generation, fight_id, self.sequence)
            group.update(status="fighting", claim=lease)
            return lease, deepcopy(group["members"])

    def finish(self, lease, *, defeated):
        if type(defeated) is not bool:
            raise ValueError("Outcome must be explicit")
        with self.lock:
            group = self.groups.get(lease[0])
            if group is None or group["claim"] != lease:
                return False
            group.update(status="defeated" if defeated else "available", claim=None)
            return True

    def release_session(self, generation):
        with self.lock:
            restored = []
            for key, group in self.groups.items():
                if group["claim"] is not None and group["claim"][1] == generation:
                    group.update(status="available", claim=None)
                    restored.append(dict(key=key, members=deepcopy(group["members"])))
            return restored

    def respawn(self, key):
        with self.lock:
            group = self.groups[key]
            if group["status"] != "defeated":
                raise ValueError("Only defeated groups can respawn")
            group.update(status="available", claim=None)
            return deepcopy(group["members"])
