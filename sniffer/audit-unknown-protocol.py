#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
"""Inventory observed unknown messages using JAR evidence; never output payloads."""
import argparse, base64, collections, hashlib, importlib.util, json, struct, zipfile
from pathlib import Path
from protocol_codec import decode_body

# Manually reviewed meanings. The remaining messages retain their uncertainty.
REVIEWED = {
    ("in", 13726): (
        "animation_mort_combattant",
        "inherited fight action header + i64 eIj; full header schema pending",
        "cvE -> cjp -> aTW: schedules actor AnimMort animation",
    ),
    ("in", 13420): (
        "executer_file_actions_combat",
        "inherited fight header; no local fields does not imply empty body",
        "cvG -> cjq -> aUb.Ac(fight_id) action queue execution",
    ),
    ("in", 13337): (
        "debut_tour_combattant",
        "inherited fight header + i64 fighter; full schema pending",
        "cvW -> cku -> aVi: explicit missing fighter at start-of-turn error and turn manager update",
    ),
    ("in", 13482): (
        "debut_tour_avec_echeance",
        "inherited fight header + fighter/time parameters; full schema pending",
        "cvT -> ckm -> aUN: same start-turn path, deadline TX time plus cvT.bhy",
    ),
    ("in", 12502): (
        "fin_tour_combattant",
        "inherited fight header + turn parameter; full schema pending",
        "cvU -> cjG -> aUM: ends turn and sends cpd(13510) acknowledgment; explicit premature client end-of-turn branch",
    ),
    ("in", 13494): (
        "orientation_combattant",
        "inherited fight header + aAS direction; full schema pending",
        "cvL -> cjx -> aTU: waits for movement completion then applies big.a(direction)",
    ),
    ("in", 12727): (
        "etat_vital_combattant",
        "inherited fight header + i8 state; full schema pending",
        "cvK -> cjw -> aTS: state dispatcher animates KO/death/raise and emits fight.ko/fight.die/fight.raise",
    ),
    ("in", 13624): (
        "deplacement_combattant",
        "inherited fight header + amK path + fcC movement enum/direction; full schema pending",
        "cvP -> cjA: dispatches aUY walking, aVt position, aVu teleport, aVw portal animations according to fcC",
    ),
    ("in", 13684): (
        "debut_placement_combat",
        "inherited fight header + eHH duration parameter; full schema pending",
        "cvl -> cki -> aUC: queues fight.placement UI and starts timed placement",
    ),
    ("in", 13462): (
        "recibir_objeto_inventario",
        "i64 item UID + i32 reference + i16 quantity + bool notification + i64 actor",
        "cAC.dp; cio creates fnR item, sets quantity, inserts biB.dqT inventory, optionally opens notification",
    ),
    ("in", 12549): (
        "sincronizar_reto_zona",
        "cAH fields including TQ duration and TIntArrayList; nested schema pending",
        "cio dispatch calls bhA challenge manager; explicit no-challenge-in-zone branch and challenge activation/update",
    ),
    ("in", 12782): (
        "modificar_estado_recurso",
        "i32 x/y + i16 z/state + i64 kEB + i32 kEC; final parameters meaning pending",
        "cAx.dp; cFJ updates existing bOm resource with m(state,true), lV(kEB), IB(kEC); does not remove actor/resource",
    ),
    ("in", 13948): (
        "actualizar_meteorologia",
        "i64 mwN + i8 mwO + six float parameters + i32 Vl weather enum; parameter labels pending",
        "ctm.dp; chl applies zone climate and weather; warns if territory absent",
    ),
    ("in", 12789): (
        "sincronizar_ecosistema_territorio",
        "i32 kZD + i32 length/byte[] mxZ + i32 length/byte[] mya; nested schema pending",
        "cuE.dp; chl updates wakfuGlobalZoneManager, wakfuEcosystemEnabled and protector satisfaction UI",
    ),
    ("in", 314): (
        "respuesta_ping",
        "i8 service + i32 ping_id + three i64 timestamps; receive timestamp generated locally is not transmitted",
        "Nz.dp reads exactly 29 bytes; cis reports chat.ping/network metrics",
    ),
    ("in", 23354): (
        "sincronizar_reloj_servidor",
        "i64 server time; receive timestamp inherited from Nt is not transmitted",
        "cEm.dp; cgX subtracts local receive time from currentTimeMillis and updates TX clock with server time plus elapsed",
    ),
    ("in", 23597): (
        "sugerencias_nombres_personaje",
        "i8 count + repeated signed i8 UTF8 byte length and string",
        "cEz.dp via BV.eG; cha -> cZo.H appends random-name queue consumed by character creation",
    ),
    ("in", 304): (
        "actualizar_inventario_pvp",
        "oE protobuf envelope containing ow inventory; nested schema pending",
        "cxN.dp -> oE.cv; cmh -> bJm.f inventory and refresh pvpInventoryDialog",
    ),
    ("in", 12218): (
        "avanzar_o_cerrar_dialogo",
        "i32 dialogue_node; zero closes current dialogue",
        "cuA.dp; chC -> dcj.Op: zero unregisters dialogue, nonzero loads eUD.Sq node",
    ),
    ("in", 12969): (
        "abrir_dialogo",
        "i32 dialogue_node + i8 result/type + i64 actor",
        "cuz.dp; chC -> dcj.a creates dialogue UI with eUF enum and target actor",
    ),
    ("in", 12470): (
        "quitar_cantidad_inventario",
        "i64 item UID + i16 quantity + two observed padding bytes",
        "cwZ.dp reads first 10 bytes; all 13 observed messages have trailing 0000; cwZ ignores them; chK dispatch calls bFS.b(uid, quantity); sale semantics not inferred from neighboring cxc handler",
    ),
    ("in", 13479): (
        "error_artesania",
        "i8 eTg result + i32 mxQ + i16 quantity; mxQ interpretation unresolved",
        "cuu.dp; chh.a(biB,eTo,cuu) maps eTg errors to craft UI notifications",
    ),
    ("in", 12401): (
        "orientacion_actor",
        "i64 actor + i8 direction",
        "ctz.dp; cgN.a(ctz) applies beS.a(direction), waiting until movement ends",
    ),
    ("in", 12447): (
        "modificar_propiedad_actor",
        "i64 actor + i8 property_family + i8 property_id + i8 operation",
        "ctC.dp; cgN.a(ctC) resolves eHQ/ffe property and applies big.f/h/g according to PG operation",
    ),
    ("in", 12503): (
        "aprender_hechizos",
        "i64 actor + repeated i32 reference/i64 uid/i16 level until end",
        "ctG.dp; cgN.a(ctG) adds spells to inventory and logs already known/full inventory",
    ),
    ("in", 13249): (
        "reposicionar_actor",
        "i64 actor + i32 x + i32 y + i16 z",
        "ctH.dp; cgN.a(ctH) stops current movement and updates scene position",
    ),
    ("in", 13259): (
        "sincronizar_posicion_actor",
        "i64 actor + i32 x + i32 y + i16 z + bool mxm + bool mxn; flag meaning unresolved",
        "ctI.dp; cgN.a(ctI) position/map synchronization; flags retained under Java names",
    ),
    ("in", 13417): (
        "consumir_cantidad_objeto",
        "i64 actor + i32 item_reference + i32 quantity; -1 removes all",
        "cAQ.dp; cio removes reference quantities from actor inventory and corresponding item/spell inventories",
    ),
    ("out", 363): (
        "ping",
        "u8 service + i32 ping_id + i64 nanoTime",
        "Ny.aWH; PingCommand",
    ),
    ("out", 12058): (
        "seleccion_dialogo",
        "i32 dialog_id + i32 choice_id",
        "cot.aWH; dcj dialogue runner",
    ),
    ("out", 12091): (
        "actualizar_atajos",
        "i64 character + u16 deletions + i32 keys + u16 updates + (i32 key, yu shortcut)",
        "cnE.aWH; bOY shortcut manager; nested yu pending",
    ),
    ("out", 12296): (
        "usar_teletransportador",
        "i64 IE + i32 destination + bool + i32 parameter",
        "cpJ.aWH; bEk teleporter action",
    ),
    ("out", 12659): (
        "usar_objeto",
        "i64 item + bool position_present + optional i32 x/i32 y/i16 z",
        "cnB.aWH; dcu/dfL chat.item.selfUse",
    ),
    ("out", 12870): (
        "accion_elemento_interactivo",
        "i64 IE + i16 action + two zero padding bytes",
        "cpF.aWH; bEG interaction dispatcher",
    ),
    ("out", 12921): (
        "evento_servidor",
        "i32 event_id",
        "cnF.aWH; cac Trigger an event on the server",
    ),
    ("out", 12925): (
        "finalizacion_cliente_combate",
        "i32 fight_id + bool flag",
        "coQ.aWH; aUH End fight",
    ),
    ("out", 12995): (
        "recolectar_recurso",
        "resources.proto ActorCollectRequestMessage: int32 actionId=1,x=2,y=3",
        "cWn constructs cmC(3,12995,zg); current dynamic protobuf replaces cnj",
    ),
    ("out", 13429): (
        "resultado_ocupacion_cliente",
        "i8 result + i16 occupation_type",
        "cro.aWH; callers blQ, bmm, bme cancellation/finish paths",
    ),
    ("out", 13481): (
        "recolectar_monstruo",
        "resources.proto ActorCollectMonsterRequestMessage: int32 actionId=1,int64 monsterId=2",
        "cXc constructs cmC(3,13481,zc); current dynamic protobuf replaces cni",
    ),
    ("out", 13510): (
        "fin_turno_cliente",
        "i32 turn_id",
        "cpd.aWH; aUM fin de tour prematuree du client",
    ),
    ("out", 15494): (
        "consultar_clasificacion_mazmorra",
        "i8 query_type + i32 eiR + i32 lXi",
        "cBy.aWH; daA dungeon.ladder",
    ),
    ("in", 12304): (
        "eliminar_actor_mundo",
        "see ctA.dp typed fields; full schema pending",
        "ctA; cgN removal handler; local World.leave implementation",
    ),
    ("in", 12608): (
        "crear_actor_remoto",
        "entity binary blocks; nested layout in entity-layouts.json",
        "ctE; cgN spawn handler; local wire.spawn implementation",
    ),
    ("in", 13021): ("saldo_kamas", "i64 kamas", "cwg.dp; chW account money handler"),
    ("in", 13078): (
        "inventario_equipo_personaje",
        "i64 character + i32 protobuf length + protobuf + bool compression flag",
        "cxC.dp; chZ; local wire inventory adapter",
    ),
    ("in", 12393): (
        "hojas_atributos_personaje",
        "protobuf equipment sheet map; nested fields pending",
        "cxD.dp; cia; local attribute_sheets adapter",
    ),
    ("in", 13713): (
        "actualizar_bolsas_personaje",
        "i64 character + entity BAGS section",
        "cwY.dp; chK; local wire bag adapter",
    ),
    ("in", 12103): (
        "hojas_aptitudes",
        "nested protobuf aptitude sheets",
        "ctL.dp; cFN Aptitude sheet notification",
    ),
    ("in", 12996): (
        "hojas_configuracion_personaje",
        "nested build sheet payload",
        "ctO.dp; cFO Build sheet notification",
    ),
    ("in", 12613): (
        "crear_efecto_activo_combate",
        "i32 effect identifier + binary state + bool",
        "cvX.dp; cjK runningEffect constructor",
    ),
    ("in", 13497): (
        "actualizar_efecto_activo_combate",
        "i32 effect identifier + binary state",
        "cvY.dp; cjL runningEffect constructor",
    ),
    ("in", 13560): (
        "efecto_activo_combate_con_fuente",
        "i32 effect identifier + binary state + two i64 source fields",
        "cvZ.dp; cjM runningEffect constructor",
    ),
    ("in", 13135): (
        "crear_recurso",
        "resource binary fields; nested resource schema pending",
        "cAz.dp; cFL Resource already exist on client",
    ),
    ("in", 13916): (
        "sincronizar_recurso",
        "resource binary fields; nested resource schema pending",
        "cAA.dp; cFM ResourceSynchroMessageRunner",
    ),
    ("in", 13984): (
        "crear_elementos_interactivos",
        "collection of interactive element ID and binary state",
        "cwJ.dp; cEX INTERACTIVE_ELEMENT_SPAWN_MESSAGE",
    ),
    ("in", 13992): (
        "modificar_estados_npc",
        "monster state payload",
        "cyk.dp; cFf modification des etats NPC",
    ),
    ("in", 15624): (
        "resultado_clasificacion_mazmorra",
        "binary result; nested ranking schema pending",
        "cCF.dp; ciN Error parsing ladder result/dungeonDialog",
    ),
    ("in", 22790): (
        "lista_companeros",
        "binary companion records; nested schema pending",
        "cEq.dp; aZk Receiving companion list",
    ),
    ("in", 23053): (
        "configuracion_sistema",
        "system property records",
        "cEo.dp; cir systemConfiguration/Unknown property",
    ),
    ("in", 22995): (
        "resultado_conversion_clave_api",
        "authentication API response; payload intentionally omitted",
        "cEt.dp; cie apiKey conversion handler",
    ),
}


def constant_pool(data):
    pos = 8
    count = struct.unpack_from(">H", data, pos)[0]
    pos += 2
    cp = [None] * count
    i = 1
    while i < count:
        tag = data[pos]
        pos += 1
        if tag == 1:
            n = struct.unpack_from(">H", data, pos)[0]
            pos += 2
            value = data[pos : pos + n].decode("utf-8", "replace")
            pos += n
        elif tag in (3, 4):
            value = None
            pos += 4
        elif tag in (5, 6):
            value = None
            pos += 8
            cp[i] = (tag, value)
            i += 1
        elif tag in (7, 8, 16, 19, 20):
            value = struct.unpack_from(">H", data, pos)[0]
            pos += 2
        elif tag in (9, 10, 11, 12, 17, 18):
            value = struct.unpack_from(">HH", data, pos)
            pos += 4
        elif tag == 15:
            value = None
            pos += 3
        else:
            raise ValueError("Unsupported constant pool tag " + str(tag))
        cp[i] = (tag, value)
        i += 1

    def utf(i):
        return cp[i][1]

    strings = [
        utf(v) for item in cp[1:] if item and (tag := item[0]) == 8 for v in [item[1]]
    ]
    refs = []
    for item in cp[1:]:
        if item and item[0] in (10, 11):
            owner, name_type = item[1]
            name, descriptor = cp[name_type][1]
            refs.append((utf(cp[owner][1]), utf(name), utf(descriptor)))
    return strings, refs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshots", nargs="+", type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location(
        "summarize_protocol", "sniffer/summarize-protocol.py"
    )
    known = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(known)
    catalog = json.loads(Path("server/protocol/catalog.json").read_text())
    classes = collections.defaultdict(list)
    for message in catalog["messages"]:
        classes[(message["direction"], message["opcode"])].append(message)
    counts = collections.defaultdict(collections.Counter)
    sizes = collections.defaultdict(collections.Counter)
    for snapshot in args.snapshots:
        path = snapshot / "decoded/frames.jsonl" if snapshot.is_dir() else snapshot
        for frame in map(json.loads, path.read_text().splitlines()):
            key = frame["direction"], frame["opcode"]
            body = base64.b64decode(frame["body_base64"])
            counts[key]["observed_count"] += 1
            sizes[key][len(body)] += 1
            try:
                decoded = decode_body(*key, body)
            except (ValueError, UnicodeError):
                counts[key]["decode_errors"] += 1
            else:
                counts[key][
                    "decoded_count" if decoded is not None else "opaque_count"
                ] += 1
    callers = collections.defaultdict(list)
    with zipfile.ZipFile("client/lib/wakfu-client.jar") as jar:
        for path in jar.namelist():
            if not path.endswith(".class"):
                continue
            strings, refs = constant_pool(jar.read(path))
            for owner in {owner for owner, _, _ in refs}:
                callers[owner].append(
                    {
                        "class": path[:-6],
                        "methods": sorted(
                            {
                                name + desc
                                for target, name, desc in refs
                                if target == owner
                            }
                        ),
                        "string_literals": strings,
                    }
                )
    reviews = (
        json.loads(Path("server/protocol/source-review-notes.json").read_text())[
            "reviews"
        ]
        if Path("server/protocol/source-review-notes.json").exists()
        else {}
    )
    messages = []
    for key in sorted(counts):
        if key in known.KNOWN:
            continue
        ms = classes[key]
        evidence = []
        for message in ms:
            for caller in callers[message["class"]]:
                if caller["class"] in (message["class"], "cgD"):
                    continue
                # Keep literal source evidence, never inferred gameplay labels.
                evidence.append(caller)
        review = reviews.get(key[0] + ":" + str(key[1]), {})
        messages.append(
            {
                "direction": key[0],
                "opcode": key[1],
                **counts[key],
                "body_lengths": dict(sorted(sizes[key].items())),
                "message_classes": [m["class"] for m in ms],
                "java_fields": {
                    m["class"]: m["fields"] + m.get("inherited_fields", []) for m in ms
                },
                "codec_calls": {m["class"]: m.get("codec_calls", []) for m in ms},
                "source_callers": evidence,
                "semantic_action": review.get(
                    "semantic_action", REVIEWED.get(key, ("unresolved",))[0]
                ),
                "reviewed_schema": review.get(
                    "reviewed_schema", REVIEWED.get(key, ("", "", ""))[1]
                ),
                "review_evidence": review.get(
                    "review_evidence", REVIEWED.get(key, ("", "", ""))[2]
                ),
                "semantic_status": review.get(
                    "semantic_status",
                    "source_reviewed" if key in REVIEWED else "pending_source_review",
                ),
                "wire_headers": review.get("wire_headers", []),
                "source_disassembly_sha256": review.get(
                    "source_disassembly_sha256", {}
                ),
                "schema_status": "current_dynamic_protobuf_verified"
                if key in [("out", 12995), ("out", 13481)]
                else "java_codec_identified"
                if ms
                else "class_not_in_literal_opcode_catalog",
            }
        )
    report = {
        "jar_sha256": hashlib.sha256(
            Path("client/lib/wakfu-client.jar").read_bytes()
        ).hexdigest(),
        "snapshots": [str(p) for p in args.snapshots],
        "observed_frames": sum(c["observed_count"] for c in counts.values()),
        "observed_distinct_messages": len(counts),
        "known_dictionary_messages": sum(key in known.KNOWN for key in counts),
        "unknown_dictionary_messages": len(messages),
        "additional_source_reviewed_messages": sum(
            m["semantic_status"] == "source_reviewed" for m in messages
        ),
        "reviewed_unresolved_messages": sum(
            m["semantic_status"] == "reviewed_unresolved" for m in messages
        ),
        "pending_source_review_messages": sum(
            m["semantic_status"] == "pending_source_review" for m in messages
        ),
        "inheritance_notice": "Inherited Java fields are not necessarily transmitted: aAa receive timestamp and handler reference are local metadata. Only cuQ.fj (i32 fight_id) and cvB.fl (fj+i32 action_id+i32 mzn) are confirmed wire prefixes. Each concrete dp serializer may skip the base codec entirely.",
        "notice": "Java field and call inventories are evidence, not a complete wire schema or proof of semantic decoding. Nested binary blocks remain opaque unless independently decoded. No captured payload is included.",
        "messages": messages,
    }
    Path("server/protocol/unknown-message-map.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    lines = [
        report["notice"],
        f"Observed {report['observed_frames']} frames, {report['observed_distinct_messages']} distinct messages; dictionary unknown {len(messages)}; additionally source reviewed {report['additional_source_reviewed_messages']}.",
        "direction | opcode | class | frames | decoded | opaque | review status | semantic action | schema | source caller evidence",
    ]
    for m in messages:
        labels = []
        for e in m["source_callers"]:
            hints = [s for s in e["string_literals"] if "." in s or " " in s]
            labels.append(e["class"] + (": " + "; ".join(hints[:6]) if hints else ""))
        lines.append(
            f"{m['direction']} | {m['opcode']} | {','.join(m['message_classes'])} | {m['observed_count']} | {m.get('decoded_count',0)} | {m.get('opaque_count',0)} | {m['semantic_status']} | {m['semantic_action']} | {m['reviewed_schema']} | {'; '.join(labels)}"
        )
    Path("server/protocol/unknown-message-map.txt").write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in ("messages", "snapshots", "notice")
            }
        )
    )


if __name__ == "__main__":
    main()
