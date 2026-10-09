# Native owned spell level lookup

The general `GetSpellLevel(reference[, selector])` criterion now consumes the complete owned spellbook, independently of deck membership. Ordinary player snapshots share `owned_spell_records` with the `sy` inventory serializer. The actual parsed `fzf` cap is passed from `server_runtime`; native `gvc()` disables capping only for negative caps, so zero remains an actual cap.

Native proof: parser `eQd` token 75 constructs `eLo`. `eLo` uses `eGj.dok()` and `fyR.pb(reference)`: a null book or absent reference returns zero. For a PLAYER_CHARACTER with a found spell, `fzj.a` scans the complete progression inventory (`dsx`), returns minus one for missing progression authority/reference, and otherwise returns `cmZ`, capped by `fzf.tL` when applicable. Reference expressions undergo Java long-to-int wrapping.

Decode proof: `biS.zm` installs `sy.Zc` through `fyR.b(yC)`. `fyG.e(yy)` calls `cr(short)`, which caps the received level to `fyF.Fq()`. The authority mirrors this normalization using exported `maximum_level` metadata. Ordinary NPC/summon spellbooks are not inferred by this player provider.

The current wire producer sends character levels for both active and passive records. Native definitions 6271 and 6949 have maximum level 245, so decode does not convert these values to passive rank one. This criterion accurately reflects the current inventory; it does not certify the passive rank producer or its unlock behavior. Correcting that producer requires separate native evidence.

Zero-argument `GetSpellLevel()` uses a third argument that is specifically `fyG`; the existing `GetContainerLevel` provider reads an `eZR` running effect and cannot substitute for it. This branch remains explicitly unsupported.

Validation: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_spell_level test_combat_conditions test_spells`: 35 tests passed. No live service, database, or AI changes.
