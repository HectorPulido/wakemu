#!/usr/bin/env bash
# Install host prerequisites only; never create or restart a Wakemu stack.
# Official repository procedure: https://docs.docker.com/engine/install/debian/
set -euo pipefail

if [[ "${1:-}" == "--help" ]]; then
    echo 'Usage: sudo bash tools/bootstrap-debian-host.sh'
    echo 'Debian 12/13 only. Installs Python 3, Git, Docker Engine, Buildx and Compose.'
    echo 'Requires root and outbound HTTPS/APT access; does not install game data.'
    exit 0
fi
if [[ $# != 0 ]]; then
    echo 'Unexpected arguments; use --help.' >&2
    exit 2
fi
if [[ $(id -u) != 0 ]]; then
    echo 'Root is required: sudo bash tools/bootstrap-debian-host.sh' >&2
    exit 1
fi
if [[ $(uname -s) != Linux || ! -r /etc/os-release ]]; then
    echo 'This bootstrap supports Debian Linux only.' >&2
    exit 1
fi
# The operating-system file is supplied by the host, not downloaded code.
source /etc/os-release
if [[ "${ID:-}" != debian || ! "${VERSION_CODENAME:-}" =~ ^(bookworm|trixie)$ ]]; then
    echo 'Supported hosts: Debian 12 (bookworm) or 13 (trixie).' >&2
    exit 1
fi

compose_ready() {
    local version major
    version=$(docker compose version --short 2>/dev/null) || return 1
    version=${version#v}
    major=${version%%.*}
    [[ "$major" =~ ^[0-9]+$ ]] && (( major >= 2 ))
}

docker_ready=false
if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
    docker_ready=true
fi
if "$docker_ready" && compose_ready && docker buildx version >/dev/null 2>&1 \
        && command -v python3 >/dev/null && command -v git >/dev/null; then
    echo 'Host prerequisites already ready; no packages or services changed.'
    exit 0
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends python3 git ca-certificates curl
if "$docker_ready" && compose_ready && docker buildx version >/dev/null 2>&1; then
    echo 'Python/Git prerequisites installed; existing Docker configuration preserved.'
    exit 0
fi

# A working Docker daemon is preserved, including its images and volumes.
# On a nonworking installation do not silently remove another runtime.
if ! "$docker_ready"; then
    conflicts=()
    for package in docker.io docker-compose docker-doc docker-buildx podman-docker containerd runc; do
        if [[ $(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true) == 'install ok installed' ]]; then
            conflicts+=("$package")
        fi
    done
    if (( ${#conflicts[@]} )); then
        echo "Existing conflicting runtime packages require explicit operator migration: ${conflicts[*]}" >&2
        exit 1
    fi
fi

install -d -m 0755 /etc/apt/keyrings
if [[ ! -s /etc/apt/keyrings/docker.asc ]]; then
    temporary_key=$(mktemp /etc/apt/keyrings/.docker.XXXXXX)
    trap 'rm -f -- "$temporary_key"' EXIT
    curl --fail --silent --show-error --location \
        --proto '=https' --proto-redir '=https' \
        https://download.docker.com/linux/debian/gpg -o "$temporary_key"
    chmod 0644 "$temporary_key"
    mv -- "$temporary_key" /etc/apt/keyrings/docker.asc
    trap - EXIT
fi
architecture=$(dpkg --print-architecture)
repository=$(cat <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: $VERSION_CODENAME
Components: stable
Architectures: $architecture
Signed-By: /etc/apt/keyrings/docker.asc
EOF
)
if [[ -e /etc/apt/sources.list.d/docker.sources ]]; then
    if [[ $(cat /etc/apt/sources.list.d/docker.sources) != "$repository" ]]; then
        echo 'Existing docker.sources differs; preserve it and resolve the repository configuration explicitly.' >&2
        exit 1
    fi
else
    printf '%s\n' "$repository" > /etc/apt/sources.list.d/docker.sources
    chmod 0644 /etc/apt/sources.list.d/docker.sources
fi
apt-get update
if "$docker_ready"; then
    # Do not upgrade/restart an already working engine to add missing plugins.
    apt-get install -y --no-install-recommends docker-buildx-plugin docker-compose-plugin
else
    apt-get install -y --no-install-recommends \
        docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    if ! docker info >/dev/null 2>&1; then
        systemctl start docker
    fi
fi
docker info >/dev/null
compose_ready
docker buildx version
python3 --version
git --version
echo 'Host prerequisites ready. No Wakemu services or player data were created.'
echo 'Run the project installer separately; continue using sudo if Docker requires root.'
