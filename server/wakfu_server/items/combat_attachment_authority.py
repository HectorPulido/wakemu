"""Immutable enabled attachment authority for one owned combat preparation."""
from types import MappingProxyType

from .sublimation_eligibility import decode_pattern, decode_special_target


class CombatAttachmentAuthority:
    def __init__(self, patterns, targets):
        self.patterns = MappingProxyType(self._records(patterns, decode_pattern))
        self.targets = MappingProxyType(self._records(targets, decode_special_target))

    @staticmethod
    def _records(rows, decode):
        result = {}
        seen = set()
        for row in rows:
            reference = row.get("reference")
            if type(reference) is not int or reference <= 0 or reference in seen:
                raise ValueError("Invalid native attachment authority identity")
            seen.add(reference)
            if type(row.get("enabled")) is not bool:
                raise ValueError("Missing native attachment enablement")
            if row["enabled"]:
                result[reference] = MappingProxyType(dict(decode(row)))
        return result

    @classmethod
    def from_database(cls, db):
        patterns = db.execute(
            "SELECT reference,slot_colors,pattern_type,client_jar_sha256,enabled "
            "FROM native_sublimation_patterns ORDER BY reference"
        ).fetchall()
        targets = db.execute(
            "SELECT reference,item_level,pattern_type,rarity_code,"
            "client_jar_sha256,enabled FROM native_sublimation_targets "
            "ORDER BY reference"
        ).fetchall()
        return cls(patterns, targets)

    def __call__(self, gear, state, reference, field_tag):
        from wakfu_server.inventory_shards import validate
        from wakfu_server.wire import proto_fields

        if type(reference) is not int or type(field_tag) is not int:
            raise ValueError("Invalid native attachment source identity")
        validate(state)
        fields = dict(proto_fields(state))
        if field_tag not in (24, 32) or fields.get(field_tag, 0) != reference:
            raise ValueError("Attachment source differs from persisted native slot")
        entry = self.patterns.get(reference)
        if entry is None:
            return False  # Missing/disabled native definitions yield no iterator.
        if entry["tag"] != field_tag or gear.get("quantity") != 1:
            return False
        if entry["kind"] != "BASIC":
            target = self.targets.get(gear.get("reference"))
            return target is not None and target["pattern_type"] == entry["kind"]
        slots = []
        for tag, nested in proto_fields(state):
            if tag == 10:
                row = dict(proto_fields(nested))
                slots.append((row.get(80, 0), row.get(96, 0)))
        slots.sort()
        if [position for position, _ in slots] != list(range(len(slots))):
            raise ValueError("Socket slots have invalid native positions")
        required = entry["colors"]
        for start in range(len(slots) - len(required) + 1):
            if all(
                actual in (1, 2, 3, 4)
                and (actual == 4 or expected == 0 or actual == expected)
                for (_, actual), expected in zip(slots[start:], required)
            ):
                return True
        return False
