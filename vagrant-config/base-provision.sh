#!/bin/bash

set -euo pipefail

if (( EUID != 0 )); then
    echo "base-provision.sh must run as root."
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive

MARKER_DIR=/var/lib/director-provision
MARKER_FILE="$MARKER_DIR/base-system.sha256"
mkdir -p "$MARKER_DIR"

# Hash the system-layer implementation itself. A refreshed base box records the
# same hash, while a meaningful change to this script invalidates the marker.
step_fingerprint=$(sha256sum "$0" | awk '{print $1}')
if [[ -f "$MARKER_FILE" ]] && grep -Fxq "$step_fingerprint" "$MARKER_FILE"; then
    echo "Skipping base system provisioning (content unchanged)"
    exit 0
fi

echo "Provisioning base system layer"

# Avoid interactive service-restart prompts while package operations run.
if [[ -d /etc/needrestart ]]; then
    mkdir -p /etc/needrestart/conf.d
    cat <<'EOF' >/etc/needrestart/conf.d/99-director.conf
$nrconf{restart} = 'l';
EOF
fi

# Bootstrap repository-management tools only when the source image does not
# already provide them. Most current Bento images therefore need one apt index
# refresh for the complete package pipeline rather than three.
bootstrap_packages=()
command -v add-apt-repository >/dev/null 2>&1 || bootstrap_packages+=(software-properties-common)
command -v curl >/dev/null 2>&1 || bootstrap_packages+=(curl)
command -v gpg >/dev/null 2>&1 || bootstrap_packages+=(gnupg)
[[ -f /etc/ssl/certs/ca-certificates.crt ]] || bootstrap_packages+=(ca-certificates)

if (( ${#bootstrap_packages[@]} > 0 )); then
    apt-get update
    apt-get install -y "${bootstrap_packages[@]}"
fi

# Configure all external repositories before the main index refresh.
add-apt-repository -y --no-update ppa:deadsnakes/ppa

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor --yes --batch --no-tty -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# shellcheck disable=SC1091
source /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" \
    >/etc/apt/sources.list.d/docker.list

apt-get update
apt-get -y dist-upgrade

# Keep package installation in one transaction so dependency resolution,
# triggers, and needrestart checks are not repeated for each package group.
apt-get install -y \
    build-essential \
    ca-certificates \
    curl \
    docker-ce \
    expect \
    gnupg \
    htop \
    krb5-user \
    libcrypto++-dev \
    libmariadb-dev \
    libmariadb-dev-compat \
    libpq-dev \
    libssl-dev \
    pkg-config \
    postgresql \
    postgresql-contrib \
    python3.13 \
    python3.13-dev \
    python3.13-venv \
    redis-server \
    software-properties-common \
    tmux

if ! command -v python3.13 >/dev/null 2>&1; then
    echo "python3.13 installation failed; check apt sources and PPA availability."
    exit 1
fi

# Install pipenv and Fabric outside the system Python environment.
python3.13 -m venv /opt/pipenv
/opt/pipenv/bin/pip install --upgrade pip pipenv fabric
ln -sf /opt/pipenv/bin/pipenv /usr/local/bin/pipenv
ln -sf /opt/pipenv/bin/fab /usr/local/bin/fab

systemctl enable postgresql redis-server docker

# Nginx runs in Swarm for this development environment.
if dpkg-query -W -f='${db:Status-Abbrev}' nginx-full 2>/dev/null | grep -q '^ii'; then
    apt-get remove -y nginx-full
fi

printf '%s\n' "$step_fingerprint" >"$MARKER_FILE"

# Packer-created base boxes do not need apt archives; ordinary Vagrant fallback
# provisioning retains them for faster package work inside the active VM.
if [[ ${DIRECTOR4_BASE_BOX_BUILD:-0} == 1 ]]; then
    apt-get clean
fi
