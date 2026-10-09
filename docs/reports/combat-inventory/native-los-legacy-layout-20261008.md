# Remaining LOS archive decode failures

All 27 failed archives use a distinct record layout. Their 1,100 non-empty chunks (903 VO/type4 and 197 VP/type5) close exactly when each surface record occupies seven bytes. None closes with the installed reader's eight-byte layout. The 409 empty VJ/type0 chunks are unaffected. The accompanying JSON records each archive, not a per-map exception implementation.

Example map149/chunk `-1_-1` is 676 bytes. Candidate seven-byte parsing yields 16 records, 27 bitmap longs and 74 multi-surface indices, consuming exactly 676 bytes. Installed `VP.a(aoG)` consumes eight bytes per record, shifts the bitmap boundary, reads a false count of 46,509 indices and throws `BufferUnderflowException`. Original `VC.ag` selects the same VP reader; there is no compatibility branch in that installed API. This is an archive/client schema mismatch, not a LOS surface-buffer limit.

The apparent missing field is the additional `Vy.bLE` byte; that interpretation is not certified by an original legacy serializer or reader. Removing/inserting bytes based only on structural fitting would invent field provenance. No failed map was published and no clear-ray fallback was introduced. Recovery requires an authoritative original seven-byte schema (or matching client reader/archive version). The exporter now preserves the failing map, chunk, class, byte count and original exception in diagnostics, so the mismatch remains actionable.

Validation: installed original reader reproduced map149 failure directly in an offline 128 MiB JVM. The 27-archive structural census used ZIP bytes only; the 934 successful exports were not rerun. No service or database operation occurred.
