# Contributing

[Wiki home](README.md) · Related: [Limitations](limitations.md)

Small, reproducible improvements are welcome. Start with a system you can run and describe what you expected, what happened, and how another person can reproduce it.

## Where changes belong

| Area | Main location |
| --- | --- |
| Protocol routing and integration | `server/local_game_server.py` |
| Game rules | `server/wakfu_server/` domain folders |
| Database changes | `server/migrations/` |
| Regression tests | `server/tests/` |
| Tactical planning | `server/ai-service/wakfu_ai/` |
| Client launch and diagnostics | `client-tools/` |
| Protocol investigation tools | `sniffer/` |
| Readable documentation | `docs/` |

Prefer general rules over fixes tied to one map, monster, or spell. Combat additions should reuse effect, condition, state, and trigger primitives where possible. Keep binary layouts explicit and preserve existing combat and spell behavior.

Applied migrations have recorded checksums. Add a forward migration instead of rewriting one already used by a database. Keep unrelated formatting and refactors out of focused fixes.

## Verify a change

Install Python dependencies in an isolated environment and run the relevant regression tests:

```sh
python3 -m venv .runtime/wiki-venv
.runtime/wiki-venv/bin/pip install -r server/requirements.txt
PYTHONPATH=server .runtime/wiki-venv/bin/python -m unittest discover -s server/tests
```

The complete suite includes database integration and private research dependencies; a fresh clone may not run every test. Report the exact command, passes, failures, skips, and missing prerequisites. Never point destructive integration tests at the gameplay database.

For visible gameplay, also provide one complete manual journey: setup, exact actions or commands, expected results, and reconnect checks. Automated tests and graphical acceptance establish different things.

## Share responsibly

Contribute original code and synthetic tests. Keep client files, credentials, personal databases, captures, and generated logs out of contributions. Summarize protocol evidence without publishing private sessions.

A good contribution explains the problem, resulting behavior, relevant limits, and verification. See the [project README](../README.md) for the experiment's purpose and third-party notice.
