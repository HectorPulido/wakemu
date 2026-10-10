# Aniripsa mark, source-value and area pipelines

Scope: local real-actor regressions for ANI-04/ANI-07. No service restart, deployment, live fight mutation or production handler change. These results certify the listed branches, not every mark/passive combination.

## Verified behavior

`server/tests/test_aniripsa_mark_pipeline.py` runs the actual published catalog, owned decks, class initialization, casting transactions, QI population and turn/movement providers. It does not inject marks or subscription records.

| Pipeline | Assertions |
|---|---|
| Explosana645 → state3882 → lethal owned Corrosana636 | Mark exists before the lethal hit; victim reaches HP0; exactly one death; nearby hostile receives63 secondary damage through the native ring1–2 reaction. |
| Ting3884 → hostile Iop hit crossing the HP threshold | Actual damage triggers53 healing,108 damage to the hostile cross recipient and consumes the mark. |
| Hmill3885 → zone damage, then point Corrosana636 | Zone645 does not heal or consume the carrier; qualifying point damage heals the nearby ally43 and consumes the old mark UID. The new Corrosana may legitimately apply a new mark. |
| Reintegro3888 → actual allied turn end1002 | The qualifying adjacent-allies branch heals44 and consumes the carrier. |
| Breo3919 → healing a different ally | Actual779 copies8 healing to the carrier; the full-health follow-up consumes3919 and creates3902. |
| Retraso5451 + owned Palabra Sanadora779 | Identical injured-player fixtures heal42 without passive and21 with passive. The passive creates3899 level21 with actual caster/target7. A successful voluntary movement step heals the deferred21 and removes3899. |
| Fuente salvadora7985 | Exactly one area1812 is created at the requested cell, owner7, level200. The original preview has no area. Actual turn/ACK progression expires the created area within15 boundaries. |

The near-death mark victim uses an explicit PA.on(1) fixture operand after the first mark cast. The second owned cast supplies the genuine lethal source. This test establishes reaction routing and recipients; it does not claim the victim reached that HP naturally in a longer fight.

## Native contracts that prevent false fixes

Family430 (`eZL`) mutates the triggering running effect amount; it is not itself a delayed execution runner. Retraso369980 subscribes to healing event1 on channel2. Child371823 modifies that live healing amount by−50%;371824/371825 accumulate the deferred amount in3899. State listener371828 subscribes to1005, the voluntary-movement boundary in the current server policy. Expecting damage mitigation or healing at the next turn end would test the wrong contract.

The Explosana KO listener367423 observes1010 and runs367424 fire damage in ring1–2. Its cleanup child367425 is a distinct321 runner. Native `eZi` inherits `eZR.bcd` without an override. Child367425 has no flag15, special spell2040 container or own1010 subscription mask, so the OFF_PLAY corpse guard rejects its decurse. The regression preserves3882 on the dead carrier rather than weakening this guard. This is not evidence that a living mark remains reusable indefinitely.

Other marks have distinct triggers:3884 observes damage2 with an HP threshold;3885 observes direct/non-zone damage;3888 observes1002 with adjacent allies;3919 observes healing1. They must not all be implemented as death rewards. All five now have actual positive consequence tests; Hmill additionally has a zone-damage negative control. Cross-owner kills, multiple simultaneous marked victims, nested explosions, mark-specific passive modifiers, Cunejo area1814 and Retraso's1047 fallback remain outside these scoped assertions.

## Validation

Command, with the existing local published-catalog configuration:

```sh
PYTHONPATH=server:server/tests:server/tools WAKFU_TEST_GRANTEDCAST=1 \
  /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_aniripsa_mark_pipeline -v
```

Expanded result: **7/7 passed**,40.079seconds. Private terminal evidence: `.runtime/aniripsa-all-marks-pipeline.log`. The earlier three-case result is historical. The executed process used garbage-collection suppression and an explicit exit after flushing the unittest result to avoid catalog finalization delays; gameplay assertions were unchanged.
