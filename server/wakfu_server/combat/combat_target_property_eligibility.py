"""Original eXt/eXs target75 execution gate and source-bound owned-state PL.

This is an effect gate, not primary selection or cast admission. World runtime
binds it before UID/RNG/L1 work. Original definitions supply state categories;
using them for Wakemu's authentic owned PL is an explicit reconstruction, not
an assertion that client cu() copies fyW.tyD.
"""
from functools import lru_cache
from pathlib import Path
import hashlib
import json

_CATEGORY_SHA256 = "f592ca9b95dc21f788cb6c1f1e3c45d8d1335e4d6dbc0f934ded2aaa29596f17"


@lru_cache(maxsize=1)
def _state_categories():
    raw = (
        Path(__file__).with_name("native_state_container_categories.json").read_bytes()
    )
    if hashlib.sha256(raw).hexdigest() != _CATEGORY_SHA256:
        raise ValueError("Owned state PL category source changed")
    data = json.loads(raw)
    ids = data.get("special_state_ids")
    if (
        data.get("schema") != "wakemu.source-definition-category-for-owned-state-PL.v1"
        or not isinstance(ids, list)
        or ids != sorted(set(ids))
        or any(type(value) is not int or value <= 0 for value in ids)
    ):
        raise ValueError("Malformed owned state PL categories")
    return data["qualified_native_release"], frozenset(ids)


def special_state_container(fight, invocation):
    """Resolve an actual active/retained iterator-owned state, never a label."""
    from wakfu_server import native_catalog
    from .combat_native_container import resolve_state_container

    if type(invocation.state_uid) is not int:
        raise ValueError("SPECIAL PL requires an authentic state container UID")
    state = resolve_state_container(fight, invocation.state_uid)
    if state.uid != invocation.state_uid or type(state.reference) is not int:
        raise ValueError("Owned state PL identity changed")
    revision, references = _state_categories()
    if native_catalog.release() != revision:
        raise ValueError("Owned state PL native publication changed")
    if state.reference not in references:
        raise ValueError("State category outside qualified native source")
    return True  # Every exported original definition has guU == SPECIAL.


def property75_eligible(
    fight, actor, invocation, *, actor_authority, retention, special_state_container
):
    """eZR.fSb: target.a(seS), except its actual SPECIAL fyW owner."""
    from .combat_property_stack import property_present

    counts = getattr(actor, "native_fight_property_counts", None)
    if counts is None:
        query = getattr(actor_authority, "property_counts", None)
        if not callable(query):
            raise ValueError("Missing complete native target property authority")
        counts = query(fight, actor)
    if not property_present(counts, 75):
        return True
    if retention is None or not callable(getattr(retention, "container", None)):
        raise ValueError("Missing actual eZR owner container")
    container, _ = retention.container(invocation)
    if container.get("container_type") != 1:
        return False
    if not callable(special_state_container):
        raise ValueError("Actual fyW SPECIAL state category authority required")
    special = special_state_container(invocation)
    if type(special) is not bool:
        raise ValueError("Verified fyW SPECIAL state category required")
    return special


def target_property_eligibility(*, fight, actor_authority, retention):
    """Bind eXt/eXs to live signed PB counters; no cached actor decisions."""
    from .combat_native_actor_lookup import native_actor

    def eligible(effect, invocation):
        actor = native_actor(fight, invocation.target_id)
        if actor is None:
            # Current faV contracts own fbo area properties, not fighter PB75.
            # Their existing typed-PV/resource guards remain authoritative;
            # an unknown/nonexistent target still errors in those guards.
            return True
        return property75_eligible(
            fight,
            actor,
            invocation,
            actor_authority=actor_authority,
            retention=retention,
            special_state_container=lambda row: special_state_container(fight, row),
        )

    return eligible
