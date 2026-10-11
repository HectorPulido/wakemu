"""Authenticated panel adapter to the isolated service lifecycle broker."""
import json
import os
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AdminOperations:
    def _control(self, path, data=None):
        token_path = os.environ.get("WAKFU_ADMIN_CONTROL_TOKEN_FILE")
        if not token_path:
            raise ValueError("Service controls are not configured")
        token = Path(token_path).read_text().strip()
        base = os.environ.get(
            "WAKFU_ADMIN_CONTROL_URL", "http://admin-control:8094"
        ).rstrip("/")
        request = Request(
            base + path,
            data=None if data is None else json.dumps(data).encode(),
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                return json.loads(response.read(1024 * 1024))
        except HTTPError as error:
            payload = json.loads(error.read(8192))
            raise ValueError(
                payload.get("error", "Service control request failed")
            ) from None
        except (URLError, TimeoutError):
            raise ValueError(
                "Service controls are unavailable; no restart was confirmed"
            ) from None

    def operation_services(self):
        return self._control("/services")

    def restart_service(self, data, operator):
        if not isinstance(data, dict) or set(data) != {"service", "request_id"}:
            raise ValueError("Service and request_id are required")
        if data["service"] not in {"world", "ecology", "shop", "ai", "profiler"}:
            raise ValueError("Unsupported service")
        if not isinstance(data["request_id"], str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,100}", data["request_id"]
        ):
            raise ValueError("Invalid restart request_id")
        result = self._control("/restart", data)
        with self.store.connection() as db:
            self._audit(
                db,
                operator,
                "service.restart",
                data["service"],
                None,
                dict(
                    request_id=data["request_id"],
                    handle=result["handle"],
                    status=result["status"],
                ),
            )
        return result

    def operation(self, handle):
        if not isinstance(handle, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]{1,100}", handle
        ):
            raise ValueError("Invalid operation handle")
        return self._control("/operations/" + handle)
