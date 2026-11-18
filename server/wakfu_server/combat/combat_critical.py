"""One owned critical decision per cast; server roll policy is explicit.

Native facts: ffw.sgI/PC9 FEROCITY is fqX.CRITICAL_CHANCE, base3 with
characteristic bounds -1000..1000. Server percentage roll is an owned policy,
not a recovered client producer. Selected native effect variants determine
critical damage/healing; this module never applies a damage multiplier.
"""
from wakfu_server import native_catalog as protocol_catalog
from dataclasses import dataclass
from collections.abc import Mapping


@dataclass(frozen=True)
class CriticalDecision:
    critical: bool
    mode: str
    chance: int | None
    threshold: int | None
    roll: int | None

    def diagnostic(self):
        return {
            "critical": self.critical,
            "critical_mode": self.mode,
            "critical_chance": self.chance,
            "critical_threshold": self.threshold,
            "critical_roll": self.roll,
        }


def choose_critical(actor, *, rng, mode="auto", critical_available=True):
    """Caller must roll inside the same reversible transaction as the cast.

    Guaranteed/impossible rolls consume no random draw, like eZR's ordinary
    probability boundary policy. Missing live PC9 rejects auto; never substitute
    a base or trust a client flag. Overrides remain explicit developer policy.
    """
    if mode not in ("auto", "normal", "critical"):
        raise ValueError("Critical mode must be auto, normal or critical")
    if type(critical_available) is not bool:
        raise ValueError("Missing native critical branch availability")
    if mode == "normal":
        return CriticalDecision(False, mode, None, None, None)
    if mode == "critical":
        if not critical_available:
            raise ValueError("Native critical branch is unavailable")
        return CriticalDecision(True, mode, None, None, None)
    stats = getattr(actor, "effect_stats", None)
    if not isinstance(stats, Mapping) or type(stats.get(9)) is not int:
        raise ValueError("Missing live native FEROCITY critical chance")
    chance = stats[9]
    if not -1000 <= chance <= 1000:
        raise ValueError("Live FEROCITY exceeds native characteristic bounds")
    threshold = max(0, min(100, chance))
    if not critical_available:
        return CriticalDecision(False, mode, chance, threshold, None)
    if threshold in (0, 100):
        return CriticalDecision(threshold == 100, mode, chance, threshold, None)
    if not callable(getattr(rng, "randint", None)):
        raise ValueError("Critical roll requires transaction-owned RNG")
    roll = rng.randint(1, 100)
    if type(roll) is not int or not 1 <= roll <= 100:
        raise ValueError("Invalid owned critical percentage roll")
    return CriticalDecision(roll <= threshold, mode, chance, threshold, roll)


def prepare_with_critical(actor, *, rng, prepare, mode="auto", critical_available=True):
    """Atomic RNG boundary includes branch draw AND all mandatory child effects.

    prepare(critical=bool, rng=same_rng) must return an uncommitted owned preview;
    network sending/commit remain callers' responsibilities after success.
    """
    from .combat_random_transaction import rollback_external_rng

    if not callable(prepare):
        raise ValueError("Critical cast requires an owned preview preparation")

    @rollback_external_rng
    def transaction(*, rng):
        decision = choose_critical(
            actor, rng=rng, mode=mode, critical_available=critical_available
        )
        result = prepare(critical=decision.critical, rng=rng)
        return decision, result

    return transaction(rng=rng)


def spell_critical_available(spell_id, level):
    if type(spell_id) is not int or type(level) is not int or not 0 <= level <= 32767:
        raise ValueError("Missing audited native spell critical level")
    if level == 0:
        scoped = _rii_zero_critical().get(str(spell_id))
        if type(scoped) is bool:
            return scoped
        scoped = _morph_zero_critical().get(str(spell_id))
        if scoped is not None:
            from .combat_morph_dependencies import zero_catalog

            source = zero_catalog()
            if source is None or str(spell_id) not in source["spells"]:
                raise ValueError(
                    "Missing audited native morph zero-level critical source"
                )
            return 0 in scoped["critical_levels"]
    row = _spell_availability().get(str(spell_id))
    if row is None:
        raise ValueError("Missing native spell critical availability")
    # The original general export sampled 1..200. Scoped native producers can
    # explicitly attest further levels without inventing absent observations.
    minimum = row.get("evaluated_minimum_level", 1)
    maximum = row.get("evaluated_maximum_level", 200)
    if not minimum <= level <= maximum:
        raise ValueError("Missing audited native spell critical level")
    return level in row["critical_levels"]


from functools import lru_cache


@lru_cache(maxsize=1)
def _rii_zero_critical():
    import json
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "achievements"
        / "rii_level_zero_critical.json"
    )
    data = json.loads(path.read_text())
    return data["spells"]


@lru_cache(maxsize=1)
def _spell_availability():
    from wakfu_server.paths import DATA_ROOT
    import json

    data = protocol_catalog.load(DATA_ROOT / "native-critical-availability.json")
    return data["spells"]


@lru_cache(maxsize=1)
def _morph_zero_critical():
    """Original bPO critical observations for published zero-level morph books."""
    import json
    from hashlib import sha256
    from pathlib import Path

    raw = Path(__file__).with_name("native_morph_zero_critical.json").read_bytes()
    if (
        sha256(raw).hexdigest()
        != "ab6cc5be23b31f0f9268fc24a400c4eb2bd4f48f6de2a2cafb7e55921447eaa2"
    ):
        raise ValueError("Native morph critical attestation changed")
    data = json.loads(raw)
    if (
        data.get("source")
        != "Scoped original bPO.hasCriticalEffect, explicit every level 0..native Fq"
        or type(data.get("native_checks")) is not int
        or data["native_checks"] <= 0
        or not isinstance(data.get("spells"), dict)
    ):
        raise ValueError("Missing native morph critical attestation")
    for reference, row in data["spells"].items():
        if (
            not reference.isdigit()
            or int(reference) <= 0
            or type(row.get("evaluated_minimum_level")) is not int
            or row["evaluated_minimum_level"] != 0
            or type(row.get("evaluated_maximum_level")) is not int
            or row["evaluated_maximum_level"] < 0
            or not isinstance(row.get("critical_levels"), list)
            or any(
                type(level) is not int
                or not 0 <= level <= row["evaluated_maximum_level"]
                for level in row["critical_levels"]
            )
        ):
            raise ValueError("Invalid native morph critical observation")
    return data["spells"]
