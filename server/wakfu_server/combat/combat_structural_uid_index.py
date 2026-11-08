"""Ephemeral UID buckets constructed by the existing synchronize traversal."""
from collections import defaultdict
from .combat_retained_collections import OwnedMap, TrackedRow
from time import perf_counter_ns
from .combat_structural_qf_scope import COUNTS

SOURCE_MAPS = (
    "owned_stat_effects",
    "native_owned_group_effects",
    "native_owned_area_effects",
    "native_owned_spatial_effects",
)


class UidIndex:
    def __init__(self, fight):
        self.fight = fight
        self.by_manager = defaultdict(list)
        self.ordinals = {}
        self.valid = True
        self.carriers = {}
        started = perf_counter_ns()
        for name in SOURCE_MAPS:
            rows = getattr(fight, name, {})
            if type(rows) is not dict and type(rows) is not OwnedMap:
                self.valid = False
                break
            order = {}
            for position, uid in enumerate(rows):
                COUNTS["source_index_rows"] += 1
                if type(uid) is not int:
                    self.valid = False
                    break
                order[uid] = position
            self.ordinals[name] = order
        COUNTS["source_index_build_ns"] += perf_counter_ns() - started
        COUNTS["uid_index_builds"] += 1

    def capture_carrier(self, actor, state):
        COUNTS["carrier_index_rows"] += 1
        uid = state.uid
        if type(uid) is not int or uid in self.carriers:
            self.valid = False
            return
        self.carriers[uid] = (actor, state)

    def append(self, uid, record):
        COUNTS["uid_index_rows"] += 1
        if not self.valid:
            return
        if (
            type(uid) is not int
            or (type(record) is not dict and type(record) is not TrackedRow)
            or type(record.get("manager_id")) is not int
            or type(record.get("uid")) is not int
            or record["uid"] != uid
        ):
            self.valid = False
            return
        self.by_manager[record["manager_id"]].append(uid)

    def rows(self, name, uids):
        current, order = getattr(self.fight, name, {}), self.ordinals[name]
        # Read actual current rows; preserve their original source-map order.
        chosen = sorted((uid for uid in uids if uid in order), key=order.__getitem__)
        return ((uid, current[uid]) for uid in chosen)
