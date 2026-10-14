"""Native authority for the exact ordinary PC/NPC creation path.

PC eHd kind0; NPC eHj kind1/master -1. eGj.d(eGH) loads fsp
breed properties. No summon/carrier/Qq relationships exist in these creation
blobs. This provider deliberately accepts neither summons nor wrapped actors.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT
from .combat_runtime_adapter import NativeActorAuthority


@lru_cache(maxsize=1)
def native_property_catalog():
    return protocol_catalog.load(DATA_ROOT / "native-actor-properties.json")


@lru_cache(maxsize=1)
def _immutable_property_catalog():
    from .combat_static_catalogs import ImmutableCatalog

    # Asset definitions are immutable services, not owned preview state.
    # Mutable actor/deck sources still follow the ordinary deepcopy boundary.
    return ImmutableCatalog(native_property_catalog())


def ordinary_native_sex(source, player):
    """Fresh ordinary eGj.aXz: actual owned PC sex or aWs NPC byte zero."""
    if type(player) is not bool or not isinstance(source, dict):
        raise ValueError("Missing native ordinary sex creation source")
    if not player:
        return 0
    value = source.get("sex")
    # Store.character returns the PostgreSQL boolean column; native aXz is
    # the corresponding byte. Preserve strict byte validation for fixtures.
    if type(value) is bool:
        return int(value)
    if value is not None and (type(value) is not int or value not in (0, 1)):
        raise ValueError("Invalid owned player sex byte")
    # Legacy pure fixtures without this source remain unknown, never male.
    return value


class OrdinaryActorAuthority:
    def __init__(
        self,
        *,
        characters,
        monsters,
        decks,
        excluded_decks,
        catalog=None,
        deck_caps=None,
        deck_blobs=None,
        npc_spellbook=None,
    ):
        if (
            set(characters) & set(monsters)
            or set(decks) != set(characters)
            or set(excluded_decks) != set(characters)
        ):
            raise ValueError("Exact owned player/NPC and deck sources required")
        self.characters, self.monsters = characters, monsters
        if npc_spellbook is not None and not callable(npc_spellbook):
            raise ValueError("Missing ordinary NPC spellbook provider")
        self.npc_spellbook = npc_spellbook
        self.decks, self.excluded_decks = decks, excluded_decks
        self.catalog = _immutable_property_catalog() if catalog is None else catalog
        self.deck_caps = (
            {identity: None for identity in characters}
            if deck_caps is None
            else dict(deck_caps)
        )
        if set(self.deck_caps) != set(characters):
            raise ValueError("Every owned player requires its native deck cap")
        if deck_blobs is not None and (
            set(deck_blobs) != set(characters)
            or any(not isinstance(blob, bytes) for blob in deck_blobs.values())
        ):
            raise ValueError("Every owned player requires its exact raw fzf deck bytes")
        self.deck_blobs = None if deck_blobs is None else dict(deck_blobs)

    def _monster_sources(self, preview):
        if getattr(preview, "rift_wave_state", None) is None:
            return self.monsters
        sources = getattr(preview, "rift_monsters", None)
        if not isinstance(sources, dict):
            raise ValueError("Missing checkpointed ordinary rift monster sources")
        return sources

    def __call__(self, preview, actor):
        from .combat_native_actor_lookup import detached_authority

        construction = detached_authority(preview, actor)
        if construction is not None:
            return construction
        withdrawn = {
            identity
            for identity, candidate in preview.actors.items()
            if getattr(candidate, "pve_withdrawn", False)
        }
        monsters = self._monster_sources(preview)
        if set(preview.actors) - withdrawn != set(self.characters) | set(monsters):
            raise ValueError(
                "Ordinary authority roster changed: summons/wrapped actors need native registration"
            )
        if preview.actors.get(actor.id) is not actor:
            raise ValueError("Ordinary actor must belong to current preview")
        if actor.id in withdrawn:
            raise ValueError("Withdrawn PvE actor has no active ordinary authority")
        player = actor.id in self.characters
        source = (self.characters if player else monsters)[actor.id]
        if source["id"] != actor.id or actor.controlled != player:
            raise ValueError("Creation actor kind disagrees with owned source")
        profile = (
            self.catalog["player"]
            if player
            else self.catalog["npc"].get(str(source["ref"]))
        )
        if profile is None:
            raise ValueError("Missing native breed properties")
        # Carrying has a separate reciprocal/QI producer; master/controller
        # registrations remain outside this ordinary creation authority.
        if getattr(actor, "native_master_id", None) is not None:
            raise ValueError(
                "Ordinary authority cannot attest changed native relationships"
            )
        from .combat_carrying import carrying_relations

        carrying = carrying_relations(preview, actor)
        properties = frozenset(profile["fight_properties"])
        live = getattr(actor, "native_fight_properties", None)
        if live is not None:
            properties = frozenset(live)
        # eGn.zm copies pW.Uj through eGj.M into eGz.bgW: obstacle byte.
        # fcb affiliation/eGj.bcM remains actor.team and is separate.
        if type(actor.team) is not int or not 0 <= actor.team < 128:
            raise ValueError("Missing native signed-byte fight affiliation")
        from .combat_ordinary_death import owned_fighter_guards

        life = owned_fighter_guards(preview, actor)
        in_play = life["baF"]
        context = dict(
            bcN=actor.native_obstacle_id,
            is_amO=True,
            is_eGj=True,
            is_Qq=False,
            is_eHH=True,
            is_eHG=True,
            bEe=42 not in properties,
            UNTARGETTABLE_BY_OTHER=21 in properties,
            buX=carrying["is_carried"],
            dTE=False,
            # big.dnG/dnH -> eGj.b/c fall back to self with no registered
            # master/controller relation. Changed relations are rejected above.
            dpu_id=actor.id,
            dpr_id=actor.id,
            **life,
        )
        from .combat_spell_grant import granted_spells

        extra_spells = frozenset(granted_spells(preview, actor.id))
        spellbook = source.get("native_spellbook")
        if spellbook is None and not player and self.npc_spellbook is not None:
            spellbook = self.npc_spellbook(preview, actor, source)
            from .combat_spell_level import NativeSpellBook

            if (
                not isinstance(spellbook, NativeSpellBook)
                or spellbook.player_character is not False
            ):
                raise ValueError("Invalid ordinary NPC spellbook authority")
        if spellbook is None and player:
            from wakfu_server.spells import owned_spell_records
            from .combat_spell_level import NativeSpellBook, decoded_spell_levels
            from .combat_native_spell_casting import catalog as casting_catalog

            levels = decoded_spell_levels(
                owned_spell_records(source), casting_catalog()
            )
            spellbook = NativeSpellBook(
                levels, True, dict(levels), self.deck_caps[actor.id]
            )

        if spellbook is not None:
            from .combat_morph_spellbook import active_morph_book
            from .combat_spell_grant_book import merged_grant_book

            spellbook = active_morph_book(preview, actor.id, spellbook)
            spellbook = merged_grant_book(preview, actor.id, spellbook)

        captured_roster = None
        if player:
            from wakfu_server.characters.captured_roster import (
                OwnedCapturedRoster,
                roster_from_character,
            )

            overlay = getattr(preview, "native_captured_rosters", {}).get(str(actor.id))
            if overlay is not None:
                captured_roster = OwnedCapturedRoster.from_record(
                    overlay, expected_owner_id=actor.id
                )
            elif source.get("captured_roster") is not None:
                captured_roster = roster_from_character(source)

        cosmetic_state = getattr(actor, "native_cosmetic_state", None)
        if cosmetic_state is not None:
            if (
                not isinstance(cosmetic_state, dict)
                or set(cosmetic_state) != {"selected_values", "active_cosmetics"}
                or not isinstance(cosmetic_state["selected_values"], dict)
                or not isinstance(cosmetic_state["active_cosmetics"], dict)
            ):
                raise ValueError("Malformed native cosmetic constructor snapshot")
            selected_cosmetics = dict(cosmetic_state["selected_values"])
            active_cosmetics = dict(cosmetic_state["active_cosmetics"])
        else:
            selected_cosmetics = active_cosmetics = None

        metadata = NativeActorAuthority(
            context,
            player,
            frozenset(self.decks[actor.id]) | extra_spells if player else frozenset(),
            frozenset(self.excluded_decks[actor.id]) if player else frozenset(),
            carrying["is_carried"],
            source["breed"] if player else source["ref"],
            0,
            {},
            True,
            # big.dpr -> dnH -> eGj.c returns self when fdt has no controlled
            # relation. Both ordinary PC/NPC creation have no such registration;
            # changed master/carrier relations are rejected above.
            native_controller_id=actor.id,
            native_in_play=in_play,
            native_controlled_by_ai=getattr(actor, "native_controlled_by_ai", None),
            # Actual serialized source classes: biB/bjo.dpR=false, bje.dpR=true.
            native_ai_control_baseline=False if player else True,
            is_summon=False,
            # Exact source classes: bjo PLAYER_CHARACTER, owned monster NPC;
            # companion/summon routes require their own creation authority.
            is_challenger=player,
            # Fresh ordinary creation has null pGV. Carry registration requires
            # a separate authority; the guard above rejects changed relations.
            is_carrying=carrying["is_carrying"],
            summon_root_id=actor.id,
            # combat_actor POSITION writes this exact signed long into rE.Vp;
            # eGt.zm applies it through eGj.fE, which is read by eKB/arM.
            native_instance_id=source.get("map_id"),
            native_real_level=source.get("level") if player else actor.effective_level,
            native_spellbook=spellbook,
            # Ordinary fresh actors have no eHD in their eGZ.pHM; dTC is false.
            native_summoned_from_symbiot=False,
            native_summon_counts_complete=True,
            # Owned client actor is biB, which explicitly implements eHP.
            # Its optional drI component is hydrated separately by Store.character.
            native_is_ehp=player,  # Exact ordinary biB implements eHP; bje does not.
            native_captured_roster=captured_roster,
            # eGj.aWs assigns dpV to asQ: bjo=0, bje=1.
            native_actor_type=0 if player else 1,
            native_npc_prototype_ref=None if player else source["ref"],
            native_copied_equipment_operand=None if player else 0,
            # eGj constructor initializes ePn=0; ordinary NPC blobs do not
            # replace it. Owned PC sources preserve the real account/selected
            # primary; unavailable player primary remains unknown.
            native_account_id=source.get("account_id") if player else 0,
            native_primary_character_id=(
                source.get("selected_character_id") if player else 0
            ),
            native_sex=ordinary_native_sex(source, player),
            native_selected_cosmetics=selected_cosmetics,
            native_active_cosmetics=active_cosmetics,
        )
        from .combat_controller_registry import current_controller_authority

        return current_controller_authority(preview, actor, metadata)

    def item_quantity(self, preview, actor, references):
        """eKE uses source actor inventory, not the current effect target."""
        self(preview, actor)
        if actor.id not in self.characters:
            return 0  # Ordinary NPC creation has native drK=null.
        from .combat_inventory_date_conditions import owned_item_quantity

        return owned_item_quantity(
            self.characters[actor.id].get("inventory_items"), references
        )

    def property_counts(self, preview, actor):
        """eGj.d(eGH): reset each recognized fsp ID, then eHN.c once.

        Only the installed creation profile is a baseline. A live set without
        counters is not enough authority to reconstruct multiplicity.
        """
        self(preview, actor)
        counts = getattr(actor, "native_fight_property_counts", None)
        if counts is not None:
            from .combat_property_stack import property_present

            property_present(counts, 0)  # Complete signed-byte mapping validation.
            return counts
        if getattr(actor, "native_fight_properties", None) is not None:
            raise ValueError("Live native property set lacks counter population")
        row = (
            self.catalog["player"]
            if actor.id in self.characters
            else self.catalog["npc"][
                str(self._monster_sources(preview)[actor.id]["ref"])
            ]
        )
        from .combat_fight_property import property_registry

        return {
            identity: 1
            for identity in row["fight_properties"]
            if identity in property_registry()
        }

    def property_side_effect(self, preview, actor, identity, *, applying):
        self(preview, actor)
        if applying and identity in (10, 37):
            if getattr(preview, "native_timeline_policy", None) != "feq":
                raise ValueError("Missing native feq timeline policy")
            if identity == 10:
                return lambda: None  # SU.bhM -> Tc.bip -> feq.c is a no-op.
            if (
                preview.phase != "active"
                or not preview.order
                or not 0 <= preview.turn_index < len(preview.order)
            ):
                raise ValueError("Missing native current timeline cursor")
            if getattr(preview, "native_summon_registrations", {}):
                raise ValueError(
                    "Combined extra-turn/summon timeline remains unaudited"
                )
            slot = (1 + preview.turn_index) % (len(preview.order) + 1)
            base = (
                list(preview.order)
                if getattr(preview, "native_base_turn_order", None) is None
                else list(preview.native_base_turn_order)
            )

            def insert():
                if slot > preview.turn_index:
                    preview.native_base_turn_order = base
                    preview.order.insert(slot, actor.id)

            return insert
        if identity in (5, 18):
            los = getattr(preview, "native_los_ignored_affiliations", None)
            walk = getattr(preview, "native_walk_ignored_affiliations", None)
            if not isinstance(los, frozenset) or not isinstance(walk, frozenset):
                raise ValueError("Missing native QI affiliation sets")
            affiliation = self(preview, actor).targeting["bcN"]
            if type(affiliation) is not int or not -128 <= affiliation <= 127:
                raise ValueError("Missing native QK.bcN affiliation")

            def update():
                if applying:
                    preview.native_los_ignored_affiliations = los | {
                        affiliation
                    }  # QI.d
                else:
                    preview.native_los_ignored_affiliations = los - {
                        affiliation
                    }  # QI.e
                    preview.native_walk_ignored_affiliations = walk - {
                        affiliation
                    }  # QI.c

            return update
        if identity == 25 and applying:
            observers = getattr(actor, "native_resource_numeric_observers", None)
            if not isinstance(observers, dict) or 4 not in observers:
                raise ValueError("Missing native complete WP numeric observer snapshot")
            if observers[4] != ():
                raise ValueError(
                    "Native linked WP observer execution remains unaudited"
                )
            if not self(preview, actor).is_player:
                raise ValueError(
                    "Native NPC WP observer initialization remains unaudited"
                )

            def notify():
                # PA.aZk: UI listeners execute on client from packet447.
                # This diagnostic is not a Qf gameplay event or resource reset.
                preview._event(
                    "resource_observers_notified",
                    actor_id=actor.id,
                    stat_id=4,
                    numeric_observer_count=0,
                    reason="native_eWt_PA_aZk",
                )

            return notify
        raise ValueError("Native property resource-listener branch remains unaudited")

    def properties(self, preview, actor):
        self(preview, actor)
        live = getattr(actor, "native_fight_properties", None)
        if live is not None:
            return frozenset(live)
        row = (
            self.catalog["player"]
            if actor.id in self.characters
            else self.catalog["npc"][
                str(self._monster_sources(preview)[actor.id]["ref"])
            ]
        )
        return frozenset(row["fight_properties"])

    def world_property_counts(self, preview, actor):
        """Complete PB counters from live mutation or original fresh profile list."""
        from .combat_property_stack import add_property, property_present
        from .combat_native_actor_lookup import detached_authority

        live = getattr(actor, "native_world_property_counts", None)
        if live is not None:
            counts = dict(live)
            for identity in counts:
                property_present(counts, identity)  # Validate signed PB domain.
            return counts
        if (
            detached_authority(preview, actor) is not None
            or getattr(actor, "native_world_properties", None) is not None
        ):
            raise ValueError("Missing complete live native world-property counters")
        self(preview, actor)
        row = (
            self.catalog["player"]
            if actor.id in self.characters
            else self.catalog["npc"][
                str(self._monster_sources(preview)[actor.id]["ref"])
            ]
        )
        counts = {}
        # ExportActorProperties stores actual profile.fsq(), not a presence set.
        for identity in row["world_properties"]:
            add_property(counts, identity)
        return counts

    def world_properties(self, preview, actor):
        from .combat_native_actor_lookup import detached_authority

        if detached_authority(preview, actor) is not None:
            live = getattr(actor, "native_world_properties", None)
            if live is None:
                raise ValueError("Missing detached native world-property source")
            return frozenset(live)
        self(preview, actor)
        live = getattr(actor, "native_world_properties", None)
        if live is not None:
            return frozenset(live)
        row = (
            self.catalog["player"]
            if actor.id in self.characters
            else self.catalog["npc"][
                str(self._monster_sources(preview)[actor.id]["ref"])
            ]
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
    """Sl.o: native float32 normalization and FRONT/BACK/SIDE thresholds.

    Target owns the locator; source supplies the other PV coordinates.
    Sl ignores z after its sameXYZ check. Direction must be authoritative.
    """
    import math
    from .combat_parameters import _float32 as f
    from .combat_effect_area_targets import NativeAreaTarget

    if isinstance(target, NativeAreaTarget):
        # Qq.baB returns null: eXt.fOF has no Sl.o/back event for this PV.
        return "FRONT"

    direction = getattr(target, "direction", None)
    vectors = ((1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1))
    if type(direction) is not int or not 0 <= direction < 8:
        raise ValueError("Missing authoritative native actor direction")
    if source.position == target.position:
        return "FRONT"
    # Java subtracts signed ints before converting to float, and normalizes
    # by multiplying with a float32 reciprocal (not two direct divisions).
    dx = f(
        ((target.position[0] - source.position[0] + (1 << 31)) % (1 << 32)) - (1 << 31)
    )
    dy = f(
        ((target.position[1] - source.position[1] + (1 << 31)) % (1 << 32)) - (1 << 31)
    )
    length = f(math.sqrt(f(f(dx * dx) + f(dy * dy))))
    if length != 0:
        reciprocal = f(1 / length)
        dx, dy = f(reciprocal * dx), f(reciprocal * dy)
    vx, vy = vectors[direction]
    dot = f(f(dx * vx) + f(dy * vy))
    return "FRONT" if dot <= -0.7 else "BACK" if dot >= 0.72 else "SIDE"


def native_facing_front(source, target):
    return native_facing(source, target) == "FRONT"


def native_damage_target(preview, identity):
    """Resolve eXt's actual registered or currently constructing PV."""
    from .combat_native_actor_lookup import native_actor

    actor = native_actor(preview, identity)
    if actor is not None:
        return actor
    row = getattr(preview, "native_effect_areas", {}).get(identity)
    if not isinstance(row, dict):
        return None
    from .combat_effect_area_targets import area_targets

    return next(
        (candidate for candidate in area_targets(preview) if candidate.id == identity),
        None,
    )


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
        from .combat_native_actor_lookup import native_actor

        source = native_actor(p, i.caster_id)
        actors(p, source)
        target = native_damage_target(p, i.target_id)
        if target is None:
            raise ValueError("Native damage requires an actor or typed fbd PV target")
        if native_actor(p, i.target_id) is target:
            actors(p, target)
        location = native_facing(source, target)
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
        from .combat_native_actor_lookup import native_actor

        target = native_actor(p, i.target_id)
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
            target_ko=authority.targeting["baK"],
        )

    def stat(p, plan, e, i):
        # Timing provider audits retention/clocks and source eligibility. An
        # ordinary NPC immune to MP loss cannot be falsely attested executable.
        from dataclasses import replace

        context = timing.stat(p, plan, e, i)
        from .combat_native_actor_lookup import native_actor

        target = native_actor(p, i.target_id)
        from .combat_static_catalogs import characteristic_registry

        registry = characteristic_registry()["effects"]
        row = registry.get(str(e["effect_class"]))
        if (
            row
            and row["runner"] == "eWR"
            and row.get("fixed_stat_id") == 3
            and target is not None
            and 4 in actors.properties(p, target)
        ):
            return replace(context, executable=False)
        return context

    def obstacle(p, plan, e, i):
        # eOV queries actual QI.V, including registered dynamic QK objects.
        # Actor identities retained after OUT_OF_PLAY are not QI occupancy.
        if i.cell is None:
            return None
        from .combat_qi_fight import current_registry

        registry = current_registry(p)
        order = registry.ordered_U(*i.cell[:2])
        return bool(order and registry.slots[order[0]] is not None)

    def group_cells(p, plan, e, i):
        from .combat_group_cells import group_cells as native_group_cells

        if e["effect_class"] == 349:
            from .combat_cell_group import native_cell_group_population
            from .combat_definitions import effect_profile

            return native_cell_group_population(p, e, effect_profile(e, i.level), i)

        center = i.cell
        if e["effect_class"] == 352:
            from .combat_definitions import effect_profile
            from .combat_symmetry_group import symmetry_center

            caster = p.actors.get(i.caster_id)
            center = symmetry_center(
                p,
                effect_profile(e, i.level)["parameters"],
                None if caster is None else caster.position,
                i.cell,
            )
            if center is None:
                return ()
        return native_group_cells(p, e, center, caster_id=i.caster_id)

    def resolution(p, plan, e, i):
        from .combat_delivery_owners import native_owner_flags

        actor_mode, cell_mode = native_owner_flags(e)
        selection = "cell" if cell_mode and not actor_mode else "actors"
        # A fresh Qe.a performs neither path for bbA=false/bbB=false.
        # Native state children are already bound by eVE/Qe.d, and native
        # subscriptions retain that binding before calculation is deferred.
        eligible = actor_mode or cell_mode or i.state_uid is not None
        variant_mode = "CRITICALS_ONLY" if critical else "EFFECTS_ONLY"
        if i.state_uid is not None:
            from .combat_state_variants import state_child_variant_mode
            from .combat_state_critical_source import causing_state_critical

            variant_mode = state_child_variant_mode(
                p,
                i.state_uid,
                effect_reference=i.reference,
                effect_definitions=timing.catalog["effects"],
                causing_critical=causing_state_critical(i, current_critical=critical),
            )
        return EffectResolutionContext(
            variant_mode,
            "immediate",
            selection,
            eligible,
        )

    def cell_eligible(p, plan, e, i):
        from .combat_delivery_owners import native_owner_flags

        actor_mode, cell_mode = native_owner_flags(e)
        # Native Qe.a supplies the cell once before any actor target selection.
        # Runner-specific geometry and effect criteria remain their own guards.
        return cell_mode and not actor_mode

    def damage_block(p, plan, effect, invocation):
        from .combat_native_actor_lookup import native_actor

        target = native_damage_target(p, invocation.target_id)
        if target is None:
            raise ValueError("Missing native eXt block target")
        if native_actor(p, invocation.target_id) is target:
            return native_block(effect, target, draw_integer=draw)
        from .combat_effect_area import native_effect_areas
        from .combat_wall_area import wall_damage_snapshot

        row = p.native_effect_areas[invocation.target_id]
        definition = native_effect_areas().get(str(row.get("reference")))
        snapshot = wall_damage_snapshot(row, definition)
        # fbd.rMK has no BLOCK characteristic. PV.b(shG) therefore returns
        # null and eXt.fOH exits without consuming a random roll.
        if 87 not in snapshot["stats"]:
            return False
        from types import SimpleNamespace

        return native_block(
            effect,
            SimpleNamespace(effect_stats=snapshot["stats"]),
            draw_integer=draw,
        )

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
        random_number=lambda p, plan, limit, exclusions: native_random_number(
            limit, exclusions, draw_index=lambda size: rng.randint(0, size - 1)
        ),
        damage_block=damage_block,
    )


def ordinary_container_type(preview, plan, invocation):
    """eZR's actual eVo owner container, independent of the caster turn."""
    if invocation.state_uid is not None:
        from .combat_native_container import resolve_state_container

        resolve_state_container(preview, invocation.state_uid)
        return 1
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


def native_random_number(limit, exclusions=(), *, draw_index):
    """eLb: uniform index over ascending [0,limit) after exclusion filtering."""
    if type(limit) is not int or not -(1 << 63) <= limit < (1 << 63):
        raise ValueError("Limit not an integer")
    if not isinstance(exclusions, (tuple, list)) or any(
        type(v) is not int or not -(1 << 63) <= v < (1 << 63) for v in exclusions
    ):
        raise ValueError("Invalid native random exclusion list")
    if limit < 0:
        raise ValueError("Invalid native closed-open random range")
    removed = sorted({v for v in exclusions if 0 <= v < limit})
    size = limit - len(removed)
    if not size:
        raise ValueError("No number to roll")
    index = draw_index(size)
    if type(index) is not int or not 0 <= index < size:
        raise ValueError("Invalid authoritative native random index")
    # Same ascending candidate order without materializing up to Long.MAX_VALUE.
    value = index
    for excluded in removed:
        if excluded > value:
            break
        value += 1
    return value
