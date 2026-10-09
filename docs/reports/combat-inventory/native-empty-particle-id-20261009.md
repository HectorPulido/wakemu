# Empty particle ID in the shared spell animation script

The fight80 client reports at local 15:45:48.642 and 15:46:43.310 identify `1040.lua:127`: `Particle.addParticleSystem` received a string where its first argument requires an integer. This is an original script sentinel mismatch, not an APS value serialized by the server cast packet.

Original `scripts.jar/1009140.lua` (spell4819, Explosive Arrow) assigns `casterApsId_1` through `_8` to the empty string in the branch without state9306. It passes these parameters to shared script1040 with `useDiags=true`, `isCasterApsOnCell=true`, and delay0. `selectAps` returns a non-null directional value unchanged. The shared `aps` helper previously skipped only nil and integer0, allowing the empty string to reach the native integer particle function. The cast packet12588 contains spell identity, level, critical/failed flags and target coordinates, but no APS ID.

`client-tools/patches/patch-empty-particle-ids.py` adds the empty string to the shared `aps` absent-ID guard. Numeric APS IDs, delayed calls, animation names and particle targeting remain unchanged. It does not coerce arbitrary strings to numbers. The patcher validates the exact native guard, preserves other archive entries, saves an original backup, and permits repeated application. Unknown source layouts fail without replacing the archive.

Apply with `python3 client-tools/patches/patch-empty-particle-ids.py client/contents/scripts/scripts.jar`. Client relaunch remains coordinated with the parent task; changing the disk archive does not prove the running client has loaded the patch.

This fixes the demonstrated native type error. It does not establish that this error caused the separate fight80 death identity, delayed timeline update or scene recovery failures.

Validation: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_client_empty_particle_ids` passed2/2 (delegated). Applied after validation: only1040.lua differs from the original archive. Exact original backup SHA256 `99fbfc7ac49e916d36846fa051e322c0c252cb51c52e5359f4b107b8dedfb2c4`; patched archive SHA256 `fd55b37304f77d2f8db202fd4147658cb2f7af960ac36a4876b1588093bb5c7b`. No client restart was performed.
