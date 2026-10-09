# Reference session events

`events.jsonl` is the original sniffer event stream from the reference session, moved out of the ignored local runtime directory. It is historical captured evidence, not a synthetic fixture.

This file is not the `decoded/frames.jsonl` currently required by the world server. Moving events does not remove that startup dependency.

The existing local capture directory has a relative symlink to this file so directory-based analysis tools continue to work; that symlink remains private under `.runtime/` and is not required to read this file directly.
