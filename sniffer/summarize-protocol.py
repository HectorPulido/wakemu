#!/usr/bin/env python3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
"""Build the action dictionary and evidence report from a closed local capture."""
import base64, collections, hashlib, json, sys
from pathlib import Path
from protocol_codec import decode_body

# Labels supported by source code or observed UI actions; uncertain meanings stay explicit.
KNOWN = {
    ("out", 22296): (
        "crear_personaje",
        "i64 id + i16 breed + str8 name + bool flag + u16 appearance_length + appearance protobuf",
        "cDM.aWH; dS ProtoAppearance",
    ),
    ("in", 22025): (
        "resultado_creacion_personaje",
        "i8 status; success when zero",
        "cEc.dp; cEc.ePf",
    ),
    ("out", 12231): (
        "fabricar_receta",
        "i64 station_id + i32 recipe_id + i32 quantity",
        "com.aWH; dag.a(boQ,int)",
    ),
    ("in", 13852): (
        "ruta_explicita_actor",
        "i64 actor_id + i32 start_x + i32 start_y + i16 start_z + u8 count + packed steps; no movement mode",
        "csR.dp; aAT.eY",
    ),
    ("out", 33): ("presentar_version", "Version bytes", "cmP.aWH"),
    ("out", 574): (
        "solicitar_desafio_autenticacion",
        "Empty; route selects context",
        "cmO.aWH",
    ),
    ("out", 584): (
        "autenticacion_cifrada_dispatcher",
        "u32 length + encrypted authentication blob",
        "cmL.aWH; cgU.nj",
    ),
    ("out", 402): ("consultar_servidores", "Empty", "cmN.aWH"),
    ("out", 575): (
        "seleccionar_servidor",
        "i32 server_id + bool has_optional_id + optional i64",
        "cmS.aWH",
    ),
    ("out", 426): (
        "autenticar_servidor_ticket",
        "str32 ticket + str32 machine identifier",
        "cmG.aWH; cgU.a(cmZ)",
    ),
    ("out", 22954): ("establecer_idioma_seleccion", "str32 language", "cDT.aWH"),
    ("out", 23664): (
        "entrar_con_personaje",
        "i64 character_id + str32 character_name",
        "cDR.aWH; cZl.ay",
    ),
    ("out", 649): (
        "solicitud_auxiliar_tipo_sin_resolver",
        "i32 request_type; observed values 3, 6, 10",
        "Captured payload only; class unresolved",
    ),
    ("out", 12225): (
        "consulta_asociada_personaje_csD",
        "i64 character_id; exact functional meaning pending",
        "csD.aWH",
    ),
    ("out", 12851): (
        "consulta_asociada_personaje_cpP",
        "i64 character_id; inventory-related handler",
        "cpP.aWH; chK.b",
    ),
    ("out", 13003): (
        "establecer_idioma_mundo",
        "UTF-8 bytes without length prefix",
        "cpo.aWH",
    ),
    ("out", 12010): (
        "establecer_idiomas_chat",
        "u8 language_mask + u8 language_id",
        "cqp.aWH",
    ),
    ("out", 1026): (
        "solicitud_auxiliar_OA",
        "Empty; exact functional meaning pending",
        "OA.aWH",
    ),
    ("out", 14689): (
        "solicitud_auxiliar_cDt",
        "Empty; exact functional meaning pending",
        "cDt.aWH",
    ),
    ("out", 13331): (
        "moverse_fuera_combate",
        "i32 movement_mode + i32 start_x + i32 start_y + i16 start_z + u8 step_count + step_count packed bytes",
        "cnl.aWH; aAT.aWH; beO.dgy",
    ),
    ("out", 300): ("keepalive_juego", "Empty", "ND.aWH; aTn.channelIdle"),
    ("in", 309): ("semilla_handshake", "4 bytes", "Nq.dp"),
    ("in", 23): (
        "resultado_version",
        "bool accepted + remaining version bytes",
        "Ns.dp",
    ),
    ("in", 400): (
        "desafio_y_clave_publica",
        "i64 challenge + remaining public key DER bytes",
        "cmZ.dp",
    ),
    ("in", 472): (
        "resultado_autenticacion_dispatcher",
        "u8 result + bool account_present + optional account data",
        "cmV.dp; cmW.f",
    ),
    ("in", 453): (
        "lista_servidores",
        "Server collections; nested fields retained by JAR decoder",
        "cmY.dp",
    ),
    ("in", 466): ("ticket_para_servidor", "u8 result + str32 ticket", "cnd.dp"),
    ("in", 457): (
        "resultado_autenticacion_servidor",
        "u8 result; conditional extra data; on success u16 data_length + data",
        "cmU.dp",
    ),
    ("in", 23548): (
        "lista_personajes",
        "u8 character_count; repeated u32 length + character blob; extra records",
        "cEk.dp; cgY.a(cEk)",
    ),
    ("in", 23082): ("resultado_seleccion_personaje", "u8 result", "cEi.dp; cgY.a(cEi)"),
    ("in", 12666): (
        "informacion_personaje_local",
        "i16 reserved_id_count; i64 ids; three u32-length binary blocks",
        "csY.dp; ciu.b",
    ),
    ("in", 13974): (
        "entrada_personaje_mundo",
        "Four u16-length outer blocks; entity, protectors, protector info, dungeon; nested fields require interpretation",
        "csW.dp; ciu.b; comparison with WakBox CharacterHandler",
    ),
    ("in", 13530): (
        "actualizar_posicion_actor",
        "i64 actor_id + i32 x + i32 y + i16 z + u8 direction + i32 movement_mode",
        "csQ.dp; cgN.a(csQ)",
    ),
    ("in", 13046): (
        "actualizar_estado_actor",
        "i64 actor_id + i16 state_length + state bytes",
        "csZ.dp; cgN.a(csZ); big.as",
    ),
    ("in", 12728): (
        "bloque_binario_ctl",
        "u8 length + bytes; internal meaning pending",
        "ctl.dp",
    ),
    ("in", 762): (
        "recibir_chat",
        "i32 channel_id + str8 sender + u8 language_mask + u8 language_id + i64 sender_id + bool flag + str16 text",
        "NP.dp; NQ.b",
    ),
    ("in", 13877): (
        "particion_recursos_mundo",
        "Protobuf resource partition",
        "cAw.dp",
    ),
    ("in", 13873): ("bloque_binario_cwf", "Raw payload; subformat pending", "cwf.dp"),
    ("out", 12366): (
        "chat_proximidad",
        "str16 text",
        "VicinityMessageCommand; cmy; cmq.d",
    ),
    ("out", 13074): ("chat_comercio", "str16 text", "TradeMessageCommand; cmx; cmq.d"),
    ("out", 13744): ("chat_gremio", "str16 text", "GuildMessageCommand; cms; cmq.d"),
    ("out", 13702): (
        "chat_campo_batalla",
        "str16 text",
        "BattlegroundMessageCommand; cmp; cmq.d",
    ),
    ("out", 13188): (
        "chat_reclutamiento",
        "u8 language_id + str16 text",
        "RecruitmentMessageCommand; cmw.aWH",
    ),
    ("out", 13831): (
        "chat_comunidad",
        "u8 language_id + str16 text",
        "CommunityMessageCommand; cmr.aWH",
    ),
    ("out", 13224): (
        "chat_grupo",
        "i64 group_id + str16 text",
        "PartyMessageCommand; cmt.aWH",
    ),
    ("out", 13917): (
        "chat_privado",
        "str8 recipient + str16 text",
        "cmv.aWH; ayq.ho; cmq.d; aNV.R",
    ),
    ("out", 12161): (
        "mover_actor_en_combate",
        "i64 actor_id + repeated (i32 x, i32 y, i16 z); point count inferred from (body_size-8)/10",
        "cpa.aWH; dbe.a",
    ),
    ("out", 12889): (
        "accion_hechizo_en_combate",
        "i64 actor_id + i64 spell_instance_id + u8 mode + i32 x + i32 y + i16 z",
        "cpe.aWH; dbd.ad; fnR.LV",
    ),
    ("out", 13655): (
        "orientar_actor_en_combate",
        "i64 actor_id + u8 direction",
        "coZ.aWH; dbl.b; dbh.b",
    ),
    ("out", 12543): (
        "seleccionar_celda_combate",
        "i32 x + i32 y + i16 z",
        "coNN.aWH; dba.b",
    ),
    ("out", 12806): (
        "posicionar_actor_combate",
        "i64 actor_id + i32 x + i32 y + i16 z",
        "coO.aWH; dbh.b",
    ),
    ("out", 12523): ("estado_listo_combate", "bool ready", "cpc.aWH; dbh.b"),
    ("out", 13110): ("pedir_ayuda_combate", "bool request_help", "coM.aWH; dbh.b"),
    ("out", 12403): (
        "finalizar_turno_actor",
        "i64 actor_id + i16 turn_id",
        "cpb.aWH; buH.aX",
    ),
}


def main():
    capture = Path(sys.argv[1])
    out = capture / "decoded"
    catalog = json.loads(Path(".runtime/protocol-catalog.json").read_text())
    frames = [json.loads(l) for l in (out / "frames.jsonl").read_text().splitlines()]
    inbound = [json.loads(l) for l in (out / "inbound.jsonl").read_text().splitlines()]
    counts = collections.Counter((r["direction"], r["opcode"]) for r in frames)
    bykey = collections.defaultdict(list)
    for m in catalog["messages"]:
        bykey[(m["direction"], m["opcode"])].append(m)
    dictionary = []
    for key in sorted(set(counts) | set(KNOWN)):
        direction, op = key
        ms = bykey.get(key, [])
        label, schema, evidence = KNOWN.get(
            key,
            (
                f"mensaje_{op}_semantica_pendiente",
                "See catalog and extracted fields",
                "JAR decoder and capture",
            ),
        )
        dictionary.append(
            {
                "direction": direction,
                "opcode": op,
                "opcode_hex": f"0x{op:04x}",
                "action": label,
                "schema": schema,
                "evidence": evidence,
                "message_classes": [m["class"] for m in ms],
                "observed_count": counts[key],
                "status": "observed_and_source"
                if counts[key] and key in KNOWN and op != 649
                else "observed_unresolved"
                if counts[key]
                else "source_only_unvalidated",
            }
        )
    jarhash = hashlib.sha256(
        Path("client/lib/wakfu-client.jar").read_bytes()
    ).hexdigest()
    catalog["jar_sha256"] = jarhash
    catalog[
        "scope"
    ] = "Nt/Nx descendants with a literal opcode in d(); excludes internal UI messages; may omit dynamic/inherited opcode classes."
    Path("server/protocol/catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"
    )
    Path("server/protocol/actions.json").write_text(
        json.dumps(
            {"jar_sha256": jarhash, "actions": dictionary}, ensure_ascii=False, indent=2
        )
        + "\n"
    )
    semantic = []
    for r in frames:
        fields = decode_body(
            r["direction"], r["opcode"], base64.b64decode(r["body_base64"])
        )
        if fields is not None:
            r = dict(r, fields=fields)
        semantic.append(r)
    (out / "semantic.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in semantic)
    )
    # Compare independently implemented Python layouts with the JAR's field extraction.
    pairs = [
        (
            13530,
            {"actor_id": "mwm", "x": "bbn", "y": "bbo", "z": "bbl", "direction": "bbw"},
        ),
        (
            762,
            {"sender": "aZU", "sender_id": "aZX", "text": "aZZ", "channel_id": "aZT"},
        ),
        (13046, {"actor_id": "aEp"}),
    ]
    oracle = {r["frame_index"]: r for r in inbound}
    checked = 0
    for r in semantic:
        if r["direction"] != "in":
            continue
        for op, mapping in pairs:
            if r["opcode"] == op:
                reference = oracle[r["frame_index"]]["fields"]
                for a, b in mapping.items():
                    assert r["fields"][a] == reference[b], (r["capture_seq"], a)
                checked += 1
    observed_objects = collections.Counter()
    for line in (capture / "events.jsonl").open():
        r = json.loads(line)
        if r.get("direction") == "in" and r.get("stage") == "aTm#0":
            observed_objects[r["class"]] += 1
    parsed_objects = collections.Counter(r["message_class"] for r in inbound)
    assert (
        observed_objects == parsed_objects
    ), "Reassembled frame/class counts differ from live client decoder"
    assert not any(r.get("decode_error") for r in inbound), "JAR decoding exceptions"
    movements = [
        {"capture_seq": r["capture_seq"], "time": r["time"], "fields": r["fields"]}
        for r in semantic
        if r["direction"] == "out" and r["opcode"] == 13331
    ]
    positions = [
        json.loads(l)
        for l in (capture / "player-positions.jsonl").read_text().splitlines()
    ]
    assert movements[-1]["fields"]["start_position"] == {
        k: positions[0][k] for k in ("x", "y", "z")
    }
    assert movements[-1]["fields"]["end_position"] == {
        k: positions[1][k] for k in ("x", "y", "z")
    }
    report = {
        "jar_sha256": jarhash,
        "wire_catalog_classes": len(catalog["messages"]),
        "observed_inbound_frames": len(inbound),
        "observed_outbound_frames": sum(r["direction"] == "out" for r in frames),
        "inbound_extraction_exceptions": 0,
        "inbound_decoder_true": sum(r["decoder_return"] for r in inbound),
        "inbound_decoder_false": sum(not r["decoder_return"] for r in inbound),
        "independent_layout_oracle_matches": checked,
        "stream_object_count_matches": True,
        "outbound_movement_requests": movements,
        "verified_position_samples": positions,
        "opaque_payload_notice": "Field extraction does not imply that all nested binary formats or their semantics are decoded.",
    }
    (out / "analysis-summary.json").write_text(json.dumps(report, indent=2) + "\n")
    table = ["direccion | id | clase | accion | observados | certeza"]
    for a in dictionary:
        table.append(
            f"{a['direction']} | {a['opcode']} | {','.join(a['message_classes']) or '?'} | {a['action']} | {a['observed_count']} | {a['status']}"
        )
    Path("server/protocol/actions.txt").write_text("\n".join(table) + "\n")
    print(
        json.dumps(
            {
                k: v
                for k, v in report.items()
                if k not in ("outbound_movement_requests", "verified_position_samples")
            }
        )
    )


if __name__ == "__main__":
    main()
