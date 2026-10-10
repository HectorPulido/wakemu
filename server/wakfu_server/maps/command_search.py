"""Bounded development-chat lookup over published native item and mob names."""
from difflib import SequenceMatcher
from functools import lru_cache
import math
import re
import unicodedata

PAGE_SIZE = 8
MAX_QUERY_LENGTH = 120


def normalize(value):
    decomposed = unicodedata.normalize("NFKD", str(value).casefold())
    return " ".join(
        re.findall(
            r"[^\W_]+",
            "".join(
                character
                for character in decomposed
                if not unicodedata.combining(character)
            ),
        )
    )


def build_index(items, monsters):
    entries = []
    for kind, records, key in (("item", items, "reference"), ("mob", monsters, "ref")):
        for record in records:
            reference = int(record[key])
            if reference <= 0:
                continue
            name = record.get("name") or f"{kind} {reference}"
            entry = dict(kind=kind, id=reference, name=name, normalized=normalize(name))
            if kind == "mob":
                entry.update(
                    min_level=record.get("min_level"), max_level=record.get("max_level")
                )
            entries.append(entry)
    return tuple(entries)


@lru_cache(maxsize=1)
def native_index():
    from .inventory_move import STACKS
    from .monsters import REFERENCES

    return build_index(STACKS.values(), REFERENCES.values())


def _score(query, entry):
    name = entry["normalized"]
    if query.isdecimal():
        return 1.0 if query == str(entry["id"]) else 0.0
    if query == name:
        return 1.0
    if query in name:
        return 0.96 if query in name.split() else 0.93
    tokens = name.split()
    query_tokens = query.split()
    # Every requested word needs a plausible match; extra name words are allowed.
    token_score = sum(
        max((SequenceMatcher(None, word, token).ratio() for token in tokens), default=0)
        for word in query_tokens
    ) / len(query_tokens)
    return max(token_score * 0.90, SequenceMatcher(None, query, name).ratio() * 0.89)


def search(query, *, kind="all", page=1, index=None):
    """Return a stable, paginated chat response without mutating game state."""
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= MAX_QUERY_LENGTH:
        raise ValueError("Escribe un nombre o ID de hasta 120 caracteres")
    query_normalized = normalize(query)
    if not query_normalized:
        raise ValueError("Escribe un nombre o ID")
    aliases = {
        "all": "all",
        "todo": "all",
        "item": "item",
        "items": "item",
        "objeto": "item",
        "objetos": "item",
        "mob": "mob",
        "mobs": "mob",
        "monstruo": "mob",
        "monstruos": "mob",
    }
    kind = aliases.get(normalize(kind))
    if kind is None:
        raise ValueError("Filtro de búsqueda: item, mob o all")
    if type(page) is not int or not 1 <= page <= 10000:
        raise ValueError("Página de búsqueda inválida")
    ranked = []
    for entry in native_index() if index is None else index:
        if kind != "all" and kind != entry["kind"]:
            continue
        score = _score(query_normalized, entry)
        if score >= 0.59:
            ranked.append((score, entry))
    ranked.sort(
        key=lambda row: (
            -row[0],
            len(row[1]["normalized"]),
            row[1]["normalized"],
            row[1]["kind"],
            row[1]["id"],
        )
    )
    pages = max(1, math.ceil(len(ranked) / PAGE_SIZE))
    if page > pages:
        raise ValueError(f"Solo hay {pages} páginas de resultados")
    matches = [
        dict(entry) for _, entry in ranked[(page - 1) * PAGE_SIZE : page * PAGE_SIZE]
    ]
    lines = [
        f"Búsqueda: {query.strip()[:MAX_QUERY_LENGTH]} | {len(ranked)} coincidencias | página {page}/{pages}"
    ]
    for entry in matches:
        label = "objeto" if entry["kind"] == "item" else "mob"
        levels = ""
        if entry["kind"] == "mob" and entry.get("min_level") is not None:
            levels = f" (nivel {entry['min_level']}-{entry['max_level']})"
        lines.append(f"[{label}] {entry['id']}: {entry['name'][:80]}{levels}")
    if not matches:
        lines.append("Sin coincidencias; prueba una palabra más corta")
    return dict(
        message="\n".join(lines),
        matches=matches,
        total=len(ranked),
        page=page,
        pages=pages,
    )
