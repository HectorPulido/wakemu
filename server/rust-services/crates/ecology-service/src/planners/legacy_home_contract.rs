//! Frozen regression scenarios from the retired Python pre-send validator.
//! Coordinates are translated by -1 on X to put its x <= 0 home boundary
//! exactly on the native 18-cell territory grid rather than mocking authority.
use super::*;
use rand::{rngs::StdRng, SeedableRng};

fn p(x: i64) -> Point {
    [x - 1, 0, 0]
}
fn actor(id: i64, at: Point) -> Value {
    json!({"id":id,"ref":4,"level":10,"x":at[0],"y":at[1],"z":at[2]})
}
fn terrain() -> TerrainPolicy {
    let mut regions = HashMap::new();
    for x in -2..=18 {
        for y in -1..=1 {
            regions.insert([x, y], if x < 0 { 11 } else { 22 });
        }
    }
    TerrainPolicy {
        regions,
        surfaces: HashMap::new(),
        has_map: true,
        outdoor: false,
        authority: "legacy-home-native-grid".into(),
    }
}
fn graph(edges: &[(i64, i64)]) -> Geometry {
    let edges: Vec<_> = edges.iter().map(|(a, b)| (p(*a), p(*b))).collect();
    let cells: BTreeSet<_> = edges.iter().flat_map(|(a, b)| [*a, *b]).collect();
    geometry(&json!({"cells":cells,"edges":edges})).unwrap()
}
fn movement(path: &[i64], flag: Option<&str>) -> Value {
    let points: Vec<_> = path.iter().map(|x| p(*x)).collect();
    let mut row = json!({"group_id":17,"expected_members":[actor(-1,points[0])],
        "moved_members":[actor(-1,*points.last().unwrap())],
        "packets":[[13852,hex::encode(movement_packet(-1,&points).unwrap())]]});
    if let Some(flag) = flag {
        row[flag] = json!(true);
    }
    row
}
fn allowed(indexed: &Geometry, row: &Value, radius: i64) -> bool {
    let (_, expected, moved, paths) = validate_move(row).unwrap();
    queued_movement_allowed(
        indexed,
        &terrain(),
        11,
        &[radius],
        &expected,
        &moved,
        &paths,
    )
    .unwrap()
}

#[test]
fn long_displaced_native_route_is_planned_and_accepted_without_leaving_home_again() {
    let mut edges: Vec<_> = (1..=301).map(|x| (x, x - 1)).collect();
    edges.push((300, 301));
    let indexed = graph(&edges);
    let policy = terrain();
    let result = homing_path(
        &[actor(-1, p(300))],
        &[[299, 3, 0]],
        &indexed,
        &HashSet::new(),
        20,
        8,
        8,
        &policy.authority,
        11,
        &[0],
        &|at| policy.home_allowed(Some(11), at, &[0]),
        &|_| true,
        &mut StdRng::seed_from_u64(17),
    )
    .unwrap()
    .unwrap();
    assert_eq!(point(&result.members[0]).unwrap(), p(292));
    assert_eq!(decode_packet(&result.packets[0]).unwrap().2.len(), 8);
    let row = json!({"group_id":17,"expected_members":[actor(-1,p(300))],
        "moved_members":result.members,"packets":result.packets});
    assert!(allowed(&indexed, &row, 0));
    assert!(!allowed(&indexed, &movement(&[300, 301], None), 0));
}

#[test]
fn old_roaming_and_escape_markers_cannot_leave_home() {
    let indexed = graph(&[(0, 1), (0, -1)]);
    for flag in [None, Some("dispersal"), Some("overlap_escape")] {
        assert!(!allowed(&indexed, &movement(&[0, 1], flag), 0));
        assert!(allowed(&indexed, &movement(&[0, -1], flag), 0));
    }
    // Single and bulk wander dispatch share this exact production kernel.
    assert!(!allowed(&indexed, &movement(&[0, 1], None), 0));
}

#[test]
fn displaced_queue_can_only_get_closer_then_stay_home_on_native_edges() {
    let indexed = graph(&[(2, 1), (1, 0), (2, 3), (3, 2), (0, 1)]);
    assert!(allowed(&indexed, &movement(&[2, 1, 0], None), 0));
    assert!(!allowed(&indexed, &movement(&[2, 3], None), 0));
    assert!(!allowed(&indexed, &movement(&[2, 1, 0, 1], None), 0));
    assert!(!allowed(&graph(&[]), &movement(&[0, -1], None), 0));
}

#[test]
fn homing_uses_whole_footprint_when_center_already_appears_inside() {
    let policy = terrain();
    assert!(policy.home_allowed(Some(11), p(0), &[0]));
    assert!(!policy.home_allowed(Some(11), p(0), &[1]));
    assert!(allowed(&graph(&[(0, -1)]), &movement(&[0, -1], None), 1));
}

#[test]
fn reproduction_and_bulk_reproduction_require_child_home() {
    let policy = terrain();
    // Both direct and lifecycle-bulk dispatch call this production kernel.
    for (x, expected) in [(-1, true), (1, false)] {
        let child = actor(-2, p(x));
        assert_eq!(
            queued_reproduction_allowed(&policy, 11, p(x), Some(&child), 0).unwrap(),
            expected
        );
    }
    let child = actor(-2, p(-1));
    assert!(!queued_reproduction_allowed(&policy, 11, p(0), Some(&child), 0).unwrap());
    assert!(!queued_reproduction_allowed(&policy, 11, p(0), Some(&actor(-2, p(0))), 1).unwrap());
}
