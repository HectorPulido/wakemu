# Feca complete manual acceptance battery

Run after the complete shared server checkout has passed its automated gate and
been deployed by the responsible agent. This document is a test plan, not a
claim of graphical acceptance.

## Preparation

1. Use a Feca and an allied player in the same group. Outside combat, enter
   `!nivel 200` on the Feca to unlock the available active/passive choices.
2. Save the original build. Rotate the following spells and passives through
   legal decks between fights. Start with no optional Feca passive, then add
   each optional passive separately before testing combinations.
3. Start a PvP fight first, then PvM with at least two enemies, then two
   consecutive dungeon rooms. Record combat ID/time and before/after resources,
   HP, armor, states and exact caster/recipient for every unexpected outcome.

## All owned active spells

| Branch | Spells |
|---|---|
| Fire | Fecalistófedes6967, Meteorito6968, Ataque Natural6969, Magma6970, Volcán6971 |
| Water | Gota6972, Onda6973, Avalancha6974, Tormenta6975, Filo Abisal6976 |
| Earth | Golpe Telúrico6977, Orbe Defensivo6978, Bastión6979, Muralla6980, Bastón6981 |
| Utility | Inmune6982, Tregua6983, Pacificación6984, Provocación6985, Égida6986, Magnetismo6987 |

For each action, use each self/allied/enemy/empty-cell branch allowed by its
current tooltip. Compare normal and critical amounts with mastery/resistance;
confirm resources are charged exactly once and invalid casts change nothing.
Test range, LOS, occupied cells, dead recipients, recast limits and turn limits.

## Shields, protection and retaliation

1. Apply each armor/protection to self and an ally where legal. Check the exact
   initial amount and buff characteristics, then receive melee and ranged hits.
2. Confirm armor absorption before HP loss, correct attacker/victim animation,
   protection duration and expected restrictions while protected. Repeat with
   an amount smaller than the incoming hit and with a potentially lethal hit.
3. Reapply to the same target, apply to another target and let the effect expire.
   No characteristic, armor, immunity or retaliation may remain unintentionally.
4. Test Inmune, Tregua, Pacificación and Provocación against their actual native
   conditions. Inspect the tooltip rather than assuming they share durations,
   target restrictions or damage policies.

## Glyphs, Égida and temporary actions

1. Create each available glyph on a free cell. Check its displayed footprint.
2. Enter it, move inside it, leave it and start a turn inside it with the Feca,
   an ally and an enemy. Only permitted recipients should receive its effect.
3. Overlap glyphs, create a replacement, destroy/remove an owned area where
   possible and let its native lifetime end. Charges and per-turn guards must
   prevent unintended repeated application. Old areas must release their cells.
4. Use Égida and Magnetismo against their permitted actors/areas and check
   movement, direction, LOS and final registered position. No ghost obstacle
   may remain after removal or combat end.
5. Check naturally granted Armadura de la Paz7009 and Teletransportación7052
   when their actual native prerequisite is met. Confirm appearance, costs,
   restrictions and removal; never manually add these actions to fake a grant.

## Every optional passive

Rotate6988 through7005 independently. Test the actual tooltip branch, including
its positive condition and the nearest negative condition. Then combine glyph
modifiers, shield modifiers and protection/retaliation modifiers. Check spell
costs, shapes, duration, maximum targets and characteristic cleanup numerically.
Source installation alone does not establish passive acceptance.

## Shared combat lifecycle

Play with the allied character in the same fight, including the first turn.
Check each player's own action book and legal movement. Kill multiple enemies,
attack or create an area behind the former corpse, disconnect/reconnect once,
win one fight and surrender another. Both clients must leave combat cleanly;
party swords, action ownership and dungeon progression must clear together.
Repeat a baseline Cra/Iop fight after any shared combat correction.
