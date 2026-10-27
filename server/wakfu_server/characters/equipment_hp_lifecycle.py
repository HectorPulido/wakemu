"""Owned native eWO HP PA receipts for equipment build transitions.

Callers must hold the character/build/item locks and run inside one transaction.
This module deliberately consumes family21 operations generically; it does not
identify or qualify item references and it does not resolve dynamic operands.
"""
from contextlib import nullcontext
from dataclasses import dataclass, field

from psycopg.pq import TransactionStatus


def _native_catalog():
    from wakfu_server.combat_actor_snapshot import native_actor_catalog

    return native_actor_catalog()


def _native_effects():
    from wakfu_server.combat.combat_hp_maximum_reduction import (
        apply_hp_maximum_reduction,
        remove_hp_maximum_reduction,
    )

    return apply_hp_maximum_reduction, remove_hp_maximum_reduction


def _effective_maximum(raw, percentage, low, high):
    from wakfu_server.combat.combat_maximum_resource import effective_maximum

    return effective_maximum(raw, percentage, low, high)


@dataclass
class NativeHPActor:
    """Exact raw HP fields consumed by existing native eWO setters."""

    raw_current: int
    raw_maximum: int
    raw_minimum: int = 0
    percentage: int = 0
    frozen: bool = False
    effect_stats: dict = field(init=False)
    effect_maxima: dict = field(init=False)
    effect_minima: dict = field(init=False)
    effect_base_maxima: dict = field(init=False)
    effect_base_minima: dict = field(init=False)
    effect_percentages: dict = field(init=False)
    effect_frozen: set = field(init=False)
    effect_hp_raw_current: int = field(init=False)
    hp: int = field(init=False)
    max_hp: int = field(init=False)

    def __post_init__(self):
        if (
            any(
                type(value) is not int
                for value in (
                    self.raw_current,
                    self.raw_maximum,
                    self.raw_minimum,
                    self.percentage,
                )
            )
            or type(self.frozen) is not bool
        ):
            raise ValueError("Invalid native HP raw PA fields")
        definition = _native_catalog()["characteristics"]["1"]
        low, high = definition["hard_minimum"], definition["hard_maximum"]
        if self.raw_maximum < self.raw_minimum:
            raise ValueError("Native HP raw maximum is below raw minimum")
        minimum = max(low, min(high, self.raw_minimum))
        maximum = _effective_maximum(self.raw_maximum, self.percentage, low, high)
        if maximum < minimum:
            raise ValueError("Native HP maximum is below minimum")
        current = max(minimum, min(maximum, self.raw_current))
        self.effect_stats = {1: current}
        self.effect_maxima = {1: maximum}
        self.effect_minima = {1: minimum}
        self.effect_base_maxima = {1: self.raw_maximum}
        self.effect_base_minima = {1: self.raw_minimum}
        self.effect_percentages = {1: self.percentage}
        self.effect_frozen = {1} if self.frozen else set()
        self.effect_hp_raw_current = self.raw_current
        self.hp, self.max_hp = current, maximum
        self.native_hp_raw_current_source = "fresh_initial_tB_HP.on_resource_override"

    def plain(self):
        return dict(
            raw_current=self.effect_hp_raw_current,
            raw_maximum=self.effect_base_maxima[1],
            raw_minimum=self.effect_base_minima[1],
            percentage=self.effect_percentages[1],
            frozen=1 in self.effect_frozen,
        )


class OwnedEwoHPReplay:
    """Apply/remove fully resolved equipment eWO effects with native receipts."""

    def __init__(self, actor, receipts=()):
        if not isinstance(actor, NativeHPActor):
            raise ValueError("Missing native HP PA state")
        self.actor = actor
        self.receipts = {}
        for row in receipts:
            self._load(row)

    @staticmethod
    def _key(row):
        source_uid, index = row.get("source_uid"), row.get("effect_index")
        if (
            type(source_uid) is not int
            or source_uid <= 0
            or type(index) is not int
            or index < 0
        ):
            raise ValueError("Invalid eWO equipment source identity")
        return source_uid, index

    @staticmethod
    def _order(row):
        slot = row.get("slot")
        if type(slot) is not int or type(row.get("effect_index")) is not int:
            raise ValueError("Missing native eWO source order")
        return slot, row["effect_index"]

    @staticmethod
    def _fingerprint(row):
        return (
            row.get("effect_id"),
            row.get("amount", row.get("requested")),
            row.get("definition_type", 0),
            row.get("restore_current", True),
            row.get("reduce_current", True),
            row.get("effect_index"),
            row.get("chance", 100),
        )

    def _load(self, row):
        if not isinstance(row, dict):
            raise ValueError("Malformed eWO HP receipt")
        key = self._key(row)
        if (
            key in self.receipts
            or type(row.get("actual")) is not int
            or type(row.get("requested")) is not int
            or type(row.get("definition_type")) is not int
            or row["definition_type"] not in (0, 1, 2)
            or type(row.get("restore_current")) is not bool
            or type(row.get("reduce_current")) is not bool
        ):
            raise ValueError("Invalid or duplicate eWO HP receipt")
        self._validate_draw(row, required=row.get("chance", 100) != 100)
        self.receipts[key] = dict(row)

    @staticmethod
    def _validate_draw(row, *, required=False):
        chance = row.get("chance", 100)
        if type(chance) is not int or not 0 <= chance <= 100:
            raise ValueError("Invalid native HP application chance")
        roll = row.get("chance_roll")
        if required or roll is not None:
            if type(roll) is not int or not 0 <= roll < 100:
                raise ValueError("Missing durable native HP application draw")
        return chance, roll

    @classmethod
    def resolved_operations(cls, desired, receipts=(), *, rng=None):
        """Reuse equip draws, including failures; only a locked writer may draw."""
        prior = {cls._key(row): row for row in receipts}
        result = []
        for operation in desired:
            row = dict(operation)
            chance, roll = cls._validate_draw(row)
            if chance != 100:
                previous = prior.get(cls._key(row))
                # Slot ordering can change without ending the physical item's
                # equip lifetime. A changed descriptor starts a new lifetime.
                if (
                    previous is not None
                    and all(
                        previous.get(field, default) == row.get(field, default)
                        for field, default in (
                            ("effect_id", None),
                            ("chance", 100),
                            ("restore_current", True),
                            ("reduce_current", True),
                            ("definition_type", 0),
                        )
                    )
                    and previous["requested"] == row["amount"]
                ):
                    roll = previous.get("chance_roll")
                if roll is None:
                    if rng is None:
                        raise ValueError(
                            "Probabilistic HP equipment requires owned equip transaction"
                        )
                    roll = rng(100)
                row["chance_roll"] = roll
                cls._validate_draw(row, required=True)
            result.append(row)
        return result

    def apply(self, operation):
        key = self._key(operation)
        self._order(operation)
        amount = operation.get("amount")
        mode = operation.get("definition_type", 0)
        restore = operation.get("restore_current", True)
        reduce = operation.get("reduce_current", True)
        if (
            key in self.receipts
            or type(amount) is not int
            or type(mode) is not int
            or mode not in (0, 1, 2)
            or type(restore) is not bool
            or type(reduce) is not bool
        ):
            raise ValueError("Unsupported or duplicate eWO HP operation")
        chance, roll = self._validate_draw(
            operation, required=operation.get("chance", 100) != 100
        )
        if chance == 100 or roll < chance:
            apply_native, _ = _native_effects()
            actual, events = apply_native(
                self.actor, amount, definition_type=mode, reduce_current=reduce
            )
        else:
            actual, events = 0, ()
        receipt = dict(
            source_uid=key[0],
            effect_index=key[1],
            slot=operation["slot"],
            effect_id=operation.get("effect_id"),
            actual=actual,
            requested=amount,
            definition_type=mode,
            restore_current=restore,
            reduce_current=reduce,
            events=list(events),
        )
        if chance != 100:
            receipt.update(chance=chance, chance_roll=roll)
        self.receipts[key] = receipt
        return dict(receipt)

    def matches(self, desired):
        """Check whether these receipts exactly represent selected equipment."""
        if not isinstance(desired, (tuple, list)):
            return False
        by_key = {}
        for row in desired:
            try:
                key = self._key(row)
                self._order(row)
            except (AttributeError, ValueError):
                return False
            if key in by_key:
                return False
            by_key[key] = row
        return set(by_key) == set(self.receipts) and all(
            self._fingerprint(self.receipts[key]) == self._fingerprint(by_key[key])
            for key in by_key
        )

    def remove(self, key, effect_index=0):
        if type(key) is int:
            key = (key, effect_index)
        if not isinstance(key, tuple) or len(key) != 2 or key not in self.receipts:
            raise ValueError("Unknown eWO HP receipt")
        receipt = self.receipts.pop(key)
        _, remove_native = _native_effects()
        remove_native(
            self.actor,
            receipt["actual"],
            restore_current=receipt["restore_current"],
        )
        return dict(receipt)

    def reconcile(self, desired, *, rng=None):
        """Reconcile live roots; caller provides real slot/effect order.

        For changed roots, native inverse runs first and native application runs
        after. The caller must supply all operations for the selected build.
        """
        if not isinstance(desired, (tuple, list)):
            raise ValueError("Invalid desired eWO equipment operation list")
        desired = self.resolved_operations(desired, self.plain_receipts(), rng=rng)
        by_key = {}
        for row in desired:
            key = self._key(row)
            self._order(row)
            if key in by_key:
                raise ValueError("Duplicate eWO source/effect ordinal")
            by_key[key] = row
        ordered_current = sorted(
            self.receipts, key=lambda key: (self._order(self.receipts[key]), key)
        )
        ordered_desired = sorted(
            by_key, key=lambda key: (self._order(by_key[key]), key)
        )
        common = set(ordered_current) & set(ordered_desired)
        reordered = [key for key in ordered_current if key in common] != [
            key for key in ordered_desired if key in common
        ]
        unchanged = {
            key
            for key in common
            if self._fingerprint(self.receipts[key]) == self._fingerprint(by_key[key])
        }
        inserted_before_retained = False
        if unchanged:
            last_order = max(self._order(self.receipts[key]) for key in unchanged)
            inserted_before_retained = any(
                key not in unchanged and self._order(by_key[key]) <= last_order
                for key in ordered_desired
            )
        replay_all = reordered or inserted_before_retained
        removed = []
        for key in sorted(
            tuple(self.receipts),
            key=lambda item: (self._order(self.receipts[item]), item),
            reverse=True,
        ):
            if (
                replay_all
                or key not in by_key
                or self._fingerprint(self.receipts[key])
                != self._fingerprint(by_key[key])
            ):
                removed.append(self.remove(key))
        applied = []
        for key in ordered_desired:
            if replay_all or key not in self.receipts:
                applied.append(self.apply(by_key[key]))
            else:
                # Moving a retained item without changing relative effect
                # order is not another native application. Keep its draw and
                # HP receipt, and only update the equipment ordering metadata.
                self.receipts[key]["slot"] = by_key[key]["slot"]
        return dict(
            applied=applied,
            removed=removed,
            replayed_all=replay_all,
            receipts=self.plain_receipts(),
        )

    def plain_receipts(self):
        return [
            dict(self.receipts[key])
            for key in sorted(
                self.receipts,
                key=lambda item: (self._order(self.receipts[item]), item),
            )
        ]

    def checkpoint(self):
        return dict(actor=self.actor.plain(), receipts=self.plain_receipts())

    @classmethod
    def restore(cls, checkpoint):
        if not isinstance(checkpoint, dict) or set(checkpoint) != {"actor", "receipts"}:
            raise ValueError("Malformed eWO HP checkpoint")
        actor = checkpoint["actor"]
        if not isinstance(actor, dict) or set(actor) != {
            "raw_current",
            "raw_maximum",
            "raw_minimum",
            "percentage",
            "frozen",
        }:
            raise ValueError("Malformed raw HP actor checkpoint")
        return cls(NativeHPActor(**actor), checkpoint["receipts"])


def load(db, character_id, *, for_update=False):
    suffix = " FOR UPDATE" if for_update else ""
    row = db.execute(
        "SELECT raw_current,raw_maximum,raw_minimum,percentage,frozen,receipts,revision "
        "FROM character_equipment_hp_projection WHERE character_id=%s" + suffix,
        (character_id,),
    ).fetchone()
    if row is None:
        return None
    receipts = row["receipts"]
    if not isinstance(receipts, list) or type(row["revision"]) is not int:
        raise ValueError("Malformed persisted eWO HP projection")
    actor = NativeHPActor(
        raw_current=row["raw_current"],
        raw_maximum=row["raw_maximum"],
        raw_minimum=row["raw_minimum"],
        percentage=row["percentage"],
        frozen=row["frozen"],
    )
    return dict(actor=actor, receipts=receipts, revision=row["revision"])


def save(db, character_id, replay, *, expected_revision):
    """CAS projection state; caller owns character and equipment row locks."""
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("eWO HP receipt save requires caller transaction")
    if (
        type(character_id) is not int
        or character_id <= 0
        or not isinstance(replay, OwnedEwoHPReplay)
    ):
        raise ValueError("Invalid eWO HP projection owner")
    actor = replay.actor.plain()
    receipts = replay.plain_receipts()
    from psycopg.types.json import Jsonb

    encoded_receipts = Jsonb(receipts)
    if expected_revision is None:
        row = db.execute(
            "INSERT INTO character_equipment_hp_projection"
            "(character_id,raw_current,raw_maximum,raw_minimum,percentage,frozen,receipts,revision) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,0) ON CONFLICT(character_id) DO NOTHING "
            "RETURNING revision",
            (
                character_id,
                actor["raw_current"],
                actor["raw_maximum"],
                actor["raw_minimum"],
                actor["percentage"],
                actor["frozen"],
                encoded_receipts,
            ),
        ).fetchone()
    else:
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("Invalid eWO HP projection revision")
        row = db.execute(
            "UPDATE character_equipment_hp_projection SET raw_current=%s,raw_maximum=%s,"
            "raw_minimum=%s,percentage=%s,frozen=%s,receipts=%s,revision=revision+1 "
            "WHERE character_id=%s AND revision=%s RETURNING revision",
            (
                actor["raw_current"],
                actor["raw_maximum"],
                actor["raw_minimum"],
                actor["percentage"],
                actor["frozen"],
                encoded_receipts,
                character_id,
                expected_revision,
            ),
        ).fetchone()
    if row is None:
        raise ValueError("Stale or duplicate eWO HP projection write")
    return row["revision"]


def reconcile_in_transaction(db, character, desired, *, baseline=None):
    """Prepare the domain operation for a Store-owned transaction hook.

    The caller must hold the character/session/build/item locks and must pass a
    fully evaluated family21 list from the selected build. On first admission,
    `baseline` is the native raw HP row before any eWO operation. Dynamic context
    operands remain rejected upstream. Equip draws are resolved here once and
    committed in the same durable receipt as the native HP inverse.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("eWO HP reconciliation requires active character transaction")
    if not isinstance(character, dict) or type(character.get("id")) is not int:
        raise ValueError("Invalid eWO HP character owner")
    food_layer = bool(character.get("consumable_states"))
    layer_character = character
    if food_layer:
        from wakfu_server.equipment_stats import effective_character
        from wakfu_server.health_policy import visible

        if character["hp"] != visible(
            character["max_hp"],
            character["hp_damage"],
            character["health_dead"],
            character.get("hp_zero_valid", False),
        ):
            raise ValueError("Food HP disagrees with canonical wound")
        layer_character = effective_character(character)
    existing = load(db, character["id"], for_update=True)
    if existing is None:
        if not desired:
            return None
        if not isinstance(baseline, dict):
            raise ValueError("Missing first native HP baseline")
        actor = NativeHPActor(**baseline)
        revision = None
        receipts = ()
    else:
        actor, revision, receipts = (
            existing["actor"],
            existing["revision"],
            existing["receipts"],
        )
        if actor.max_hp != layer_character["max_hp"] or (
            not character.get("health_dead") and actor.hp != layer_character["hp"]
        ):
            raise ValueError(
                "Persisted eWO HP raw actor disagrees with canonical health"
            )
        if not isinstance(baseline, dict):
            raise ValueError("Missing current native HP baseline")
    from secrets import randbelow

    old_wound = actor.max_hp - actor.hp
    desired = OwnedEwoHPReplay.resolved_operations(desired, receipts, rng=randbelow)
    replay = OwnedEwoHPReplay(actor, receipts)
    if existing is not None:
        # Rebuild only when the non-eWO native actor baseline changed (level,
        # aptitudes, or other equipment). Remove old roots in native inverse
        # order first; eWO's no-restore option remains effective here.
        stripped = OwnedEwoHPReplay.restore(replay.checkpoint())
        for key in sorted(
            tuple(stripped.receipts),
            key=lambda item: (stripped._order(stripped.receipts[item]), item),
            reverse=True,
        ):
            stripped.remove(key)
        old_base = stripped.actor.plain()
        if any(
            old_base[key] != baseline[key]
            for key in ("raw_maximum", "raw_minimum", "percentage", "frozen")
        ):
            # A changed ordinary baseline follows canonical wound policy:
            # current becomes new maximum minus the same persisted wound.
            # Copying the old absolute PA current would lose that invariant
            # whenever the new maximum differs.
            replay = OwnedEwoHPReplay(NativeHPActor(**baseline))
    transition = replay.reconcile(desired)
    revision = save(db, character["id"], replay, expected_revision=revision)
    from wakfu_server.health_policy import apply_native_equipment_hp

    maximum = replay.actor.max_hp
    hp = 0 if character.get("health_dead") else replay.actor.hp
    if food_layer:
        # Equipment operates on the pre-food PA. Persist its actual wound
        # delta against the complete world maximum instead of replacing the
        # food-inclusive canonical maximum with this smaller native layer.
        projected = dict(
            character,
            equipment_hp_projection=dict(
                actor=replay.actor.plain(),
                receipts=replay.plain_receipts(),
                revision=revision,
            ),
        )
        maximum = effective_character(projected, include_consumable_buffs=True)[
            "max_hp"
        ]
        damage = max(
            0,
            character["hp_damage"] + replay.actor.max_hp - replay.actor.hp - old_wound,
        )
        hp = visible(
            maximum,
            damage,
            character["health_dead"],
            replay.actor.hp == 0 and not character["health_dead"] and damage >= maximum,
        )
    updated = apply_native_equipment_hp(
        db,
        character,
        hp=hp,
        maximum=maximum,
    )
    return dict(
        character=updated, replay=replay, transition=transition, revision=revision
    )


def reconcile_selected_build(db, character):
    """Apply the selected build's family21 roots in owner order."""
    from wakfu_server.equipment_stats import bonuses, native_hp_baseline

    evaluated = bonuses(character)
    return reconcile_in_transaction(
        db,
        character,
        evaluated["hp_operations"],
        baseline=native_hp_baseline(character),
    )


def reconcile_territory_projection(db, before, after, *, hp):
    """Move an applied territorial maximum without replaying equipment roots.

    Territory is a flat ordinary maximum contribution, before the percentage
    phase. Native eWO receipts retain their original resolved amounts/draws;
    changing this independent contribution must not remove or reapply them.
    The caller has already computed the canonical, food-inclusive transition.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Territorial HP projection requires caller transaction")
    if (
        before.get("id") != after.get("id")
        or before.get("account_id") != after.get("account_id")
        or type(hp) is not int
        or hp != after.get("hp")
    ):
        raise ValueError("Foreign territorial HP projection transition")
    existing = load(db, before["id"], for_update=True)
    if existing is None:
        return None

    def applied(character):
        projection = character.get("territory_health_projection")
        value = 0 if projection is None else projection.get("applied_flat")
        if type(value) is not int or not -1000 <= value <= 1000:
            raise ValueError("Invalid applied territorial raw maximum")
        return value

    from wakfu_server.equipment_stats import effective_character
    from wakfu_server.health_policy import visible

    # Food is imported separately into combat. The equipment PA must keep its
    # own pre-food maximum rather than copying the food-inclusive world cap.
    old_layer = effective_character(dict(before, hp_zero_valid=False))
    new_layer = effective_character(dict(after, hp_zero_valid=False))
    actor = existing["actor"]
    if actor.max_hp != old_layer["max_hp"]:
        raise ValueError("Territorial HP baseline disagrees with owned native maximum")
    from wakfu_server.combat.combat_hp_raw import (
        hp_raw_current,
        set_hp_raw_current,
        set_hp_raw_maximum,
    )

    def layer_current(character, maximum):
        return visible(
            maximum,
            character["hp_damage"],
            character["health_dead"],
            character.get("hp_zero_valid", False) and character["hp_damage"] >= maximum,
        )

    updated = NativeHPActor(**actor.plain())
    raw_current = hp_raw_current(updated)
    # fff.or changes the maximum independently of raw current, even for a
    # frozen pool. In particular, an unchanged visible current is no authority
    # to erase a latent negative or over-cap raw PA operand.
    set_hp_raw_maximum(
        updated, updated.effect_base_maxima[1] + applied(after) - applied(before)
    )
    current_delta = layer_current(after, new_layer["max_hp"]) - layer_current(
        before, old_layer["max_hp"]
    )
    if current_delta:
        # The actual current delta uses HP.on's existing int32/hard-bound
        # semantics; its frozen-pool no-op remains native and unchanged.
        set_hp_raw_current(updated, raw_current + current_delta)
    expected_current = layer_current(after, new_layer["max_hp"])
    if updated.hp != expected_current:
        # A larger maximum can reveal a latent raw current without any heal.
        # The explicit regional no-heal policy owns this current write only
        # when that revelation disagrees with the committed canonical current.
        # Otherwise the exact latent raw operand above remains untouched.
        set_hp_raw_current(updated, expected_current)
    if updated.hp != expected_current:
        raise ValueError(
            "Territorial current cannot satisfy native HP bounds or frozen policy"
        )
    if updated.max_hp != new_layer["max_hp"]:
        raise ValueError(
            "Territorial raw maximum differs from owned characteristic reducer"
        )
    replay = OwnedEwoHPReplay(updated, existing["receipts"])
    revision = save(db, before["id"], replay, expected_revision=existing["revision"])
    return dict(
        actor=updated.plain(), receipts=replay.plain_receipts(), revision=revision
    )


def sync_fight_raw_current(db, character, actor, *, resulting_hp, resulting_maximum):
    """Persist an owned eWO actor's exact HP PA at the existing fight checkpoint.

    Ordinary characters have no projection row and retain the old persistence
    path byte for byte. For projected characters, this requires the actual
    native raw-current source and matching raw bounds/percentage/frozen state;
    it never reconstructs raw current from visible HP.
    """
    projection = load(db, character["id"], for_update=True)
    if projection is None or not projection["receipts"]:
        return False
    if (
        type(resulting_hp) is not int
        or type(resulting_maximum) is not int
        or not 0 <= resulting_hp <= resulting_maximum
        or not 0 < actor.max_hp < 2**31
    ):
        raise ValueError("Native eWO fight HP does not match persisted maximum")
    native = projection["actor"]
    if 1 in actor.effect_frozen:
        if 1 not in native.effect_frozen:
            raise ValueError("Frozen fight HP disagrees with owned eWO projection")
        return True
    from wakfu_server.combat.combat_hp_raw import hp_raw_current

    raw_current = hp_raw_current(actor)
    if (
        actor.effect_base_maxima.get(1) != native.effect_base_maxima[1]
        or actor.effect_base_minima.get(1) != native.effect_base_minima[1]
        or actor.effect_percentages.get(1) != native.effect_percentages[1]
        or (1 in actor.effect_frozen) != (1 in native.effect_frozen)
        or actor.effect_minima.get(1) != native.effect_minima[1]
        or actor.effect_maxima.get(1) != native.effect_maxima[1]
        or actor.max_hp != native.max_hp
    ):
        raise ValueError("Native eWO fight actor bounds differ from owned projection")
    if 1 not in actor.effect_frozen:
        # Finished-return recovery and an authorized end-of-fight restoration
        # change visible HP through the same raw fZB setter. Existing combat
        # damage already lives in raw_current and is not reconstructed here.
        from wakfu_server.combat.combat_maximum_resource import _int32
        from wakfu_server.combat.combat_character_copy_metadata import (
            native_copy_characteristics,
        )

        high = native_copy_characteristics()["fresh_characteristics"]["1"][
            "hard_maximum"
        ]
        raw_current = max(
            actor.effect_minima[1],
            min(high, _int32(raw_current + resulting_hp - actor.hp)),
        )
    row = db.execute(
        "UPDATE character_equipment_hp_projection SET raw_current=%s,revision=revision+1 "
        "WHERE character_id=%s AND revision=%s RETURNING revision",
        (raw_current, character["id"], projection["revision"]),
    ).fetchone()
    if row is None:
        raise ValueError("Stale native eWO fight raw-current checkpoint")
    return True


def rebase_after_fight(db, character, actor):
    """Rebase retained HP roots after settlement changes the native baseline."""
    existing = load(db, character["id"], for_update=True)
    if existing is None or not existing["receipts"]:
        return None
    current, receipts, revision = (
        existing["actor"],
        existing["receipts"],
        existing["revision"],
    )
    if (
        actor.effect_base_maxima.get(1) != current.effect_base_maxima[1]
        or actor.effect_base_minima.get(1) != current.effect_base_minima[1]
        or actor.effect_percentages.get(1) != current.effect_percentages[1]
        or (1 in actor.effect_frozen) != (1 in current.effect_frozen)
    ):
        raise ValueError("Fight actor does not match owned eWO projection")
    from wakfu_server.equipment_stats import bonuses, native_hp_baseline

    replay = OwnedEwoHPReplay(current, receipts)
    for key in sorted(
        tuple(replay.receipts),
        key=lambda item: (replay._order(replay.receipts[item]), item),
        reverse=True,
    ):
        replay.remove(key)
    raw_baseline = replay.actor.plain()
    baseline = native_hp_baseline(character)
    if all(
        raw_baseline[key] == baseline[key]
        for key in ("raw_maximum", "raw_minimum", "percentage", "frozen")
    ):
        return None
    # native_hp_baseline derives the new raw current from canonical wounds.
    # Do not carry the old absolute current across a changed maximum: native
    # build progression preserves the wound while current follows its new cap.
    fresh = OwnedEwoHPReplay(NativeHPActor(**baseline))
    for operation in OwnedEwoHPReplay.resolved_operations(
        bonuses(character)["hp_operations"], receipts
    ):
        fresh.apply(operation)
    save(db, character["id"], fresh, expected_revision=revision)
    from wakfu_server.health_policy import apply_native_equipment_hp

    updated = apply_native_equipment_hp(
        db,
        character,
        hp=0 if character.get("health_dead") else fresh.actor.hp,
        maximum=fresh.actor.max_hp,
    )
    return dict(character=updated, replay=fresh)
