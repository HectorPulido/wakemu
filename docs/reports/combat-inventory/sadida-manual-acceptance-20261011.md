# Sadida complete manual acceptance — 2026-10-11

Prepared acceptance procedure; not a claim of manual completion. PostgreSQL and deployed World/AI/Ecology currently use catalog `bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`; the Sadida 44/44 aggregate remains historical on release677, not a bd79 rerun. The class inventory contains21 owned actives and20 class passives; use [Sadida inventory](remaining-six-refresh-20261010/sadida.md), [semantic qualification](remaining-six-refresh-20261010/sadida-semantic-qualification.md), and [passive coverage matrix](sadida-passive-coverage-matrix-20261011.md) alongside this procedure. Eight shared breed−2 passive rows in the machine export are not additional Sadida-owned choices. Run the corrected full18 gate before manual acceptance. Use one Sadida and one previously accepted Cra/Iop in the same party, then a second Sadida for ownership controls. Keep server logs correlated with the fight and character IDs.

## Preparation

1. On the Sadida, run `!nivel 200` (existing alias `!level 200`). Equip a legal build; do not grant hidden spells or class states through debug commands.
2. Use a durable legal enemy and injured allies. Existing spawn command `!mob 4 8 1` can provide an ordinary monster group where permitted. Repeat in a dungeon room with normal progression.
3. First active deck: Toxinas914, Árbol915, Lágrima de Sadida918, Viento Envenenado919, Sacrificio Muñequero920, Vaporizar921, Drenaje922, Zarza925, Hierbas Locas927, Resfriado928, Abono929, Arcilla930.
4. Second active deck: Herrumbre931, Hedor Boscoso932, Komhir934, Terremoto935, Zarzas Múltiples937, Borrasca938, Despertar Silvestre5057, Fertilizante7054, Fuerza de la Naturaleza8139, plus suitable seed-transforming spells from the first deck. Change decks outside combat.
5. Record starting AP/MP/WP, armor and every visible temporary action. Seed8137, Voodoll926 and Superpoderosa911 must come from actual innate/grant routes, never a fabricated action bar entry.

## Complete doll/seed/tree cycle

1. Cast Semilla8137 on an empty legal cell. One owned seed appears there; a rejected wall/out-of-range placement spends no partial resources and leaves no invisible blocker.
2. In separate fresh contexts, cast Zarza925, Vaporizar921, Lágrima918, Hedor932 and Arcilla930 on a real seed. Expected native profiles/books respectively:3747→5024/8138;3748→5023/8138;3749→5021/8138;3750→5026/8138;3751→5025/5356/8138. For5356, transform another real seed with Komhir934: the Enganchadora variant has the required8190 state; Arcilla930 alone does not supply it. Verify the actual client names and available actions; do not infer behavior merely from an icon.
3. Let each doll receive its actual turn. Check original-controller authority, legal movement and each available action, enemy versus injured-ally targeting, action cost and no cross-character action bar replacement.8138 is conditional on controller passive912; verify its absence/rejection without that prerequisite.
4. With an actual owned doll present, cast Superpoderosa911. Profile3746 has exactly5153/5023/5021/5026/5024/5025/5356. It must obey the native cap and prerequisites; a fresh arena with no qualifying doll is a negative control.
5. Recast Semilla8137 on its owned seed to create tree5577/state8217. Its native book is empty. Verify native tree reactions over real turns, owner/foreign-owner selection and count limits; do not add attacks to this profile.
6. Grow Reacción en Cadena3624 through genuine turns/events, check its native maximum4 and each resulting form. Test casts at the cap, replacement, different Sadida owners and a full team cap. Counts must follow the native doll/seed/tree expressions rather than a universal global summon count.
7. Kill each kind through ordinary attacks, then reuse the freed cell and summon again. No retained dead actor may block LOS, placement, turns or class counts. Repeat simultaneous area deaths and a second fight.

## Voodoll and damage/armor/healing

1. Cast La Vudul926 on a legal character target at its actual range. The native constructor places profile3745 in a free neighboring caster cell; its action8140 must belong to the original controller. Verify binding and recasting interval.
2. Use Zarza925 on the owned allied Voodoll. The automatically qualified level200 branch grants armor through300634; compare with an enemy-target control. Observe actual armor absorption and loss rather than assuming armor from a tooltip.
3. Exercise direct, area, critical and poison damage against the Voodoll and its bound target. Record both HP/armor deltas and ensure exactly one authored reaction per recipient. Check healing and owner/target death, dismissal, recast and foreign Sadida isolation.
4. Preserve disabled native branches: affiliation root164943 and lethal/armor root378558 contain literalFalse. No invented team switching or dormant transfer behavior is expected from those branches.
5. Use8140 on an actual owned doll and confirm that the Voodoll and doll exchange positions. In a separate context acquire Voodoll first, then create a tree by8137→8137; use8140 on that tree and check friendly armor without enemy armor. Test occupied destinations and protected targets without stale positions or partial AP loss.

## All active spell outcomes

Run both decks against enemy, injured ally, own doll/tree/seed and empty cell where native targeting permits. Check legal positive effect, normal/critical distinction, AP/MP/WP receipts, per-target/per-turn/interval limits and rejection rollback.

- Damage/poison:914/918/919/921/928/932/934/935/937/938. Delayed damage must follow the actual recipient/event and stop at the native lifetime; death must not animate or remove another actor.
- Healing/armor:922/925/927/929/930/931/7054. Compare self, allied player, own doll and enemy branches. Genuine healing cannot exceed its native maximum; armor must be consumed by a real incoming attack and removed/reset through its actual lifetime.
-920 Sacrificio Muñequero requires an actual owned doll excluding Voodoll counts. Confirm retirement, resource/reward and QI release exactly once.
-915 Árbol must follow its native self/target conditions and duration; test movement/control restoration.
-5057 Despertar Silvestre: let an allied character be killed by a genuine enemy attack, then cast legally. Confirm HP restoration, state6505/native penalty, QI registration, return to future turns and no duplicate actor. Check restricted/previously marked targets and native interval.
-8139 Fuerza de la Naturaleza needs genuine positive caster armor and no8224. Acquire armor through legal actions, then verify consumption/derived state and the no-armor negative control.

## All20 passive branches

Equip each passive before Ready and compare a matched no-passive encounter. Do not substitute successful initialization for the actual gameplay trigger.

| Passive | Required comparison |
|---|---|
|912 Sadida Solitario|Owned-doll/no-doll behavior, conditional8138 and clean restoration.|
|913 Guarda Plantas|Actual incoming damage/plant trigger, positive and non-qualifying recipients.|
|916 Enlace Muñequero|Actual owner/doll relation, damage/resource reaction, owner death and foreign doll.|
|917 Don Silvestre|Actual native grant/reaction and its count/lifetime.|
|933 Explomuñeca|Real doll death including simultaneous deaths; exactly once explosion and owner isolation.|
|4959 Rezo Sadida|Actual qualifying event and native resource/cap reset.|
|5055 Terreno Infectado|Owned field and poisoned recipient, boundary and removal controls.|
|5058 Murmullos Salvajes|Actual Voodoll/doll enabled branch and original-controller isolation.|
|5234 Venenoso|Genuine poison/application and later event, compared with direct damage and no passive.|
|7053 Terreno de Entendimiento|Owned-area/actor reaction and foreign-area negative control.|
|8149 Bendición Vudul|Native Voodoll target restriction and allied/enemy controls.|
|8150 Empuje Silvestre|Compare with7053 alone: first8137 creates a tree directly with8150; two legal casts create two trees, and the next creates a seed. Check actual QI footprints and count limits.|
|8151 Terreno Fértil|Keep an owned1835 seed inside the1836 tree ring (not its excluded center). On the genuine trigger, the seed receives3624 level3 and changes stage1855→1853. The recipient is the seed, not a persistent state on the owner.|
|8152 Crecimiento Acelerado|Preserve literalFalse379549; do not expect disabled form conversion. Test enabled sibling mechanics only.|
|8153 Devoción Muñequil|Actual doll event, native resource payment/refund and cap.|
|8154 Mala Semilla|Actual seed/death/replacement context and no duplicate reaction.|
|8155 Ciclo Silvestre|Actual owned doll/tree turn cycle and cleanup.|
|8156 Comunicación Vegetal|Actual authored communication/state8230, distance/team controls and expiry.|
|8157 Conocimiento Sadida|Ghulotona profile3748 action5023 changes legal range3→5 when the original controller equips this passive; compare matched no-passive and foreign-controller cases.|
|8158 Cadena de la Naturaleza|Genuine chain progression, native caps and no foreign-owner propagation.|

Exact numerical expectations must follow the final automatic semantic evidence, not invented tooltip interpretations. Any remaining unqualified branch must be recorded before acceptance.

## Shared combat stability and dungeon completion

1. Start PvP with Sadida and accepted Cra/Iop. Ready both; verify the very first actor, both action bars and movement authority. Finish normally, then surrender another encounter.
2. Run PvM with both players, all doll forms, areas and Voodoll. Reconnect one participant during a real turn, verify the complete actor roster, state/book ownership and continued turns.
3. Kill the last enemy with delayed poison or a doll reaction. Both clients leave combat, party swords clear, no disconnect occurs and the next dungeon room/group appears without reconnecting.
4. Repeat a new fight. No stale summon, area, grant, armor, class count, corpse LOS blocker or old event listener may survive incorrectly.
5. Re-run Cra beacon creation/activation/Desbalizaje and Iop combo/standard scenarios to catch shared regressions. Stop and preserve logs if either previously accepted class changes behavior.
