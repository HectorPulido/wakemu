"""Redis-coordinated world scheduler. Only explicitly enabled verified jobs run."""
import json
import os
import threading
import time
import urllib.request
import redis
from wakfu_server.world_scheduler import RedisBackend, Scheduler


def http_action(task):
    def action(occurrence, lease_lost):
        if lease_lost.is_set():
            raise RuntimeError("Task lease lost before request")
        body = dict(task.get("body", {}), request_id=occurrence)
        request = urllib.request.Request(
            task["url"],
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Idempotency-Key": occurrence},
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
                        base + "/" + handle,
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


def main():
    config = json.load(open(os.environ.get("WAKFU_CRON_CONFIG", "/app/config.json")))
    client = redis.Redis.from_url(os.environ["WAKFU_REDIS_URL"], decode_responses=True)
    tasks = {
        name: dict(task, action=http_action(task))
        for name, task in config["tasks"].items()
    }
    scheduler = Scheduler(RedisBackend(client), tasks)
    while True:
        try:
            for result in scheduler.tick():
                print(json.dumps(result), flush=True)
        except Exception as error:
            print(json.dumps({"scheduler_error": str(error)}), flush=True)
        time.sleep(config.get("poll_seconds", 1))


if __name__ == "__main__":
    main()
