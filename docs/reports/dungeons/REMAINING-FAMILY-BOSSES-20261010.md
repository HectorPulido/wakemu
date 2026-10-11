# Remaining classic dungeon boss and family evidence

Scope: 72 inactive definitions at the frozen 47-flow baseline: 70 remaining distinct ordinary classic names and two inactive level variants of the already active Mineral Tower. Ultimate bosses, Neo, arcade and rifts are excluded.

The machine-readable companion JSON resolves all 72 boss identities: 71 from installed native dungeon membership and one from an independently checked online family matched exactly to installed monster names. This does not certify official room counts, layouts, boss AI, spells or mechanics. User-authorized local family rosters may approximate counts and sequence; they must reserve every identified boss for the final encounter.

## Reusable extraction

`server/tools/extract_dungeon_family_bosses.py` reads native monster world-property array `raw_visual_arrays.csc`. Property 43 is `BOSS`, as already documented in the native combat reflection investigation. It never assumes the final reference, largest reference, highest level or a boss-sounding name identifies the boss.

Native `raw_cno` dungeon membership is the starting pool. With multiple flagged boss families, ordinary members identify the principal family and unrelated optional guest bosses are excluded. A single flagged boss is retained even if its family differs from ordinary members: Nox and Bilby Queen legitimately require this. Multiple bosses within the selected family are preserved.

The exact monster snapshot SHA-256 is recorded in every JSON row. It is an existing read-only installed-client export; no client assets were modified.

## Important corrections

- Dragoeuf: final boss 4400 Ancient Egg, not guest Aguabrial 5165.
- Blérox: final boss 4318, not guest Aguabrial 5165.
- Égarés and Ravageurs: final bosses 5295 and 5301; guest Anathar 5305 excluded.
- Marteaux, Morts-Brûlés, Poisseux, Steamers and Pulpe: final bosses 5388, 5382, 5394, 5400 and 5376; guest Cire Momore references excluded.
- Scarrière: actual BOSS-tagged actor is 4913, despite 4909's misleading Spanish name Escaraboss.
- Miss Moches: all four BOSS-tagged actors 5445–5448 are required in the final encounter; alternate Leila 5481 is not another boss.
- Super-Vilains: all four actors 2708, 2709, 2710 and 2714 are BOSS-tagged.
- Vignoble Ignoble: 4060 and 4061 are both BOSS-tagged and retained.

## Empty native pool fallback: Théâtre intemporel

The installed dungeon202 pool is empty. [The MethodWakfu database](https://db.methodwakfu.com/dungeons/202), checked 2026-10-10, explicitly names Nox as boss and Tartufo, Frisco and Marama as ordinary family members. Exact installed names identify Tartufo5717, Frisco5716 and Marama5715, all family1150. Nox5718 is the unique same-family Nox with native BOSS43. This provides a reproducible family fallback without selecting one of the unrelated Nox variants by guesswork.

Additional online boss-label confirmations are attached to rows161,186,187,179,129,126,143 and150. These third-party pages support identity; they are not authoritative server spawn registries.

## Validation

`PYTHONPATH=server python3 -m unittest server/tests/test_dungeon_family_boss_evidence.py`: five tests passed. They cover guest-boss exclusion, legitimate cross-family singleton bosses, intentional multi-boss encounters, empty-pool failure and rejection of highest-reference guessing. Activation and geometry validation belong to the separate preparation pipeline.
