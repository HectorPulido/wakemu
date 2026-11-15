//! Migrated compact/scattered roster and one-group batch contracts.
use super::*;
use rand::{rngs::StdRng, SeedableRng};

fn actor(id: i64, x: i64, y: i64) -> Value {
    json!({"id":id,"ref":6,"x":x,"y":y,"z":0,"level":4})
}
fn graph(edges: &[(Point, Point)]) -> Geometry {
    let cells: BTreeSet<_> = edges.iter().flat_map(|(a, b)| [*a, *b]).collect();
    geometry(&json!({"cells":cells,"edges":edges})).unwrap()
}
fn plan(
    roster: &[Value],
    players: &[Point],
    indexed: &Geometry,
    occupied: &HashSet<Point>,
    allowed: &impl Fn(Point) -> bool,
) -> Option<MovePlan> {
    group_path(
        roster,
        players,
        &[],
        indexed,
        occupied,
        20,
        1,
        1,
        allowed,
        &mut StdRng::seed_from_u64(17),
    )
    .unwrap()
}

#[test]
fn one_group_admission_and_plan_produce_eight_member_packets_in_one_batch() {
    let roster: Vec<_> = (0..8).map(|i| actor(-i - 1, i % 4, i / 4)).collect();
    let edges: Vec<_> = roster
        .iter()
        .map(|member| {
            let a = point(member).unwrap();
            (a, [a[0], a[1] + 1, 0])
        })
        .collect();
    let indexed = graph(&edges);
    let mut draws = 0;
    assert!(wander_admitted(false, true, 1.0, || {
        draws += 1;
        0.0
    }));
    assert_eq!(draws, 1);
    let result = plan(&roster, &[[10, 10, 0]], &indexed, &HashSet::new(), &|_| {
        true
    })
    .unwrap();
    assert_eq!(result.packets.len(), 8);
    for (old, new) in roster.iter().zip(&result.members) {
        assert_eq!(
            point(new).unwrap(),
            [point(old).unwrap()[0], point(old).unwrap()[1] + 1, 0]
        );
    }
    let config = json!({"move_probability":1.0,"radius":20,"min_steps":1,"max_steps":1});
    let mut batch = WanderBatch::new("cohesion", [527, 0], &config);
    assert!(batch.append(1, &roster, &result).unwrap());
    assert_eq!(batch.moved_members, 8);
    assert_eq!(batch.moves.len(), 1);
    assert_eq!(batch.moves[0]["packets"].as_array().unwrap().len(), 8);
    assert_eq!(roster[0]["y"], 0);
}

#[test]
fn compact_translation_keeps_offsets_and_missing_edge_never_becomes_a_native_step() {
    let roster = [actor(-1, 0, 0), actor(-2, 0, 1)];
    let indexed = graph(&[([0, 0, 0], [1, 0, 0]), ([0, 1, 0], [1, 1, 0])]);
    let result = plan(&roster, &[[10, 0, 0]], &indexed, &HashSet::new(), &|_| true).unwrap();
    assert_eq!(
        member_points(&result.members).unwrap(),
        vec![[1, 0, 0], [1, 1, 0]]
    );
    assert_eq!(result.packets.len(), 2);
    let missing = graph(&[([0, 0, 0], [1, 0, 0])]);
    assert!(ordinary_path(
        &roster,
        &[[10, 0, 0]],
        &missing,
        &HashSet::new(),
        20,
        1,
        &|_| true,
        None,
        &mut StdRng::seed_from_u64(1)
    )
    .unwrap()
    .is_none());
    // Current production additionally permits a compact flexible step. It
    // must keep the follower on its native cell and preserve cohesion.
    if let Some(result) = plan(&roster, &[[10, 0, 0]], &missing, &HashSet::new(), &|_| true) {
        assert_eq!(point(&result.members[1]).unwrap(), [0, 1, 0]);
        assert!(
            chebyshev(
                point(&result.members[0]).unwrap(),
                point(&result.members[1]).unwrap()
            ) <= COHESION
        );
    }
}

#[test]
fn scattered_follower_uses_one_native_edge_toward_stationary_leader() {
    let roster = [actor(-1, 0, 0), actor(-2, 8, 0)];
    let indexed = graph(&[([8, 0, 0], [7, 0, 0])]);
    let result = plan(&roster, &[[10, 0, 0]], &indexed, &HashSet::new(), &|_| true).unwrap();
    assert_eq!(
        member_points(&result.members).unwrap(),
        vec![[0, 0, 0], [7, 0, 0]]
    );
    assert_eq!(result.packets.len(), 1);
    let (_, origin, path) = decode_packet(&result.packets[0]).unwrap();
    assert_eq!(origin, [8, 0, 0]);
    assert_eq!(path, vec![[7, 0, 0]]);
    assert!(plan(
        &roster,
        &[[10, 0, 0]],
        &indexed,
        &HashSet::from([[7, 0, 0]]),
        &|_| true
    )
    .is_none());
    assert!(
        plan(&roster, &[[10, 0, 0]], &indexed, &HashSet::new(), &|_| {
            false
        })
        .is_none()
    );
    assert!(plan(&roster, &[], &indexed, &HashSet::new(), &|_| true).is_none());
}

#[test]
fn regrouping_cannot_increase_distance_or_teleport() {
    let roster = [actor(-1, 0, 0), actor(-2, 8, 0)];
    for edges in [
        vec![],
        vec![([8, 0, 0], [9, 0, 0])],
        vec![([8, 0, 0], [0, 0, 0])],
    ] {
        assert!(plan(
            &roster,
            &[[10, 0, 0]],
            &graph(&edges),
            &HashSet::new(),
            &|_| true
        )
        .is_none());
    }
}
