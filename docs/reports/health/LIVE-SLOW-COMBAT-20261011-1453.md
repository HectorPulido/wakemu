# Fight187 latency investigation

Status: reproduced in existing server telemetry; not fixed or release-qualified.

User report: October11 approximately14:53 America/Bogota (19:53UTC).
Fight187, map527, actor10. Running World image begins `ed508b166abd`.

## Entry

Request `ea038faf4a514faab0764479555bf858` started19:50:57.554UTC and completed19:51:16.740UTC:19,185.676ms.

| Phase | Wall milliseconds | Thread CPU milliseconds |
| --- | ---: | ---: |
| Arena geometry | 9,014.147 | 8,861.902 |
| Arena selection | 546.640 | 527.670 |
| Surface catalog | 522.106 | 477.578 |
| Actor snapshot initialization | 4,643.838 | 4,463.053 |
| Forced terrain prewarm | 4,152.298 | 4,064.976 |

The three largest phases account for approximately17.81seconds. Selection of arena size is not the dominant measured phase in this request. Costs are CPU-dominant; these numbers do not establish which functions inside each phase consumed that CPU.

## Spell and turn processing

Ready request took7,023.073ms. Spell4807 request `c1ae7ec306fc44b2882be698f9e4286e` completed19:52:36.186UTC in7,432.175ms; recorded preparation alone was7,403.919ms. Dispatch was1.469ms. A subsequent cast took949.918ms. Preparation needs further attribution before changing casting semantics.

Turn acknowledgements took5.67,10.20,9.85,10.96and12.57seconds. Existing native diagnostics identify AI preview execution as a major CPU cost:

| Turn | Preview wall ms | Preview thread CPU ms | HTTP ms |
| --- | ---: | ---: | ---: |
| 4 | 6,461 | 6,416 | Not extracted |
| 6 | 9,741.9 | 9,552.8 | 255.6 |
| 7 | 8,199.7 | 7,900.8 | 101.8 |

Turn6 had9previews and7failures; one preview reached approximately9,451ms. Pre/post-commit duplicate diagnostic events are not added together. Network transport is not the dominant measured cost in those turns.

## Verification and limitations

Running bootstrap explicitly reported24,488,072frozen startup objects, with cyclic GC still enabled. The prior startup heap freeze is active. Internal aggregate telemetry nevertheless reports two generation2collections, maximum16,548.959ms. Aggregate maxima lack enough incident attribution to blame either collection for this exact request.

The external sampled profiler was absent from the running Compose services; newest artifacts were from October10at21:27local. Consequently no sampled stack capture for this incident is claimed. Restore continuous recording under the shared service-operation coordination procedure.

Two concurrent offline catalog validation workers were CPU-active during inspection. Their contribution to this incident is not proven; they were not stopped. Shared runtime sources and services were left unchanged during the monster release qualification window.

Private bounded transport evidence: `.runtime/local/diagnostics/ai-transport-fight187-20261011/bounded-events.json`. Arena and transport audits continue independently; any remedy requires focused regressions and a coordinated complete shared-source deployment.
