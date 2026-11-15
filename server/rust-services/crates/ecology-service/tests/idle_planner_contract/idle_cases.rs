//! Four retired test_monster_idle_distribution.py scenarios, plus explicit
//! multi-height/native-connectivity and public preparation-budget contracts.
//! The tests call production Rust prepare; fixtures never choose placements.
use super::*;
use std::collections::{BTreeMap, BTreeSet, HashMap, HashSet, VecDeque};

type Point = [i64; 3];
fn roster(map: i32, gid: i64, x: i64, y: i64, count: usize) -> Vec<Value> {
    (0..count).map(|index|json!({"id":-gid*10-index as i64,"ref":4+index,"level":10+index,"hp":7+index,"max_hp":100+index,"map_id":map,"instance_id":0,"team":1,"x":x+index as i64,"y":y,"z":0})).collect()
}
fn square(size: i64, heights: &[i64]) -> (Vec<Point>, Vec<(Point, Point)>) {
    let mut cells = Vec::new();
    let mut edges = Vec::new();
    for z in heights {
        for x in 0..size {
            for y in 0..size {
                let point = [x, y, *z];
                cells.push(point);
                for (dx, dy) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
                    let next = [x + dx, y + dy, *z];
                    if (0..size).contains(&next[0]) && (0..size).contains(&next[1]) {
                        edges.push((point, next));
                    }
                }
            }
        }
    }
    (cells, edges)
}
async fn geometry(f: &Fixture, map: i32, cells: &[Point], edges: &[(Point, Point)]) -> Result<()> {
    f.document(
        &format!("combat-maps/{map}.json"),
        json!({"map_id":map,"cells":cells,"edges":edges}),
    )
    .await?;
    let grids: BTreeSet<[i64; 2]> = cells
        .iter()
        .map(|p| [p[0].div_euclid(18), p[1].div_euclid(18)])
        .collect();
    f.document("territory-map-cells.json",json!({"schema_version":1,"grid_size":18,"maps":[{"map_id":map,"regions":[{"region_id":11,"cells":grids}]}]})).await?;
    f.document("ecology-regions.json", json!([])).await
}
async fn install(
    f: &Fixture,
    map: i32,
    gid: i64,
    status: &str,
    members: &[Value],
) -> Result<Value> {
    f.group(map, gid, json!(members), 11).await?;
    f.ctx
        .db
        .get()
        .await?
        .execute(
            "UPDATE combat_groups SET status=$1 WHERE map_id=$2 AND group_id=$3",
            &[&status, &map, &gid],
        )
        .await?;
    Ok(json!({"group_id":gid,"status":status,"members":members}))
}
async fn prepare(f: &Fixture, map: i32, epoch: &str) -> Result<Vec<Value>> {
    let snapshot = json!({"world_epoch":epoch,"empty_scopes":[{"map_id":map,"instance_id":0,"empty_generation":1}]});
    let proposals = mob_idle::prepare(&f.ctx, &snapshot, 256).await?;
    let mut moves = Vec::new();
    for proposal in proposals {
        assert!(mob_idle::home_chunk_allowed(&f.ctx, &proposal).await?);
        moves.extend(mob_idle::read_chunk(&f.ctx, &proposal).await?);
    }
    Ok(moves)
}
fn owned_unchanged(before: &Value, after: &Value) {
    let mut before = before.as_object().unwrap().clone();
    let mut after = after.as_object().unwrap().clone();
    for key in ["x", "y", "z"] {
        before.remove(key);
        after.remove(key);
    }
    assert_eq!(before, after);
}
fn final_groups(groups: &[Value], moves: &[Value]) -> Vec<Value> {
    let mut final_groups = groups.to_vec();
    for movement in moves {
        let group = final_groups
            .iter_mut()
            .find(|g| g["group_id"] == movement["group_id"])
            .unwrap();
        assert_eq!(group["members"], movement["expected_members"]);
        let before = movement["expected_members"].as_array().unwrap();
        let after = movement["moved_members"].as_array().unwrap();
        assert_eq!(before.len(), after.len());
        for (old, new) in before.iter().zip(after) {
            assert_eq!(old["id"], new["id"]);
            owned_unchanged(old, new);
        }
        group["members"] = movement["moved_members"].clone();
    }
    final_groups
}
async fn durable_unchanged(f: &Fixture, groups: &[Value]) -> Result<()> {
    let db = f.ctx.db.get().await?;
    let rows: BTreeMap<i64, (Value, String, i64)> = db
        .query(
            "SELECT group_id,members,status,revision FROM combat_groups ORDER BY group_id",
            &[],
        )
        .await?
        .into_iter()
        .map(|row| (row.get(0), (row.get(1), row.get(2), row.get(3))))
        .collect();
    assert_eq!(rows.len(), groups.len());
    for group in groups {
        let row = &rows[&group["group_id"].as_i64().unwrap()];
        assert_eq!(row.0, group["members"]);
        assert_eq!(row.1, group["status"].as_str().unwrap());
        assert_eq!(row.2, 0);
    }
    Ok(())
}
fn connected_native_roster(movement: &Value, edges: &[(Point, Point)]) -> Result<()> {
    let members = movement["moved_members"].as_array().unwrap();
    let anchor = mob_geometry::point(&members[0])?;
    let mut adjacent: HashMap<Point, Vec<Point>> = HashMap::new();
    for (a, b) in edges {
        adjacent.entry(*a).or_default().push(*b);
    }
    let mut seen = HashSet::from([anchor]);
    let mut pending = VecDeque::from([anchor]);
    while let Some(p) = pending.pop_front() {
        for q in adjacent.get(&p).into_iter().flatten() {
            if seen.insert(*q) {
                pending.push_back(*q);
            }
        }
    }
    for member in members {
        let point = mob_geometry::point(member)?;
        assert!(
            seen.contains(&point),
            "Compact roster endpoints must remain natively connected"
        );
        assert!(
            (point[0] - anchor[0])
                .abs()
                .max((point[1] - anchor[1]).abs())
                <= 4
        );
    }
    Ok(())
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn uniform_distribution_covers_map_area_without_corner_only_placement() -> Result<()> {
    let f = Fixture::new().await?;
    let map = 999940i32;
    // One actual native surface per area stratum makes the density assertion
    // independent of production OS randomness, without adding an RNG seam.
    let cells: Vec<Point> = [1, 5, 9, 13]
        .into_iter()
        .flat_map(|x| [1, 5, 9, 13].into_iter().map(move |y| [x, y, 0]))
        .collect();
    geometry(&f, map, &cells, &[]).await?;
    let mut groups = Vec::new();
    for i in 0..16 {
        groups.push(
            install(
                &f,
                map,
                i + 1,
                "available",
                &roster(map, i + 1, -100 + i % 4, -100 + i / 4, 1),
            )
            .await?,
        );
    }
    let moves = prepare(&f, map, "uniform-native-area").await?;
    assert_eq!(moves.len(), 16);
    let final_groups = final_groups(&groups, &moves);
    let points: Vec<Point> = final_groups
        .iter()
        .map(|g| mob_geometry::point(&g["members"][0]))
        .collect::<Result<_>>()?;
    assert_eq!(
        points.iter().copied().collect::<HashSet<_>>().len(),
        points.len()
    );
    assert_eq!(
        points
            .iter()
            .map(|p| (p[0] / 8, p[1] / 8))
            .collect::<HashSet<_>>(),
        HashSet::from([(0, 0), (0, 1), (1, 0), (1, 1)])
    );
    assert!(points
        .iter()
        .any(|p| (3..=12).contains(&p[0]) && (3..=12).contains(&p[1])));
    assert!(
        points
            .iter()
            .map(|p| (p[0] / 4, p[1] / 4))
            .collect::<HashSet<_>>()
            .len()
            >= 10
    );
    assert!(points.iter().all(|p| cells.contains(p)));
    durable_unchanged(&f, &groups).await?;
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn multi_member_groups_preserve_health_stages_membership_and_reserved_actors() -> Result<()> {
    let f = Fixture::new().await?;
    let map = 999941i32;
    let (cells, edges) = square(24, &[0]);
    geometry(&f, map, &cells, &edges).await?;
    let mut groups = Vec::new();
    for i in 0..12 {
        groups.push(
            install(
                &f,
                map,
                i + 1,
                "available",
                &roster(map, i + 1, (i % 4) * 4, i / 4, 4),
            )
            .await?,
        );
    }
    groups.push(install(&f, map, 100, "fighting", &roster(map, 100, 12, 12, 1)).await?);
    groups.push(install(&f, map, 101, "defeated", &roster(map, 101, 15, 15, 1)).await?);
    let reserved = roster(map, 200, 23, 23, 1);
    let resource = json!({"map_id":map,"instance_id":0});
    f.ctx.db.get().await?.execute("INSERT INTO planting_growth_outbox(published,resource,group_payload) VALUES(false,$1,$2)",&[&resource,&json!({"key":[map,0,200],"members":reserved})]).await?;
    let moves = prepare(&f, map, "multi-native-groups").await?;
    assert!(!moves
        .iter()
        .any(|m| m["group_id"] == 100 || m["group_id"] == 101));
    for movement in &moves {
        connected_native_roster(movement, &edges)?;
    }
    let final_groups = final_groups(&groups, &moves);
    let mut claimed = HashSet::new();
    for group in final_groups.iter().filter(|g| g["status"] != "defeated") {
        for member in group["members"].as_array().unwrap() {
            let point = mob_geometry::point(member)?;
            assert!(claimed.insert(point));
            assert_ne!(point, [23, 23, 0]);
            assert!(cells.contains(&point));
        }
    }
    assert_eq!(&final_groups[12..], &groups[12..]);
    durable_unchanged(&f, &groups).await?;
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn unplaceable_roster_waits_without_inventing_cells_or_losing_members() -> Result<()> {
    let f = Fixture::new().await?;
    let map = 999942i32;
    geometry(&f, map, &[[0, 0, 0]], &[]).await?;
    let group = install(&f, map, 1, "available", &roster(map, 1, 0, 0, 4)).await?;
    assert!(prepare(&f, map, "unplaceable-native").await?.is_empty());
    durable_unchanged(&f, &[group]).await?;
    let db = f.ctx.db.get().await?;
    assert_eq!(
        db.query_one("SELECT status FROM monster_idle_distribution_runs", &[])
            .await?
            .get::<_, String>(0),
        "completed"
    );
    assert_eq!(
        db.query_one("SELECT count(*) FROM monster_idle_distribution_moves", &[])
            .await?
            .get::<_, i64>(0),
        0
    );
    drop(db);
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn large_physical_footprints_fit_native_cells_and_never_intersect() -> Result<()> {
    let f = Fixture::with_radius(1).await?;
    let map = 999943i32;
    let (cells, edges) = square(24, &[0]);
    geometry(&f, map, &cells, &edges).await?;
    let mut groups = Vec::new();
    for i in 0..4 {
        groups.push(
            install(
                &f,
                map,
                i + 1,
                "available",
                &roster(map, i + 1, 2 + 4 * i, 2, 1),
            )
            .await?,
        );
    }
    let moves = prepare(&f, map, "physical-footprints").await?;
    let final_groups = final_groups(&groups, &moves);
    let mut occupied = HashSet::new();
    for group in final_groups {
        let physical = mob_geometry::footprint(mob_geometry::point(&group["members"][0])?, 1)?;
        assert_eq!(physical.len(), 9);
        for point in physical {
            assert!(cells.contains(&point));
            assert!(occupied.insert(point), "Native full footprints intersected");
        }
    }
    durable_unchanged(&f, &groups).await?;
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn stacked_native_heights_keep_each_compact_roster_connected_without_flattening() -> Result<()>
{
    let f = Fixture::new().await?;
    let map = 999944i32;
    let (mut cells, mut edges) = square(8, &[3]);
    cells.extend([[0, 0, 0], [1, 0, 0]]);
    edges.extend([([0, 0, 0], [1, 0, 0]), ([1, 0, 0], [0, 0, 0])]);
    geometry(&f, map, &cells, &edges).await?;
    let mut groups = Vec::new();
    for i in 0..4 {
        let mut members = roster(map, i + 1, (i % 2) * 4, (i / 2) * 4, 3);
        for member in &mut members {
            member["z"] = json!(3);
        }
        groups.push(install(&f, map, i + 1, "available", &members).await?);
    }
    // The lower disconnected native shelf has only two cells: a three-member
    // roster must stay on the actual upper surface, never flatten to z=0.
    let moves = prepare(&f, map, "native-stacked-heights").await?;
    assert!(!moves.is_empty());
    for movement in &moves {
        connected_native_roster(movement, &edges)?;
        let members = movement["moved_members"].as_array().unwrap();
        let z = members[0]["z"].as_i64().unwrap();
        assert_eq!(z, 3);
        assert!(members.iter().all(|m| m["z"].as_i64() == Some(z)));
        assert!(members
            .iter()
            .all(|m| cells.contains(&mob_geometry::point(m).unwrap())));
    }
    final_groups(&groups, &moves);
    durable_unchanged(&f, &groups).await?;
    f.close().await
}

#[tokio::test]
#[ignore = "requires WAKFU_POSTGRES_TEST_URL dedicated test database"]
async fn invalid_preparation_budgets_fail_before_creating_frozen_state() -> Result<()> {
    let f = Fixture::new().await?;
    let snapshot = json!({"world_epoch":"bounded-idle","empty_scopes":[]});
    for limit in [0, 257, usize::MAX] {
        assert!(mob_idle::prepare(&f.ctx, &snapshot, limit).await.is_err());
    }
    assert!(mob_idle::prepare(&f.ctx, &snapshot, 1).await?.is_empty());
    let db = f.ctx.db.get().await?;
    assert_eq!(
        db.query_one("SELECT count(*) FROM monster_idle_distribution_runs", &[])
            .await?
            .get::<_, i64>(0),
        0
    );
    drop(db);
    f.close().await
}
