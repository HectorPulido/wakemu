# Progressive native-family transport candidates, version 5

This source-only batch supersedes the roster proposals in `FAMILY-TRANSPORT-CANDIDATES-20261010.json`. No runtime activation or deployment was performed. Native route, terrain, literal transport endpoints, placement and exit proofs remain unchanged. New artifacts are isolated under `.runtime/local/family-transport-progressive-v2-20261010/` and configuration version 5.

The native-role gate excludes ARCH_MONSTER (property 45), DOMINANT_NPC (115), missing/malformed role evidence, and unselected bosses. Selected BOSS (43) actors occur once each and only in the final encounter. This includes both bosses of Vid Vil.

For each multistage candidate, the composition helper enforces strictly increasing `sum(count * actual_spawn_level)`, using the verified native-minimum spawn-level policy. This is a deterministic progression proxy, not proof that boss mechanics produce a harder fight.

| Candidate | Stage threat values | Geometry status |
|---|---|---|
| Castillo de Wagnar | 255 → 510 → 702 | Three native classic transport stages |
| Pastos de los Jalatós | 12 → 44 → 87 | Three native classic transport stages |
| Vid Vil | 402 → 810 → 1099 | Three local native-spine stages; both final bosses |
| Palacio Zollo | 516 → 1063 | Two local native-spine stages; proved backward return to entry exit |
| Topera Oculta | 1061 | Collapsed single local arena; no multiroom progression claim |
| Milubo | 581 | Collapsed single local arena; no multiroom progression claim |
| Kokolost Island | 461 | Collapsed single local arena; no multiroom progression claim |
| Cono de Crújian Jerry | 939 | Collapsed single local arena; no multiroom progression claim |
| Necrópelis de Morbax | 711 | Collapsed single local arena; no multiroom progression claim |

The five collapsed arenas must not be counted as implementing their original native multiroom definition. Their optional internal transports have no reachable source approach in the selected entry component. They are retained as explicit playable local fallbacks, with their actual family boss in the sole encounter. Implementing the full intended stage structure remains unresolved.

Six blockers are unchanged and individually documented in `FAMILY-TRANSPORT-PREPARATION-20261010.md`: Factor Trool, Steamers, Astrolillo, Balinería, Montaña Conohos and Escarantera.

Validation: `PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest test_family_transport_preparation test_physical_candidate_exits` passed 13 tests. The artifact regression independently verifies all nine configuration versions, every included native role, strict multistage threat increases and explicit identification of five single-arena collapses. All nine placement/sequence gates passed again during regeneration. PostgreSQL lifecycle acceptance and root activation review remain separate gates.
