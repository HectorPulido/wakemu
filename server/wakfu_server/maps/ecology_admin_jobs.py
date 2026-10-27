"""Single-job administrative ecology coordination with isolated preparation."""
import threading
import time
from collections import OrderedDict
from types import MappingProxyType


class EcologyAdminCancelled(RuntimeError):
    """The original administrator session no longer owns future mutations."""


COMMANDS = frozenset(
    (
        "!genesis",
        "!genesis-all",
        "!genesis-all-flora",
        "!nuke",
        "!nuke-all",
        "!nuke-all-flora",
    )
)


def job_message(result):
    handle, status = result["handle"], result["status"]
    if status == "running":
        return f"Ecología #{handle} en preparación. Puedes seguir jugando y viajar; te avisaré al terminar."
    if status == "busy":
        return f"Ya hay una operación de ecología en curso (#{handle}). Espera a que termine antes de iniciar otra."
    scopes = len(result.get("scopes", ()))
    counts = f"{result.get('added', 0)} añadidos, {result.get('removed', 0)} retirados; {scopes} zonas completadas."
    if status == "cancelled":
        return f"Ecología #{handle} interrumpida porque cambió la sesión o el personaje seleccionado. {counts} Las zonas ya completadas se conservan."
    if status == "failed":
        return f"Ecología #{handle} no pudo terminar. {counts} Las zonas ya completadas se conservan; revisa la consola del servidor."
    skipped = len(result.get("failures", ()))
    message = f"Ecología #{handle} terminada: {counts}" + (
        f" {skipped} zonas no pudieron completarse; revisa la consola del servidor."
        if skipped
        else ""
    )
    if result.get("publication_failures"):
        message += " Hay cambios guardados cuya visualización está pendiente; reconecta para refrescar la zona."
    return message


class EcologyAdminJobs:
    def __init__(
        self,
        store,
        groups,
        *,
        players=(),
        coordination=None,
        publish=None,
        validate_actor=None,
        prepare_factory=None,
        clock=time.monotonic,
    ):
        self.store, self.groups = store, groups
        self.players, self.coordination, self.publish = players, coordination, publish
        self.validate_actor, self.prepare_factory = validate_actor, prepare_factory
        self.clock = clock
        self.lock = threading.Lock()
        self.active, self.sequence = None, 0
        self.results = OrderedDict()
        self.closed = False
        self.thread = None
        self.preparer = None

    def _validate(self, db, job):
        with self.lock:
            if self.closed:
                raise EcologyAdminCancelled("Administrative ecology worker is stopping")
        actor = job["character"]
        admin = db.execute(
            "SELECT is_admin FROM accounts WHERE id=%s FOR SHARE",
            (job["account_id"],),
        ).fetchone()
        row = db.execute(
            "SELECT character_id FROM sessions "
            "WHERE account_id=%s AND generation=%s AND expires_at>%s FOR SHARE",
            (job["account_id"], job["generation"], self.store.now()),
        ).fetchone()
        if (
            row is None
            or row["character_id"] != actor["id"]
            or admin is None
            or admin["is_admin"] is not True
        ):
            raise EcologyAdminCancelled("Administrative ecology session changed")
        if self.validate_actor is not None:
            self.validate_actor(db, job)

    def request(self, *, account_id, generation, character, command, notify=None):
        if command not in COMMANDS or character.get("account_id") != account_id:
            raise ValueError("Invalid administrative ecology request")
        actor = MappingProxyType(
            {
                key: character[key]
                for key in ("id", "account_id", "map_id", "instance_id", "x", "y", "z")
            }
        )
        key = (
            account_id,
            generation,
            actor["id"],
            command,
            actor["map_id"],
            actor["instance_id"],
            actor["x"],
            actor["y"],
            actor["z"],
        )
        with self.lock:
            if self.closed:
                raise ValueError(
                    "El servicio de ecología se está cerrando; vuelve a intentarlo después."
                )
            if self.active is not None:
                same = self.active["key"] == key
                if not same:
                    raise ValueError(
                        job_message(
                            dict(handle=self.active["job"]["handle"], status="busy")
                        )
                    )
                result = dict(
                    handle=self.active["job"]["handle"],
                    status="running",
                    coalesced=True,
                )
            else:
                self.sequence += 1
                job = MappingProxyType(
                    dict(
                        handle=f"eco-{self.sequence}",
                        account_id=account_id,
                        generation=generation,
                        character=actor,
                        command=command,
                    )
                )
                run = dict(job=job, key=key, started=self.clock(), notify=notify)
                self.active = run
                self.thread = threading.Thread(
                    target=self._run,
                    args=(run,),
                    name="wakfu-ecology-admin-job",
                    daemon=True,
                )
                self.thread.start()
                result = dict(handle=job["handle"], status="running", coalesced=False)
        return dict(result, message=job_message(result))

    def status(self, handle):
        with self.lock:
            if self.active is not None and self.active["job"]["handle"] == str(handle):
                result = dict(
                    handle=str(handle),
                    status="running",
                    account_id=self.active["job"]["account_id"],
                )
            elif str(handle) in self.results:
                result = dict(self.results[str(handle)])
            else:
                raise ValueError("Operación de ecología desconocida o expirada")
        return dict(result, message=job_message(result))

    def close(self, timeout=3):
        with self.lock:
            self.closed = True
            thread, preparer = self.thread, self.preparer
        child = getattr(preparer, "process", None)
        cancel = getattr(preparer, "cancel", None)
        if callable(cancel):
            cancel()
        elif child is not None and child.poll() is None:
            child.terminate()
        if thread is not None:
            thread.join(timeout=timeout)
        return thread is None or not thread.is_alive()

    def _run(self, run):
        job = run["job"]
        result = dict(
            handle=job["handle"],
            account_id=job["account_id"],
            status="failed",
            added=0,
            removed=0,
            deferred=0,
            cancelled=0,
            scopes=[],
            operation_ids=[],
        )

        def publish(outcome):
            for key in ("added", "removed", "deferred", "cancelled"):
                result[key] += outcome.get(key, 0)
            result["scopes"].extend(outcome.get("scopes", ()))
            result["operation_ids"].extend(outcome.get("operation_ids", ()))
            if self.publish is not None:
                self.publish(dict(outcome, command=job["command"]))

        try:
            from wakfu_server.ecology_admin_worker import PreparationProcess
            from wakfu_server.ecology_admin import execute

            if job["command"].endswith("-flora"):
                from wakfu_server.ecology_flora_admin import execute
            factory = self.prepare_factory or PreparationProcess
            with factory() as prepare:
                with self.lock:
                    self.preparer = prepare
                outcome = execute(
                    self.store,
                    self.groups,
                    job["character"],
                    job["command"],
                    players=self.players,
                    coordination=self.coordination,
                    publish=publish,
                    prepare_scope=prepare,
                    validate_actor=self._validate,
                    job=job,
                )
                # Retain receipts and summaries only, never packet bodies or terrain.
                for key in (
                    "added",
                    "removed",
                    "deferred",
                    "cancelled",
                    "scopes",
                    "operation_ids",
                ):
                    result[key] = outcome.get(
                        key, [] if key in ("scopes", "operation_ids") else 0
                    )
                result["failures"] = [
                    tuple(row[:3]) for row in outcome.get("failures", ())
                ]
                result["publication_failures"] = len(
                    outcome.get("publication_failures", ())
                )
                result["status"] = (
                    "cancelled" if outcome.get("interrupted") else "completed"
                )
                result["worker_pid"] = getattr(prepare, "pid", None)
        except EcologyAdminCancelled:
            result["status"] = "cancelled"
        except Exception as error:
            result["error_type"] = type(error).__name__
            if self.closed:
                result["status"] = "cancelled"
        result["worker_pid"] = getattr(self.preparer, "pid", None)
        result["preparation_failures"] = list(getattr(self.preparer, "failures", ()))
        result["elapsed_ms"] = round((self.clock() - run["started"]) * 1000, 3)
        with self.lock:
            self.preparer = None
            self.results[job["handle"]] = result
            while len(self.results) > 32:
                self.results.popitem(last=False)
            self.active = None
        if run["notify"] is not None:
            try:
                run["notify"](dict(result, message=job_message(result)))
            except Exception:
                pass
