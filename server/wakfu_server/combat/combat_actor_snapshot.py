"""Authoritative fresh actor snapshots from native ffh/ffx and owned gear.

Initialize once, before combat effects. Handlers subsequently mutate the same
snapshot; rebuilding would erase active modifiers and is deliberately rejected.
Absent characteristic values are never filled with invented zeros.
"""
import gzip
import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT
from wakfu_server.equipment_stats import bonuses, effective_character
from .equipment_damage import _float


@lru_cache(maxsize=1)
def native_actor_catalog():
    with gzip.open(DATA_ROOT / "native-actor-characteristics.json.gz", "rt") as source:
        return json.load(source)


def _int32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def _clamp(value, minimum, maximum):
    return min(maximum, max(minimum, value))


def _fresh(actor, running_effects):
    if running_effects is None or tuple(running_effects):
        raise ValueError(
            "Fresh snapshots require authoritatively empty running effects"
        )
    if actor.state_ledger.entries or any(
        getattr(actor, name) is not None
        for name in (
            "effect_stats",
            "effect_minima",
            "effect_maxima",
            "effect_frozen",
            "physical_radius",
            "spell_ap_cost_modifiers",
        )
    ):
        raise ValueError(
            "Cannot replace an initialized or state-modified actor snapshot"
        )


@dataclass(frozen=True)
class ActorSnapshot:
    actor_id: int
    stats: dict
    minima: dict
    maxima: dict
    frozen: frozenset
    physical_radius: int
    provenance: str
    percentages: dict = field(default_factory=dict)
    base_maxima: dict = field(default_factory=dict)

    def install(self, actor):
        _fresh(actor, ())
        if (
            actor.id != self.actor_id
            or any(
                self.stats[k] != v
                for k, v in (
                    (1, actor.hp),
                    (2, actor.ap),
                    (3, actor.mp),
                    (35, actor.initiative),
                )
            )
            or any(
                self.maxima[k] != v
                for k, v in ((1, actor.max_hp), (2, actor.max_ap), (3, actor.max_mp))
            )
        ):
            raise ValueError("Actor changed since native snapshot construction")
        actor.effect_stats = dict(self.stats)
        actor.effect_minima = dict(self.minima)
        actor.effect_maxima = dict(self.maxima)
        actor.effect_frozen = self.frozen
        actor.physical_radius = self.physical_radius
        actor.effect_percentages = dict(self.percentages)
        actor.effect_base_maxima = dict(self.base_maxima)
        # Resource native PA.bqF is explicitly initialized before live effects.
        actor.effect_base_minima = dict(self.minima)
        # eGj constructor creates eHl with null pOJ/pOK; a(fyU) returns0.
        # Builders reject running effects and non-flat gear/aptitudes, so no
        # effect capable of writing eHl has run at this fresh boundary.
        # Future passives/active handlers must mutate this same mapping.
        actor.spell_ap_cost_modifiers = {}


def _rows(catalog):
    rows = {int(k): v for k, v in catalog["characteristics"].items()}
    if not {1, 2, 3, 4, 9, 32, 35, 92, 97, 100} <= rows.keys():
        raise ValueError("Incomplete native characteristic catalog")
    return rows


def _finish(actor, rows, values, *, wp_current, wp_maximum, radius, provenance):
    if type(radius) is not int or not 0 <= radius <= 127:
        raise ValueError("Unsupported native physical radius")
    minima = {k: v["minimum"] for k, v in values.items()}
    maxima = {k: v["maximum"] for k, v in values.items()}
    stats = {k: v["current"] for k, v in values.items()}
    frozen = frozenset(k for k, v in values.items() if v["frozen"])
    for k, current, maximum in (
        (1, actor.hp, actor.max_hp),
        (2, actor.ap, actor.max_ap),
        (3, actor.mp, actor.max_mp),
        (4, wp_current, wp_maximum),
    ):
        row = rows[k]
        if (
            type(current) is not int
            or type(maximum) is not int
            or not row["hard_minimum"] <= current <= maximum <= row["hard_maximum"]
        ):
            raise ValueError("Live resource violates native bounds")
        stats[k] = current
        maxima[k] = maximum
    stats[35] = actor.initiative
    return ActorSnapshot(
        actor.id,
        stats,
        minima,
        maxima,
        frozen,
        radius,
        provenance,
        {k: 0 for k in stats},
        dict(maxima),
    )


def build_player_snapshot(
    character,
    actor,
    *,
    wp_current,
    wp_maximum,
    running_effects,
    build_index=None,
    catalog=None
):
    """bjo uses ffh/eGE.pIq; gear/aptitudes come from owned selected sheet.

    Actor resources are already authoritative, including level adjustment.
    Unsupported equipment/aptitude effects reject initialization. Deck passives
    must subsequently execute through their own native registration path.
    """
    _fresh(actor, running_effects)
    if actor.id != character["id"] or not actor.controlled:
        raise ValueError("Player snapshot belongs to a different actor")
    catalog = native_actor_catalog() if catalog is None else catalog
    rows = _rows(catalog)
    adjusted = dict(character, level=actor.effective_level)
    evaluated = bonuses(adjusted, build_index=build_index)
    if evaluated["unsupported"]:
        raise ValueError("Unsupported owned equipment/aptitude effects")
    if set(evaluated["percentages"]) - {1}:
        raise ValueError("Unsupported native percentage characteristic")
    if actor.max_hp != effective_character(adjusted, build_index=build_index)["max_hp"]:
        raise ValueError("Live player maximum HP disagrees with owned build")
    values = {k: dict(v) for k, v in rows.items()}
    for k, delta in evaluated["stats"].items():
        if k not in rows:
            raise ValueError("Unknown owned characteristic bonus")
        row = values[k]
        if rows[k]["expandable"]:
            row["maximum"] = _clamp(
                _int32(row["maximum"] + delta),
                rows[k]["hard_minimum"],
                rows[k]["hard_maximum"],
            )
        row["current"] = _clamp(
            _int32(row["current"] + delta), row["minimum"], row["maximum"]
        )
    result = _finish(
        actor,
        rows,
        values,
        wp_current=wp_current,
        wp_maximum=wp_maximum,
        radius=catalog["default_actor_radius"],
        provenance="bjo ffh + owned equipment/aptitudes + live resources",
    )
    percentage = evaluated["percentages"].get(1, 0)
    if percentage:
        result.percentages[1] = percentage
        result.base_maxima[1] = effective_character(adjusted, build_index=build_index)[
            "base_max_hp"
        ] + evaluated["stats"].get(1, 0)
    return result


def build_npc_snapshot(
    monster, actor, *, wp_current, wp_maximum, running_effects, catalog=None
):
    """Exact bbo/ffC/ffx curves, anchored at native minimum breed level.

    ffC multiplies float32 growth as double, truncates/saturates d2i, then wraps
    iadd. Full reference characteristics include combat mastery/resistance.
    Local instance resource overrides remain authoritative and explicit.
    """
    _fresh(actor, running_effects)
    if actor.id != monster["id"] or actor.controlled:
        raise ValueError("NPC snapshot belongs to a different actor")
    catalog = native_actor_catalog() if catalog is None else catalog
    rows = _rows(catalog)
    profile = catalog["npc_profiles"].get(str(monster["ref"]))
    if (
        profile is None
        or type(actor.effective_level) is not int
        or not 0 < actor.effective_level < 32768
    ):
        raise ValueError("Missing native NPC profile or level")
    values = {int(k): dict(v) for k, v in profile["at_base_level"].items()}
    if set(values) != set(rows):
        raise ValueError("Incomplete native lazy NPC characteristic fixture")
    for k, row in rows.items():
        curve = profile["curves"].get(str(k))
        if curve is None:
            continue  # Native feZ initialized every PC with ffw.aZs().
        growth = (actor.effective_level - profile["base_level"]) * _float(curve[1])
        increment = _clamp(math.trunc(growth), -(1 << 31), (1 << 31) - 1)
        native = _int32(curve[0] + increment)
        value = values[k]
        if row["expandable"]:
            value["maximum"] = _clamp(native, row["hard_minimum"], row["hard_maximum"])
        value["current"] = _clamp(native, value["minimum"], value["maximum"])
    return _finish(
        actor,
        rows,
        values,
        wp_current=wp_current,
        wp_maximum=wp_maximum,
        radius=profile["physical_radius"],
        provenance="bbo native NPC curves + ffx bounds + live resources",
    )


def initialize_fight_snapshots(
    fight, *, characters, monsters, wp_resources, running_effects, initial_effect_uid
):
    """Initialize every fresh participant atomically before placement publishes.

    Source maps use actor IDs; wp_resources[id]=(current,maximum) and explicit
    running_effects[id] cover the exact roster. No new identities or creature
    mechanics are inferred. UID counter is fight-local and caller-owned.
    """
    identities = set(fight.actors)
    if (
        fight.phase != "placement"
        or fight.native_effect_uid_next is not None
        or fight.owned_stat_effects
        or fight.state_wire_payloads
    ):
        raise ValueError("Fight is not an uninitialized placement")
    if (
        type(initial_effect_uid) is not int
        or not 0 < initial_effect_uid < (1 << 63)
        or set(characters) & set(monsters)
        or set(characters) | set(monsters) != identities
        or set(wp_resources) != identities
        or set(running_effects) != identities
    ):
        raise ValueError("Missing exact fight snapshot sources or initial UID")
    prepared = {}
    for identity, actor in fight.actors.items():
        wp = wp_resources[identity]
        if not isinstance(wp, (tuple, list)) or len(wp) != 2:
            raise ValueError("Missing native actor WP current/maximum")
        if identity in characters:
            snapshot = build_player_snapshot(
                characters[identity],
                actor,
                wp_current=wp[0],
                wp_maximum=wp[1],
                running_effects=running_effects[identity],
            )
        else:
            snapshot = build_npc_snapshot(
                monsters[identity],
                actor,
                wp_current=wp[0],
                wp_maximum=wp[1],
                running_effects=running_effects[identity],
            )
        prepared[identity] = snapshot
    # All builders above are read-only. Each installation below performs only
    # dataclass field assignments, after the entire roster has been validated.
    for identity, snapshot in prepared.items():
        snapshot.install(fight.actors[identity])
    fight.native_effect_uid_next = initial_effect_uid
    return prepared
