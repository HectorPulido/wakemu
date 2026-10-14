"""Pure receipt-driven full-book selection; never executes a fight or rebinds owners."""
from pathlib import Path
import ast
import collections
import gzip
import hashlib
import json


def select_exact_fullbooks(
    *, root, index_path, native_inventory_path, live_catalog_path
):
    """Return exact original owner/level contexts awaiting actual AI acceptance."""
    ROOT = Path(root).resolve()
    INDEX = Path(index_path).resolve()
    index = json.loads(INDEX.read_text())
    with gzip.open(Path(native_inventory_path), "rt") as f:
        native = {r["ref"]: r for r in json.load(f)["monsters"]}
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    path = Path(live_catalog_path)
    decoder = json.JSONDecoder()
    buffer = ""
    policy = None
    with path.open() as handle:
        while policy is None:
            chunk = handle.read(1048576)
            if not chunk:
                raise ValueError("Missing live source policy")
            buffer += chunk
            marker = buffer.find('"activation_policy":')
            if marker >= 0:
                try:
                    policy = decoder.raw_decode(
                        buffer, marker + len('"activation_policy":')
                    )[0]
                except json.JSONDecodeError:
                    continue
            else:
                buffer = buffer[-100:]
    live = policy["enabled_monsters"]
    receipts = {}
    contexts = collections.defaultdict(dict)
    for cache in index["actual_case_cache"]:
        ctx = index["receipt_contexts"][cache["context_ref"]]
        source = Path(ctx["receipt"])
        if str(source) not in receipts:
            if sha(source) != ctx["sha256"]:
                raise ValueError("Original receipt drift")
            receipts[str(source)] = json.loads(source.read_text())
        report = receipts[str(source)]
        pointer = cache["original_json_pointer"]
        row = report
        for part in pointer.strip("/").split("/"):
            row = row[int(part)] if isinstance(row, list) else row[part]
        raw = row.get("raw_case", row)
        authority = row.get("context", {})
        ref, level, spell, pl = (
            cache[k] for k in ("reference", "actor_level", "spell_id", "spell_level")
        )
        if authority and authority != {
            "reference": ref,
            "actor_level": level,
            "spell_id": spell,
            "spell_level": pl,
        }:
            raise ValueError("Cache context differs from original owner/level")
        if report.get("sources_stable") is not True:
            continue
        if (
            raw.get("spell_id") != spell
            or raw.get("spell_level") != pl
            or raw.get("level") != level
        ):
            raise ValueError("Original raw identity differs")
        contexts[ref, level][spell] = dict(
            spell_id=spell,
            spell_level=pl,
            status=raw["status"],
            raw=raw,
            receipt=str(source),
            receipt_sha256=ctx["sha256"],
            pointer=pointer,
            source_root=ctx["source_root"],
            candidate_manifest_sha256=ctx["candidate_manifest_sha256"],
        )
    class_only = set()
    for source in index.get("input_sha256", {}):
        if source.endswith("/queue.json"):
            queue = json.loads(Path(source).read_text())
            class_only.update(queue.get("verified_class_only_excluded_refs", []))
    casting_path = next(
        (
            Path(p)
            for p in index.get("input_sha256", {})
            if p.endswith("/native-spell-casting.json")
        ),
        None,
    )
    if casting_path is None:
        raise ValueError("Missing source-pinned native casting maxima")
    if sha(casting_path) != index["input_sha256"][str(casting_path)]:
        raise ValueError("Native casting source drift")
    casting = json.loads(casting_path.read_text())
    casting = casting.get("spells", casting)
    resolver_source = ROOT / "server/wakfu_server/maps/monsters.py"
    native_function = next(
        n
        for n in ast.parse(resolver_source.read_text()).body
        if isinstance(n, ast.FunctionDef) and n.name == "native_abilities"
    )
    spell_resolver = next(
        n
        for n in native_function.body
        if isinstance(n, ast.FunctionDef) and n.name == "spell_level"
    )
    resolver_code = compile(
        ast.Module(body=[spell_resolver], type_ignores=[]), str(resolver_source), "exec"
    )
    ready = []
    near = []
    for (ref, level), cases in sorted(contexts.items()):
        n = native[ref]
        namespace = {"casting": casting, "level": level}
        exec(resolver_code, namespace)
        expected = {a["spell_id"]: namespace["spell_level"](a) for a in n["abilities"]}
        if not expected or not max(1, n["min_level"]) <= level <= n["max_level"]:
            continue
        if not set(expected) <= set(cases):
            continue
        if any(cases[s]["spell_level"] != pl for s, pl in expected.items()):
            continue
        rows = [cases[s] for s in expected]
        if len({r["source_root"] for r in rows}) != 1:
            continue
        originals = n["raw_native"]["cle"]
        constructors = [
            receipt
            for row in rows
            for receipt in row["raw"].get("initialization_receipts", [])
        ]
        ctor = not originals or any(
            r.get("ref") == ref
            and r.get("descriptor_level") == level
            and r.get("raw_triples") == originals
            and r.get("initialized") is True
            for r in constructors
        )
        base = dict(
            ref=ref,
            name=n["name"],
            native_range=[n["min_level"], n["max_level"]],
            proven_range=[level, level],
            original_owned_book=sorted(expected.items()),
            source_root=rows[0]["source_root"],
            constructor_proven=ctor,
            live_policy=live.get(str(ref)),
            blocked_minigame=ref in index["effective_minigame_references"],
            summon_chain_pending=bool(n.get("dependencies", {}).get("candidate_links")),
            original_proofs=[{k: v for k, v in r.items() if k != "raw"} for r in rows],
            full_native_max_claim=level == n["min_level"] == n["max_level"],
            actual_ai_qualified=False,
            admission=False,
        )
        if all(r["status"] == "validated" for r in rows) and ctor:
            ready.append(base)
        elif all(
            r["status"]
            in (
                "validated",
                "native_passive_initialization",
                "native_zero_amount_unavailable",
            )
            for r in rows
        ):
            near.append(base)
    new = [
        r
        for r in ready
        if r["live_policy"] is None
        and not r["blocked_minigame"]
        and r["ref"] not in class_only
    ]
    tails = [
        r
        for r in ready
        if r["live_policy"] is not None
        and not r["live_policy"]["min_level"]
        <= r["proven_range"][0]
        <= r["live_policy"]["max_level"]
        and not r["blocked_minigame"]
    ]
    result = dict(
        schema="same-owner-exact-level-fullbook-selector-v1",
        live_policy_count=len(live),
        native_level_resolver_sha256=sha(resolver_source),
        casting_maxima_sha256=sha(casting_path),
        index_sha256=sha(INDEX),
        owner_level_contexts=len(contexts),
        complete_validated_books=ready,
        unpublished_ready_native_contexts=new,
        active_uncovered_ready_native_contexts=tails,
        deep_mode_review_required=near,
        new_ref_count=len({r["ref"] for r in new}),
        tail_ref_count=len({r["ref"] for r in tails}),
        actual_ai_queue=new + tails,
        actual_ai_qualified=False,
        admission=False,
        engines_executed=False,
        policy="Only exact original owner and actor level; no different-owner receipt transfer or unproved integer-level expansion",
    )
    return result
