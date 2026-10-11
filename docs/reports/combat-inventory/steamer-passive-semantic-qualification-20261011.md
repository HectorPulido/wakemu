# Steamer passive semantic qualification

Steamer native20 passives; core semantic qualification with explicit branch limits.

The coherent aggregate is queued. Individual positive/negative results are evidence for the stated mechanism; they do not certify every transitive branch or live client behavior. No restart, deployment or catalog activation is included.

| Passive | Core semantic evidence | Limits |
|---|---|---|
|6925 Moderador de Energía|Full-WP state7745, stat120+30 and actual Microbot full-WP table|Enemy-on-area interaction is a separate6940 branch.|
|6926 Caminos Tortuosos|Initial and full-WP Microbot conditional range with baseline controls|No client tooltip acceptance.|
|6927 Versatilidad|Near/far fallback7678/7679 with level200 numeric stat changes|Both mutually exclusive branches executed.|
|6928 Blindaje Reforzado|Turret range1–3 versus1–6 and actual HP924 versus616|Fixture ownerHP2050; source float32 nearest rounding.|
|6929 Estrategia Robótica|Actual owned6910 arms7698; specialization heal346194 executes only with passive|Heal execution qualified; injured-owner net HP restoration not separately asserted.|
|6930 Tecnología de Transportes|Actual Microbot range/cost conditional variants|Combined6926/6940/full-WP contexts covered.|
|6931 Asistencia Telúrica|Actual6912 cast boundary creates6288 companion; baseline creates none|Three actual same-turn companions, bound owner-start death cleanup and fourth paid-cast capacity control PASS.|
|6932 Sustitución Mecánica|Actual turret WP cost conditional with/without passive|This does not qualify every disabled cross-class root.|
|6933 Paciencia|Native opening WP payment and naturally armed7677/SP-max expansion|Startup table-turn policy separately owned/tested by event_closure.|
|6934 Aleación Ligera|Actual MP maximum/current−1 and Microbot creation|Repeated actual placement reaches6/8 and rejects one further eligible empty-cell placement (PASS).|
|6935 Inversión de Energía|Actual WP/SP regeneration through real turns|Combined inverse form and threshold fixtures covered.|
|6936 Revestimiento Absoluto|Actual maxHP+1200 and7647-form turn HP loss; no-form negative|No fabricated injury/resource refill.|
|6937 Activación|Actual7700 upgrades:7649 caps at2 with passive and exceeds2 without|Alternate non-owned-target branches remain outside this assertion.|
|6938 Ejecución Inmediata|Enabled1037 marker395185 executes; literalFalse damage child344025 absent|Native dormant damage branch intentionally stays disabled.|
|6939 Protección Stasiada|Actual turret selects distinct recirculation304 producer/PL|Nested abilityPL1 makes both observed levels1; selection is not an invented numeric4-versus1 claim.|
|6940 Ruedas Calientes|Natural7677 threshold followed by owned7008 executes SP context only with passive|Enemy on actual385/978 at1005/1037→7688 numeric branch not separately executed.|
|6941 Conquista Serena|Actual SP max−2/playerstat87+50 and fresh turret inheritedstat87|Actual player Cannoner7648 transition removes50stat87 only with passive (PASS).|
|6942 Chapuza|Actual6914 arms7699;7671 selects half-growth1083 branch versus full-growth baseline|Native calculated full/half amounts compared with rounding tolerance (PASS). Ambush7726 producer343443 is literalFalse.|
|6943 Mecánica Avanzada|Actual owned6902 outgoing direct damage reduced with344029; baseline no modifier|Actual state-container indirect damage excludes344029 (PASS). Incoming reduction is not the contract;6500 exclusion remains source-qualified.|
|7810 Despliegue Táctico|Turret casting linearity/LOS changes, baseline negative; nested swap disabled|350970False dominates350971→350972→350973; no enabled swap claim.|

Latest positive6929/6942 run: `.runtime/remaining-six-refresh-20261010/steamer-final-active677.log`,2/2 PASS, no skips/errors. Source special module SHAde783060 (full hash in execution manifest). Corrected outgoing6943:1/1 PASS. Ambush actual swap with dormant damage exclusion:1/1 PASS.

Important fixture sources:6907 Corriente contains push300/343186 and can break the turret cardinal firing line;6929 uses6910 Piratería (range3–4, no displacement descendants).6912 Steamaza has range1;6942 uses6914 Machacado (range1–4, no displacement descendants). All use actual Ready, owned casts and end/ACK/start callbacks.

## Coherent aggregate and numeric follow-ups

The 13-module aggregate passed **28/28**, with no failures, errors or skips, against unchanged active revision `677062aedeeb9fa0deaad21e0c9a40989e5c8b64cc13b1ebba7200f684d3437d`. Evidence: `.runtime/remaining-six-refresh-20261010/steamer-all13-active677.log`. This qualifies the listed core contracts; it does not complete every transition limit below.

The additional specialization test passed the actual native full-versus-half damage calculations, including integer rounding tolerance (`steamer-numeric-followup-677.log`). Actual Cannoner entry passed the reservoir-bonus removal assertion (`steamer-transition-limits-677.log`). The capacity test placed the six/eight Microbots but exhausted its adjacent rejection-cell search; its corrected fixture reserves a genuinely eligible cell before placements, and awaits a focused rerun.

The injured-recipient extension passed actual enemy7962 damage, a real two-cell retreat and subsequent346194 net HP restoration (`steamer-injured-heal-677.log`). The indirect guard extension passed positive actual state-container damage and absence of successful344029 under those sources (`steamer-indirect-guard-677.log`). Capacity final evidence: `steamer-motor-capacity-677-final.log`; both native6/8 limits and additional-placement rejection passed.

## Historical shared turn-recipient gap (superseded by the qualified policy below)

An actual enemy standing on a genuinely cast Microbot does not yet qualify the6940 damage branch. Exact active677 metadata343996 is global with caster_code2 and target_code5; its native application flag isTRIGGERING_EFFECT_TARGET. Its criterion sees the actual enemy turn through typed boundary facts, but the null-Qe subscription clone retains the original owner target. Consequently343998 checks owner7, returnsFalse and no7688 damage occurs. This was the reproduced caller-context gap before the shared policy below; the subsequent aggregate qualifies enemy-area acceptance. Native eZR null-source behavior must remain intact; any server reconstruction policy needs explicit provenance and general tests.

Companion lifecycle extension passed: native bound kill-handler recipients are actual3792 summons even though the dispatcher entry records the carrier owner. Three living6288 companions were created through three actual6914 casts in one turn, with exact2AP percast. Evidence: `steamer-companion-close-cap-677.log`. A fourth paid cast using source-validated equipment is queued as the negative cap control.

The fourth-companion control also passed (`steamer-companion-fourth-677-final.log`). Real source-validated equipped items provide sufficient AP before actor construction. A fourth6914 is rejected by its native per-turn usage limit and leaves AP/turn/roster unchanged. A distinct owned6913 then legally pays3AP but344157 rejects creation at three living6288 companions. This isolates both native usage and shared companion capacity without bypassing either.

## Approved owned-turn recipient reconstruction

The approved shared fix introduces `combat_external_turn_recipient.py`. The actual turn publisher attests the exact context object only during its delivery scope and removes the attestation in `finally`. A null-Qe external event with native target_code5 may then select that validated current turn participant. The policy checks active fight, current actor identity, turn, phase/event consistency and scope identity. Copied, forged, stale or mismatched facts fail explicitly. Bare external events, other target codes and real native source runners keep their existing behavior. No class/reference check, source UID, fake runner or non-null PL is introduced.

This is a named Wakemu server caller reconstruction; native eZR null-source rebinding itself is unchanged. The focused turn/movement/control gate passed14/14 on unchanged active677 (`turn-movement-policy-steamer-677.log`). Movement1005 is a separate boundary and must not borrow current-turn facts without its own committed-step provenance.

## Committed movement and team qualification

The same explicitly approved caller policy now covers1005 with separate committed-step facts: actor, turn, positive action ID, native origin/destination and event1005. `prepare_area_movement` supplies the actual action ID at its sole production call site. The publication scope validates current actor identity, actual destination position, selected native cells and the real terrain edge, and is removed in `finally`. It never substitutes a turn actor for a different moving actor.

Only target_code5 uses these attested participants. The `GetTeamId("triggeringTarget")` provider may obtain the participant's actual authoritative bcM under that exact active scope, preventing null-source sentinel−1 from turning friendly boundaries into enemy events. The native triggering runner remains absent, as do its UID, PL, caster/target fields and all unrelated getters. Outside qualified scopes the old native null-source behavior remains unchanged. Production contains no breed, spell, passive or effect reference checks.

Frozen tests include enemy1005 through actual domain movement followed by production area movement, enemy1037 through real turn advancement, owner negatives and a distinct allied player using the existing multi-player Ready fixture. Coherent21-module Steamer qualification is delegated; final readiness is pending its terminal result and the wider18-class gate.

The first complete21-module aggregate completed40 tests:39 passed and one new allied-player fixture failed before movement because it assumed actor8 immediately followed owner7. Native initiative actually selected NPC−7. The fixture now reaches actor8 through bounded real end/ACK boundaries; production is unchanged. Its focal rerun and the refreshed aggregate remain pending. All other39 methods passed, including actual enemy entry/turn damage and owner exclusions. Evidence: `steamer-complete-21-active677.log`.

## Final coherent qualification

The corrected21-module Steamer aggregate passed **40/40**, with zero errors or skips, unchanged active677 catalog and every frozen source hash matching. Evidence: `.runtime/remaining-six-refresh-20261010/steamer-complete-21-active677-corrected.log`. The distinct allied-player entry/turn exclusion now passes through native initiative order and real end/ACK boundaries. The separate generic boundary gate remains14/14 PASS. This supersedes the earlier39/40 fixture result and the historical6940 recipient gap. Broader18-class regression, client manual acceptance and deployment are separate release gates.
