"""Read explicit public lifecycle fields from captured graphs without gameplay imports."""
import json


def unwrap(value):
    if isinstance(value, dict):
        if set(value) == {"__tuple__"}:
            return tuple(unwrap(item) for item in value["__tuple__"])
        for key in ("__bytes_hex__", "bytes_hex"):
            if set(value) == {key}:
                return bytes.fromhex(value[key])
        return {key: unwrap(item) for key, item in value.items()}
    if isinstance(value, list):
        return [unwrap(item) for item in value]
    return value


class CapturedLifecycle:
    """Only inspect requested fields; do not materialize cyclic Fight objects."""

    def __init__(self, captured):
        if "game_state" in captured:
            captured = json.loads(captured["game_state"])
        if captured.get("schema") != "wakemu-combat-reproduction-state-v1":
            raise ValueError("Explicit captured combat graph required")
        self.graph = captured
        self.nodes = captured["nodes"]
        root = self.node(captured["root"])
        self.fields = (
            self.mapping(root["attrs"])
            if root["kind"] == "object"
            else self.mapping(captured["root"])
        )

    def node(self, reference):
        if not isinstance(reference, dict) or set(reference) != {"ref"}:
            raise ValueError("Explicit graph reference required")
        return self.nodes[reference["ref"]]

    def mapping(self, reference):
        node = self.node(reference)
        if node["kind"] != "dict":
            raise ValueError("Explicit captured mapping required")
        return dict(node["items"])

    def attributes(self, reference):
        node = self.node(reference)
        if node["kind"] == "dict":
            return self.mapping(reference)
        if node["kind"] != "object":
            raise ValueError("Explicit captured owner instance required")
        return self.mapping(node["attrs"])

    def sequence(self, reference):
        node = self.node(reference)
        if node["kind"] not in ("tuple", "list"):
            raise ValueError("Explicit captured sequence required")
        return node["items"]

    def states(self, ledger, owner):
        attributes = self.attributes(ledger)
        result = {}
        for reference in self.sequence(attributes["_entries"]):
            entry = self.attributes(reference)
            if entry["retained"] is True:
                result[str(entry["uid"])] = dict(
                    state_id=entry["reference"], level=entry["level"], owner=owner
                )
        return result

    def projection(self):
        states, areas = {}, {}
        for actor_id, reference in self.mapping(self.fields["actors"]).items():
            actor = self.attributes(reference)
            states.update(self.states(actor["state_ledger"], actor_id))
        if "native_effect_areas" not in self.fields:
            raise ValueError("Captured native area registry unavailable")
        for area_uid, reference in self.mapping(
            self.fields["native_effect_areas"]
        ).items():
            area = self.attributes(reference)
            areas[str(area_uid)] = dict(
                prototype=area["reference"], cell=list(self.sequence(area["cell"]))
            )
            if "state_ledger" in area and area["state_ledger"] is not None:
                states.update(self.states(area["state_ledger"], area_uid))
        return dict(states=states, areas=areas)

    def actor_ids(self):
        return tuple(self.mapping(self.fields["actors"]))
