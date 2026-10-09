#!/usr/bin/env python3
"""Rebuild installed-client encyclopedia offline; retain native unknown fields."""
import gzip, hashlib, json, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ROOT / "sniffer/java/ExportMonsterEncyclopedia.java"
    jar = ROOT / "client/lib/wakfu-client.jar"
    classes = ROOT / ".runtime/local/classes"
    classes.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        raw = Path(temp) / "encyclopedia.json"
        subprocess.run(
            [
                "javac",
                "-proc:none",
                "-cp",
                "client/lib/*",
                "-d",
                str(classes),
                str(source),
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [
                "java",
                "-cp",
                str(classes) + ":client/lib/*",
                "ExportMonsterEncyclopedia",
                str(raw),
            ],
            cwd=ROOT,
            check=True,
        )
        data = json.loads(raw.read_text())
    data["provenance"] = {
        "client_jar_sha256": digest(jar),
        "exporter_sha256": digest(source),
        "binary_archives": {
            p.name: digest(p)
            for p in sorted((ROOT / "client/contents/bdata").glob("*.jar"))
        },
        "loader": "apw.bGL().a(aMb/fFc/aMD,apB); local jar:file only",
    }
    data["field_evidence"] = {
        "combat_drops": "bbo.a(aMb,short) -> ble/fqH -> bld",
        "probability": "aMf.cmY -> fqH.ad -> fqG.cmY; brq.h formats 100*probability",
        "roll_count": "aMf.csD -> fqH.gE -> fqG.giM; brB.dIo distinguishes each-fighter sentinel",
        "quantity_min_max": "aMf.cqy/cqz -> fqH.fm/fn -> fqG.giN/giO",
        "is_loot_table": "aMf.cqA -> fqH.nG -> brq.d recursively resolves fqE lists",
        "conditions": "aMf.csG -> ble.z parses pairs blo.DU(id),value; csH flags opaque complex criteria",
        "external_loot_tables": "bat loads fFc -> fqJ/fqE. fFe.czk and gBO retained even when client builder ignores them",
        "collect_actions": "bbo.a(aMb,short,blj) loads aMi -> boq/eTu; brq.f bootstrap MethodHandle boq.csP yields item_ref=aMi.csP",
        "territories": "brg.a(aMD) associates aMD.ctH territory with aME.aIc monster family",
    }
    data["availability"] = {
        "base_combat_xp": "not_identified_in_aMb_client_reference; unknown, not zero",
        "breeding": "raw ecosystem actions preserved; reproduction formula not identified",
        "spawn_coordinates": "absent from these encyclopedia tables",
        "authoritative_rewards": "not implemented: modifiers, ownership and complex/server criteria still need evaluation",
    }
    payload = json.dumps(
        data, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode()
    dest = ROOT / "server/protocol/monster-encyclopedia.json"
    dest.write_bytes(payload)
    print(
        "Saved",
        dest,
        "monsters",
        data["count"],
        "tables",
        len(data["external_loot_tables"]),
        "territories",
        len(data["territories"]),
    )


if __name__ == "__main__":
    main()
