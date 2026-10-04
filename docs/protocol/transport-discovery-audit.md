Transport discovery (current client)

Account packet13873 section12 is eDS.TRANSPORTS→eDX.foR→fzy.
fzy.a reads i32 length then protobuf zR/Transportation:
repeated field1 TravelDetails, whose required enum type field1 is ZAAP=1 or DRAGO=2,
and repeated int32 knownIds field2. Enum ordinals0/1 are not wire values.
Native fzy.foH writes DRAGO thenZAAP. Python account_packet follows that order.
Incremental cBg.d=12674,dp reads i32 discoveredID then byte type viazP.ld.
cgN.a(cBg) calls fzB.b(accountID,type,ID), announcing chat.travel.discovered only
when the known set gains an ID. IDs belong to the account, not character.

Native validation: tools/VerifyOwnTransport.java consumes own generated account
section body after ordinal; ZAAP123 andDRAGO456 resolve to native sets and leave0
bytes. Tests cover persistent account isolation, duplicate discovery and stale
session rejection. No official connection is involved.

This persistence does not enable unknown destinations. Existing transports.py
supports only four tutorial routes1385↔1387/1388. Map1134 zaap/dragopavo route
catalog, discovery triggers, price and destination response remain unimplemented.
Do not reuse13778 as discovery: it allocates reserved client object identifiers.
Do not treatfqv dungeon/access timers used bybFE as the transport known set.

Implemented extension (local test policy)

Native ZAAP/DRAGO is bEu, not bEk tutorial teleporters. bEu registration
calls bEG.b(QT.REGISTER), which sends cpF12870 sourceUID+i16 action24+00 00.
Native provider bRr opens ZAAP menu dfN.c locally; bRp opens DRAGO daw.c.
Travel for both sends csO13686 two i64 values: source anddestinationUID.

protocol/native-transports.json exports45ZAAP fromaNN and121DRAGO fromaKT.
ForZAAP aNN.clO is destinationmap, clM/clN arrivalXY, clP is a separate
parameter and must not be called map or altitude. EveryZAAP has exactly one
walkable arrivalheight from native VB/VC/Vy readers of installedTPLG archives.
31316 is map1134 arrival(-10,-10,-1), while interactive object sits(-10,-11,-1).
ExportNativeTransports then ExportTransportHeights reproduces the catalog.

native_transports.resolve supports all45ZAAP, checks source map/privateinstance,
proximity andknownID. Explicit waive_criteria=True is the authorized local
all-active testing policy; normal mode rejects unimplemented conditionexpressions.
DRAGO records lack destinationmap/height, therefore routing them is still pending.
bootstrap builds own format28 ID/IDENTITY/POSITION plus empty actor/contextlists,
and clean eVa.b(new eUZ()) stasis context. It sends13256,13974,12318 without
captured NPCs orinventory. RealJAR verifier checks csW,eHj andeVa fields. GUI
transition/mapready remains to be checked by the parent; native decoding alone
does not prove the rendered trip succeeds.
