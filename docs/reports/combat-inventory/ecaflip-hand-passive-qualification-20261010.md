# Ecaflip hand-dependent passive qualification

Scope: actual Ready, owned spell requests, native movement and end/ACK turn transactions against the read-only published PostgreSQL catalog. No state, resource, grant, turn-counter or criterion injection is used. Production code is unchanged.

The three focused tests in `server/tests/test_ecaflip_hand_passives_pipeline.py` passed through Luna's serial validator. They qualify the following specific behavioral paths, rather than every possible combination of these passives.

## Black Jack (7960)

The native subscriber359899 consumes event1005, which the current server publishes on successful voluntary movement. Its parameters `[1,1]` stop after the first successful child. The weighted owned-card total in361071 assigns weights0 through12 to cards7938 through7950.

Real seeded Ready hands on both sides of the threshold were moved through a legal native interior edge. A total at most20 gives armor equal to the rounded ten percent of maximum HP plus maximum VIRTUAL_HP and does **not** execute the fallback state. A total above20 gives no armor and applies6624 at level5. This is movement behavior, not a turn-start reward.

## Triunfos Periódicos (7961)

The native conditions exclude one card parity according to `GetFightCurrentTableTurn()`. Ready's pre-timeline table value is distinct from the round subsequently adopted by the actual runtime; the test advances real complete cycles until the opposite parity is reached.

The actual fixture begins with owned cards7940/7944/7946. At actual table turn3, an owned2060 request to the caster's actual cell commits and produces carriers7962/7964/7970 at level2, corresponding to cards7939/7941/7947: all three have the permitted odd parity. Its exact numerical effects are:

- Draw counter7940: 10 → 7.
- Hand counter7941: level4 remains level4.
- Racha3683: 40 → 61.
- The original owned hand remains unchanged.

This is Doble o Nada's three-card **autoplay**, not a persistent hand draw. Root359256 has limit3; its lottery applies level2 carriers. Their649 grant runners exist only at level1, while their426 immediate casts require at least level2. The actual three359822 activations supply seven Racha each. Marker359372 prevents these autoplay cards from consuming the existing hand counter.

## Racha de Cartas (8001)

The actual1037 regeneration subscriber371345 checks grant ownership at execution time, rather than merely checking whether a card's carrier state survives. Its children are signed:

- Cards7939/7941/7944/7946/7948/7949 remove fifteen Racha through321.
- The other seven cards add fifteen through304.

The test observes the actual subscriber immediately before and after execution, preserving its source, channel60, manager7, criteria and result. It checks ordered arithmetic and the native0..100 state bounds, witnesses both positive and negative outcomes, and verifies that the subscriber is absent without8001. A real card play additionally proves that a surviving played-card carrier is excluded when its grant has been removed. Earlier snapshots of the hand are not substituted for ownership at1037.

## Limits

These are focused runtime tests with a complete native combat fixture and controlled LOS callbacks for unrelated casting geometry. They do not certify client rendering, probability distributions or every passive combination. No service was restarted or deployed for this work.
