//! Context regressions migrated from Python for_cell to the production planner.
use super::*;
use wakemu_ecology::planners::planting_intents::native_cell_probability;

#[tokio::test]
async fn native_climate_classes_and_absent_weather_use_published_metadata() -> Result<()> {
    let fixture = Fixture::create().await?;
    let ctx = native_context(&fixture).await?;
    let climates = ctx.catalog.document("resource-climates.json").await?;
    let surfaces = vec![json!({"z":2,"ground_id":515,"region_id":7001})];
    let grounds = json!([{"ground_id":515,"resources":{},"families":{"19":100}}]);
    for (reference, weather, expected) in [
        (76, "STORM", 1.0),
        (76, "LIGHT", 0.8),
        (60, "LIGHT", 1.0),
        (15, "LIGHT", 0.8),
        (37, "HEAVY", 1.0),
        (15, "ABSENT", 1.0),
    ] {
        let resource = json!({"resource_reference":reference,"family_id":19});
        assert_eq!(
            native_cell_probability(&resource, weather, 0.0, &surfaces, 2, &grounds, &climates)?,
            expected,
            "reference={reference}, weather={weather}"
        );
    }
    drop(ctx);
    fixture.cleanup().await
}

#[test]
fn explicit_resource_zero_precedes_native_family_threshold() -> Result<()> {
    let resource = json!({"resource_reference":60,"family_id":19});
    let surfaces = vec![json!({"z":2,"ground_id":515,"region_id":7001})];
    let climates = json!([{"resource_reference":60,"climate":"LIGHT","allowed_weather":["LIGHT"]}]);
    for (grounds, expected) in [
        (
            json!([{"ground_id":515,"resources":{"60":0},"families":{"19":100}}]),
            0.0,
        ),
        (
            json!([{"ground_id":515,"resources":{},"families":{"19":70}}]),
            0.7,
        ),
    ] {
        assert_eq!(
            native_cell_probability(&resource, "LIGHT", 0.0, &surfaces, 2, &grounds, &climates)?,
            expected
        );
    }
    Ok(())
}

#[test]
fn exact_height_must_be_unique_and_probability_context_must_exist() -> Result<()> {
    let resource = json!({"resource_reference":60,"family_id":19});
    let surfaces = vec![
        json!({"z":1,"ground_id":514,"region_id":7000}),
        json!({"z":2,"ground_id":515,"region_id":7001}),
    ];
    let grounds = json!([{"ground_id":515,"resources":{},"families":{"19":100}}]);
    let climates = json!([{"resource_reference":60,"climate":"LIGHT","allowed_weather":["LIGHT"]}]);
    assert_eq!(
        native_cell_probability(&resource, "LIGHT", 0.0, &surfaces, 2, &grounds, &climates)?,
        1.0
    );
    assert!(
        native_cell_probability(&resource, "LIGHT", 0.0, &surfaces, 3, &grounds, &climates)
            .unwrap_err()
            .to_string()
            .contains("surface")
    );
    let duplicate = vec![surfaces[1].clone(), surfaces[1].clone()];
    assert!(
        native_cell_probability(&resource, "LIGHT", 0.0, &duplicate, 2, &grounds, &climates)
            .unwrap_err()
            .to_string()
            .contains("surface")
    );
    assert!(
        native_cell_probability(&resource, "UNKNOWN", 0.0, &surfaces, 2, &grounds, &climates)
            .unwrap_err()
            .to_string()
            .contains("weather")
    );
    assert!(
        native_cell_probability(&resource, "LIGHT", 0.0, &surfaces, 2, &json!([]), &climates)
            .unwrap_err()
            .to_string()
            .contains("context")
    );
    assert!(
        native_cell_probability(&resource, "LIGHT", 0.0, &surfaces, 2, &grounds, &json!([]))
            .unwrap_err()
            .to_string()
            .contains("context")
    );
    Ok(())
}
