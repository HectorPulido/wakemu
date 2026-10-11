# Regional weather and forecast implementation

Status: source READY as of 2026-10-11 07:20:14 UTC; automated verification passed.
Deployment and graphical acceptance remain pending.

## Behavior

Migration 118 enables a deterministic local weather model for every materialized
territory whose baseline source is `LOCAL_POLICY`. A weather day lasts 86400
seconds by default. All instances of one physical region calculate the same
weather; storage, forecast and delivery remain scoped to the exact instance.
Different regions have independent deterministic weather. Native snapshots,
operator-authored forecasts and scheduled transitions retain precedence.
An explicit snapshot or transition clears an owned automatic forecast through
the normal durable outbox, preventing stale predictions from remaining visible.

The next five weather days use the same model as the eventual current day.
Winter, spring, summer and autumn use configurable temperature samples and
seasonal precipitation weights. Dry, light, heavy and storm states have explicit
local weights, not reconstructed official rates. Native consumers establish
temperature in their displayed degree scale and wind as a 0..1 ratio displayed
as a percentage. The automatic 13948 encoder now derives temperature and wind
from the same model as the 13895 forecast. Explicit native snapshots remain
untouched.

The verified `ctm.dp → chl.b → bRW` mapping is:

| 13948 field | Native consumer meaning |
| --- | --- |
| Signed byte | Current base temperature |
| Float1 | Current wind ratio; `bRX.windStrengthDescription` displays ratio × 100 |
| Float2/float3 | Daily base minimum/maximum temperature |
| Float4 | Temperature modifier, added to current temperature and ambient range |
| Float5/float6 | Base wind and wind modifier used by ambient classification |

`bRW.toString` labels temperature with a degree symbol and wind `/1.0`.
`bRX.currentTemperature` displays the byte plus float4. Celsius versus another
physical calibration is not established and is not claimed. Forecast seasonal
minimum/maximum rows are clamp bounds in the actual `bRX` display consumer;
they now cover the model's seasonal range instead of flattening forecast
temperatures to zero. Private bytecode evidence is in
`.runtime/local/weather-native-contract.javap.txt` and
`.runtime/local/weather-native-day.javap.txt`. `VerifyRegionalWeather.java`
decodes generated packets through the installed native models.

Current weather, its outbox, the matching 13895 forecast and the simulation cursor
commit in one transaction. A failed forecast rolls back the weather change.
Repeated ticks do not reroll or increment versions. Restart skips missed days
and installs the current day directly. Configuration changes refresh both state
and forecast on the next applicable request or bounded background batch.
First entry resolves only the current scope before returning its weather, so the
following forecast bootstrap is populated without waiting for a global scan.

No client files, spell behavior or combat calculations are changed. Native-mode
planting consumes the current weather through its existing authoritative resolver.
Open planting intentionally keeps its existing SQL probability policy. Growth
modifiers are owned by the separate flora implementation.

## Configuration

`settings.weather_simulation` contains `enabled`, `seed`, `day_seconds`,
`forecast_days`, `weather_weights`, `season_temperature_samples`,
`temperature_variation` and `wind_samples`. All values are validated before use.
Changing the policy needs no restart. Disabling it freezes the existing state
and clears its automatic forecast; explicit transitions continue operating.
Re-enabling installs the current modeled day and a fresh forecast.

The preserved native region 79301 remains independently configured. To opt that
region into the automatic local policy, deliberately change its baseline source
to `LOCAL_POLICY`. A saved native snapshot or explicit scheduled transition sets
`territory_weather_simulation.explicit_override=true`; reset that flag to resume
automation. A separately authored forecast version also overrides automation.
Resume by deleting its forecast policy and simulation cursor for the exact scope,
then resolving the next context. Never copy a captured weather payload across
regions.

Both world and the external ecology worker need complete rebuilt images. The
worker uses the common `advance_due` path. The world bootstrap also advances the
current scope. This report does not claim either image has been deployed.

## Complete manual acceptance after deployment

1. With clients A and B in map 1134, execute `!tp 1134 -23 -143 70` on both.
   Execute `!pos` and confirm territory 79201. Open the weather panel on both:
   current state and five-day forecast must agree.
2. Execute `!tp 1134 -39 -72 47` on A, confirm territory 79301 and reopen the
   panel. Its preserved independent policy must replace or explicitly clear the
   previous forecast. B must keep territory 79201's forecast. Return A to 79201;
   both clients must again agree.
3. Reconnect A. The current region's weather and forecast must be restored on
   first entry. Change region and return once more; no previous-region forecast
   may remain visible.
4. For a complete accelerated lifecycle test, save the policy before changing
   `day_seconds` to 30 through the administrator's settings editor. Keep A and B
   in 79201. Across several model days, both must receive the same changes and
   rolled forecast without reconnecting. The first forecast day's weather must
   become current on the next model day; a day may repeat the previous weather.
   Restore `day_seconds` to 86400 after the test.
5. Restart acceptance, if included in the shared system test: record current
   weather and forecast, perform the authorized full-world/ecology restart and
   reconnect. The same model day must yield the same values, without replaying
   missed states or receiving another region's weather.

## Automatic verification coverage

`test_territory_weather_simulation` covers deterministic regional variation,
seasonal wire encoding, disabled weather weights, invalid policy, future
forecast agreement, restart catch-up, native temperature/wind field mapping, idempotency,
atomic rollback, bounded instance batches, explicit overrides, hot policy
updates, first-entry scope and preservation of explicit transitions. Existing
weather, forecast, region movement and ecology proposal tests remain part of the
required gate.

Luna independently passed the combined planting/weather gate: **109 tests, zero
failures, errors or skips**, in 82.145 seconds. Private execution log:
`.runtime/local/verification-20261011-planting-weather-final.log`.
The installed-client `VerifyRegionalWeather` oracle also passed: actual generated
13948/13895 packets produced coherent current temperature, ambient range, wind,
forecast fields and unclipped seasonal bounds through `ctm`, `bRW`, `bRY` and
`bRX`. This is native component verification, not graphical acceptance.
