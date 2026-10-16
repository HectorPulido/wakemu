"""Cold/warm player snapshots against the real native catalogue in read-only mode."""
import json
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import unittest


class ObjectivesPlayerRuntimeTests(unittest.TestCase):
    @unittest.skipUnless(
        os.environ.get("WAKFU_DATABASE_URL"), "Read-only runtime DSN is required"
    )
    def test_real_http_snapshot_cold_and_warm_stays_under_memory_and_latency_budgets(
        self,
    ):
        script = textwrap.dedent(
            r"""
            import json, os, resource, sys, threading, time, urllib.request
            # Prevent this regression test from reproducing a production OOM.
            memory_limit = 512 * 1024 * 1024
            if sys.platform != 'darwin':
                resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))
            import importlib.util
            from pathlib import Path
            from unittest.mock import patch
            from wakfu_server.objectives import player_auth, player_travel, player_actions, player_views, repository, rankings
            import psycopg
            from psycopg.rows import dict_row
            url = os.environ['WAKFU_DATABASE_URL']
            password_file = os.environ.get('WAKFU_DATABASE_PASSWORD_FILE')
            kwargs = {'row_factory': dict_row}
            if password_file:
                kwargs['password'] = Path(password_file).read_text().strip()
            with psycopg.connect(url, **kwargs) as db:
                mode = db.execute('SHOW transaction_read_only').fetchone()['transaction_read_only']
                assert mode == 'on', 'runtime database must be read-only'
                actor = db.execute('SELECT id,account_id FROM characters WHERE deleted_at IS NULL ORDER BY level DESC,id LIMIT 1').fetchone()
            identity = {'account_id': actor['account_id'], 'character_id': actor['id'], 'generation': None}
            player_travel._CACHE.clear()
            player_travel._GEOMETRY_INDEXES.clear()
            player_travel._TARGETS.clear()
            timings = {}
            def time_function(module, attribute, label):
                original = getattr(module, attribute)
                def timed(*args, **kwargs):
                    start = time.perf_counter()
                    value = original(*args, **kwargs)
                    timings.setdefault(label, []).append(round(time.perf_counter() - start, 4))
                    return value
                setattr(module, attribute, timed)
            for module, attribute, label in (
                (repository, 'list_definitions', 'list_definitions'),
                (repository, 'list_progress', 'list_progress'),
                (rankings, 'list_rankings', 'list_rankings'),
                (player_actions, 'allowed_actions', 'allowed_actions'),
                (player_travel, 'actions', 'travel_actions'),
                (player_travel, '_eligible', 'travel_eligibility'),
                (player_travel, '_geometry_index', 'geometry_index'),
                (player_views, 'decorate_reward_names', 'reward_names'),
                (player_views, 'snapshot', 'snapshot'),
            ):
                time_function(module, attribute, label)
            service_path = Path('server/objectives-service/service.py').resolve()
            spec = importlib.util.spec_from_file_location('readonly_player_service', service_path)
            service = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(service)
            server = service.ThreadingHTTPServer(('127.0.0.1', 0), service.Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            player_auth.authenticate = lambda _db, _token: identity
            address = f'http://127.0.0.1:{server.server_port}/player-api/adventures'
            elapsed = []
            codes = []
            try:
                for _ in range(2):
                    start = time.perf_counter()
                    request = urllib.request.Request(address, headers={'Authorization': 'Bearer ' + 'a' * 43})
                    with urllib.request.urlopen(request, timeout=20) as response:
                        codes.append(response.status)
                        payload = json.loads(response.read())
                    elapsed.append(time.perf_counter() - start)
                    assert payload['actor']['id'] == actor['id']
                    assert 'sections' in payload and 'connection' in payload
            finally:
                server.shutdown()
                server.server_close()
            travel_key = next(action['key'] for action in payload['actions']
                              if action['key'].startswith('travel.map.'))
            player_travel._CACHE.clear()
            player_travel._GEOMETRY_INDEXES.clear()
            player_travel._TARGETS.clear()
            with psycopg.connect(url, **kwargs) as db:
                start = time.perf_counter()
                resolved = player_travel.resolve(db, identity, travel_key)
                direct_resolution_seconds = time.perf_counter() - start
            assert resolved['action_key'] == travel_key
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform == 'darwin':
                rss //= 1024
            component_summary = {
                name: {'calls': len(values), 'total_s': round(sum(values), 3),
                       'max_s': round(max(values), 3)}
                for name, values in timings.items() if values
            }
            print(json.dumps({'cold_seconds': elapsed[0], 'warm_seconds': elapsed[1],
                              'peak_rss_kib': rss, 'http_statuses': codes,
                              'readonly': mode, 'visible_actions': len(payload['actions']),
                              'direct_resolution_seconds': direct_resolution_seconds,
                              'component_seconds': component_summary}))
        """
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        measurements = json.loads(result.stdout.strip().splitlines()[-1])
        print("RUNTIME_SNAPSHOT_METRICS " + json.dumps(measurements, sort_keys=True))
        self.assertEqual(measurements["http_statuses"], [200, 200])
        self.assertEqual(measurements["readonly"], "on")
        self.assertLessEqual(measurements["peak_rss_kib"], 512 * 1024)
        self.assertLess(measurements["cold_seconds"], 10.0, measurements)
        self.assertLess(measurements["warm_seconds"], 2.0, measurements)


if __name__ == "__main__":
    unittest.main()
