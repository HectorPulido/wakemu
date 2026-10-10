# AI transport and complete-context audit — 2026-10-10

Scope: world bridge, context inventory, HTTP framing, content-addressed receiver, native graph parts, cancellation and session lifetime. This audit does not weaken complete-state validation, omit catalogue entries, or change spell semantics. Findings distinguish captured production evidence from offline risk demonstrations.

## Captured incident and priority

The 02:10 incident analysis from `live_slow_combat` identifies fight 150 repertoire metadata encoding consuming approximately **15.55 seconds of CPU**. Network exchange total was approximately **357 ms**, seven requests and **3.67 MB sent**. Network waiting does not explain this incident. Inclusive metrics must not be summed as independent costs. The private aggregate is `.runtime/local/diagnostics/slow-combat-20261010-0710/aggregate-post-r68.json`; consult the live incident report for exact timestamps and request identities.

The largest inspected individual casting record was approximately 120 KB and class definition approximately 24 KB. These figures do not prove the aggregate authority graph is small, nor establish why metadata encoding is expensive. The native-context owner is investigating traversal and retained graph state. No production replay or restart was performed by this audit agent.

## Findings

| Priority | Finding | Evidence and qualification | Location |
| --- | --- | --- | --- |
| P1, addressed in this audit | Parts identity traversal can exceed a cooperative deadline within a single huge node/run. | `_unpack` expanded one run with an unchecked inner comprehension; `_terrain_ids` traversed aliases/primitive children without checks; `_remap` copied large item lists before checking. Deterministic clock tests demonstrate cancellation during those loops. This is a confirmed implementation gap, **not** the proven fight-150 hot stack. | `context/native_graph_parts.py`: `_checked`, `_unpack`, `_terrain_ids`, `_remap`, `read_parts`, `partition`, `restore` |
| P1, residual | Whole-object JSON conversion and parsing have only checks before/after native work; receiver decompression is whole-object. | Source inspection plus offline measurements below. A large JSON node may monopolize Python execution until encoding returns. No claim that JSON alone caused 15.55 seconds. | `bridge/world_bridge.py`: `_json_bytes`, `ContextTransport.request`, `instance`, `instance_bytes`; `context/context_store.py`: `json`; `context/native_graph_parts.py`: `_bytes`, `_verified_blob` |
| P2, residual | HTTP frame bound does not bound decoded context memory or retained disk. | HTTP rejects request bodies over 4 MiB, but block uploads intentionally allow complete objects spanning frames; gzip decompression and `json.loads` materialize full decoded context. `ContextStore` has no total object/disk quota; sealed manifests remain until store close. Bounded graph cache uses 32 entries, not bytes. This is a capacity exposure, not evidence of current exhaustion. | `http/server.py:15,188`; `context/context_store.py:111,219,427`; `context/native_graph_parts.py:39` |
| P2, residual | Receiver storage/seal work lacks an owner deadline outside `/v3/decide`. | HTTP context endpoints share the decision semaphore but run `context_request` without a `bounded` owner scope. Client timeout closes its socket, which does not cancel server hashing/sealing. Other requests can consequently encounter capacity pressure during a cold catalogue. | `http/server.py:208`; `context/context_store.py`: `has`, `_capture_manifest`, `seal_manifest` |
| P2, conditional | Inventory scans serialize and remain complete/fresh. | `_inventory_condition` shares only a not-yet-started batch, while later arrivals queue a fresh complete scan. Waiting checks deadlines every at most 50 ms. This is deliberate correctness, not safe to replace with a stale global manifest. Prior incidents had path-sort CPU; latest known scan was short. | `bridge/world_bridge.py:213,340` |
| P2, conditional | Per-session and per-digest locking still has cold-work contention. | Query registry lock is short and independent sessions have separate locks; catalogue seal has one lock per digest. Context read verifies exact bytes, so removing its checksum without a verified immutable snapshot would weaken authority guarantees. Global fragment cache lock is held only around cache bookkeeping. | `planning/query_sessions.py`; `context/context_store.py`: `_publication_lock`, `seal_manifest`; `context/native_graph_parts.py`: `_verified_blob` |
| P3 | Retry and framing copies are finite but add work. | Three immediate HTTP retries are bounded by the active owner deadline. Each 1 MiB block expands to base64 then JSON; persistent HTTP collects chunks and joins a second response buffer. Responses have no explicit byte ceiling. Default persistent transport has an absolute timer; optional nonpersistent transport uses socket timeout alone. | `bridge/world_bridge.py:631,745,757` |

## Offline serialization measurements

Local Python 3.12, synthetic complete graph with one list node holding integer primitive wrappers, three uninstrumented runs per size. This is not the live runtime graph and does not imply production speedups.

| Primitive entries | JSON bytes | gzip bytes | JSON encode milliseconds, observed range | gzip level 1 milliseconds, observed range |
| --- | ---: | ---: | ---: | ---: |
| 10,000 | 148,978 | 24,573 | 1.90–2.28 | 0.37–0.44 |
| 100,000 | 1,588,978 | 248,195 | 19.32–21.67 | 4.57–4.89 |
| 1,000,000 | 16,888,978 | 2,486,862 | 191.33–213.02 | 46.63–48.86 |

Separate tracemalloc runs measured additional peak allocations of approximately 0.45 MB, 3.18 MB and 33.78 MB for encoding/compression, excluding the already allocated input graph. Tracemalloc greatly increases runtime (million-entry JSON 3.67 s), so those timings must not be compared with the uninstrumented table. A legal multi-frame compressed object can decode substantially larger than one HTTP frame.

## Implemented bounded traversal

Added `_checked` that checks the active deadline at loop admission, every 1,024 visited values, and completion. Applied it to identity runs, expansion within runs, terrain references, ownership/alias loops, remapping and materialization. `_remap` preserves original field order and complete contents, and avoids an initial unchecked copy of its large `items` list. Hashes, identity mappings and alias conflict validation remain intact.

New `test_native_graph_parts_deadline.py` covers single-run expansion, pack traversal, single-node remapping, terrain alias traversal, and complete identity roundtrip parity. Existing graph-parts byte-for-byte tests exposed an initial field-order mistake; it was corrected before delivery. Luna owns the final focused regression run. No production deployment by this agent.

## Proposed follow-up validation

1. Capture per-stage wall/CPU/allocated bytes for live graph encode, gzip, receiver decompress, JSON parse, graph validate, catalogue seal and plain projection. Record node count, primitive/reference visits and decoded bytes alongside compressed bytes.
2. Exercise a cold catalogue simultaneously in two independent encounters; verify independent sessions proceed and publication/seal waits remain bounded without missing any required asset.
3. Use a cooperative cancelled owner during a large legitimate dynamic row and large fragment; ensure no partial graph/session becomes visible. Whole-object dynamic `deepcopy`, JSON and gzip remain limitations and require separate bounded implementations or isolation.
4. Run concurrent complete-context transfer and cancellation at configured semaphore capacity. Cancellation should remain responsive; consider a small separate control admission budget only after measurement.
5. Measure retained CAS/sealed snapshot/cache bytes over an hour. Introduce lifecycle cleanup only with reference-safe retention; never truncate a context to satisfy an arbitrary payload cap.
6. Compare persistent versus nonpersistent transport only offline. Persistent is already default; connection reuse is not a proposed fix for the captured 15.55-second CPU event.
