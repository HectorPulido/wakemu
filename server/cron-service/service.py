"""Redis-coordinated world scheduler. Only explicitly enabled verified jobs run."""
import json
import os
import threading
import time
import urllib.request
from pathlib import Path
import redis
from wakfu_server.world_scheduler import RedisBackend, Scheduler
from wakfu_server.storage.postgres import Database
from wakfu_server.storage.cron_policy import load_policy
from wakfu_server.storage.scheduler_credentials import provision


def http_action(task):
    def action(occurrence, lease_lost):
        if lease_lost.is_set():
            raise RuntimeError("Task lease lost before request")
        token_path = os.environ.get("WAKFU_CRON_API_TOKEN_FILE", "")
        token = (
            Path(token_path).read_text().strip()
            if token_path
            else os.environ.get("WAKFU_CRON_API_TOKEN", "").strip()
        )
        if not token:
            raise RuntimeError("Scheduler API credential is not configured")
        headers = {
            "Content-Type": "application/json",
            "Idempotency-Key": occurrence,
            "Authorization": "Bearer " + token,
        }
        body = dict(task.get("body", {}), request_id=occurrence)
        request = urllib.request.Request(
            task["url"],
            data=json.dumps(body).encode(),
            headers=headers,
        )
        deadline = time.monotonic() + task.get("timeout_seconds", 10)
        with urllib.request.urlopen(
            request, timeout=task.get("timeout_seconds", 10)
        ) as response:
            result = json.load(response)
            if response.status == 202:
                handle = result["handle"]
                base = task.get("poll_url", task["url"])
                while time.monotonic() < deadline:
                    if lease_lost.wait(0.1):
                        raise RuntimeError("Task lease lost")
                    with urllib.request.urlopen(
                        urllib.request.Request(
                            base + "/" + handle,
                            headers={"Authorization": "Bearer " + token},
                        ),
                        timeout=max(0.1, deadline - time.monotonic()),
                    ) as poll:
                        result = json.load(poll)
                    if result["status"] not in ("pending", "running"):
                        break
                else:
                    raise TimeoutError(
                        "Session command remains pending; retry keeps occurrence ID"
                    )
            if result.get("status") in ("failed", "cancelled"):
                raise RuntimeError(result.get("error", "Command failed"))

    return action


def run_scheduler(database, backend):
    scheduler = Scheduler(backend, {})
    poll_seconds = 1
    credential_check_at = 0
    while True:
        try:
            if time.monotonic() >= credential_check_at:
                provision(database, os.environ["WAKFU_CRON_API_TOKEN_FILE"])
                credential_check_at = time.monotonic() + 60
            config = load_policy(database)
            poll_seconds = config["poll_seconds"]
            scheduler.tasks = {
                name: dict(task, action=http_action(task))
                for name, task in config["tasks"].items()
            }
            for result in scheduler.tick():
                print(json.dumps(result), flush=True)
        except Exception as error:
            # Invalid or unavailable DB policy must never execute stale jobs.
            print(json.dumps({"scheduler_error": str(error)}), flush=True)
        time.sleep(poll_seconds)


def main():
    database = Database(
        os.environ["WAKFU_DATABASE_URL"],
        password_file=os.environ.get("WAKFU_DATABASE_PASSWORD_FILE"),
        min_size=1,
        max_size=2,
    )
    try:
        provision(database, os.environ["WAKFU_CRON_API_TOKEN_FILE"], bootstrap=True)
        client = redis.Redis.from_url(
            os.environ["WAKFU_REDIS_URL"], decode_responses=True
        )
        run_scheduler(database, RedisBackend(client))
    finally:
        database.close()


if __name__ == "__main__":
    main()
