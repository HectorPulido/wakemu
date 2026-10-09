# Iop / Yopuka current code inventory — 2026-10-08

## Exact result

Authoritative published spell identity gives **native breed8, IOP**. Current compiled catalogs contain every requested Iop dependency: **zero missing effects, zero missing states, zero missing casting definitions**. Current factory/dispatcher analysis finds **zero missing handler families**. These findings establish availability and routing. **Separate semantic source review originally identified three incomplete paths and one partial event gap. Shared repairs now have actual-route automated validation**, detailed below; client acceptance remains pending.

| Domain | Count |
|---|---:|
| active | 21 |
| passive | 20 |
| granted | 4 |
| innate_roots | 2 |
| entry_roots | 47 |
| effects | 1422 |
| states | 59 |
| casting_spells | 45 |
| families | 74 |
| areas | 3 |
| profiles | 1 |

The45 distinct spells include21 active deck spells,20 passive deck spells and four granted abilities. There are two innate roots:state7553 and shared state4464. The47 entry roots include every deck spell, granted spell and innate seed. Shared finisher branches under4464 are presentation dependencies, not additional Iop attack mechanics.

Published catalog revision: `7071a8d8c8664e9e0d5fe8f44bf2a948d4138060fc1353ea70f65f2dcf00b568`. No protocol import file was treated as the active authority.

## Exhaustive spell inventory

| Reference | Installed name | Domain | Effects in closure | States in closure |
|---|---|---|---:|---:|
| 4775 | Fulgor | active | 101 | 7 |
| 4776 | Juicio | active | 83 | 8 |
| 4777 | Súper Puño Yopuka | active | 100 | 7 |
| 4778 | Espada Celeste | active | 101 | 8 |
| 4779 | Ira de Yopuka | active | 90 | 7 |
| 4780 | Sacudida | active | 98 | 8 |
| 4781 | Lanza Rocas | active | 110 | 8 |
| 4782 | Cuchillo de Carnicero | active | 109 | 8 |
| 4783 | Carga | active | 254 | 13 |
| 4784 | Estragos | active | 87 | 8 |
| 4785 | Jabs | active | 122 | 7 |
| 4786 | Ráfaga | active | 84 | 8 |
| 4787 | Bofetada | active | 105 | 8 |
| 4788 | Casca | active | 122 | 9 |
| 4789 | Espada de Yopuka | active | 107 | 9 |
| 4790 | Focalización | active | 15 | 6 |
| 4791 | Virtud | active | 8 | 0 |
| 4792 | Postura | active | 74 | 4 |
| 4793 | Amplificación | active | 16 | 3 |
| 4794 | Duelo | active | 5 | 1 |
| 4795 | Virilidad | passive | 13 | 2 |
| 4796 | Compulsión | passive | 13 | 2 |
| 4797 | Autoridad | passive | 6 | 0 |
| 4798 | Duelista | passive | 5 | 1 |
| 4799 | Rey de la Colina | passive | 20 | 1 |
| 5100 | Valentía | passive | 3 | 0 |
| 5101 | Precipitación | passive | 1 | 0 |
| 5102 | Agrupación | passive | 1 | 0 |
| 5103 | Minisalto | passive | 1 | 0 |
| 5104 | Falla Sísmica | passive | 1 | 0 |
| 5130 | Hora de Gloria | active | 5 | 1 |
| 8413 | Destino | passive | 1 | 0 |
| 8414 | Impetuoso | passive | 4 | 1 |
| 8415 | Demostración | passive | 11 | 1 |
| 8416 | Golpea y Corre | passive | 1 | 0 |
| 8417 | Disipación | passive | 1 | 0 |
| 8418 | Puesto Avanzado | passive | 1 | 0 |
| 8419 | Fortificación | passive | 5 | 0 |
| 8420 | El Yopuka de Wazemmes | passive | 2 | 0 |
| 8421 | Conquista | passive | 62 | 3 |
| 8422 | Portaestandarte | passive | 1 | 0 |
| 8402 | Borrasca | granted | 74 | 0 |
| 8403 | Uppercut | granted | 95 | 6 |
| 8404 | Salto | granted | 18 | 2 |
| 8405 | Estandarte de Valentía | granted | 89 | 8 |

## Construction gates and concrete native configurations

All listed gates have production suppliers: `combat_server_spell.py` supplies the actual ordinary actor authority as both displacement and summon authority; `combat_effect_runtime.py` constructs retained authority when the plan has a spell ID or retained container. Every effect below has native execution mode2 in the inspected configurations. A construction gate is not itself an absent feature.

| Family | Native effect count | Provider requirement | Example effect and raw parameters |
|---|---:|---|---|
| 300 | 11 | self.displacement_authority is not None | 151737: `[3.0, 0.0, 1.0, 0.0]` |
| 301 | 6 | self.displacement_authority is not None | 148998: `[1.0, 0.0, 0.0, 0.0]` |
| 302 | 4 | self.displacement_authority is not None | 397427: `[]` |
| 305 | 8 | self.displacement_authority is not None | 149485: `[3.0, 0.0]` |
| 307 | 2 | self.summon_authority is not None | 397437: `[3793.0, 0.0, -2.0, 0.0, 0.0, 0.0]` |
| 315 | 7 | retention is not None | 397439: `[889.0, 0.0, 1.0, 0.0, 1.0, 0.0]` |
| 421 | 21 | retention is not None | 148996: `[148997.0, 0.0]` |
| 843 | 6 | retention is not None | 151993: `[-1.0, 0.0]` |
| 1013 | 25 | self.displacement_authority is not None | 291175: `[0.0, 1.0, 0.0, 0.0]` |

The companion JSON preserves **every gated effect configuration**, criteria, selector, masks, timing, flags and affected entry root, rather than treating representative examples as complete coverage.

- Summon307 has two concrete definitions397437/398767, native profile3793 and parameter vector `[3793,0,-2,0,0,0]`; masks are null and native execution mode is2. `combat_summon_handler.py` intentionally rejects retained/subscribed summon creation. These particular direct configurations do not establish that guard is hit.
- Area315 has seven definitions referencing native889/2042/2047. Passive8413 chooses the relevant area branch; removal843 uses actual owned-area identity. The area and summon/standard lifecycle is a shared implementation dependency, not a spell-ID patch.
- Displacement300/301/302/305 and displacement-conditioned group1013 require actual geometry and actor authority. Criteria include alignment, facestabbed identity, distance and passive5102. Native target/state preconditions must be preserved.

## Combo inventory

The native closure includes the following named combo states:

- State3444: Combo de Robo de Vida; native roots [150420, 397559, 397915]; maximum level3.
- State3445: Combo de Empuje; native roots [397560, 397561, 397919]; maximum level3.
- State3446: Combo de Preparación; native roots [397562, 397563, 397917]; maximum level3.
- State3447: Combo de Daños Adicionales; native roots [397564, 397565, 397923]; maximum level3.
- State3448: Combo de PA; native roots [397566, 397567, 397568, 397921]; maximum level4.
- State3485: Combo; native roots [152079, 152070, 152073, 152076, 152080, 152083, 152086, 152089, 152092]; maximum level10.

Combo state transitions, costs, AP/MP changes, damage, healing and state removal route through the shared native state/group/stat/damage machinery. All their requested effect definitions and registered families are present. The report includes each state and effect dependency and the entire per-spell native casting record. It does not infer combo correctness from the names.

**Do not mistake legacy executor restrictions for current missing code:** `combat_iop_cast.py` says3444/3467/6117 are unsupported by its old two-spell executor. Source search finds no production caller outside that file. Current ordinary casting uses `combat_server_spell.py` and its general factory; the legacy docstring is not evidence that the shared engine lacks those states.

## Remaining evidence gaps

Source-only event review identified the following historical incompleteness. The current repairs and actual-route validation are recorded below; zero missing definitions or handlers alone never establishes complete behavior. See [producer/source-context evidence](iop-semantic-producer-current-audit-20261008.md).

| Finding | Exact affected mechanic | Incomplete behavior | Preserved alternative |
|---|---|---|---|
| IOP-SEM-01 | Preparación3462, listener151183 | Local500 has no current explicit producer or Iop publication-mask6 source. | No alternative event in this listener is established. |
| IOP-SEM-02 | Juicio4776/state8912, listener397245 | Cast1024 has null triggering source; same-caster identity is false, blocking the elemental first criterion branch. |8402/8403 with state8916 OR branch remains reachable. |
| IOP-SEM-03 | Carga4783 via Guerrero7553,397553→397554/397555/397556 | Null-source replay retains SELF target/cell; intended distance1/2/3 branches observe0. | Other spell-ID alternatives remain reachable. |
| IOP-SEM-04 | Estandarte de Valentía8405/Portaestandarte8965,398802; innate null332064 |1005 publication is absent. |1010 is present; the entire state is not blocked. |

Preparation is shared structurally by elemental actives4775–4789, Virilidad4795, Demostración8415, granted Uppercut8403 and innate7553; structural reachability does not mean every action must always trigger500. The full reverse dependency list is preserved in JSON. No unverified replacement event or triggering source was inferred.

The following additional behavior is **not certified**: actual combo sequences and resets; all20 passive event activations; normal/critical secondary branches; banner placement/ownership/entry/exit/removal; grant/withdrawal of8402/8403/8404/8405; retained expiration and reconnect; exact costs, damage, armor and resource ceilings. The missing semantic-case count is not known and must not be presented as zero.

The closure contains56 named predicate functions. All56 appear in current combat source; textual presence alone is insufficient to prove every provider and argument combination. Actual legality, typed authority and condition timing must be validated against native configurations.

## Reproducibility and limits

Read-only current-world catalog query resolved47 historical graph roots against current compiled effects/states/casting. Current AST factory and dispatcher routes were refreshed using the exact existing route-builder binding logic and published characteristic/set-current registries. The companion JSON records74 families, their current source binding lines and source hashes. It lists every entry root/dependency, all59 states, all1422 effect configurations (omitting bulky evaluated-level arrays), and all45 casting definitions.

Private temporary query inputs/results are `/tmp/wakemu-iop-live-readonly.py`, `/tmp/wakemu-iop-live-readonly.json`, and `/tmp/wakemu-iop-routes.json`. No gameplay test, service restart or deployment occurred. The published reader may fill its normal Redis cache. No secrets are included in the report.

## Whole-system manual acceptance after shared repairs

Run this complete route after the four recorded semantic findings have been repaired and automatically validated. No current all-Iop acceptance is claimed. Use the existing Iop test character, a legal native level/deck and the current deployed version; record character level, equipment, deck, release and expected versus observed values. The report does not invent item or character commands.

1. Enter a fresh fight and verify native AP/MP/WP, health, displayed range and spellbook. Confirm all four class-granted actions8402/8403/8404/8405 are available under their native prerequisites.
2. Exercise the15 elemental attacks4775–4789, including all three elements, normal and critical branches where available, single/multiple targets, range/LOS boundaries and insufficient-resource rejection. Verify actual damage, costs, orientation, armor interactions and resulting states against the native spell description; invalid actions must preserve resources.
3. Complete each of the five combo systems: lifesteal3444, push3445, preparation3446, additional damage3447 and AP3448. Follow the native displayed sequence for each; verify intermediate state levels, final effect, resource changes, interruption/reset and end-turn expiration. Repeat Carga4783 at native distances1/2/3 to verify the corrected Guerrero distance context.
4. Verify Preparación3462 consumption/activation and native Power/resource transitions after qualifying attacks. Verify Juicio4776 with elemental triggers and its separate8402/8403+8916 alternative; both criterion paths must retain their own legality. Verify Sacudida4780/Sacudido8913 using each repaired event path.
5. Exercise all21 active deck spells across legal deck configurations. The exhaustive table above is the checklist; the six non-elemental active actions include Focalización4790, Virtud4791, Postura4792, Amplificación4793, Duelo4794 and Hora de Gloria5130. Verify application, expiration, removal and failure cases, not only successful animations.
6. Exercise all20 passive definitions individually with the actual native event/condition they require, then representative legal combinations. Use the exhaustive passive rows above and JSON dependency descriptions. A400 marker alone is not a verdict: inspect the corresponding casting/innate branch and its expected value.
7. Create Estandarte de Valentía8405, verify profile3793 ownership, passive-selected area889/2042/2047, positioning, allies/enemies entering or leaving, duration, removal and recreation. Verify Portaestandarte8965 on both documented event alternatives after the1005 repair.
8. During an active fight with combo/state/banner/grant effects present, reconnect. Verify current turn, ACK recovery, AP/MP/WP, state levels, native grants, banner identity and next action; effects must neither disappear unexpectedly nor duplicate.
9. Complete a victory, surrender in a separate fight, return to the world and enter another fight. Verify all temporary states, banners, grants and resources reset according to native rules. Record any exact unresolved case without certifying the entire class from one successful action.

Detailed high-risk acceptance: [native combo sequences, Carga distance branches, Juicio fire source, Preparation, banner and armor](manual-iop-high-risk-acceptance-20261008.md). Element1 is FIRE in the current published registry; an earth spell is not the positive Juicio first-branch test.

Sacudido8913/event2236 correction: the shared current-stat consumer receives native ARMOR97 reduction notifications2236, including family1011 produced events. Damage2 is also present. An Iop-local publication-mask census cannot exclude incoming general/cross-class events;2236 is **not** classified as an absent producer.

## Completed shared repairs and actual-route verification

The integration agent reports actual owned routes now validate the reviewed fixes:

- Juicio8912: next FIRE cast is positive; EARTH cast is negative. Native element1 is FIRE.
- Carga4783: distance1/2/3 branches use the actual validated target. Uppercut8403 establishes3448 level1; a legal2MP retreat followed by Carga at distance3 advances it to level2.
- Preparación: Borrasca8402 twice then Uppercut8403 produces3462 level20. Next Jabs4785 uses its actual family5 damage modifier+20 and consumes Preparation.4785 is Jabs, not Carga.
- Estandarte8405: passive8422 plus actual granted8405 UID cast on SELF supplies8965, followed by legitimate voluntary movement removing it through the implemented source-backed boundary.
- Sacudido2236: the shared armor-stat notification producer already existed; it was not a missing feature.

These results were supplied by the integration agent, not newly executed by this report author. The complete r47 build/deployment is managed by root and must be verified separately before client acceptance. None of these focused results certifies every Iop spell, passive or variant.

The500/1005 producer repairs are explicit Wakemu policies, not recovered original-server callers. The granted8405 action must not be inserted into a normal active-deck slot.


## Iop repair delivery update

The shared Iop context, Preparation and voluntary-movement repairs are delivered in the complete r47 image. Current code and catalogs were verified before restart; actual Iop/Cra regressions and summon retirement checks passed. See the [delivery and validation record](iop-shared-repair-delivery-20261009.md). Manual whole-class acceptance remains pending.
