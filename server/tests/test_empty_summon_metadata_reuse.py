"""Bounded validation and isolated publication for empty summon headers."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from copy import deepcopy

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from tools import publish_compiled_combat_catalog as compiled_publisher
from tools import publish_empty_summon_metadata as header_publisher
from wakfu_server.native_compiled_catalog import canonical_bytes


ROOT = Path(__file__).resolve().parents[2]
PROFILES = ("3206", "3239", "3240")
ABILITY_DOC = "native-class-summon-abilities.json"
INITIAL_DOC = "native-class-summon-initial-states.json"
PROPERTIES_DOC = "native-actor-properties.json"
STATE = {
    "name": "IA Larva",
    "levels": [{"effects": [120672, 120749], "duration": -1}],
}
EFFECTS = {
    "120672": {"effect_class": 400, "children": []},
    "120749": {"effect_class": 400, "children": []},
}


def _summon_documents(*, added=True, bad_abilities=None, bad_state=None):
    abilities = {"profiles": {}, "npc_dependency_exports": []}
    initial = {"profiles": {}, "npc_dependency_exports": []}
    if added:
        abilities["profiles"].update(
            {profile: {"abilities": []} for profile in PROFILES}
        )
        initial["profiles"].update(
            {
                profile: {
                    "initial_state_triples": [3127, 1, 0],
                    "fight_properties": [15, 93, 51, 78, 28, 94, 69, 92],
                }
                for profile in PROFILES
            }
        )
        for document in (abilities, initial):
            document["npc_dependency_exports"] = [
                {"added_profile_ids": [3206, 3239, 3240]}
            ]
    if bad_abilities is not None:
        abilities["profiles"][PROFILES[0]] = bad_abilities
    if bad_state is not None:
        initial["profiles"][PROFILES[0]]["initial_state_triples"] = bad_state
    return {ABILITY_DOC: abilities, INITIAL_DOC: initial}


def _native_properties():
    audit = json.loads(
        (
            ROOT
            / ".runtime/quest-archetypes/pizza/candidate-native-source/fresh-summon-three-profile-audit.json"
        ).read_text()
    )
    return {
        row["record_key"]: row["payload"]
        for row in audit
        if row["path"] == PROPERTIES_DOC
        and row["collection"] == "npc"
        and row["record_key"] in PROFILES
    }


def _source_raw(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


class EmptySummonMetadataQualificationTests(unittest.TestCase):
    def setUp(self):
        self.before = _summon_documents(added=False)
        self.after = _summon_documents()
        self.previous = {
            "policy": "isolated-empty-summon-metadata-v1",
            "source_revision": "a" * 64,
            "source_inventory_sha256": "b" * 64,
            "compiler_contract_sha256": "c" * 64,
            "config_sha256": "d" * 64,
            "compiler_sources": {"tools/compiler.py": "e" * 64},
            "config": {"fight_policy": "unchanged"},
            "source_documents": {
                name: _sha(_source_raw(document))
                for name, document in self.before.items()
            },
        }
        self.identity = deepcopy(self.previous)
        self.identity.update(
            source_revision="f" * 64,
            source_inventory_sha256="1" * 64,
            source_documents={
                name: _sha(_source_raw(document))
                for name, document in self.after.items()
            },
        )

    def test_empty_books_and_original3127_are_the_only_additive_profile_changes(self):
        proof = header_publisher.qualify(
            self.previous,
            self.identity,
            self.before,
            self.after,
            states={"3127": STATE},
            effect_ids={120672, 120749},
            properties=_native_properties(),
        )
        self.assertEqual(
            proof, {"profile_ids": [3206, 3239, 3240], "state_ids": [3127]}
        )

        changed_existing = deepcopy(self.after)
        changed_existing[ABILITY_DOC]["profiles"]["3206"]["abilities"] = [
            {"spell_id": 999}
        ]
        with self.assertRaisesRegex(ValueError, "Only exact empty"):
            header_publisher.qualify(
                self.previous,
                self.identity,
                self.before,
                changed_existing,
                states={"3127": STATE},
                effect_ids={120672, 120749},
                properties=_native_properties(),
            )

        nonempty_book = deepcopy(self.after)
        nonempty_book[ABILITY_DOC]["profiles"]["3206"] = {
            "abilities": [{"spell_id": 1}]
        }
        with self.assertRaisesRegex(ValueError, "Only exact empty"):
            header_publisher.qualify(
                self.previous,
                self.identity,
                self.before,
                nonempty_book,
                states={"3127": STATE},
                effect_ids={120672, 120749},
                properties=_native_properties(),
            )

        new_root_state = {"3127": {"levels": [{"effects": [999999]}]}}
        with self.assertRaisesRegex(ValueError, "new uncompiled root"):
            header_publisher.qualify(
                self.previous,
                self.identity,
                self.before,
                self.after,
                states=new_root_state,
                effect_ids={120672, 120749},
                properties=_native_properties(),
            )


class FreshSummonSourceAssemblerTests(unittest.TestCase):
    def test_original307_profile_graph_adds_both_books_with_only_complete_metadata(
        self,
    ):
        from tools.stage_encounter_morph_catalog import fresh_summon_outputs

        properties = _native_properties()["3206"]["fight_properties"]
        graph = [
            {
                "kind": "effect",
                "family": 307,
                "classified_reference_samples": [
                    {"kind": "profile", "reference": 3206, "sample_level": 0}
                ],
            },
            {
                "kind": "profile",
                "reference": 3206,
                "native_ability_profile": {
                    "profile_id": 3206,
                    "abilities": [],
                    "initial_state_triples": [3127, 1, 0],
                    "fight_properties": properties,
                },
            },
        ]
        base = {
            ABILITY_DOC: {"profiles": {}, "npc_dependency_exports": []},
            INITIAL_DOC: {"profiles": {}, "npc_dependency_exports": []},
        }
        provenance = {
            "original_inputs_stable": True,
            "source": "test fixture from original307 classified graph",
        }
        documents, ids = fresh_summon_outputs(graph, base, provenance)
        self.assertEqual(ids, [3206])
        self.assertEqual(documents[ABILITY_DOC]["profiles"]["3206"], {"abilities": []})
        self.assertEqual(
            documents[INITIAL_DOC]["profiles"]["3206"],
            {"initial_state_triples": [3127, 1, 0], "fight_properties": properties},
        )

        incomplete = deepcopy(graph)
        del incomplete[1]["native_ability_profile"]["fight_properties"]
        with self.assertRaisesRegex(ValueError, "complete fresh constructor metadata"):
            fresh_summon_outputs(incomplete, base, provenance)

        conflicting = deepcopy(base)
        conflicting[ABILITY_DOC]["profiles"]["3206"] = {
            "abilities": [{"spell_id": 999}]
        }
        with self.assertRaisesRegex(ValueError, "conflicts with existing"):
            fresh_summon_outputs(graph, conflicting, provenance)

        unstable = dict(provenance, original_inputs_stable=False)
        with self.assertRaisesRegex(
            ValueError, "Missing sealed native summon provenance"
        ):
            fresh_summon_outputs(graph, base, unstable)


class EmptySummonMetadataPublicationTests(PostgresCase):
    def _install_native_source(self, db, revision, documents, *, properties=None):
        source_documents = dict(documents)
        if properties is not None:
            source_documents[PROPERTIES_DOC] = {
                "npc": properties,
            }
        encoded = {name: _source_raw(value) for name, value in source_documents.items()}
        db.execute(
            "INSERT INTO native_catalog_releases"
            "(revision,document_count,source_bytes,complete) VALUES(%s,%s,%s,false)",
            (revision, len(encoded), sum(len(raw) for raw in encoded.values())),
        )
        for name, document in source_documents.items():
            raw = encoded[name]
            rows = (
                document.get("profiles", {})
                if name in (ABILITY_DOC, INITIAL_DOC)
                else document.get("npc", {})
            )
            collection = "profiles" if name in (ABILITY_DOC, INITIAL_DOC) else "npc"
            db.execute(
                "INSERT INTO native_catalog_documents"
                "(revision,path,raw,sha256,source_bytes,record_count) VALUES(%s,%s,%s,%s,%s,%s)",
                (revision, name, raw, _sha(raw), len(raw), len(rows)),
            )
            for key, payload in rows.items():
                db.execute(
                    "INSERT INTO native_catalog_records"
                    "(revision,path,collection,record_key,payload) VALUES(%s,%s,%s,%s,%s)",
                    (revision, name, collection, key, Jsonb(payload)),
                )
        db.execute(
            "UPDATE native_catalog_releases SET complete=true WHERE revision=%s",
            (revision,),
        )
        return {name: _sha(raw) for name, raw in encoded.items()}

    def test_derived_header_keeps_sealed_contents_and_adds_only_valid_native_metadata(
        self,
    ):
        before, after = _summon_documents(added=False), _summon_documents()
        properties = _native_properties()
        old_revision, new_revision = "a" * 64, "b" * 64
        with self.store.connection() as db:
            old_hashes = self._install_native_source(db, old_revision, before)
            new_hashes = self._install_native_source(
                db, new_revision, after, properties=properties
            )

            with tempfile.TemporaryDirectory() as temporary:
                spool = compiled_publisher.PublicationSpool(
                    str(Path(temporary) / "compiled.sqlite")
                )
                self.addCleanup(spool.db.close)
                spool.collection("fixture.states", {"3127": STATE})
                spool.collection(
                    "fixture.effects", EFFECTS, representation="frozen_effect"
                )
                previous = {
                    "policy": "isolated-empty-summon-metadata-v1",
                    "source_revision": old_revision,
                    "source_inventory_sha256": "c" * 64,
                    "compiler_contract_sha256": "d" * 64,
                    "config_sha256": "e" * 64,
                    "compiler_sources": {"tools/compiler.py": "f" * 64},
                    "config": {"fight_policy": "unchanged"},
                    "source_documents": old_hashes,
                    "states": "fixture.states",
                    "variants": {"native": {"effects": "fixture.effects"}},
                    "collections": spool.collections,
                }
                previous_generation = compiled_publisher.publish(
                    db, spool, previous, canonical_bytes
                )

            identity = dict(
                previous,
                source_revision=new_revision,
                source_inventory_sha256="1" * 64,
                source_documents={
                    name: new_hashes[name] for name in (ABILITY_DOC, INITIAL_DOC)
                },
            )
            original_contents = db.execute(
                "SELECT collection,content_id,record_count FROM native_compiled_catalog_collections "
                "WHERE generation=%s ORDER BY collection",
                (previous_generation,),
            ).fetchall()
            published = header_publisher.publish(
                db, previous_generation, identity, canonical_bytes
            )
            self.assertEqual(published["proof"]["profile_ids"], [3206, 3239, 3240])
            self.assertEqual(published["proof"]["state_ids"], [3127])
            header = db.execute(
                "SELECT manifest_raw,complete FROM native_compiled_catalog_releases WHERE generation=%s",
                (published["generation"],),
            ).fetchone()
            self.assertTrue(header["complete"])
            self.assertEqual(
                _sha(bytes(header["manifest_raw"])), published["generation"]
            )
            new_contents = db.execute(
                "SELECT collection,content_id,record_count FROM native_compiled_catalog_collections "
                "WHERE generation=%s ORDER BY collection",
                (published["generation"],),
            ).fetchall()
            self.assertEqual(new_contents, original_contents)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_compiled_catalog_records WHERE generation=%s",
                    (previous_generation,),
                ).fetchone()["n"],
                3,
            )
