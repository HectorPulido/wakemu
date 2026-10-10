# Native teleport composition candidates

Of fifteen proved native teleport chains, eleven have resolved native species and reviewed boss identities, and pass actual combat formation and native per-stage arrival/approach checks. No configurations were activated by this exporter.

Ten guide room counts differ from native region counts. Their candidate rosters use an explicit DEV native-room policy; the original guide rooms remain unaltered in `unaltered_guide_rooms`. All generated species come from the installed native definition pool, with one reviewed final boss. This is not official encounter composition.

| Dungeon | Native rooms | Candidate status | Gap |
|---|---:|---|---|
| Castillo de los Cangwejos | 4 | roster_candidate_prepared | Explicit DEV native-room adaptation |
| Mazmorra Arakna | 3 | roster_candidate_prepared | Reviewed room assignment retained |
| Mazmorra Solgazanes | 2 | manual_evidence_required | final_boss_identity_not_reviewed |
| Mazmorra Crustariscos | 2 | roster_candidate_prepared | Explicit DEV native-room adaptation |
| Mazmorra de los Cocodrails Delnilo | 3 | roster_candidate_prepared | Explicit DEV native-room adaptation |
| Mazmorra de los Trópikos | 2 | roster_candidate_prepared | Explicit DEV native-room adaptation |
| Mazmorra Gerbilinda | 3 | roster_candidate_prepared | Explicit DEV native-room adaptation |
| Mazmorra de los Güinos | 2 | roster_candidate_prepared | Explicit DEV native-room adaptation |
| Mazmorra Nievajas | 2 | manual_evidence_required | final_boss_identity_not_reviewed |
| Mazmorra Vandalienados | 2 | roster_candidate_prepared | Explicit DEV native-room adaptation |
| Torre Helada | 4 | roster_candidate_prepared | Explicit DEV native-room adaptation |
| Ratacumbas | 2 | manual_evidence_required | roster_policy_refused: Reviewed roster contains unresolved native monster identities |
| Guarida de los Magik Riktus | 3 | manual_evidence_required | roster_policy_refused: Reviewed roster contains unresolved native monster identities |
| Sliptorium | 3 | roster_candidate_prepared | Explicit DEV native-room adaptation |
| Fábrica Buhatrás | 3 | roster_candidate_prepared | Explicit DEV native-room adaptation |

Two dungeons have no reviewed boss identity; Ratacumbas and Magik Riktus retain unresolved guide species. They are withheld. No name or level inference fills these gaps.

Reproduce with `PYTHONPATH=server python server/tools/audit_dungeon_flow_compositions.py --flows docs/reports/dungeons/AUTOMATIC-TELEPORT-FLOW.json --candidates .runtime/local/native-teleport-topology-candidates --output docs/reports/dungeons/AUTOMATIC-TELEPORT-COMPOSITION-COVERAGE.json --native-room-policy --validate-placement` and catalog access.

[Structured roster and placement evidence](AUTOMATIC-TELEPORT-COMPOSITION-COVERAGE.json). Native exit binding, durable progression, reward settlement and boss mechanics are separate acceptance gates.
