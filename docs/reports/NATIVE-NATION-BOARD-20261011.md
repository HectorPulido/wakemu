# Physical native nation-selection board

Status: server-only adapter and native dispatcher integrated; focused automated verification passed10/10, including actual dispatcher execution and a fresh isolated PostgreSQL schema with migrations1–142; deployment and graphical acceptance pending. No client change, new command, schema migration, government office or reward is introduced.

The installed catalog contains one `NationSelectionBoard`: object20158, map527, position(90,0,5). Original class `bCX` exposes only `QT.READ`28. Its action registers `bDa`, which waits for server14006 (`cyB`) and installs the original `ddw` chooser. The common `bEG.b(QT)` producer sends `cpF`12870 with the real object identity and action. The existing12463 enrollment handler remains responsible for citizenship persistence.

## Independent original-client evidence

Read-only installed-JAR inspection establishes `bCX.b(QT,Rd)` → `bDa` →14006 and `bEG.b(QT)` → `cpF`. Running a fresh original `cpF` with object20158 and `QT.bjV` produced:

```text
opcode=12870 action=28
framed=000000130332460000000000004ebe001c0000
body=0000000000004ebe001c0000
```

The twelve-byte body is `>qHH`: identity20158, action28, zero parameter. A second independent oracle fed the actual100-byte server chooser body into the original `cyB.dp`: opcode14006, parsed=true, four native rows. Private reproduction sources and bytecode are under `.runtime/environment-interactions-20261011/board-oracle/`, `nation-board.javap.txt`, `interactive-bEG.javap.txt` and `interactive-Nm.javap.txt`. These runs do not launch or modify the game client.

## Server authority

`server/wakfu_server/maps/nation_board.py` resolves the installed object in the current scene, rejects every other action/parameter, private instance and non-finite position, and applies the existing environment range policy: Manhattan distance at most4 and height difference at most1. That range is explicit server policy, not a reconstruction of native approach geometry.

One transaction locks the selected session and owned character, excludes durable active/placement combat, checks current stored citizenship and level, and builds the existing14006 chooser from current populations. The caller additionally supplies live occupation/combat exclusion. Repeated browsing cannot enroll, charge, grant an office or award anything; citizenship still changes only through12463.

Dispatcher integration must consume any request identifying this installed board, including rejected actions, rather than forwarding a rejected board action to unrelated generic handlers. Native loader/state publication stays unchanged.

## Complete manual acceptance segment

After deployment, use a neutral character and enter `/l !tp 527 90 1 4` in the existing local test console. This exact native walkable approach has bidirectional edges to(89,1,4) and(91,1,4), one cardinal step and one height unit from the board. The board position(90,0,5) itself is not a walkable destination. Right-click the native nation-selection board. Choose its read action. The existing four-nation chooser should open without entering a command. Close and reopen it: citizenship and inventory should remain unchanged. Select a nation: the existing12463 enrollment flow should persist citizenship through reconnect. A character already enrolled must not reopen enrollment; using the board while fighting or too far away must not open the chooser. Test the surrounding ordinary stools, lights and transport interactions afterward to confirm board routing does not intercept other object types.

Focused gate: `PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest -v test_nation_board`, with the standard read-only runtime catalog DSN, isolated PostgreSQL test DSN, password-file environment and `WAKFU_MIGRATIONS_TEST_DIR=server/migrations`. Result:10/10 passed (seven helper/catalog tests, two actual-dispatcher AST regressions and one real PostgreSQL integration test), with a fresh schema migrated through142. The dispatcher tests prove valid14006 delivery, rejected action consumption and unrelated interactive fallback. PostgreSQL proves selected-session renewal, durable combat exclusion, current stored citizenship, population read, private-scene and proximity rejection. Private result: `.runtime/environment-interactions-20261011/board-oracle/qualification.log`. Deployment and rendered GUI acceptance remain unverified.
