# Native AI Graph Deadline Audit — 2026-10-10

## Finding

The native graph encoder previously checked the owner-thread deadline mainly when it allocated graph nodes. Large arrays of primitive values or repeated references can traverse many entries without allocating nodes. `encode` and `encode_bytes` now count every visit and check the active deadline every 256 visits. `NativeGraph` validation and plain projection count primitive and reference visits as well, and native graph parts bounds its long identity, alias, and remapping traversals.

The checks preserve graph data: differential tests compare the complete encoded forms, including aliases and cycles, while deadline tests verify expiration during primitive-heavy and memo-hit-heavy traversals.

## Validation

The final focused validation passed 130 tests with no skips or failures:

| Suite | Passed |
| --- | ---: |
| Native fingerprint | 8 |
| Native context encoder and graph validation | 18 |
| Graph traversal deadline regressions | 5 |
| Native graph parts | 20 |
| Graph-parts deadline regressions | 5 |
| Native turn | 15 |
| Bridge context and transport | 26 |
| Native session, using read-only runtime catalog access | 14 |
| GC pause monitor | 4 |
| Performance acceptance monitor | 15 |

The primitive sequence and alias-sequence deadline regressions exercise both `encode` and `encode_bytes` with 100,000 entries. Additional checks cover a single-node graph with 100,000 references, graph-parts projection, canonical field ordering, alias identity, and encoded graph parity.

Logs are retained under `.runtime/local/diagnostics/ai-final-*.log`, `.runtime/local/diagnostics/ai-deadline-final2-*.log`, `.runtime/local/diagnostics/ai-gc-pause-monitor.log`, and `.runtime/local/diagnostics/ai-performance-acceptance.log`.

## Remaining limit

`NativeGraph` checks references while traversing object fields, but its preliminary validation of field-name types uses a small `all(...)` pass over the field dictionary before that traversal. This scan remains uninterruptible; it is expected to be short for ordinary object schemas and was left unchanged in this audit. Large serialized field values still pass through the counted reference checks.

No runtime services were restarted and no runtime database mutations were performed.
