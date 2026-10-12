"""Pure immutable-fact validation and local task evaluation."""
import hashlib
import uuid
from .catalog import canonical, positive


def event_payload(event):
    if type(event) is not dict:
        raise ValueError("Custom task event must be an object")
    kind = event.get("kind")
    if kind == "original_monster_killed":
        if (
            set(event) != {"kind", "fight_id", "actors"}
            or type(event["actors"]) is not list
            or not 1 <= len(event["actors"]) <= 10000
        ):
            raise ValueError("Invalid original monster facts")
        actors, seen = [], set()
        for actor in event["actors"]:
            if type(actor) is not dict or set(actor) != {"actor_id", "reference"}:
                raise ValueError("Invalid original monster actor")
            identity = actor["actor_id"]
            if (
                type(identity) is not int
                or not -(2**63) <= identity < 2**63
                or identity in seen
            ):
                raise ValueError("Invalid or duplicate original monster actor identity")
            seen.add(identity)
            actors.append(
                {"actor_id": identity, "reference": positive(actor["reference"])}
            )
        fight_id = event["fight_id"]
        if type(fight_id) is not int or not 0 < fight_id < 2**63:
            raise ValueError("Invalid custom task fight identity")
        return {
            "kind": kind,
            "fight_id": fight_id,
            "actors": sorted(actors, key=lambda actor: actor["actor_id"]),
        }
    if kind == "monster_seed_planted":
        if set(event) != {
            "kind",
            "family_ids",
            "seed_reference",
            "resource_reference",
            "operation_id",
        }:
            raise ValueError("Invalid successful monster seed facts")
        operation_id = event["operation_id"]
        if not isinstance(operation_id, str):
            raise ValueError("Invalid planting operation UUID")
        try:
            parsed = uuid.UUID(operation_id)
        except (ValueError, AttributeError) as exc:
            raise ValueError("Invalid planting operation UUID") from exc
        if parsed.hex != operation_id or parsed.int == 0:
            raise ValueError(
                "Planting operation UUID must be native lowercase32hex and nonzero"
            )
        result = {"kind": kind, "operation_id": operation_id}
        families = event["family_ids"]
        if type(families) is not list or not 1 <= len(families) <= 1000:
            raise ValueError("Invalid native planting family binding")
        for family in families:
            positive(family)
        if len(set(families)) != len(families):
            raise ValueError("Duplicate native planting family binding")
        result["family_ids"] = sorted(families)
        for field in ("seed_reference", "resource_reference"):
            result[field] = positive(event[field])
        return result
    raise ValueError("Unsupported custom task event")


def event_signature(event):
    payload = event_payload(event)
    return payload, hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def increment(definition, event):
    """Call only with validated definitions and event_payload output."""
    predicate = definition["predicate"]
    if not definition["enabled"] or predicate["kind"] != event["kind"]:
        return 0
    if event["kind"] == "original_monster_killed":
        allowed = set(predicate["references"])
        return sum(actor["reference"] in allowed for actor in event["actors"])
    return int(
        predicate["family_id"] in event["family_ids"]
        and all(
            predicate[field] == event[field]
            for field in ("seed_reference", "resource_reference")
        )
    )


def canonical_event_key(event):
    """Derive the only admitted dedupe identity from a validated source fact."""
    if event["kind"] == "original_monster_killed":
        return "fight:" + str(event["fight_id"])
    return "planting:" + event["operation_id"]
