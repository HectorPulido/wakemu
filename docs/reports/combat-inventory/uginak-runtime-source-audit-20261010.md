# Ouginak native/runtime source audit — 2026-10-10

## Scope and evidence

This is an offline audit of Ouginak Presa (6283), Wauwau (6286), Uginikántropo (6855), Perseguidor grant sources (6856), and the linked summon profile. No services or catalog writes were performed. The published source is active native catalog revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`; the direct PostgreSQL read-only reconciliation and complete document hashes are recorded in [the all-class source audit](remaining-classes-source-audit-20261010.md).

Relevant published documents in that revision include `spell-effect-trees.json` (SHA-256 `a188b3681c79ad455d296b303491370419cbe23da130501a8b86b51bd9a518ba`), `granted-spell-effect-trees.json` (`2d07839bdf094a23cd6cba02da6853766bc21f82244b59a1d2fcdc3bfb903477`), `combat-state-definitions.json` (`845f211b808b9ce20a14b25f3e3068480094243c507e4aaa8f9da5fad5bca7b9`), `native-class-summon-abilities.json` (`3f90d274c512ebc2611e84dceb37acb0f21f6c4b9329b7bd774ce2bdec3dc383`), `native-class-summon-initial-states.json` (`8946715f461a5eec278a580a9208ad460d3d9800df260a1408b547ea8d3c5466`), `native-class-morph-profiles.json` (`3861759f2e71b360b4812cc3424a0fe3255be2d7dc72a496778558bcf86ee8f8`), and `native-actor-characteristics.json` (`8b626aeba45f747eda596e15a2ae614c2c400c3cea8494b4ed1e4c5651edb447`).

## Wauwau profile and current runtime path

Published class summon profile 4559 has fight properties `[28, 78, 15]`, no initial-state triples, and the exact native ability book below. Each ability UID equals its reference, override level is `-1`, and maximum level is 245.

| Reference | Casting UID | Override | Maximum |
|---:|---:|---:|---:|
| 6291 | 6291 | -1 | 245 |
| 6292 | 6292 | -1 | 245 |
| 6293 | 6293 | -1 | 245 |
| 6294 | 6294 | -1 | 245 |

The native 6286 root sequence is concrete: effect 240997 is family307 with profile 4559 and level selector `-2`; 240998 is an own-summon guard; 240999 applies state7529 (Wauwau); 241000 applies state1304 unless passive6273 is in the caster's deck; and 243698 is family325 AI control for the owned 4559 summon. The class innate state7521 grants 6286 through family649 effect339893.

The current runtime has the corresponding shared infrastructure. `combat_effect_runtime.py` registers family307 when the effect factory receives `summon_authority`; the production combat spell server supplies actor authority. `combat_summon_creation.py` builds a fresh profile ability book and applies the profile's initial-state plan. `combat_spell_grant.py` handles family649, and the summon/AI-control paths handle registered summon ownership and control. This source audit found no missing published profile, ability-book, or family-registration dependency for Wauwau. It does not certify turn-by-turn client behavior, death/retirement, reuse, or all four ability effects; those remain gameplay acceptance work.

## Presa ownership and exclusivity

State7525 is titled Presa and its native description says only one prey may exist per team. Its effect closure is `[339906, 339766, 395635]`:

- 339906 only enters for a direct event whose triggering effect caster equals the state effect caster, and blocks when caster state7534 or effect341036 is present. It applies caster state7534 (unless passive7554 blocks that child) and enters the tracking sequence.
- Child 341034 applies state7531 (Rastreador) to the target permanently; 341035 adds 15 to characteristic117 on the caster; 341036 is a further effect guard.
- 339766 checks distance greater than six, then removes state7525 and state7577. This encodes a distance-based cleanup path, not a same-team replacement operation.
- 395635 reacts only to the direct same-caster trigger and applies family1093 effect395636, a 0.4 final-damage modifier when state6500 is absent.

The published `native-spell-casting.json` raw criterion for 6283 is `IsEnnemy() and #IsObstacle("target")# and not #IsCarried("target")# and #(not IsSpellInDeck(6281, "caster") or IsSpellInDeck(6281, "caster") and IsBackstabbed("target"))#`. Its sole conditional casting branch is `IsSpellInDeck(6279)` (range 1–4); neither criterion checks state7525 or team membership. Granted-tree root242159 has no criterion; child242160 removes state7525 only when `HasStateFromUser(7525, "target")`, then child242161 adds state7525 to that selected target permanently. Variant root341083 uses the same same-owner/same-target remove-then-add sequence; its only additional branch is passive6279. These nodes do not inspect a different target or another team member.

The evidence above establishes only that the exported 6283 tree has no target-team predicate and that the generic client replacement path is selected-target-local: `eWu.fMY()` iterates the selected `eGj` target's `PV.bax()` state container, filters matching state IDs, and `eWu.aS()` removes only those selected old instances. Runtime `StateLedger.apply()` follows the same actor-local scope (`self._entries`, matching `reference`), and state7525 exports `replace=true`, `additive=false`, `refresh=false`, `protected=false`; those flags do not encode team scope. This does not yet rule out a separate native Ouginak-specific/global callback or prove the observed multi-cast behavior. The team-cap claim therefore remains unresolved pending an actual multi-PC Ready-and-cast probe and inspection of any alternate native state-application path; do not infer a server-side gap from criteria or this generic replacement routine alone.

## Uginikántropo contract and confirmed gap

Spell6855's root 291399 applies state7526 permanently. Its state definition describes transformation, increased damage, rage loss on each spell, exit at zero rage, and restoration of all WP. The published state effect list contains no family933 transformation effect:

- 339773 and 340103 are family126 final-damage-percent effects, selected by passive7556: +50% without it, +30% with it.
- 339783 is family447 adding fight property41. Published property41 is `CANNOT_USE_ITEM_CAST`.
- 339923 subscribes to casts of elements 2, 3, or 4 and executes family40 effect339924 to subtract from characteristic117.
- 339932 checks `GetCharac("ouginak_resource", "caster") <= 0`, then removes state7526 and applies state7535. The Regateo branch (341019) separately subtracts five from characteristic117 and checks for zero.
- Innate effect339965 sets the resource cap to 40 with passive7557 but not7554, 20 with7554 but not7557, otherwise 30. Published characteristic117 is OUGINAK_RESOURCE, current 0, min 0, max 30; passive effects provide the conditional cap behavior.

The state has an explicit height-change HMI action even though it does not invoke family933. In the published state effect record, family400 effect339772 has action ID5088 (`CHANGE_HEIGHT`) in branches `rze`, `rzf`, and `rzh`; `rzc`, `rzd`, and `rzg` are empty. The three nonempty arrays contain the same action. The exported metadata does not label these arrays as sex variants, and Ouginak has one effect339772 reference rather than Dragon's separate sex-specific effects. The Ouginak effect contains no `APPEARANCE_CHANGE` action. By comparison, Dragon effect326546 has sex0 actions `APPEARANCE_CHANGE`4776 + `CHANGE_HEIGHT`4777, and effect326547 has sex1 actions4778 + 4779 in the same three HMI branches. These are concrete native presentation differences, not evidence that Ouginak needs family933. State7535's sole family400 effect339943 has all six HMI lists empty.

The current runtime binds family400 to `NativeStatHandler` through the `eXE` registry row (`operation: none`), which emits the retained/evaluated owned-effect packet with execution status −1 and removes that effect when its owning state is removed. The actual 6855 cast evidence in `.runtime/uginak-review-20261010/baseline-normal.json` records 339772 / family400 as `completed` under state UID220; the cast commits with 27 packets, including nine opcode12613 evaluated-effect packets and eight opcode13560 removals. In this fresh-actor fixture resource117 begins at zero, so event339932 fires immediately: family400 339938 completes, 339933 removes state7526 and its owned children, and 339944 applies state7535. The final actor ledger contains 7535 and not 7526. This proves the tested server-side effect/state lifecycle and packet emission, but not visible height change or restoration in a live client. The Dragon visual fixture in `.runtime/osamodas-incident-20261010/dragon-visual-sex-{0,1}.json` demonstrates the comparator pattern: the retained HMI effect is present in the reconnect snapshot and its exact UID later appears in opcode13560 removal for both sexes. A persistent Ouginak-form probe must begin above zero resource and make the same retained-effect/reconnect/removal check, while asserting the expected `CHANGE_HEIGHT` action and verifying whether any model change is intended. Do not route Ouginikántropo through family933 without separate native evidence.

## Grant distinctions and implementation targets

Innate state7521 grants Presa6283 through family649 effect339679, Wauwau6286 through 339893, Uginikántropo6855 through 339892, and Perseguidor6856 through 339680 only when spell6285 is in the deck. Separately, spell6285 contains a family649 child291430 behind a root whose criterion is literally `False`; that edge is structurally present but unreachable under the published criterion. Therefore 6856's live grant path is the innate conditional path, not the false spell child. Family649 uses the native grant registry and current actor book; retain source ownership and removal behavior when fixing/validating it.

Recommended implementation probes are: (1) two same-team Ouginaks mark separate targets, then one marks again; assert exactly one active team prey and owner-specific tracking/damage; (2) Presa target death, distance beyond six, owner death, reconnect, and next fight; (3) Wauwau Ready→summon→book refs 6291–6294→turn/control→death→resummon, asserting team/controller and packets; (4) Uginikántropo with resource above zero, each passive-derived cap, element-specific spell spending, zero-resource exit, WP restoration, item-cast restriction, HMI height apply/removal, reconnect, and next fight. The existing normal-cast artifact covers one level90/200 direct transaction and immediate zero-resource exit; it does not cover persistent-form client presentation or restoration. These checks are not represented as completed here.
