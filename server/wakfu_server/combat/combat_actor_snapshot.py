"""Authoritative fresh actor snapshots from native ffh/ffx and owned gear.

Initialize once, before combat effects. Handlers subsequently mutate the same
snapshot; rebuilding would erase active modifiers and is deliberately rejected.
Absent characteristic values are never filled with invented zeros.
"""

from wakfu_server import native_catalog as protocol_catalog
import json
import math
from dataclasses import dataclass, field, replace
from functools import lru_cache
from collections import OrderedDict
from threading import RLock
from types import MappingProxyType
from wakfu_server.native_source_singleflight import NativeSourceFlights
from wakfu_server.paths import DATA_ROOT
from wakfu_server.equipment_stats import bonuses, effective_character
from .combat_native_death_status import FreshPlayerDeathConstructor
from wakfu_server.equipment_damage import _float


@lru_cache(maxsize=1)
def native_actor_catalog():
    from wakfu_server.combat_published_catalogs import compilation_mode
    from wakfu_server.native_catalog_document import load_published_document

    if not compilation_mode():
        return load_published_document("native-actor-characteristics.json")

    return protocol_catalog.load(DATA_ROOT / "native-actor-characteristics.json")


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
            "spell_range_modifiers",
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
    native_los_height: int | None = None

    native_hud_breed: int | None = None
    native_physical_position: tuple | None = None
    native_jump_height: int | None = None
    native_cosmetic_state: dict | None = None
    native_hp_on_operand: dict | None = None
    base_minima: dict | None = None
    native_initial_team: int | None = None
    native_player_death_constructor: FreshPlayerDeathConstructor | None = None

    def install(self, actor):
        _fresh(actor, ())
        if self.native_initial_team is not None and (
            type(self.native_initial_team) is not int
            or self.native_initial_team not in (0, 1)
            or actor.team != self.native_initial_team
        ):
            raise ValueError("Actor team changed since native snapshot construction")
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
        if (
            type(self.native_los_height) is not int
            or not -128 <= self.native_los_height < 128
            or actor.native_los_height not in (None, self.native_los_height)
        ):
            raise ValueError("Missing or conflicting native actor LOS height")
        if (
            self.native_physical_position != actor.position
            or self.native_jump_height != 4
        ):
            raise ValueError("Missing or changed native fresh actor physics snapshot")
        if self.native_player_death_constructor is not None:
            from .combat_native_death_status import (
                validate_fresh_player_death_constructor,
            )

            validate_fresh_player_death_constructor(
                actor, self.native_player_death_constructor
            )
        existing_cosmetics = getattr(actor, "native_cosmetic_state", None)
        if (
            self.native_cosmetic_state is not None
            and existing_cosmetics is not None
            and existing_cosmetics != self.native_cosmetic_state
        ):
            raise ValueError("Conflicting native fresh cosmetic constructor state")
        actor.native_hud_breed = self.native_hud_breed
        actor.native_physical_position = self.native_physical_position
        actor.native_jump_height = self.native_jump_height
        actor.native_los_height = self.native_los_height
        if self.native_cosmetic_state is not None:
            actor.native_cosmetic_state = {
                "selected_values": dict(self.native_cosmetic_state["selected_values"]),
                "active_cosmetics": dict(
                    self.native_cosmetic_state["active_cosmetics"]
                ),
            }
        actor.effect_stats = dict(self.stats)
        actor.effect_minima = dict(self.minima)
        actor.effect_maxima = dict(self.maxima)
        actor.effect_frozen = self.frozen
        if all(k in self.stats and k not in self.frozen for k in (2, 3)):
            from .combat_resource_pa_notifications import RAW_SOURCE

            actor.effect_resource_raw_currents = {k: self.stats[k] for k in (2, 3)}
            actor.native_resource_raw_current_source = RAW_SOURCE
        actor.physical_radius = self.physical_radius
        actor.effect_percentages = dict(self.percentages)
        actor.effect_base_maxima = dict(self.base_maxima)
        # Resource native PA.bqF is explicitly initialized before live effects.
        actor.effect_base_minima = dict(
            self.minima if self.base_minima is None else self.base_minima
        )
        from .combat_hupper_resource_binding import install as install_wp_binding

        install_wp_binding(actor)
        if self.native_hp_on_operand is not None:
            from .combat_hp_raw import install_fresh_hp_operand

            install_fresh_hp_operand(actor, self.native_hp_on_operand)
        # eGj constructor creates eHl with null pOJ/pOK; a(fyU) returns0.
        # Builders reject running effects and non-flat gear/aptitudes, so no
        # effect capable of writing eHl has run at this fresh boundary.
        # Future passives/active handlers must mutate this same mapping.
        actor.spell_ap_cost_modifiers = {}
        actor.spell_range_modifiers = {}
        # All owned fresh actor serializers emit po.SX=0 after characteristics.
        # eGm.zm copies that byte through eGj.lx into eGz.pHH.
        actor.native_controlled_by_ai = False
        from .combat_restore_strategy import initialize_restore_strategy

        initialize_restore_strategy(actor)
        actor.native_death_script_id = (
            -1
        )  # Fresh eGj constructor, before retained effects.
        actor.native_turn_suppression_bits = 0  # Fresh eGj.pGO = new BitSet().
        from .combat_departure_predicates import initialize_fresh_departure_flags

        initialize_fresh_departure_flags(actor)
        if self.native_player_death_constructor is not None and not hasattr(
            actor, "native_death_status"
        ):
            from .combat_native_death_status import initialize_fresh_player_death_status

            initialize_fresh_player_death_status(
                actor, constructor=self.native_player_death_constructor
            )


_CHARACTERISTIC_INDEX = OrderedDict()
_CHARACTERISTIC_INDEX_BYTES = 0
_CHARACTERISTIC_INDEX_LOCK = RLock()
_CHARACTERISTIC_INDEX_FLIGHTS = NativeSourceFlights()
_CHARACTERISTIC_MAX_GENERATIONS = 4
_CHARACTERISTIC_MAX_ROWS = 128
_CHARACTERISTIC_MAX_BYTES = 256 * 1024


def _read_characteristic_rows(source):
    rows = {}
    for key, row in source.items():
        identity = int(key)
        if identity in rows:
            raise ValueError("Duplicate native characteristic identity")
        rows[identity] = row
    if not {1, 2, 3, 4, 9, 32, 35, 92, 97, 100} <= rows.keys():
        raise ValueError("Incomplete native characteristic catalog")
    return rows


def _characteristic_projection(source, key):
    global _CHARACTERISTIC_INDEX_BYTES
    # The only retained values are small immutable PC definitions, never NPC
    # profiles, levels, actors, state ledgers, resource values or fight state.
    rows = _read_characteristic_rows(source)
    if len(rows) > _CHARACTERISTIC_MAX_ROWS:
        return rows
    if any(
        type(row) is not dict
        or len(row) > 16
        or any(
            type(field) is not str
            or len(field) > 128
            or type(value) not in (str, int, float, bool, type(None))
            or type(value) is str
            and len(value) > 1024
            for field, value in row.items()
        )
        for row in rows.values()
    ):
        return rows
    try:
        size = len(
            json.dumps(
                rows,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode()
        )
    except (TypeError, ValueError):
        return rows
    if size > _CHARACTERISTIC_MAX_BYTES:
        return rows
    immutable = MappingProxyType(
        {identity: MappingProxyType(dict(row)) for identity, row in rows.items()}
    )
    with _CHARACTERISTIC_INDEX_LOCK:
        previous = _CHARACTERISTIC_INDEX.pop(key, None)
        if previous is not None:
            _CHARACTERISTIC_INDEX_BYTES -= previous[1]
        _CHARACTERISTIC_INDEX[key] = (immutable, size)
        _CHARACTERISTIC_INDEX_BYTES += size
        while (
            len(_CHARACTERISTIC_INDEX) > _CHARACTERISTIC_MAX_GENERATIONS
            or _CHARACTERISTIC_INDEX_BYTES > _CHARACTERISTIC_MAX_BYTES
        ):
            _, (_, removed) = _CHARACTERISTIC_INDEX.popitem(last=False)
            _CHARACTERISTIC_INDEX_BYTES -= removed
    return immutable


def _rows(catalog):
    source = catalog["characteristics"]
    from .combat_published_catalogs import static_catalog_descriptor

    descriptor = static_catalog_descriptor(source)
    # Caller-owned dictionaries are intentionally revalidated on every call;
    # only a sealed publication proves an immutable cache identity.
    if descriptor is None or source.representation != "native_json":
        return _read_characteristic_rows(source)
    key = tuple(sorted(descriptor.items()))
    with _CHARACTERISTIC_INDEX_LOCK:
        cached = _CHARACTERISTIC_INDEX.get(key)
        if cached is not None:
            _CHARACTERISTIC_INDEX.move_to_end(key)
            return cached[0]
    return _CHARACTERISTIC_INDEX_FLIGHTS.run(
        key, lambda: _characteristic_projection(source, key)
    )


def native_characteristic_definitions(catalog=None):
    """Share the small sealed PC definition index, never live actor values."""
    return _rows(native_actor_catalog() if catalog is None else catalog)


def _finish(
    actor, rows, values, *, wp_current, wp_maximum, radius, provenance, los_height
):
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
        los_height,
        native_physical_position=tuple(actor.position),
        native_jump_height=4,
        native_initial_team=actor.team,
        native_hp_on_operand=(
            None
            if 1 in frozen
            else dict(
                producer="fresh_initial_tB_HP.on_resource_override",
                actor_id=actor.id,
                raw_current=actor.hp,
            )
        ),
    )


def build_player_snapshot(
    character,
    actor,
    *,
    wp_current,
    wp_maximum,
    running_effects,
    build_index=None,
    catalog=None,
    dev_skip_unsupported=False,
    initialization_warnings=None
):
    """bjo uses ffh/eGE.pIq; gear/aptitudes come from owned selected sheet.

    Actor resources are already authoritative, including level adjustment.
    Unsupported equipment/aptitude effects reject initialization. Deck passives
    must subsequently execute through their own native registration path.
    """
    _fresh(actor, running_effects)
    if actor.id != character["id"] or not actor.controlled:
        raise ValueError("Player snapshot belongs to a different actor")
    from wakfu_server.builds import effective_sheet_level

    selected_index = (
        character.get("active_build_index", 0) if build_index is None else build_index
    )
    if actor.effective_level != effective_sheet_level(character, selected_index):
        raise ValueError("Live player level disagrees with owned build")
    catalog = native_actor_catalog() if catalog is None else catalog
    rows = _rows(catalog)
    adjusted = dict(character, level=actor.effective_level)
    evaluated = bonuses(adjusted, build_index=build_index)
    from .combat_initialization_policy import partition_unsupported_equipment

    from .combat_equipment_snapshot_roles import snapshot_roles

    roles = snapshot_roles(adjusted, evaluated["unsupported"])
    static_unsupported = [
        row
        for row in evaluated["unsupported"]
        if not isinstance(row, dict)
        or (
            row.get("uid"),
            row.get("reference"),
            row.get("effect_id"),
            row.get("generic"),
        )
        not in roles
    ]
    rejected, skipped = partition_unsupported_equipment(
        static_unsupported, enabled=dev_skip_unsupported
    )
    if initialization_warnings is not None and not isinstance(
        initialization_warnings, list
    ):
        raise ValueError("Initialization warnings must be an owned list")
    if skipped and initialization_warnings is None:
        raise ValueError("Development fallback requires explicit diagnostics collector")
    if rejected:
        details = json.dumps(
            {
                "count": len(rejected),
                "effects": rejected[:16],
            },
            separators=(",", ":"),
        )
        raise ValueError("Unsupported owned equipment/aptitude effects: " + details)
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
        los_height=catalog.get("default_actor_los_height"),
        provenance="bjo ffh + owned equipment/aptitudes + live resources",
    )
    percentage = evaluated["percentages"].get(1, 0)
    if percentage:
        result.percentages[1] = percentage
        result.base_maxima[1] = effective_character(adjusted, build_index=build_index)[
            "base_max_hp"
        ] + evaluated["stats"].get(1, 0)
    hp_projection = character.get("equipment_hp_projection")
    if hp_projection is not None:
        from wakfu_server.equipment_hp_lifecycle import (
            NativeHPActor,
            OwnedEwoHPReplay,
        )

        if (
            not isinstance(hp_projection, dict)
            or not isinstance(hp_projection.get("actor"), dict)
            or not isinstance(hp_projection.get("receipts"), (tuple, list))
        ):
            raise ValueError("Malformed persisted eWO HP actor snapshot")
        projected_actor = NativeHPActor(**hp_projection["actor"])
        projected_replay = OwnedEwoHPReplay(projected_actor, hp_projection["receipts"])
        if (
            not projected_replay.matches(evaluated["hp_operations"])
            or projected_actor.hp != actor.hp
            or projected_actor.max_hp != actor.max_hp
            or projected_actor.effect_minima[1] != result.minima[1]
            or projected_actor.effect_percentages[1] != percentage
            or (1 in projected_actor.effect_frozen) != (1 in result.frozen)
        ):
            raise ValueError("Persisted eWO HP PA disagrees with fresh player actor")
        base_maxima = dict(result.base_maxima)
        base_minima = dict(result.minima)
        base_maxima[1] = projected_actor.effect_base_maxima[1]
        base_minima[1] = projected_actor.effect_base_minima[1]
        result = replace(
            result,
            base_maxima=base_maxima,
            base_minima=base_minima,
            native_hp_on_operand=(
                None
                if 1 in result.frozen
                else dict(
                    producer="fresh_initial_tB_HP.on_resource_override",
                    actor_id=actor.id,
                    raw_current=projected_actor.effect_hp_raw_current,
                )
            ),
        )
    if initialization_warnings is not None:
        from .combat_initialization_policy import initialization_warning

        initialization_warnings.extend(
            initialization_warning(actor.id, e) for e in skipped
        )
    from .combat_cosmetic_conditions import fresh_player_cosmetic_state
    from .combat_native_death_status import fresh_player_death_constructor

    return replace(
        result,
        native_hud_breed=character["breed"],
        native_cosmetic_state=fresh_player_cosmetic_state(character),
        native_player_death_constructor=fresh_player_death_constructor(actor.id),
    )


def native_npc_creation_values(reference, level, *, catalog=None):
    """Native ffx creation at any nonnegative signed-short level, also for eHD.

    World spawn policy may impose breed min/max separately; eZl creates its
    descriptor at spell/caster level and does not impose that policy.
    """
    catalog = native_actor_catalog() if catalog is None else catalog
    rows = _rows(catalog)
    profile = catalog["npc_profiles"].get(str(reference))
    if profile is None or type(level) is not int or not 0 <= level < 32768:
        raise ValueError("Missing native NPC profile or level")
    values = {int(k): dict(v) for k, v in profile["at_base_level"].items()}
    if set(values) != set(rows):
        raise ValueError("Incomplete native lazy NPC characteristic fixture")
    for k, row in rows.items():
        curve = profile["curves"].get(str(k))
        if curve is None:
            continue  # Native feZ initialized every PC with ffw.aZs().
        growth = (level - profile["base_level"]) * _float(curve[1])
        increment = _clamp(math.trunc(growth), -(1 << 31), (1 << 31) - 1)
        native = _int32(curve[0] + increment)
        value = values[k]
        if row["expandable"]:
            value["maximum"] = _clamp(native, row["hard_minimum"], row["hard_maximum"])
        value["current"] = _clamp(native, value["minimum"], value["maximum"])
    return values


def build_npc_snapshot(
    monster, actor, *, wp_current, wp_maximum, running_effects, catalog=None
):
    """Exact bbo/ffC/ffx curves with explicit owned live resource overrides."""
    _fresh(actor, running_effects)
    if actor.id != monster["id"] or actor.controlled:
        raise ValueError("NPC snapshot belongs to a different actor")
    catalog = native_actor_catalog() if catalog is None else catalog
    rows = _rows(catalog)
    profile = catalog["npc_profiles"].get(str(monster["ref"]))
    values = native_npc_creation_values(
        monster["ref"], actor.effective_level, catalog=catalog
    )
    return _finish(
        actor,
        rows,
        values,
        wp_current=wp_current,
        wp_maximum=wp_maximum,
        radius=profile["physical_radius"],
        los_height=profile.get("native_los_height"),
        provenance="bbo native NPC curves + ffx bounds + live resources",
    )


def initialize_fight_snapshots(
    fight,
    *,
    characters,
    monsters,
    wp_resources,
    running_effects,
    initial_effect_uid,
    dev_skip_unsupported=False,
    initialization_warnings=None
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
    existing_pr_policy = getattr(fight, "native_pr_completion_authority", None)
    if existing_pr_policy is not None and (
        not isinstance(existing_pr_policy, dict)
        or existing_pr_policy.get("source") != "wakemu.fresh.pr_notification_policy"
        or existing_pr_policy.get("watchers") != []
        or existing_pr_policy.get("completed") != []
    ):
        raise ValueError(
            "Existing PR notification authority is not a fresh Wakemu policy"
        )
    if (
        type(initial_effect_uid) is not int
        or not 0 < initial_effect_uid < (1 << 63)
        or set(characters) & set(monsters)
        or set(characters) | set(monsters) != identities
        or set(wp_resources) != identities
        or set(running_effects) != identities
    ):
        raise ValueError("Missing exact fight snapshot sources or initial UID")
    from .combat_haven_world_context import validate_placement

    validate_placement(fight, characters, monsters)
    if type(dev_skip_unsupported) is not bool:
        raise ValueError("Development initialization fallback must be boolean")
    if initialization_warnings is not None and not isinstance(
        initialization_warnings, list
    ):
        raise ValueError("Initialization warnings must be an owned list")
    if dev_skip_unsupported and initialization_warnings is None:
        raise ValueError("Development fallback requires explicit diagnostics collector")
    local_warnings = []
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
                dev_skip_unsupported=dev_skip_unsupported,
                initialization_warnings=local_warnings,
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
    from .combat_qi_fight import prepare_fresh_actor_slots, install_fresh_actor_slots

    qi_registry = prepare_fresh_actor_slots(
        fight,
        physical_radii={
            identity: value.physical_radius for identity, value in prepared.items()
        },
    )
    from .combat_npc_initialization import (
        initial_plans,
        initialize_ordinary_npcs,
        initial_property_counts,
        install_initial_properties,
    )

    plans = initial_plans(fight, monsters)
    properties = initial_property_counts(monsters)
    from .combat_npc_ai_initialization import initial_ai_actors

    ai_actors = initial_ai_actors(fight, monsters)
    from .combat_automatic_npc_turn import initial_root_manifest, install_root_manifest

    root_manifest = initial_root_manifest(fight, monsters)
    original_fight = fight
    if plans:
        from copy import deepcopy

        # Constructor children may reject. Never publish partial actor/state
        # mutations or consume the live effect UID on that failure boundary.
        fight = deepcopy(fight)
    # All builders above are read-only. Each installation below performs only
    # dataclass field assignments, after the entire roster has been validated.
    for identity, snapshot in prepared.items():
        snapshot.install(fight.actors[identity])
        if identity in properties:
            # Breed properties are constructor facts even with no activated
            # innate state or offensive ability (including turnless actors).
            install_initial_properties(fight.actors[identity], properties[identity])
        if identity in ai_actors:
            # Establish the actual tactical server controller before initial
            # effects run. Subsequent native control effects remain authoritative.
            fight.actors[identity].native_controlled_by_ai = True
        if identity in characters:
            # Actual fresh biB WP observers are bkq/biB, UI refresh only.
            # No owned eWr/eXb link has run at this validated fresh boundary.
            fight.actors[identity].native_resource_numeric_observers = {4: ()}
    fight.native_npc_ai_actors = ai_actors
    install_root_manifest(fight, root_manifest)
    if plans:
        fight.native_effect_uid_next = initial_effect_uid
        initialize_ordinary_npcs(fight, monsters, plans)
    install_fresh_actor_slots(fight, qi_registry)
    from .combat_pr_completion import fresh_pr_completion_authority

    if existing_pr_policy is None:
        # A successfully initialized fresh fight owns an explicit Wakemu PR
        # observer policy. Restored fights must restore their own provenance;
        # they do not inherit this constructor choice implicitly.
        fight.native_pr_completion_authority = fresh_pr_completion_authority()
    if not plans:
        fight.native_effect_uid_next = initial_effect_uid
    if fight is not original_fight:
        from .combat_pointer_qi_commit import prepare_pointer_commit

        pointer_binding = prepare_pointer_commit(fight)
        if pointer_binding is not None:
            pointer_binding.stage(original_fight)
        original_actors = original_fight.actors
        for identity, actor in fight.actors.items():
            original_actors[identity].__dict__.clear()
            original_actors[identity].__dict__.update(actor.__dict__)
        fight.actors = original_actors
        original_fight.__dict__.clear()
        original_fight.__dict__.update(fight.__dict__)
        if pointer_binding is not None:
            pointer_binding.publish()
    if initialization_warnings is not None:
        initialization_warnings.extend(local_warnings)
    return prepared
