#!/usr/bin/env python3
"""Rebuild combat tracking from catalogs; never overwrite human review.json."""
import argparse
import ast
import csv
import gzip
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "server/protocol"
OUT = ROOT / "docs/reports/combat-inventory"


def read(path):
    raw = path.read_bytes()
    return json.loads(gzip.decompress(raw) if path.suffix == ".gz" else raw)


def csv_write(path, rows, columns):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    k: json.dumps(v, ensure_ascii=False)
                    if isinstance(v, (list, dict))
                    else v
                    for k, v in row.items()
                }
            )


def md(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def literal_handler_families(tree):
    """Registered routes, including conditional routes; never gameplay coverage."""
    families = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "handlers"
                    and isinstance(target.slice, ast.Constant)
                    and type(target.slice.value) is int
                ):
                    families.add(target.slice.value)
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "handlers"
            and node.func.attr == "update"
            and len(node.args) == 1
        ):
            continue
        value = node.args[0]
        if isinstance(value, ast.Dict):
            families.update(
                key.value
                for key in value.keys
                if isinstance(key, ast.Constant) and type(key.value) is int
            )
        elif isinstance(value, ast.DictComp) and len(value.generators) == 1:
            generator = value.generators[0]
            if (
                isinstance(value.key, ast.Name)
                and isinstance(generator.target, ast.Name)
                and value.key.id == generator.target.id
                and not generator.ifs
            ):
                try:
                    keys = ast.literal_eval(generator.iter)
                except (ValueError, TypeError):
                    continue
                if isinstance(keys, (tuple, list, set)):
                    families.update(key for key in keys if type(key) is int)
    return families


def main(output=OUT):
    output.mkdir(parents=True, exist_ok=True)
    spell_data = read(PROTOCOL / "spells.json")["spells"]
    tree = read(PROTOCOL / "spell-effect-trees.json")
    state_data = read(PROTOCOL / "combat-state-definitions.json.gz")
    registry = read(PROTOCOL / "effect-characteristic-registry.json")["effects"]
    names_path = PROTOCOL / "spell-names.json"
    name_data = read(names_path) if names_path.exists() else {}
    class_names = {str(r["breed"]): r["name"] for r in name_data.get("classes", [])}
    names = name_data.get("spells", {})
    if isinstance(names, list):
        names = {str(r["id"]): r for r in names}
    review_path = output / "review.json"
    if not review_path.exists():
        review_path.write_text(
            json.dumps(
                {
                    "schema": 1,
                    "spells": {},
                    "families": {},
                    "states": {},
                    "systems": {},
                    "history": [],
                },
                indent=2,
            )
            + "\n"
        )
    review = read(review_path)
    extra_audit_path = ROOT / "docs/reports/class-extra-spells-audit.json"
    extra_audit = read(extra_audit_path) if extra_audit_path.exists() else {}
    extra_rows = []
    for extra in extra_audit.get("extras", []):
        note = review.get("spells", {}).get(str(extra["id"]), {})
        extra_rows.append(
            {
                "id": extra["id"],
                "name": extra["name"],
                "breeds": sorted({link["breed"] for link in extra["links"]}),
                "grant_paths": extra["links"],
                "tree_exported": extra["tree_exported"],
                "review_status": note.get("status", "Sin revisión individual"),
                "game_verified": note.get("game_verified", False),
                "owner": note.get("owner", "Pendiente"),
                "next_test": note.get(
                    "next",
                    "Probar desbloqueo y lanzamiento extra mediante entrada común; efectos, costes, límites y sincronización.",
                ),
                "review": note,
            }
        )
    effects = dict(state_data["effects"])
    for key, value in tree["effects"].items():
        if key in effects and effects[key] != value:
            raise ValueError(f"Conflicting effect definition {key}")
        effects[key] = value
    source = ROOT / "server/wakfu_server/combat/combat_effect_runtime.py"
    runtime_source = re.sub(r"\s+", "", ast.unparse(ast.parse(source.read_text())))
    # Fail instead of silently reporting obsolete registration when factory changes.
    for marker in (
        "foreffect_classinDAMAGE_FAMILIES",
        "HEAL_ELEMENTS",
        "('eWQ','eWR','eXE','eYO')",
        "handlers[304]=state",
        "handlers[321]=",
    ):
        if marker not in runtime_source:
            raise ValueError(
                "Review handler registration parser after runtime change: " + marker
            )
    heal_source = (
        ROOT / "server/wakfu_server/combat/combat_damage_healing.py"
    ).read_text()
    heal_tree = ast.parse(heal_source)
    heal_ids = None
    damage_ids = None
    for node in ast.walk(heal_tree):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "HEAL_ELEMENTS" for t in node.targets
        ):
            heal_ids = set(ast.literal_eval(node.value))
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "DAMAGE_FAMILIES" for t in node.targets
        ):
            damage_ids = set(ast.literal_eval(node.value))
    if heal_ids is None:
        raise ValueError("Missing healing family declaration")
    if damage_ids is None:
        raise ValueError("Missing damage family declaration")
    registered = (
        damage_ids
        | heal_ids
        | set(map(int, registry))
        | {304, 321, 330, 844, 999}
        | literal_handler_families(ast.parse(source.read_text()))
    )
    # Dispel requires the proven server-owned retained population. Registration
    # does not imply arbitrary captured/native populations can be removed.
    if "handlers[421]=NativeDispelHandler" in runtime_source:
        registered.add(421)
    dispatch_source = (
        ROOT / "server/wakfu_server/combat/combat_effect_dispatch.py"
    ).read_text()
    if 'effect["effect_class"] == 949' in dispatch_source:
        registered.add(949)
    if 'effect["effect_class"] == 1076' in dispatch_source:
        registered.add(1076)
    group_sets = []
    for node in ast.walk(ast.parse(dispatch_source)):
        if isinstance(node, ast.Compare) and any(
            isinstance(op, ast.In) for op in node.ops
        ):
            for candidate in node.comparators:
                if isinstance(candidate, ast.Tuple) and all(
                    isinstance(v, ast.Constant) and type(v.value) is int
                    for v in candidate.elts
                ):
                    group_sets.append({v.value for v in candidate.elts})
    dispatch_groups = (
        set.union(*(s for s in group_sets if 330 in s))
        if any(330 in s for s in group_sets)
        else set()
    )
    # These groups execute directly in the dispatcher rather than through its
    # handler dictionary. Registration is still only partial code coverage.
    registered.update(dispatch_groups & {341, 352, 1103})
    if 'effect["effect_class"] == 865' in dispatch_source:
        registered.add(865)
    if "1047:native_hp_group_level" in runtime_source and 1047 in dispatch_groups:
        registered.add(1047)
    if "handlers[1065]=NativeSpellCostHandler" in runtime_source:
        registered.add(1065)
    if "kind:maximumforkindin(31,41,191)" in runtime_source:
        registered.update((31, 41, 191))
    if (
        "913:native_characteristic_group_level" in runtime_source
        and 913 in dispatch_groups
    ):
        registered.add(913)
    if "1020:native_trigger_group_level" in runtime_source and 1020 in dispatch_groups:
        registered.add(1020)
    if "kind:reductionforkindin(56,57,192)" in runtime_source:
        registered.update((56, 57, 192))
    if "handlers[986]=NativePercentageHPHandler" in runtime_source:
        registered.add(986)
    for family in (910, 912):
        if (
            f"{family}:native_cost_group_level" in runtime_source
            and family in dispatch_groups
        ):
            registered.add(family)
    if "kind:parameter_maximumforkindin(1201,1202)" in runtime_source:
        registered.update((1201, 1202))
    optional = {300, 301, 302, 340, 331, 422}
    entry = re.sub(
        r"\s+",
        "",
        ast.unparse(
            ast.parse(
                (ROOT / "server/wakfu_server/combat/combat_server_spell.py").read_text()
            )
        ),
    )
    wired = registered | (
        optional if "displacement_authority=actors" in entry else set()
    )
    state_links = {}
    for key, effect in effects.items():
        refs = set()
        if effect["effect_class"] in (304, 321):
            for values in effect.get("parameters_by_level", []):
                if values:
                    refs.add(str(int(values[0])))
            if not refs and effect.get("parameter0_by_level"):
                refs.update(str(int(v)) for v in effect["parameter0_by_level"])
        state_links[key] = refs
    state_roots = {
        key: set(map(str, row.get("effect_ids", [])))
        | {str(e) for level in row.get("levels", []) for e in level.get("effects", [])}
        for key, row in state_data["states"].items()
    }

    def closure(roots):
        pending = list(map(str, roots))
        seen = set()
        states = set()
        missing = set()
        while pending:
            key = pending.pop()
            if key in seen:
                continue
            seen.add(key)
            effect = effects.get(key)
            if effect is None:
                missing.add("effect:" + key)
                continue
            pending.extend(map(str, effect.get("children", [])))
            for state in state_links[key]:
                if state in states:
                    continue
                states.add(state)
                if state not in state_roots:
                    missing.add("state:" + state)
                pending.extend(state_roots.get(state, ()))
        return seen, states, missing

    rows = []
    family_users = defaultdict(list)
    for spell in sorted(spell_data, key=lambda r: (r["breed"], r["kind"], r["id"])):
        key = str(spell["id"])
        profile = tree["spells"].get(key)
        roots = (
            sorted({e for level in profile.get("levels", []) for e in level[2]})
            if profile
            else []
        )
        reachable, states, missing = closure(roots)
        families = sorted(
            {effects[e]["effect_class"] for e in reachable if e in effects}
        )
        unsupported = sorted(set(families) - wired)
        name = names.get(key, {})
        name = name.get("name") if isinstance(name, dict) else name
        notes = review.get("spells", {}).get(key, {})
        row = {
            **spell,
            "name": name or f"Nombre pendiente ({key})",
            "root_effects": roots,
            "level_roots": profile.get("levels", []) if profile else [],
            "effect_refs": sorted(map(int, reachable)),
            "states": sorted(map(int, states)),
            "families": families,
            "families_without_entry": unsupported,
            "missing_definitions": sorted(missing),
            "criteria": sorted(
                {
                    effects[e]["criteria"]
                    for e in reachable
                    if e in effects and effects[e]["criteria"]
                }
            ),
            "review_status": notes.get("status", "Sin revisión individual"),
            "game_verified": notes.get("game_verified", False),
            "evidence": notes.get("evidence", []),
            "owner": notes.get("owner", "Sin asignar"),
            "next_test": notes.get(
                "next_test",
                "Verificar efecto por efecto en combate, ramas y condiciones.",
            ),
            "notes": notes.get("notes", ""),
            "review": notes,
        }
        rows.append(row)
        for family in families:
            family_users[family].append(spell["id"])
    assert len(rows) == len(spell_data) == len({r["id"] for r in rows})
    definitions = Counter(e["effect_class"] for e in effects.values())
    spell_families = set(e["effect_class"] for e in tree["effects"].values())
    family_rows = []
    for family, count in sorted(definitions.items()):
        status = "Sin manejador"
        if family in registered:
            status = "Implementación parcial; conectada en código"
        elif family in optional:
            status = "Implementación parcial; falta conectar entrada"
        notes = review.get("families", {}).get(str(family), {})
        module = (
            "combat_effect_dispatch.py"
            if family in (330, 844, 949, 999, 1076)
            else "combat_state_handler.py"
            if family == 304
            else "combat_state_decurse.py"
            if family == 321
            else "combat_damage_handler.py"
            if family in damage_ids
            else "combat_healing_handler.py"
            if family in heal_ids
            else "combat_stat_handler.py"
            if str(family) in registry
            else "combat_displacement.py"
            if family in optional
            else None
        )
        family_rows.append(
            {
                "family": family,
                "definitions": count,
                "in_spell_catalog": family in spell_families,
                "spell_ids": family_users[family],
                "registration": status,
                "implementation_file": f"server/wakfu_server/combat/{module}"
                if module
                else None,
                "runner": registry.get(str(family), {}).get("runner", ""),
                "characteristic_contract": registry.get(str(family), {}),
                "review": notes,
            }
        )
    state_rows = []
    for key, state in sorted(state_data["states"].items(), key=lambda r: int(r[0])):
        reachable, dependencies, missing = closure(state_roots[key])
        families = sorted(
            {effects[e]["effect_class"] for e in reachable if e in effects}
        )
        state_rows.append(
            {
                "id": int(key),
                "name": state.get("name"),
                "description": state.get("description"),
                "maximum_level": state.get("maximum_level"),
                "spell_ids": [r["id"] for r in rows if int(key) in r["states"]],
                "root_effects": sorted(map(int, state_roots[key])),
                "families": families,
                "dependencies": sorted(map(int, dependencies)),
                "families_without_entry": sorted(set(families) - wired),
                "missing_definitions": sorted(missing),
                "current_validation": review.get("states", {})
                .get(key, {})
                .get("current_validation", ""),
                "review": review.get("states", {}).get(key, {}),
            }
        )
    effect_rows = []
    for key, effect in sorted(effects.items(), key=lambda r: int(r[0])):
        effect_rows.append(
            {
                "id": int(key),
                **{
                    k: effect.get(k)
                    for k in (
                        "effect_class",
                        "variant",
                        "minimum_level",
                        "maximum_level",
                        "criteria",
                        "parameter_count",
                        "parameters",
                        "children",
                        "native_definition_class",
                        "native_execution_mode",
                        "native_timing_definition",
                        "native_timing_checks",
                        "native_effect_flags",
                        "target_masks",
                        "native_target_selector",
                        "area_native",
                    )
                },
                "referenced_states": sorted(map(int, state_links[key])),
            }
        )
    tests = []
    for path in sorted((ROOT / "server/tests").glob("test_combat*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and node.name.startswith("test"):
                tests.append(
                    {
                        "file": str(path.relative_to(ROOT)),
                        "line": node.lineno,
                        "test": node.name,
                        "execution_status": "No ejecutada por este generador",
                    }
                )
    inputs = [
        PROTOCOL / f
        for f in (
            "spells.json",
            "spell-effect-trees.json",
            "combat-state-definitions.json.gz",
            "effect-characteristic-registry.json",
        )
    ] + [source, ROOT / "server/wakfu_server/combat/combat_server_spell.py"]
    inputs.extend(sorted((ROOT / "server/wakfu_server/combat").glob("*.py")))
    inputs.extend([review_path, Path(__file__).resolve()])
    if names_path.exists():
        inputs.append(names_path)
    if extra_audit_path.exists():
        inputs.append(extra_audit_path)
    sources = {
        (
            str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else p.name
        ): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in inputs
    }
    payload = {
        "schema": 1,
        "scope": "Catálogo de clases del cliente instalado; no todo el catálogo de hechizos de NPC. Dependencias conservadoras de todos los niveles y ramas, no promesa de ejecución.",
        "sources_sha256": sources,
        "summary": {
            "spells": len(rows),
            "active": sum(r["kind"] == "active" for r in rows),
            "passive": sum(r["kind"] == "passive" for r in rows),
            "states": len(state_rows),
            "effects": len(effect_rows),
            "spell_families": len(spell_families),
            "registered_spell_families": len(spell_families & registered),
            "individual_game_verified": sum(r["game_verified"] is True for r in rows),
            "class_linked_extras": len(extra_rows),
        },
        "spells": rows,
        "extra_spells": extra_rows,
        "extra_audit_limits": extra_audit.get("limitations", []),
        "families": family_rows,
        "states": state_rows,
        "effects": effect_rows,
        "tests": tests,
        "systems": review.get("systems", {}),
    }
    (output / "inventory.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
    csv_write(
        output / "hechizos-extra.csv",
        extra_rows,
        [
            "id",
            "name",
            "breeds",
            "grant_paths",
            "tree_exported",
            "review_status",
            "game_verified",
            "owner",
            "next_test",
        ],
    )
    csv_write(
        output / "hechizos.csv",
        rows,
        [
            "id",
            "name",
            "breed",
            "kind",
            "unlock_level",
            "root_effects",
            "states",
            "families",
            "families_without_entry",
            "missing_definitions",
            "criteria",
            "review_status",
            "game_verified",
            "owner",
            "next_test",
            "evidence",
            "notes",
        ],
    )
    csv_write(
        output / "familias.csv",
        family_rows,
        [
            "family",
            "definitions",
            "in_spell_catalog",
            "registration",
            "implementation_file",
            "runner",
            "spell_ids",
            "review",
        ],
    )
    csv_write(
        output / "estados.csv",
        state_rows,
        [
            "id",
            "name",
            "description",
            "maximum_level",
            "spell_ids",
            "root_effects",
            "families",
            "dependencies",
            "families_without_entry",
            "missing_definitions",
            "current_validation",
            "review",
        ],
    )
    csv_write(output / "efectos.csv", effect_rows, list(effect_rows[0]))
    csv_write(
        output / "pruebas.csv", tests, ["file", "line", "test", "execution_status"]
    )
    class_dir = output / "clases"
    class_dir.mkdir(exist_ok=True)
    class_lines = []
    for breed in sorted({r["breed"] for r in rows}):
        spells = [r for r in rows if r["breed"] == breed]
        title = class_names.get(str(breed), f"Clase {breed}").replace("{[1*]?:}", "")
        parts = [
            f"# {title}",
            "",
            "Todos los niveles y ramas están incluidos en las dependencias. Un manejador conectado no demuestra que el hechizo funcione.",
            "",
            "| ID | Nombre | Tipo | Nivel | Familias pendientes de entrada | Revisión | Probado jugando |",
            "|---|---|---|---|---|---|---|",
        ]
        for row in spells:
            parts.append(
                "| "
                + " | ".join(
                    md(v)
                    for v in (
                        row["id"],
                        row["name"],
                        "Activo" if row["kind"] == "active" else "Pasivo",
                        row["unlock_level"],
                        ",".join(map(str, row["families_without_entry"]))
                        or "Sin ausencia detectada; validar límites",
                        row["review_status"],
                        "Sí" if row["game_verified"] else "Pendiente",
                    )
                )
                + " |"
            )
        parts.extend(["", "## Prueba y dependencias por hechizo", ""])
        for row in spells:
            parts.extend(
                [
                    f"### {row['name']} ({row['id']})",
                    "",
                    f"- Estado: {row['review_status']}. Responsable: {row['owner']}.",
                    f"- Raíces: {row['root_effects']}. Familias: {row['families']}.",
                    f"- Estados relacionados: {row['states']}.",
                    f"- Condiciones: {row['criteria'] or 'Ninguna condición escrita en las dependencias; siguen aplicando reglas de lanzamiento/objetivo.'}",
                    f"- Definiciones ausentes: {row['missing_definitions'] or 'Ninguna detectada'}.",
                    f"- Siguiente prueba: {row['next_test']}",
                    f"- Evidencia: {row['evidence'] or 'Sin prueba individual registrada'}.",
                    f"- Notas: {row['notes'] or 'Pendiente revisión individual'}.",
                    "",
                ]
            )
        class_extras = [row for row in extra_rows if breed in row["breeds"]]
        if class_extras:
            parts.extend(
                [
                    "## Hechizos extra otorgados",
                    "",
                    "Rutas explícitas identificadas; no se afirma que todas las transformaciones estén cubiertas. El estado de revisión es independiente del catálogo normal.",
                    "",
                    "| ID | Nombre | Revisión | Probado jugando |",
                    "|---|---|---|---|",
                ]
            )
            for row in class_extras:
                parts.append(
                    "| "
                    + " | ".join(
                        md(value)
                        for value in (
                            row["id"],
                            row["name"],
                            row["review_status"],
                            "Sí" if row["game_verified"] else "Pendiente",
                        )
                    )
                    + " |"
                )
            parts.append("")
            for row in class_extras:
                parts.extend(
                    [
                        f"### {row['name']} ({row['id']}, extra)",
                        "",
                        f"- Responsable: {row['owner']}. Estado: {row['review_status']}.",
                        f"- Siguiente prueba: {row['next_test']}",
                        f"- Evidencia: {row['review'].get('evidence', []) or 'Sin prueba individual registrada'}.",
                        "",
                    ]
                )
        (class_dir / f"{breed}.md").write_text("\n".join(parts) + "\n")
        class_lines.append(
            f"| [{title}](clases/{breed}.md) | {sum(r['kind']=='active' for r in spells)} | {sum(r['kind']=='passive' for r in spells)} | {sum(r['game_verified'] is True for r in spells)} |"
        )
    priority = sorted(
        (r for r in family_rows if r["family"] not in wired and r["spell_ids"]),
        key=lambda r: (-len(r["spell_ids"]), r["family"]),
    )
    csv_write(
        output / "prioridades.csv",
        [
            {
                "family": r["family"],
                "affected_spells": len(r["spell_ids"]),
                "registration": r["registration"],
                "spell_ids": r["spell_ids"],
            }
            for r in priority
        ],
        ["family", "affected_spells", "registration", "spell_ids"],
    )
    summary = payload["summary"]
    text = [
        "# Inventario de combate y seguimiento",
        "",
        f"Hay **{summary['spells']} hechizos de clase**: {summary['active']} activos y {summary['passive']} pasivos. Incluye **{summary['states']} estados**, **{summary['effects']} definiciones de efectos** y **{len(family_rows)} familias** contando los estados.",
        "",
        f"Además se siguen **{len(extra_rows)} hechizos extra** otorgados por estados, innatas y otras rutas explícitas en [hechizos-extra.csv](hechizos-extra.csv). Sus rutas y revisión individual figuran en inventory.json. Esta lista todavía no acredita cobertura exhaustiva de transformaciones ni referencias dinámicas; no se incluyen en las cifras de ejecución del catálogo normal.",
        "",
        f"**{summary['registered_spell_families']} de {summary['spell_families']} familias de los árboles de hechizos tienen ruta de ejecución registrada. Esto NO es el porcentaje de hechizos terminados.** La implementación tiene límites; las pasivas necesitan además sus eventos e instalación. Hechizos con prueba individual completa registrada: **{summary['individual_game_verified']}**. Las victorias previas no se convierten automáticamente en pruebas completas de cada hechizo.",
        "",
        "Que una ruta exista en código no demuestra que esté cargada ni probada jugando. Consultar el reporte de progreso para conocer el último despliegue y sus verificaciones.",
        "",
        "## Cómo evitar repetir trabajo",
        "",
        "- Consultar primero esta tabla, el detalle de clase y las evidencias en review.json.",
        "- Escribir responsable, estado, evidencia, límites y siguiente prueba en [review.json](review.json). El generador nunca lo modifica si ya existe.",
        "- Repetir una prueba solo si cambia su código/dependencia, aparece un fallo o queda pendiente un caso.",
        "- Regenerar con `python3 server/tools/build_spell_inventory.py`. Las huellas SHA256 identifican las fuentes exactas de cada inventario.",
        "- Revisar el [historial existente](../progress.txt) antes de abrir otra investigación.",
        "",
        "Para dar un hechizo por comprobado, su evidencia debe indicar fecha, personaje/nivel/equipo, escenario, resultado esperado, resultado observado y casos pendientes. Usar estados: Sin revisión individual → En análisis → Implementado parcialmente → Listo para probar → Probado en juego. Si falla, registrar el caso concreto; conservar la evidencia anterior. Las notas pueden contener campos adicionales: el inventario mantiene el objeto review completo.",
        "",
        "## Clases",
        "",
        "| Clase | Activos | Pasivos | Prueba completa individual |",
        "|---|---|---|---|",
        *class_lines,
        "",
        "## Prioridades comunes",
        "",
        "Familias sin ruta de entrada, ordenadas por número de hechizos relacionados. Dependencias conservadoras; el orden no demuestra que implementar una familia baste para completar esos hechizos.",
        "",
        "| Familia | Hechizos relacionados | Estado |",
        "|---|---|---|",
        *[
            f"| {r['family']} | {len(r['spell_ids'])} | {r['registration']} |"
            for r in priority[:15]
        ],
        "",
        "[Lista completa de prioridades](prioridades.csv)",
        "",
        "## Archivos completos",
        "",
        "- [Hechizos](hechizos.csv): uno por hechizo, con estados, condiciones, familias, responsable y siguiente prueba.",
        "- [Familias](familias.csv): cobertura de implementación y hechizos afectados.",
        "- [Estados](estados.csv): nombre, descripción y dependencias.",
        "- [Efectos](efectos.csv): identidad nativa, parámetros, objetivos, área, reloj y banderas.",
        "- [Pruebas](pruebas.csv): funciones existentes; su presencia no implica que se hayan ejecutado o pasado.",
        "- [Inventario JSON](inventory.json): relaciones completas y huellas de fuentes.",
        "",
        "## Inconsistencias detectadas",
        "",
        f"{sum(bool(r['missing_definitions']) for r in state_rows)} estados contienen referencias candidatas ausentes del catálogo. No se ocultaron ni se rellenaron con datos inventados: aparecen en estados.csv. Se deben revisar los parámetros dinámicos y la interpretación antes de concluir que falta un estado real. Ninguno de los 722 hechizos de clase tiene una dependencia ausente detectada por este recorrido.",
        "",
        "## Límites de este inventario",
        "",
        "Las dependencias incluyen todas las ramas y niveles, aunque algunas sean excluyentes. No se infiere comportamiento por nombres ni se considera una familia implementada como soporte completo. Las referencias de estados se extraen de los parámetros nativos304/321; otros mecanismos dinámicos requieren revisión manual. Invocaciones, zonas, desbloqueos y eventos no quedan resueltos por extraer el catálogo. El catálogo de clases no cubre todos los hechizos propios de monstruos.",
        "",
    ]
    for key, system in review.get("systems", {}).items():
        text.extend(
            [
                f"### {system.get('name',key)}",
                "",
                f"Estado: {system.get('status','Pendiente')}. {system.get('notes','')}",
                f"Evidencia: {system.get('evidence',[])}",
                f"Siguiente paso: {system.get('next','Pendiente')}",
                "",
            ]
        )
    audit_path = output / "class-initialization-audit.json"
    if audit_path.exists():
        audit = read(audit_path)
        cases = {(row["breed"], row["level"]): row for row in audit["rows"]}
        text.extend(
            [
                "## Prueba interna de inicialización por clase",
                "",
                "Nivel 1 prueba las innatas. Nivel 200 añade las primeras seis pasivas válidas de la clase. Pasar significa que se instalaron sus efectos; no demuestra activación de eventos ni hechizos completos jugando.",
                "",
                "| Clase | Nivel 1 | Nivel 200 |",
                "|---|---|---|",
            ]
        )

        def result(row):
            if row is None:
                return "Sin prueba"
            if row["status"] == "initialized":
                return "Instalación interna aprobada"
            identity = row.get("effect_reference") or row.get("innate_reference")
            family = row.get("effect_class")
            return (
                "Bloqueada"
                + (f": efecto/estado {identity}" if identity else "")
                + (f" (familia {family})" if family else "")
            )

        for breed in sorted({key[0] for key in cases}):
            title = class_names.get(str(breed), f"Clase {breed}").replace(
                "{[1*]?:}", ""
            )
            text.append(
                "| "
                + " | ".join(
                    (
                        md(title),
                        result(cases.get((breed, 1))),
                        result(cases.get((breed, 200))),
                    )
                )
                + " |"
            )
        text.extend(
            [
                "",
                "[Detalle de casos y errores](class-initialization-audit.csv). La tabla corresponde a la última ejecución guardada; las correcciones posteriores requieren repetir los casos.",
                "",
            ]
        )
    (output / "README.md").write_text("\n".join(text) + "\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUT)
    main(parser.parse_args().output)
