#!/usr/bin/env python3
"""Simple persistent local launcher; game credentials never reach Ankama."""
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]


def settings():
    source = os.environ.get("WAKFU_LAUNCHER_CONFIG")
    config = json.loads(Path(source).read_text()) if source else {}
    base = Path(source).resolve().parent if source else ROOT

    def resolved(value):
        path = Path(value).expanduser()
        return path if path.is_absolute() else base / path

    return dict(
        api_url=config.get(
            "api_url", os.environ.get("WAKFU_LOCAL_API_URL", "http://127.0.0.1:18081")
        ).rstrip("/"),
        runtime_root=resolved(config.get("runtime_root", str(ROOT / ".runtime/local"))),
        runner=resolved(
            config.get("runner", str(ROOT / "client-tools/local-client.sh"))
        ),
        install_root=resolved(config.get("install_root", str(ROOT))),
    )


def profile_root(name="main"):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", name):
        raise ValueError("Invalid local profile name")
    root = settings()["runtime_root"]
    return root if name == "main" else root / "instances" / name


def request(path, body):
    req = urllib.request.Request(
        settings()["api_url"] + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def private_write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w") as output:
        json.dump(body, output)


def authenticate(profile, username, password, remember, *, register=False, api=request):
    if register:
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,32}", username.strip()):
            raise ValueError(
                "Usuario: entre 3 y 32 letras, números, guion o guion bajo."
            )
        if not 8 <= len(password) <= 256:
            raise ValueError(
                "La contraseña de la cuenta nueva debe tener al menos 8 caracteres."
            )
    folder = profile_root(profile)
    folder.mkdir(parents=True, exist_ok=True)
    remembered = folder / "remember.json"
    result = None
    if not password and not register and remembered.exists():
        saved = json.loads(remembered.read_text())
        if not username or username == saved.get("username"):
            result = api("/remember", {"remember_token": saved["token"]})
    if result is None:
        credentials = {"username": username, "password": password}
        if register:
            api("/register", credentials)
        result = api("/login", dict(credentials, remember=remember))
    if remember and result.get("remember_token"):
        private_write(
            remembered,
            {
                "username": result["account"]["username"],
                "token": result["remember_token"],
            },
        )
    elif not remember:
        remembered.unlink(missing_ok=True)
    token_file = folder / ("launcher-session-" + uuid.uuid4().hex + ".json")
    private_write(token_file, result)
    return token_file


def spawn(profile, token_file):
    log = profile_root(profile) / "logs/local-launcher.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "ab", buffering=0) as output:
        process = subprocess.Popen(
            [
                "bash",
                str(settings()["runner"]),
                "--profile",
                profile,
                "--token-file",
                str(token_file),
            ],
            cwd=settings()["install_root"],
            stdout=output,
            stderr=output,
        )
    return process, log


def main():
    import tkinter as tk
    from tkinter import ttk

    window = tk.Tk()
    window.title("Wakfu local")
    window.resizable(False, False)
    frame = ttk.Frame(window, padding=20)
    frame.grid()
    ttk.Label(frame, text="Wakfu · servidor local", font=("Arial", 18)).grid(
        row=0, columnspan=2, pady=(0, 16)
    )
    profile = tk.StringVar(value="main")
    username = tk.StringVar()
    password = tk.StringVar()
    remember = tk.BooleanVar(value=True)
    rows = [
        ("Perfil", profile, False),
        ("Usuario", username, False),
        ("Contraseña", password, True),
    ]
    entries = []
    for row, (label, value, secret) in enumerate(rows, 1):
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 12))
        entry = ttk.Entry(
            frame, textvariable=value, width=30, show="•" if secret else ""
        )
        entry.grid(row=row, column=1, pady=5)
        entries.append(entry)
    ttk.Checkbutton(
        frame, text="Recordar acceso en este perfil", variable=remember
    ).grid(row=4, columnspan=2, pady=10)
    status = tk.StringVar(value="Usa cuentas del servidor local.")
    ttk.Label(frame, textvariable=status, wraplength=350).grid(
        row=6, columnspan=2, pady=10
    )
    events = queue.Queue()
    processes = {}
    busy = False

    def load_profile(*_):
        try:
            saved = json.loads(
                (profile_root(profile.get()) / "remember.json").read_text()
            )
            username.set(saved.get("username", ""))
            password.set("")
        except (OSError, ValueError):
            pass

    entries[0].bind("<FocusOut>", load_profile)
    load_profile()

    def launch(register=False):
        nonlocal busy
        if busy:
            return
        name = profile.get()
        user = username.get()
        secret = password.get()
        keep = remember.get()
        try:
            profile_root(name)
        except ValueError:
            status.set("Perfil: letras, números, guion o guion bajo; máximo 40.")
            return
        if name in processes and processes[name].poll() is None:
            status.set(
                "Ese perfil ya está abierto. Elige otro perfil para otra instancia."
            )
            return
        busy = True
        play.state(["disabled"])
        create.state(["disabled"])
        status.set("Preparando acceso local…")

        def worker():
            token_file = None
            try:
                token_file = authenticate(name, user, secret, keep, register=register)
                process, log = spawn(name, token_file)
                events.put(("started", name, process, log, token_file))
            except urllib.error.HTTPError:
                events.put(
                    (
                        "error",
                        "No se pudo crear la cuenta: ese usuario puede existir ya."
                        if register
                        else "Usuario o contraseña incorrectos. Si es una cuenta nueva, pulsa Crear cuenta y jugar.",
                    )
                )
            except urllib.error.URLError:
                events.put(("error", "No responde la API configurada del servidor."))
            except ValueError as error:
                events.put(("error", str(error)))
            except Exception:
                events.put(
                    (
                        "error",
                        "No se pudo iniciar. Revisa el perfil y los archivos locales.",
                    )
                )

        threading.Thread(target=worker, daemon=True).start()

    play = ttk.Button(frame, text="Jugar", command=launch)
    play.grid(row=5, column=1, sticky="e")
    create = ttk.Button(
        frame, text="Crear cuenta y jugar", command=lambda: launch(True)
    )
    create.grid(row=5, column=0)

    def poll():
        nonlocal busy
        try:
            while True:
                event = events.get_nowait()
                if event[0] == "started":
                    _, name, process, log, token_file = event
                    processes[name] = process
                    password.set("")
                    status.set(f"Arrancando {name}. Registro: {log}")

                    def monitor(p=process, n=name, path=token_file):
                        code = p.wait()
                        path.unlink(missing_ok=True)
                        events.put(("ended", n, code))

                    threading.Thread(target=monitor, daemon=True).start()
                elif event[0] == "error":
                    status.set(event[1])
                elif event[0] == "ended":
                    status.set(
                        f"{event[1]} cerrado."
                        if event[2] == 0
                        else f"{event[1]} terminó con error. Revisa logs/local-launcher.log del perfil."
                    )
                if event[0] in ("started", "error"):
                    busy = False
                    play.state(["!disabled"])
                    create.state(["!disabled"])
        except queue.Empty:
            pass
        window.after(100, poll)

    window.bind("<Return>", lambda _: launch())
    entries[1].focus()
    poll()
    window.mainloop()


if __name__ == "__main__":
    main()
