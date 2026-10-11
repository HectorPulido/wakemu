# Original observed dialogue choice edges

A new bounded capture join recovers29 exact dialogue edges, not29 new NPCs. The
previous initial-scene audit linked outgoing13222 to incoming12969; it did not
export outgoing12058 choices and incoming12218 continuation nodes.

The original creation capture contains15 initial opens,36 choice requests and
35 continuation responses. Each response was joined FIFO to an outstanding
choice inside its original speaker/root session. Every choice exists in the
installed native node, and every nonzero target exists in the installed native
node catalog. Repeated requests/responses remain separate observations, then
collapse only when the complete speaker/root/node/choice/target agrees. There
are zero conflicting targets. One duplicate Huly terminal request has no
response before the next open and is retained as unmatched rather than invented.
No outgoing12535 initial request is present in this source.

Source SHA256: `eedbfd7561e0ae53398bab0eddd26bfac674fb77953d537cea4dbbecd9c4cd69`.
Private reproducible tool/ledger:
`.runtime/local/npc-protector-frontier/recover_observed_choice_edges.py` and
`original-observed-choice-edges.json`.

| Original speaker | Initial roots | Distinct edges | Nonzero targets | Zero-target responses |
| --- | --- | ---: | ---: | ---: |
|Huly, actor-1706442046308322|5765|7|6|1|
|Otomai, PROTECTOR424|5772|3|2|1|
|Kheperalia, actor-1706442046308328|5782,5762|6|3|3|
|Airyna, actor-1706442046308339|5755,5787|10|1|9|
|Grugal, actor-1706442035962340|5764|3|2|1|
|Total|7 observed roots across5 speakers|29|14|15|

## Concrete recovered branches

Otomai now has the exact original sequence:

```text
5772 / choice13288 ->5773 (frames1615→1619 and1620→1621)
5773 / choice13289 ->5774 (frames1625→1626)
5774 / choice13290 ->0    (frames1629→1635)
```

Huly has5765→5766→5767→5768→5769→5783→5770→0 with the
choice IDs preserved in the ledger. Kheperalia's staged initial5782 reaches5786;
Airyna's staged initial5755 reaches5756. Grugal's5764 reaches5790 and5791 after
a choice requiring real level6. Additional observed roots5762 and5787 reflect
later story contexts and are not substitutes for the staged initial roots.

## Implementation before recovery and boundaries

Before this integration, `npc_world.begin` created only root-choice→None edges; every
unconditional choice closed locally. Thus Otomai13288, Huly13275, Kheperalia13305
and Airyna13258 omitted original next-node responses despite their exact
native evidence. Its speaker guard also required every later node to equal the
initial root, preventing continuation even if a graph were supplied.

The initial-scene adapter is explicitly local and does not reconstruct original
quest execution. Captured edge evidence certifies display transitions only;
quest progress, side effects, item rewards and story visibility remain separate
contracts. Native node and choice criteria must remain authoritative and fail
closed where unsupported. Specific later branches require IsAchievementRunning,
owned objective flags and GetRealLevel; this report does not bypass them.

A narrow general integration can import exact capture edges for the already
qualified actor/speaker/root identity and source hash, retain later initial roots
as inventory only, revalidate the same current actor/scene/range and original
action/root criteria, and follow only supported native node/choice criteria.
Unobserved choices must not acquire inferred transitions. Explicit original
zero-target responses can be reproduced separately from the existing local
None-close behavior. No new NPC position or initial binding follows from these
continuation edges.

## Narrow general integration

`npc_observed_dialogue.py` imports the deterministic
`protocol/npc-observed-dialogue-edges.json.gz` ledger. Selection requires an
authorized captured placement, the exact original capture SHA256, native speaker
kind/identity and configured initial root. Only reachable edges of that selected
root are admitted. Conflicting edges, unknown targets and missing native choices
fail closed; disconnected observations cannot authorize arbitrary later nodes.

The five staged initial roots select17 of the29 observed edges. The remaining12
belong to later Kheperalia/Airyna story roots and stay inventory evidence without
a new initial-root activation. `npc_world.begin` retains the original owned
action/root criteria throughout the same speaker/scene/range session and checks
native target-node and choice criteria before proceeding. Unobserved
unconditional initial choices retain their explicit local None-close behavior;
captured target0 emits the exact native12218 four-byte zero response.

The only additional criterion is exact `GetRealLevel("caster") >= N`, needed
for the captured Grugal branch. The native `eLc/eQb73` contract already
establishes `biB.drm` as progression level, distinct from selected-build `cmZ`.
The existing server dungeon criterion and reward-context adapters likewise use
owned `character.level` for real progression authority. This narrow NPC atom
requires a strict integer in1–200 and never substitutes `effective_level`;
missing/malformed levels, other selectors and unsupported achievement-running
criteria still fail closed. This permits all17 observed edges of the five
already-qualified initial scenes, without activating later story roots.

Focused tests cover all five complete paths with exact response bytes, capture
source/speaker/root fences, disconnected and conflicting edges, missing targets,
mid-tree objective/range revocation, real versus effective level and replay after
terminal closure. The SQL integration fixture persists real level6 before its
baseline, loads all five current original scenes and owned objective facts, then
asserts character/progression/wallet/facts/items remain unchanged across every
continuation. Independent Luna qualification of the final source passed39/39 pure tests and7/7 isolated PostgreSQL tests, with all five speaker paths and17 activated edges executed. Source fingerprints stayed unchanged; temporary SQL schemas returned8→8. Evidence: `.runtime/local/npc-observed-dialogue-level6-validation/`.

No database migration or additional NPC spawn is introduced. The root owns the
complete-image protocol COPY; source implementation is not a deployment claim.
