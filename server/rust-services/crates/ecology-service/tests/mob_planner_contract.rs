//! Cross-language boundary fixtures after removing Python monster planning.
//!
//! Rust owns decisions and scheduling. Python's remaining tests exercise World
//! receipts, native reconstruction, terrain, live caps and publication against
//! explicit wire envelopes. Their fixed decision block must be a real Rust
//! lifecycle output, rather than a second Python implementation of that planner.
use serde_json::Value;
use wakemu_ecology::planners::mob_lifecycle;

#[test]
fn python_world_commit_fixture_uses_exact_rust_seeded_decisions() {
    let source = include_str!(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/../../../tests/test_ecology_mobs_prepared_postgres.py"
    ));
    let declaration = source
        .split_once("FROZEN_DECISIONS = json.loads(")
        .expect("World receipt fixture declares its frozen decisions")
        .1;
    let raw = declaration
        .split_once("r\"\"\"")
        .expect("Frozen block is explicit JSON")
        .1
        .split_once("\"\"\"")
        .expect("Frozen block ends")
        .0;
    let rows: Vec<Value> = serde_json::from_str(raw).expect("Valid frozen lifecycle block");
    assert_eq!(rows.len(), 32);
    for (index, stored) in rows.iter().enumerate() {
        let cycle = index as i64 + 1;
        assert_eq!(
            stored,
            &mob_lifecycle::event(&"17".repeat(32), cycle).unwrap(),
            "World fixture cycle {cycle} differs from the Rust decision owner"
        );
    }
    assert!(rows[0]["draw"].as_f64().unwrap() < 0.08);
}
