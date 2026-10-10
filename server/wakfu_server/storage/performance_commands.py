"""Bounded administrative profiling commands; callers enforce authorization."""
import math
import shlex
import json
from urllib.request import Request, urlopen
from urllib.error import URLError

USAGE = "Uso: !perfil [informe [total|cpu|wait|max]|estado|iniciar [5-120 segundos] [cpu|waits]|detener|reiniciar]"


def external_control(action, payload=None):
    """Only fixed internal service paths are accepted; no caller-provided URL."""
    paths = {"iniciar": "/capture", "detener": "/stop", "estado": "/status"}
    encoded = None if payload is None else json.dumps(payload).encode("utf8")
    request = Request(
        "http://profiler:8092" + paths[action],
        data=encoded,
        headers={"Content-Type": "application/json"},
        method="GET" if action == "estado" else "POST",
    )
    try:
        with urlopen(request, timeout=1.0) as response:
            return json.loads(response.read(65536))
    except (URLError, TimeoutError, OSError, ValueError):
        raise ValueError(
            "Profiler externo apagado o no disponible; inicia el servicio profiler."
        ) from None


def execute_profile_command(
    profiler, text, output_dir=None, *, control=external_control
):
    fields = shlex.split(text)
    args = fields[1:]
    action = args[0].lower() if args else "informe"
    if action == "iniciar" and len(args) <= 3:
        try:
            seconds = float(args[1]) if len(args) >= 2 else 30.0
        except ValueError:
            raise ValueError(USAGE) from None
        if (
            not math.isfinite(seconds)
            or not 5 <= seconds <= 120
            or not seconds.is_integer()
        ):
            raise ValueError(USAGE)
        mode = args[2].lower() if len(args) == 3 else "cpu"
        if mode not in ("cpu", "waits"):
            raise ValueError(USAGE)
        control("iniciar", {"seconds": int(seconds), "mode": mode})
        return "Captura de perfiles solicitada; consulta !perfil estado. Puedes seguir jugando."
    if action == "detener" and len(args) == 1:
        control("detener", {})
        return "Fin de captura solicitado; el informe se escribe en segundo plano."
    if action == "reiniciar" and len(args) == 1:
        profiler.reset()
        return "Contadores de rendimiento reiniciados; los perfiles guardados se conservan."
    if action == "estado" and len(args) == 1:
        status = control("estado")
        return "Profiler externo: " + json.dumps(status, ensure_ascii=False)[:1800]
    if action == "informe" and len(args) <= 2:
        order = args[1].lower() if len(args) == 2 else "total"
        keys = {
            "total": "total_ms",
            "cpu": "cpu_ms",
            "wait": "wait_ms",
            "max": "max_ms",
        }
        if order not in keys:
            raise ValueError(USAGE)
        rows = sorted(
            profiler.snapshot()["features"],
            key=lambda row: row[keys[order]],
            reverse=True,
        )[:6]
        if not rows:
            return "Aún no hay operaciones medidas. Juega y consulta !perfil informe."
        return "Rendimiento (ms, tiempos inclusivos):\n" + "\n".join(
            f"{row['name']}: n={row['count']} total={row['total_ms']:.1f} CPU={row['cpu_ms']:.1f} "
            f"espera~={row['wait_ms']:.1f} CPUmedida={row.get('cpu_measured_calls', row['count'])}/{row['count']} max={row['max_ms']:.1f} p95<={row['p95_ms']:.1f}"
            for row in rows
        )
    raise ValueError(USAGE)
