#!/usr/bin/env python3
"""Local username/password dialog. Remember a revocable token, not a password."""
import json
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox
import urllib.request
import urllib.error
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "server"))
from wakfu_server.profiles import profile_root

api_url = "http://127.0.0.1:18081"
import os

if os.environ.get("WAKFU_LAUNCHER_CONFIG"):
    api_url = (
        json.loads(Path(os.environ["WAKFU_LAUNCHER_CONFIG"]).read_text())
        .get("api_url", api_url)
        .rstrip("/")
    )
if os.environ.get("WAKFU_SERVER_IPV4"):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "client-tools/dropin"))
    from portable_config import profile_root, settings, pin_dns

    pin_dns(settings())
runtime = profile_root(os.environ.get("WAKFU_LOCAL_PROFILE", "main"))
runtime.mkdir(parents=True, exist_ok=True)
remember_file = runtime / "remember.json"


def request(path, body):
    req = urllib.request.Request(
        api_url + path,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        return json.load(response)


def private_write(path, body):
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(json.dumps(body))


def save(result):
    private_write(runtime / "login-session.json", result)


if remember_file.exists():
    remembered = json.loads(remember_file.read_text())
    try:
        save(request("/remember", {"remember_token": remembered["token"]}))
        raise SystemExit(0)
    except (urllib.error.URLError, ValueError, KeyError):
        pass

window = tk.Tk()
window.title("Wakfu — cuenta local")
window.resizable(False, False)
frame = ttk.Frame(window, padding=24)
frame.grid()
ttk.Label(frame, text=api_url, font=("Arial", 16)).grid(
    row=0, columnspan=2, pady=(0, 20)
)
ttk.Label(frame, text="Usuario").grid(row=1, column=0, sticky="w", padx=(0, 12))
username = ttk.Entry(frame, width=28)
username.grid(row=1, column=1, pady=6)
ttk.Label(frame, text="Contraseña").grid(row=2, column=0, sticky="w", padx=(0, 12))
password = ttk.Entry(frame, show="•", width=28)
password.grid(row=2, column=1, pady=6)
remember = tk.BooleanVar(value=False)
ttk.Checkbutton(frame, text="Recordar acceso en este perfil", variable=remember).grid(
    row=3, columnspan=2, pady=12
)
success = False


def login(register=False):
    global success
    credentials = {"username": username.get(), "password": password.get()}
    try:
        if register:
            request("/register", credentials)
        result = request("/login", dict(credentials, remember=remember.get()))
        save(result)
        if remember.get():
            private_write(
                remember_file,
                {
                    "username": result["account"]["username"],
                    "token": result["remember_token"],
                },
            )
        else:
            remember_file.unlink(missing_ok=True)
        success = True
        window.destroy()
    except urllib.error.HTTPError:
        messagebox.showerror(
            "Acceso local", "Usuario/contraseña inválidos, o la cuenta ya existe."
        )
    except urllib.error.URLError:
        messagebox.showerror(
            "Servidor local",
            "Inicia docker compose up -d desde la raíz del proyecto y vuelve a intentarlo.",
        )


ttk.Button(frame, text="Crear cuenta", command=lambda: login(True)).grid(
    row=4, column=0, pady=10
)
ttk.Button(frame, text="Entrar", command=login).grid(
    row=4, column=1, sticky="e", pady=10
)
window.bind("<Return>", lambda _: login())
username.focus()
window.mainloop()
if not success:
    raise SystemExit(1)
