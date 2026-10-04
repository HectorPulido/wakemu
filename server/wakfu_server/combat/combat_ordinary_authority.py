"""Native authority for the exact ordinary PC/NPC creation path.

PC eHd kind0; NPC eHj kind1/master -1. eGj.d(eGH) loads fsp
breed properties. No summon/carrier/Qq relationships exist in these creation
blobs. This provider deliberately accepts neither summons nor wrapped actors.
"""
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT
from .combat_runtime_adapter import NativeActorAuthority


@lru_cache(maxsize=1)
def native_property_catalog():
    return json.loads((DATA_ROOT / "native-actor-properties.json").read_text())


class OrdinaryActorAuthority:
    def __init__(self, *, characters, monsters, decks, excluded_decks, catalog=None):
        if (
            set(characters) & set(monsters)
            or set(decks) != set(characters)
            or set(excluded_decks) != set(characters)
        ):
            raise ValueError("Exact owned player/NPC and deck sources required")
        self.characters, self.monsters = characters, monsters
        self.decks, self.excluded_decks = decks, excluded_decks
        self.catalog = native_property_catalog() if catalog is None else catalog

    def __call__(self, preview, actor):
        if set(preview.actors) != set(self.characters) | set(self.monsters):
            raise ValueError(
                "Ordinary authority roster changed: summons/wrapped actors need native registration"
            )
        if preview.actors.get(actor.id) is not actor:
            raise ValueError("Ordinary actor must belong to current preview")
        player = actor.id in self.characters
        source = (self.characters if player else self.monsters)[actor.id]
        if source["id"] != actor.id or actor.controlled != player:
            raise ValueError("Creation actor kind disagrees with owned source")
        profile = (
            self.catalog["player"]
            if player
            else self.catalog["npc"].get(str(source["ref"]))
        )
        if profile is None:
            raise ValueError("Missing native breed properties")
        # Creation has no summon/master/carrier registration. If a future
        # effect installs relationships it must update authority explicitly.
        if any(
            getattr(actor, key, None) is not None
            for key in ("native_master_id", "native_carrier_id")
        ):
            raise ValueError(
                "Ordinary authority cannot attest changed native relationships"
            )
        properties = frozenset(profile["fight_properties"])
        live = getattr(actor, "native_fight_properties", None)
        if live is not None:
            properties = frozenset(live)
        # eGn.zm copies pW.Uj (our serialized fight team) through eGj.M
        # into eGz.bgW; eGj.bcN reads that exact signed byte.
        if type(actor.team) is not int or not 0 <= actor.team < 128:
            raise ValueError("Missing native signed-byte fight affiliation")
        context = dict(
            bcN=actor.team,
            is_amO=True,
            is_eGj=True,
            is_Qq=False,
            is_eHH=True,
            bEe=42 not in properties,
            UNTARGETTABLE_BY_OTHER=21 in properties,
            buX=False,
            dTE=False,
            dpu_id=None,
            baG=False,
            baK=False,
        )
        return NativeActorAuthority(
            context,
            player,
            frozenset(self.decks[actor.id]) if player else frozenset(),
            frozenset(self.excluded_decks[actor.id]) if player else frozenset(),
            False,
            source["breed"] if player else source["ref"],
            0,
            {},
            True,
            is_summon=False,
            summon_root_id=actor.id,
        )

    def properties(self, preview, actor):
        self(preview, actor)
        live = getattr(actor, "native_fight_properties", None)
        if live is not None:
            return frozenset(live)
        row = (
            self.catalog["player"]
            if actor.id in self.characters
            else self.catalog["npc"][str(self.monsters[actor.id]["ref"])]
        )
        return frozenset(row["fight_properties"])

    def world_properties(self, preview, actor):
        self(preview, actor)
        live = getattr(actor, "native_world_properties", None)
        if live is not None:
            return frozenset(live)
        row = (
            self.catalog["player"]
            if actor.id in self.characters
            else self.catalog["npc"][str(self.monsters[actor.id]["ref"])]
        )
        return frozenset(row["world_properties"])


def native_probability(probability, *, draw_percent, random_fraction=None):
    """eZR.bbH uses UK.pT(100) <= UP.bt(eVn.eg(level)).

    Probability100 always accepts; probability0 always rejects on this path.
    Container eVt.fLN bypass is separate from these numeric values.
    UP.bt stochastically rounds float32 probability, never Python round.
    """
    import math
    from .combat_parameters import _float32

    if type(probability) not in (int, float) or not math.isfinite(probability):
        raise ValueError("Unknown native probability")
    if probability in (0, 100):
        return probability == 100
    draw = draw_percent(100)
    if type(draw) is not int or not 1 <= draw <= 100:
        raise ValueError("Invalid native UK.pT probability draw")
    value = _float32(probability)
    threshold = math.floor(value)
    fraction = value - threshold
    if fraction:
        if not callable(random_fraction):
            raise ValueError("Native fractional probability requires UP.bt RNG")
        random = random_fraction()
        if type(random) not in (int, float) or not 0 <= random < 1:
            raise ValueError("Invalid native stochastic probability draw")
        threshold += random < fraction
    return draw <= threshold


def native_block(effect, target, *, draw_integer):
    """eXt.fOI/fOH: positive BLOCK87 and UK.pT(100) <= current.

    Flag2 disables block. UK.pT draws integer1..100 inclusive; unlike a
    Python percentage comparison the native boundary is inclusive.
    """
    flags = effect["native_effect_flags"]
    if 2 in flags:
        return False
    value = target.effect_stats.get(87)
    if type(value) is not int:
        raise ValueError("Missing native BLOCK87 snapshot")
    if value <= 0:
        return False
    draw = draw_integer(100)
    if type(draw) is not int or not 1 <= draw <= 100:
        raise ValueError("Invalid native UK.pT draw")
    return draw <= value


def native_facing(source, target):
    """Sl.o: normalized target-minus-source dot aAS vector <= -0.7.

    Native sameXYZ returns FRONT. Side/back remain rejected by damage formula.
    Direction comes from creation/orientation/movement; absence is unknown.
    """
    import math
    from .combat_parameters import _float32 as f

    direction = getattr(target, "direction", None)
    vectors = ((1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1))
    if type(direction) is not int or not 0 <= direction < 8:
        raise ValueError("Missing authoritative native actor direction")
    if source.position == target.position:
        return "FRONT"
    dx = f(target.position[0] - source.position[0])
    dy = f(target.position[1] - source.position[1])
    length = f(math.sqrt(f(f(dx * dx) + f(dy * dy))))
    if length == 0:
        raise ValueError("Unaudited vertical-only native facing")
    vx, vy = vectors[direction]
    dot = f(f(f(dx / length) * vx) + f(f(dy / length) * vy))
    return "FRONT" if dot <= -0.7 else "BACK" if dot >= 0.72 else "SIDE"


def native_facing_front(source, target):
    return native_facing(source, target) == "FRONT"


def ordinary_cast_authority(*, actors, timing, rng, critical):
    """Immediate spell-container11 authority for the owned ordinary PVE path.

    ``critical`` is the already authoritative cast branch, not a per-target
    random draw. Client exposes FEROCITY9 as CRITICAL_CHANCE but the server
    roll consumer is absent from the client JAR; no roll is invented here.
    ``timing`` is NativeEffectTimingProvider bound to the same native timeline.
    ``rng`` owns randint(1,100)/random, and must be transaction-private.
    """
    from .combat_runtime_adapter import NativeCastAuthority
    from .combat_effect_resolver import EffectResolutionContext
    from .combat_damage_handler import DamageExecutionContext
    from .combat_healing_handler import HealingExecutionContext

    if type(critical) is not bool:
        raise ValueError("Missing authoritative cast critical branch")
    if not callable(getattr(rng, "randint", None)) or not callable(
        getattr(rng, "random", None)
    ):
        raise ValueError("Missing transaction-owned native RNG")

    def draw(n):
        return rng.randint(1, n)

    def damage(p, plan, e, i):
        target = p.actors[i.target_id]
        actors(p, target)
        location = native_facing(p.actors[i.caster_id], target)
        return DamageExecutionContext(
            critical,
            location == "FRONT",
            None,  # eXt.fOC samples block after native arithmetic.
            True,
            ordinary_container_type(p, plan, i),
            False,
            location,
        )

    def healing(p, plan, e, i):
        target = p.actors[i.target_id]
        authority = actors(p, target)
        properties = actors.properties(p, target)
        # eGj.PO: actor_kind0/5; NPC1 without eHQ.pUr does not accumulate
        # heal resistance. Ordinary PVE fcb mode is the registration contract.
        return HealingExecutionContext(
            critical,
            True,
            20 in properties,
            33 in e["native_effect_flags"],
            0,
            0,
            authority.is_player or 122 in actors.world_properties(p, target),
            target.effect_minima[32],
            target.effect_maxima[32],
            True,
        )

    def stat(p, plan, e, i):
        # Timing provider audits retention/clocks and source eligibility. An
        # ordinary NPC immune to MP loss cannot be falsely attested executable.
        from dataclasses import replace

        context = timing.stat(p, plan, e, i)
        target = p.actors[i.target_id]
        from .combat_static_catalogs import characteristic_registry
        registry = characteristic_registry()["effects"]
        row = registry.get(str(e["effect_class"]))
        if (
            row
            and row["runner"] == "eWR"
            and row.get("fixed_stat_id") == 3
            and 4 in actors.properties(p, target)
        ):
            return replace(context, executable=False)
        return context

    def obstacle(p, plan, e, i):
        # Walkable terrain does not prove native QI.V obstacle absence.
        occupied = getattr(p, "native_obstacle_cells", None)
        if occupied is None:
            return None  # Unknown cell context only blocks predicates that need it.
        return i.cell in occupied

    def group_cells(p, plan, e, i):
        from .combat_group_cells import group_cells as native_group_cells

        return native_group_cells(p, e, i.cell, caster_id=i.caster_id)

    def resolution(p, plan, e, i):
        selection = "cell" if e["effect_class"] == 302 else "actors"
        return EffectResolutionContext(
            "CRITICALS_ONLY" if critical else "EFFECTS_ONLY",
            "immediate",
            selection,
            True,
        )

    def cell_eligible(p, plan, e, i):
        if e["effect_class"] != 302:
            return False
        selector = e.get("native_target_selector")
        if (
            selector is None
            or selector.get("class") != "fcE"
            or selector.get("mask") not in (0, 1)
        ):
            raise ValueError(
                "Caster teleport cell routing requires native plain cell selector"
            )
        return i.cell in p.walkable

    return NativeCastAuthority(
        resolution,
        cell_eligible,
        group_cells,
        damage,
        healing,
        stat,
        timing.state,
        obstacle,
        lambda p, plan, probability, i: native_probability(
            probability, draw_percent=draw, random_fraction=rng.random
        ),
        lambda p, plan: rng.random(),
        damage_block=lambda p, plan, e, i: native_block(
            e, p.actors[i.target_id], draw_integer=draw
        ),
    )


def ordinary_container_type(preview, plan, invocation):
    """eZR's actual eVo owner container, independent of the caster turn."""
    if invocation.state_uid is not None:
        from .combat_native_container import resolve_state_container

        resolve_state_container(preview, invocation.state_uid)
        return 3
    explicit = plan.get("native_retained_container")
    if explicit is not None:
        if explicit.get("present") is False:
            return None
        kind = explicit.get("type", explicit.get("container_type"))
        if explicit.get("present") is not True or type(kind) is not int:
            raise ValueError("Native damage container declaration is unknown")
        return kind
    if type(plan.get("spell_id")) is int:
        return 11
    raise ValueError("Native damage requires its actual owner container")
