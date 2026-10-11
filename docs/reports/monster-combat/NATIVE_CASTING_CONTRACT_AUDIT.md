# Native casting contract audit

`server/tools/audit_monster_casting_contracts.py` detects one precise native contract conflict across the extracted monster inventory. It is an offline report; it neither changes casting guards nor activates monsters.

```bash
python3 server/tools/audit_monster_casting_contracts.py \
  --bundle .runtime/monster-combat-extraction-20261010 \
  --output .runtime/monster-blocker-generalization-20261010/casting-contract-audit.json
```

The audit normalizes owned spell levels using the original `bPD -> bPO` maximum-level clamp, then checks every effective level. A proven conflict requires baseline range `[0, 0]`, nonempty ordered roots, and an exact native `fcE` selector with bit128 on every root. Native `fcE.a` rejects the caster for this bit. Native `fcj.a` checks the fighter occupying the targeted cell against root selectors; range zero targets the caster, so the result is `twE`. Nearby eligible area recipients do not satisfy this separate target-cell check.

Miaumiau blanco2617, spell2794, demonstrates the issue: roots64489 and64488 use mask129 and ring1–2 areas. A genuinely wounded ally nearby does not remove the native rejection. The same unconditional pattern appears in36 monster references using19 distinct spells in the 2026-10-10 extraction.

Conditional casting tables remain `conditional_unknown`; missing selectors, unknown selector classes, and level-zero authority remain `unknown`. A native null selector or a root that does not require another ally breaks this particular proof. Unknown results do not claim the monster is broken. Partial level conflicts remain distinct from conflicts at every effective level.

Evidence is retained under `.runtime/monster-blocker-generalization-20261010/`: `self-centered-ally-selector-impact.json`, `fcj-self-centered-proof.txt`, `fcE-self-centered-proof.txt`, and caller proofs. Inspection of installed client call sites found no authoritative alternate NPC AI casting producer that bypasses the target-selector check. The audit therefore records an unresolved native casting contract; it does not invent an NPC exception or weaken player/class checks.

Validation: seven new offline unit tests cover the exact conflict, conditional tables, missing selectors, native null selectors, nonzero range, maximum-level normalization, input preservation, and separate level-zero authority. Existing tests were not edited.

Wakemu now provides a separate explicit NPC recipient preflight for selected self-centered spells, documented in [WAKEMU_NPC_AREA_PREFLIGHT.md](WAKEMU_NPC_AREA_PREFLIGHT.md). The offline audit continues reporting the original client `fcj` anchor conflict; it does not claim the new server policy was recovered from original server code. Native selectors, criteria, geometry, and common transactional handlers remain unchanged.
