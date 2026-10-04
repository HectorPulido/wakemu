#!/usr/bin/env python3
"""Compare pinned WakBox source and current descriptors without running either server."""
import ast, json, re, subprocess
from pathlib import Path
from google.protobuf.descriptor_pb2 import FileDescriptorProto, FileDescriptorSet

root = Path(".runtime/reference/WakBox-Evolution")
modern = FileDescriptorSet.FromString(
    Path("server/protocol/descriptors.pb").read_bytes()
)
old = FileDescriptorSet()
errors = []
for path in (root / "shared/Proto").glob("*.pb.cc"):
    text = path.read_text()
    match = re.search(r"static const char descriptor\[\]\s*=\s*\{(.*?)\};", text, re.S)
    if not match:
        errors.append(path.name + ": descriptor string missing")
        continue
    try:
        raw = b"".join(
            ast.literal_eval("b" + part.replace("\\?", "?"))
            for part in re.findall(r'"(?:\\.|[^"\\])*"', match.group(1))
        )
        old.file.append(FileDescriptorProto.FromString(raw))
    except Exception as ex:
        errors.append(path.name + ": " + str(ex))


def messages(files):
    result = {}

    def add(msg, prefix):
        name = prefix + "." + msg.name if prefix else msg.name
        name = name.removeprefix("WakfuProto.")
        result[name] = {
            f.number: {
                "name": f.name,
                "type": f.type,
                "label": f.label,
                "type_name": f.type_name.replace(".WakfuProto.", "."),
                "default": f.default_value,
            }
            for f in msg.field
        }
        for nested in msg.nested_type:
            add(nested, name)

    for file in files:
        for msg in file.message_type:
            add(msg, file.package)
    return result


old_messages = messages(old.file)
new_messages = messages(modern.file)
common = set(old_messages) & set(new_messages)
comparison = []
for name in sorted(common):
    a, b = old_messages[name], new_messages[name]
    changed = [
        {"number": n, "old": a[n], "current": b[n]}
        for n in sorted(set(a) & set(b))
        if a[n] != b[n]
    ]
    incompatible = [
        d
        for d in changed
        if any(
            d["old"][k] != d["current"][k]
            for k in ("type", "label", "type_name", "default")
        )
    ]
    comparison.append(
        {
            "message": name,
            "added_fields": [{"number": n, **b[n]} for n in sorted(set(b) - set(a))],
            "removed_fields": [{"number": n, **a[n]} for n in sorted(set(a) - set(b))],
            "changed_fields": changed,
            "changed_existing_field_layouts": incompatible,
            "identical_fields": a == b,
        }
    )
# Correspondence is semantic, not an arithmetic renumbering.
map_rows = [
    (
        "auth",
        "CMSG_CLIENT_VERSION",
        7,
        33,
        "out",
        "cmP",
        "same version body; frame widened",
    ),
    (
        "auth",
        "SMSG_CLIENT_VERSION_RESULT",
        8,
        23,
        "in",
        "Ns",
        "same accepted flag and version bytes",
    ),
    (
        "auth",
        "SMSG_CLIENT_IP",
        110,
        309,
        "in",
        "Nq",
        "four-byte seed/IP-like payload; semantics must not assume IP",
    ),
    (
        "auth",
        "CMSG_PUBLIC_KEY_REQUEST",
        1033,
        574,
        "out",
        "cmO",
        "same empty body; route byte differs by service",
    ),
    (
        "auth",
        "SMSG_PUBLIC_KEY",
        1034,
        400,
        "in",
        "cmZ",
        "same i64 challenge plus DER public key",
    ),
    (
        "auth",
        "CMSG_CLIENT_AUTH",
        1026,
        584,
        "out",
        "cmL",
        "RSA blob container retained; credentials now use launcher token flow",
    ),
    (
        "auth",
        "SMSG_CLIENT_AUTH_RESULT",
        1027,
        472,
        "in",
        "cmV",
        "account structure substantially expanded",
    ),
    ("auth", "CMSG_REALMS_REQUEST", 1035, 402, "out", "cmN", "empty body retained"),
    (
        "auth",
        "SMSG_REALMS_LIST",
        1036,
        453,
        "in",
        "cmY",
        "realm concept retained; more metadata",
    ),
    (
        "auth",
        "CMSG_AUTH_TOKEN_REQUEST",
        1211,
        575,
        "out",
        "cmS",
        "second field now bool presence plus optional i64",
    ),
    (
        "auth",
        "SMSG_AUTH_TOKEN_RESULT",
        1212,
        466,
        "in",
        "cnd",
        "result plus str32 ticket retained",
    ),
    (
        "world",
        "CMSG_AUTH_TOKEN",
        1213,
        426,
        "out",
        "cmG",
        "str32 ticket now followed by str32 machine identifier",
    ),
    (
        "world",
        "SMSG_CLIENT_AUTH_RESULT",
        1025,
        457,
        "in",
        "cmU",
        "success plus u16 account block retained; block contents changed",
    ),
    (
        "world",
        "CMSG_CHAR_SELECT",
        2049,
        23664,
        "out",
        "cDR",
        "i64 id plus str32 name retained",
    ),
    (
        "world",
        "SMSG_CHAR_LIST",
        2048,
        23548,
        "in",
        "cEk",
        "character count retained; each character block length widened u16 to u32; extra records",
    ),
    (
        "world",
        "SMSG_CHAR_SELECT",
        2050,
        23082,
        "in",
        "cEi",
        "single result byte retained",
    ),
    (
        "world",
        "SMSG_CHARACTER_INFORMATION",
        4098,
        12666,
        "in",
        "csY",
        "reserved i64 id list plus three u32 blobs; inner serialized fields changed",
    ),
    (
        "world",
        "SMSG_CHARACTER_ENTER_WORLD",
        4100,
        13974,
        "in",
        "csW",
        "four u16-sized outer blocks retained; protector subrecords expanded",
    ),
    (
        "world",
        "CMSG_CHAR_MOVEMENT",
        4113,
        13331,
        "out",
        "cnl",
        "new leading i32 movement mode; path layout retained",
    ),
    (
        "world",
        "SMSG_UPDATE_POSITION",
        4127,
        13530,
        "in",
        "csQ",
        "new trailing i32 movement mode",
    ),
    (
        "world",
        "CMSG_CLIENT_LANGUAGE",
        13001,
        13003,
        "out",
        "cpo",
        "two-byte language retained for current es sample; variable UTF-8 length now supported by serializer",
    ),
    (
        "world",
        "CMSG_CHAT_MESSAGE",
        3153,
        12366,
        "out",
        "cmy",
        "current str16 vs old str8",
    ),
    (
        "world",
        "CMSG_PRIVATE_MESSAGE",
        3155,
        13917,
        "out",
        "cmv",
        "recipient str8 retained; message str16 vs old str8",
    ),
    (
        "world",
        "CMSG_TRADE_MESSAGE",
        3159,
        13074,
        "out",
        "cmx",
        "current str16 vs old str8",
    ),
    (
        "world",
        "CMSG_RECRUIT_MESSAGE",
        3167,
        13188,
        "out",
        "cmw",
        "language prefix plus str16 text; old handler empty",
    ),
]
report = {
    "reference_url": "https://github.com/WakBox/WakBox-Evolution",
    "reference_commit": subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip(),
    "reference_client_version": "1.54.0",
    "current_captured_version": "1.93.2",
    "opcode_correspondences": [
        dict(
            zip(
                (
                    "service",
                    "old_name",
                    "old_opcode",
                    "current_opcode",
                    "direction",
                    "current_class",
                    "change",
                ),
                row,
            )
        )
        for row in map_rows
    ],
    "old_proto_files": len(old.file),
    "current_proto_files": len(modern.file),
    "old_proto_messages": len(old_messages),
    "current_proto_messages": len(new_messages),
    "common_proto_messages": len(common),
    "identical_common_proto_messages": sum(r["identical_fields"] for r in comparison),
    "protobuf_name_comparison": "Legacy WakfuProto package prefix normalized; type names otherwise preserved",
    "proto_comparison": comparison,
    "old_only_proto_messages": sorted(set(old_messages) - set(new_messages)),
    "current_only_proto_messages": sorted(set(new_messages) - set(old_messages)),
    "descriptor_extraction_errors": errors,
}
Path("server/protocol/wakbox-comparison.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(
    json.dumps(
        {
            k: v
            for k, v in report.items()
            if k
            not in (
                "opcode_correspondences",
                "proto_comparison",
                "old_only_proto_messages",
                "current_only_proto_messages",
            )
        }
    )
)
for r in comparison:
    if not r["identical_fields"]:
        print(
            r["message"],
            "added",
            len(r["added_fields"]),
            "removed",
            len(r["removed_fields"]),
            "changed existing layouts",
            len(r["changed_existing_field_layouts"]),
        )
