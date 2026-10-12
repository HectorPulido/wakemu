-- Preserve the existing scheduler policy; PostgreSQL is the runtime authority.
INSERT INTO settings(name, value) VALUES (
    'cron_scheduler_policy',
    $cron_policy${
  "poll_seconds": 1,
  "tasks": {
    "positions_flush": {
      "enabled": true,
      "interval": 2,
      "lease_seconds": 15,
      "retry_seconds": 2,
      "max_attempts": 3,
      "url": "http://world:18081/test/tasks/positions_flush",
      "body": {}
    },
    "population": {
      "enabled": false,
      "interval": 60,
      "url": "http://world:18081/test/tasks/population",
      "body": {}
    },
    "weather": {
      "enabled": false,
      "interval": 300,
      "url": "http://world:18081/test/tasks/weather",
      "body": {}
    },
    "territory_weather_tick": {
      "enabled": false,
      "interval": 5,
      "lease_seconds": 15,
      "retry_seconds": 2,
      "max_attempts": 3,
      "url": "http://world:18081/test/tasks/territory_weather_tick",
      "body": {}
    },
    "zone_challenges": {
      "enabled": false,
      "interval": 60,
      "url": "http://world:18081/test/tasks/zone_challenges",
      "body": {}
    }
  }
}$cron_policy$::jsonb
) ON CONFLICT(name) DO NOTHING;
