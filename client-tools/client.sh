#!/bin/bash
set -euo pipefail
tools_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
command="${1:-help}"
if [[ $# -gt 0 ]]; then shift; fi
server_options=()
forwarded=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --server|--config|--api-url)
      if [[ $# -lt 2 ]]; then echo "Missing value for $1" >&2; exit 2; fi
      server_options+=("$1" "$2"); shift 2 ;;
    *) forwarded+=("$1"); shift ;;
  esac
done
if [[ -f "$tools_dir/.env" ]]; then
  while IFS='=' read -r key value; do
    case "$key" in
      WAKFU_SERVER|WAKFU_API_URL) export "$key=$value" ;;
    esac
  done < "$tools_dir/.env"
fi
if [[ ${#server_options[@]} -eq 0 && -n "${WAKFU_SERVER:-}" ]]; then
  server_options+=(--server "$WAKFU_SERVER")
  if [[ -n "${WAKFU_API_URL:-}" ]]; then server_options+=(--api-url "$WAKFU_API_URL"); fi
fi
if [[ ${#server_options[@]} -gt 0 ]]; then
  export WAKFU_LAUNCHER_CONFIG="$(python3 "$tools_dir/runtime/configure-server.py" "${server_options[@]}")"
fi
set -- ${forwarded[@]+"${forwarded[@]}"}
case "$command" in
  launch) exec python3 "$tools_dir/local-launcher.py" "$@" ;;
  play) exec bash "$tools_dir/local-client.sh" "$@" ;;
  check) exec bash "$tools_dir/local-client.sh" --check "$@" ;;
  inspect) exec python3 "$tools_dir/diagnostics/inspect-client.py" "$@" ;;
  package) exec python3 "$tools_dir/packaging/package-mini-launcher.py" "$@" ;;
  patch-particles)
    if [[ $# -eq 0 ]]; then set -- "$tools_dir/../client/contents/scripts/scripts.jar"; fi
    exec python3 "$tools_dir/patches/patch-empty-particle-ids.py" "$@"
    ;;
  help|-h|--help)
    cat <<'HELP'
Usage: bash client-tools/client.sh COMMAND [OPTIONS]

  launch           Open the graphical account launcher.
  play             Start the local client (--profile NAME).
  check            Compile agents and verify network isolation without opening the game.
  inspect          Inspect a running client (--profile NAME state).
  package          Build the portable launcher (--output PATH).
  patch-particles  Apply the optional particle patch to your own client archive.

Place your own compatible game installation in the sibling client/ directory.
Copy client-tools/.env.example to client-tools/.env to set the default server.
Use --server IP_OR_DOMAIN or --config PATH with launch/play/check.
Use --api-url https://DOMAIN:PORT for a custom login API.
See client-tools/README.md for requirements, diagnostics and internal tools.
HELP
    ;;
  *) echo "Unknown command: $command. Use --help." >&2; exit 2 ;;
esac
