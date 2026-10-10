# Fight 117: slow first arena preparation

The user reported one attack click followed by a long delay. The server recorded
one start request (`95b1462d8c2047c09b8b213899892a8f`) for fight 117 on map 1134,
from 23:55:39.568 to 23:56:03.620 UTC on the r59 boot.

| Stage | Elapsed ms | Calling-thread CPU ms |
| --- | ---: | ---: |
| Select group | 10.525 | 1.593 |
| Select/prepare arena | 22,351.097 | 22,225.255 |
| Build resources | 10.393 | 4.367 |
| Freeze durable placement | 73.887 | 35.582 |
| Create placement | 5.347 | 5.346 |
| Initialize actor snapshots | 5.251 | 5.243 |
| Prepare forced terrain | 491.164 | 422.570 |
| Queue combat checkpoint | 7.870 | Not separately recorded |
| Complete request | 24,052.076 | Not separately recorded |

Continuous capture `capture-1791590110936738129` overlaps the entire request.
There are 497 arena-related samples whose leaf is the generator at
`combat_qi_surfaces.py:69`, inside the full native surface constructor. This
validates each surface's signed type/range while loading the first map surface
catalog. It is not evidence of repeated clicks or a checkpoint bottleneck.
The measured stage CPU independently confirms substantial work during arena
preparation; sample weights alone do not establish exclusive CPU durations.

`native_qi_surfaces` caches eight validated map catalogs. A cold load reads and
hash-verifies the published map, decodes JSON and validates/builds every native
surface before selecting the small encounter mask. Subsequent encounters on a
cached map may be faster; this does not close first-entry latency or cache
eviction behavior. The general cold-map path is under investigation. Native
provenance, malformed-data rejection, chunk priority, ordered surface indices
and exact placement topology must remain intact in any optimization.

Request logs and the overlapping raw profile are preserved privately under
`.runtime/local/diagnostics/fight117-entry/`. No fix or deployment is claimed by
this incident record.
