"""Thread-owned live game command queues, with pollable completion receipts."""
from collections import deque
import secrets
import threading


class LiveConsole:
    def __init__(self, *, wait_timeout=0.25, receipt_limit=1024):
        self.lock = threading.RLock()
        self.sessions = {}
        self.receipts = {}
        self.keys = {}
        self.wait_timeout = max(0, min(float(wait_timeout), 2.0))
        self.receipt_limit = receipt_limit

    def register(self, character_id, generation, *, name="", account_id=None):
        with self.lock:
            if character_id in self.sessions:
                self.unregister(character_id, self.sessions[character_id]["generation"])
            self.sessions[character_id] = dict(
                character_id=character_id,
                generation=generation,
                name=name,
                account_id=account_id,
                thread=threading.get_ident(),
                queue=deque(),
            )

    def unregister(self, character_id, generation):
        with self.lock:
            session = self.sessions.get(character_id)
            if session is None or session["generation"] != generation:
                return False
            del self.sessions[character_id]
            for handle in session["queue"]:
                receipt = self.receipts[handle]
                receipt.update(
                    status="cancelled",
                    error="La sesión terminó antes de ejecutar el comando",
                )
                receipt["event"].set()
            return True

    def list_sessions(self):
        with self.lock:
            return [
                {key: s[key] for key in ("character_id", "name", "account_id")}
                for s in self.sessions.values()
            ]

    def poll(self, handle):
        with self.lock:
            receipt = self.receipts.get(handle)
            if receipt is None:
                raise ValueError("Comando desconocido o resultado caducado")
            return {
                key: value
                for key, value in receipt.items()
                if key
                not in (
                    "event",
                    "generation",
                    "command",
                    "request_id",
                    "authorize",
                    "executor",
                    "delegated_by",
                )
            }

    def submit(
        self,
        character_id,
        command,
        *,
        request_id=None,
        requester_account_id=None,
        authorize=None,
        executor=None,
        delegated_by=None,
        expected_generation=None,
    ):
        if (
            type(character_id) is not int
            or not isinstance(command, str)
            or not command.startswith("!")
            or len(command) > 2048
        ):
            raise ValueError("Comando inválido")
        if request_id is not None and (
            not isinstance(request_id, str) or not 1 <= len(request_id) <= 128
        ):
            raise ValueError("Identificador de petición inválido")
        with self.lock:
            session = self.sessions.get(character_id)
            if session is None:
                raise ValueError("El personaje no tiene una sesión conectada")
            if (
                expected_generation is not None
                and session["generation"] != expected_generation
            ):
                raise ValueError("La sesión de destino cambió; repite el comando")
            key = (
                (requester_account_id, character_id, session["generation"], request_id)
                if request_id
                else None
            )
            previous = self.keys.get(key) if key else None
            if previous:
                receipt = self.receipts[previous]
                if receipt["command"] != command:
                    raise ValueError("Identificador reutilizado para otro comando")
                handle = previous
            else:
                # Evict only completed receipts; pending work must stay addressable.
                while len(self.receipts) >= self.receipt_limit:
                    old = next(
                        (h for h, r in self.receipts.items() if r["event"].is_set()),
                        None,
                    )
                    if old is None:
                        raise ValueError("Cola de comandos llena")
                    del self.receipts[old]
                    self.keys = {k: h for k, h in self.keys.items() if h != old}
                handle = secrets.token_urlsafe(18)
                receipt = dict(
                    handle=handle,
                    character_id=character_id,
                    requester_account_id=requester_account_id,
                    authorize=authorize,
                    executor=executor,
                    delegated_by=delegated_by,
                    status="pending",
                    command=command,
                    generation=session["generation"],
                    event=threading.Event(),
                )
                self.receipts[handle] = receipt
                if key:
                    self.keys[key] = handle
                session["queue"].append(handle)
            event = receipt["event"]
            same_thread = session["thread"] == threading.get_ident()
        if not same_thread:
            event.wait(self.wait_timeout)
        return self.poll(handle)

    def drain(self, character_id, generation, execute, *, limit=8):
        count = 0
        while count < limit:
            with self.lock:
                session = self.sessions.get(character_id)
                if session is None or session["generation"] != generation:
                    return count
                if session["thread"] != threading.get_ident():
                    raise RuntimeError("Los comandos pertenecen al hilo de sesión")
                if not session["queue"]:
                    return count
                handle = session["queue"].popleft()
                receipt = self.receipts[handle]
                receipt["status"] = "running"
            try:
                if receipt.get("authorize") is not None:
                    receipt["authorize"]()
                executor = receipt.get("executor") or execute
                if receipt.get("delegated_by") is None:
                    result = executor(receipt["command"])
                else:
                    result = executor(
                        receipt["command"], authorized_by=receipt["delegated_by"]
                    )
                update = dict(status="completed", result=result)
            except Exception as error:
                update = dict(status="failed", error=str(error))
            with self.lock:
                receipt.update(update)
                receipt["event"].set()
            count += 1
        return count
