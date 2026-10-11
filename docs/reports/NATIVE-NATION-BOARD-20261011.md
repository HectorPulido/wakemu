# Physical native nation-selection board

Status: server-only adapter and native dispatcher integrated; automated verification, deployment and graphical acceptance pending. No client change, new command, schema migration, government office or reward is introduced.

The installed catalog contains one `NationSelectionBoard`: object20158, map527, position(90,0,5). Original class `bCX` exposes only `QT.READ`28. Its action registers `bDa`, which waits for server14006 (`cyB`) and installs the original `ddw` chooser. The common `bEG.b(QT)` producer sends `cpF`12870 with the real object identity and action. The existing12463 enrollment handler remains responsible for citizenship persistence.

## Independent original-client evidence

Read-only installed-JAR inspection establishes `bCX.b(QT,Rd)` → `bDa` →14006 and `bEG.b(QT)` → `cpF`. Running a fresh original `cpF` with object20158 and `QT.bjV` produced:

```text
opcode=12870 action=28
framed=000000130332460000000000004ebe001c0000
body=0000000000004ebe001c0000
```

The twelve-byte body is `>qHH`: identity20158, action28, zero parameter. Private reproduction sources and bytecode are under `.runtime/environment-interactions-20261011/board-oracle/`, `nation-board.javap.txt`, `interactive-bEG.javap.txt` and `interactive-Nm.javap.txt`. These runs do not launch or modify the game client.

## Server authority

`server/wakfu_server/maps/nation_board.py` resolves the installed object in the current scene, rejects every other action/parameter, private instance and non-finite position, and applies the existing environment range policy: Manhattan distance at most4 and height difference at most1. That range is explicit server policy, not a reconstruction of native approach geometry.

One transaction locks the selected session and owned character, excludes durable active/placement combat, checks current stored citizenship and level, and builds the existing14006 chooser from current populations. The caller additionally supplies live occupation/combat exclusion. Repeated browsing cannot enroll, charge, grant an office or award anything; citizenship still changes only through12463.

Dispatcher integration must consume any request identifying this installed board, including rejected actions, rather than forwarding a rejected board action to unrelated generic handlers. Native loader/state publication stays unchanged.

## Complete manual acceptance segment

After deployment, use a neutral character in Astrub, map527, near(90,0,5), and right-click the native nation-selection board. Choose its read action. The existing four-nation chooser should open without entering a command. Close and reopen it: citizenship and inventory should remain unchanged. Select a nation: the existing12463 enrollment flow should persist citizenship through reconnect. A character already enrolled must not reopen enrollment; using the board while fighting or too far away must not open the chooser. Test the surrounding ordinary stools, lights and transport interactions afterward to confirm board routing does not intercept other object types.

Automated focused verification results are recorded after the dedicated gate completes; live PostgreSQL and graphical results must not be inferred from adapter tests.
