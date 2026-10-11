# Progressive native family branch encounters — V4, 2026-10-10

V4 supersedes the flat encounter compositions of branch V2/V3 for the new progression requirement. Those reports and configurations remain unchanged as historical evidence. All 14 branch candidates (36 combat stages) now have strictly increasing composition threat, valid six-player formations, and full native gate/exit traversal proofs. No activation or runtime writes were performed.

## Progression and roles

The deterministic progression proxy is `sum(monster count × actual spawn level)`. Runtime uses the native minimum grade for these configurations, so the proxy describes the levels actually spawned, not display-only maximum levels. Increasing this proxy does not certify boss mechanics, damage output or exact official difficulty.

Two-stage layouts generally use 4 then 8 enemies; three-stage layouts use 3, 6 then 8; Larventura uses 2, 4, 6 then 8. Mekafábrica has room capacity for one enemy per stage and instead progresses native levels 158 → 160 → 173. All identified bosses occur once and only in the final encounter.

For generated main-route family encounters, native role metadata is required for every eligible actor. Dominants, archmonsters and unknown roles are excluded from that generated pool; this does not prohibit documented native optional archmonster encounters. Unrelated guest bosses 5418, 5305 and 5416 are also excluded from their corresponding pools. Display names are not the role authority.

| Dungeon | Enemies per stage | Native-level threat per stage |
| --- | --- | --- |
| Blópera | 4 → 8 | 576 → 1181 |
| Base del Susurro | 3 → 6 → 8 | 298 → 596 → 826 |
| Mazmorra Abráknida | 3 → 6 → 8 | 384 → 774 → 1061 |
| Mazmorra iBúho | 4 → 8 | 636 → 1301 |
| Mazmorra de Anutropía | 4 → 8 | 576 → 1183 |
| Mazmorra Ferocirraptores | 4 → 8 | 936 → 1901 |
| Mazmorra Pezgajosos Abisales | 3 → 6 → 8 | 654 → 1314 → 1781 |
| Mazmorra de los Idos | 4 → 8 | 876 → 1781 |
| Mazmorra Tripulación del Pulpo | 4 → 8 | 156 → 341 |
| Patapinxería | 4 → 8 | 636 → 1301 |
| Larventura | 2 → 4 → 6 → 8 | 16 → 32 → 48 → 79 |
| Miasmausoleo | 3 → 6 → 8 | 249 → 504 → 701 |
| Campos Hupremos | 3 → 6 → 8 | 118 → 246 → 344 |
| Mekafábrica | 1 → 1 → 1 | 158 → 160 → 173 |

## Simplified final arenas remain separate

The fallback configurations for Necromundo, Guarida de los Supervillanos, Riktus de Élite and El Hammalmejil are not equivalent to completed multiroom progression. They must remain labelled as simplified final arenas until intermediate encounters are implemented and validated.

Necromundo and Supervillanos have only boss actors in their extracted dungeon pools; filling earlier stages would require additional evidenced ordinary family references, not repeating the final bosses. Riktus de Élite and El Hammalmejil lack a proved directed mandatory-gate frontier even after parallel gate bundling; assigning separate physical stages would currently allow progression bypasses or require a different supported local controller. These limitations are independent of final-arena playability.

## Validation

27 focused tests passed across branch spine, exact remaining scope, family progression and native role evidence. Every V4 candidate passed existing six-player formation and full exploration sequence validators. Independent PostgreSQL lifecycle results are recorded separately.

```sh
PYTHONPATH=server:server/tests python3 -m unittest test_native_branch_spine test_remaining_dungeon_geometry_audit test_dungeon_family_progression test_dungeon_family_boss_evidence
```

Frozen report: `PROGRESSIVE-FAMILY-BRANCH-CANDIDATES-V4-20261010.json`, SHA-256 `5b23d7e6dfdba1b101eeb3ebbe88718855217668d0527183cbe00db72612fc02`.
