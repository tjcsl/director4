#!/bin/bash

# Based on https://github.com/tjcsl/ion/blob/4bc6fa6de88f9b0f4595093aaa25b894da5b50f1/config/provision_vagrant.sh

set -euo pipefail

cd /home/vagrant/director

export DEBIAN_FRONTEND=noninteractive
export PYTHONPATH="/home/vagrant/director/shared${PYTHONPATH:+:$PYTHONPATH}"

# Always show a colored prompt when possible.
sed -i 's/^#\(force_color_prompt=yes\)/\1/' /home/vagrant/.bashrc

# Allow unprivileged user namespaces for unshare --map-root-user (required by orchestrator).
USERNS_SYSCTL=/etc/sysctl.d/99-director-userns.conf
cat <<'EOF' >"$USERNS_SYSCTL"
kernel.unprivileged_userns_clone=1
EOF
if sysctl -a 2>/dev/null | grep -q 'kernel.apparmor_restrict_unprivileged_userns'; then
    echo "kernel.apparmor_restrict_unprivileged_userns=0" >>"$USERNS_SYSCTL"
fi
sysctl -p "$USERNS_SYSCTL" >/dev/null || true

# Ensure the shared directorutil package is importable without symlinks.
cat <<'EOF' >/etc/profile.d/director-pythonpath.sh
export PYTHONPATH="/home/vagrant/director/shared${PYTHONPATH:+:$PYTHONPATH}"
EOF

timedatectl set-timezone America/New_York

## Configure Kerberos
cat <<'EOF' >/etc/krb5.conf
[realms]
    CSL.TJHSST.EDU = {
        admin_server = kdc1.tjhsst.edu
        kdc = kdc2.tjhsst.edu
    }

EOF

## Configure host PostgreSQL
systemctl enable --now postgresql

run_psql() {
    sudo -u postgres psql -v ON_ERROR_STOP=1 -U postgres -d postgres -c "$1"
}

psql_scalar() {
    sudo -u postgres psql -v ON_ERROR_STOP=1 -U postgres -d postgres -Atc "$1"
}

run_psql_db() {
    local dbname=$1
    local sql=$2
    sudo -u postgres psql -v ON_ERROR_STOP=1 -U postgres -d "$dbname" -c "$sql"
}

if [[ $(psql_scalar "SELECT 1 FROM pg_roles WHERE rolname = 'manager';") != 1 ]]; then
    run_psql "CREATE USER manager PASSWORD 'pwd';"
fi
if [[ $(psql_scalar "SELECT 1 FROM pg_database WHERE datname = 'manager';") != 1 ]]; then
    run_psql "CREATE DATABASE manager OWNER manager;"
fi

run_psql "ALTER USER postgres WITH PASSWORD 'pwd';"
run_psql "ALTER DATABASE manager OWNER TO manager;"
run_psql_db manager "GRANT USAGE,CREATE ON SCHEMA public TO manager;"

PG_HBA_FILE=$(sudo -u postgres psql -Atc "SHOW hba_file;")
postgres_config_changed=0
for line in "host sameuser all 127.0.0.1/32 password" "host sameuser all ::1/128 password"; do
    if ! grep -Fxq "$line" "$PG_HBA_FILE"; then
        echo "$line" >>"$PG_HBA_FILE"
        postgres_config_changed=1
    fi
done
if (( postgres_config_changed )); then
    systemctl reload postgresql
fi

## Configure host Redis
redis_config_before=$(sha256sum /etc/redis/redis.conf | awk '{print $1}')
sed -i 's/^#\(bind 127.0.0.1 ::1\)$/\1/' /etc/redis/redis.conf
sed -i 's/^\(protected-mode\) no$/\1 yes/' /etc/redis/redis.conf
redis_config_after=$(sha256sum /etc/redis/redis.conf | awk '{print $1}')
systemctl enable --now redis-server
if [[ $redis_config_before != "$redis_config_after" ]]; then
    systemctl restart redis-server
fi

# RabbitMQ is no longer used. Avoid invoking systemctl for an absent unit.
if systemctl list-unit-files rabbitmq-server.service --no-legend 2>/dev/null | grep -q '^rabbitmq-server.service'; then
    systemctl disable --now rabbitmq-server
fi

## Configure Docker
docker_config_changed=0

install_if_changed() {
    local source_path=$1
    local destination_path=$2
    local mode=$3
    local change_variable=${4:-}

    if ! cmp -s "$source_path" "$destination_path"; then
        install -m "$mode" "$source_path" "$destination_path"
        if [[ -n $change_variable ]]; then
            printf -v "$change_variable" '%s' 1
        fi
    fi
}

install -d /etc/docker
install_if_changed vagrant-config/docker-daemon.json /etc/docker/daemon.json 0644 docker_config_changed

subuid_file=$(mktemp)
subgid_file=$(mktemp)
trap 'rm -f "$subuid_file" "$subgid_file"' EXIT
printf 'vagrant:%s:1\nvagrant:100000:65536\n' "$(id -u vagrant)" >"$subuid_file"
printf 'vagrant:%s:1\nvagrant:100000:65536\n' "$(id -g vagrant)" >"$subgid_file"
install_if_changed "$subuid_file" /etc/subuid 0644 docker_config_changed
install_if_changed "$subgid_file" /etc/subgid 0644 docker_config_changed

systemctl enable --now docker
if (( docker_config_changed )); then
    systemctl restart docker
fi

if [[ $(docker info --format '{{.Swarm.LocalNodeState}}') != active ]]; then
    docker swarm init
fi
if ! docker network inspect director-sites >/dev/null 2>&1; then
    docker network create --scope=swarm --driver=overlay --opt encrypted=true --attachable director-sites
fi
if ! id -nG vagrant | tr ' ' '\n' | grep -Fxq docker; then
    usermod -a -G docker vagrant
fi

## Create persistent data directories
for dir in /data /data/db; do
    install -d -o root -g root "$dir"
done
for dir in /data/sites /data/images /data/db/postgres /data/db/mysql /data/registry /data/nginx /data/nginx/director.d; do
    install -d -o vagrant -g vagrant "$dir"
done

if [[ -d /etc/nginx/director.d ]]; then
    cp -a /etc/nginx/director.d/. /data/nginx/director.d/
fi
install_if_changed vagrant-config/nginx.conf /data/nginx/nginx.conf 0644
chown vagrant:vagrant /data/nginx/nginx.conf

## Create registry certificates
REGISTRY_SERVER_CERT_PATH=/etc/docker/certs.d/localhost:4433
REGISTRY_CERT_PATH=/etc/director-registry/certs
install -d "$REGISTRY_CERT_PATH" "$REGISTRY_SERVER_CERT_PATH"
if [[ ! -f "$REGISTRY_CERT_PATH/localhost.key" || ! -f "$REGISTRY_CERT_PATH/localhost.crt" ]]; then
    openssl req \
        -newkey rsa:4096 -nodes -sha256 \
        -keyout "$REGISTRY_CERT_PATH/localhost.key" \
        -x509 -days 3650 \
        -out "$REGISTRY_CERT_PATH/localhost.crt" \
        -subj "/C=US/ST=DC/L=Washington/CN=localhost" \
        -addext subjectAltName=DNS:localhost
fi
chown -R vagrant:vagrant "$REGISTRY_CERT_PATH"
install_if_changed "$REGISTRY_CERT_PATH/localhost.crt" "$REGISTRY_SERVER_CERT_PATH/ca.crt" 0644

service_fingerprint() {
    printf '%s\0' "$@" | sha256sum | awk '{print $1}'
}

service_exists() {
    docker service inspect "$1" >/dev/null 2>&1
}

ensure_service() {
    local service_name=$1
    local config_salt=$2
    shift 2
    local desired_hash
    local current_hash=""

    desired_hash=$(service_fingerprint "$config_salt" "$@")

    if service_exists "$service_name"; then
        current_hash=$(docker service inspect --format '{{index .Spec.Labels "director4.config-hash"}}' "$service_name")
    fi

    if [[ $current_hash == "$desired_hash" ]]; then
        echo "Keeping $service_name (configuration unchanged)"
        return 0
    fi

    if service_exists "$service_name"; then
        echo "Replacing $service_name (configuration changed)"
        docker service rm "$service_name" >/dev/null
        for _ in {1..100}; do
            service_exists "$service_name" || break
            sleep 0.1
        done
    else
        echo "Creating $service_name"
    fi

    docker service create --detach=true \
        --label "director4.config-hash=$desired_hash" \
        --name "$service_name" \
        "$@" >/dev/null
}

nginx_config_hash=$(sha256sum vagrant-config/nginx.conf | awk '{print $1}')
ensure_service director-nginx "$nginx_config_hash" \
    --replicas=1 \
    --publish published=80,target=80,mode=host \
    --mount type=bind,source=/data/nginx/nginx.conf,destination=/etc/nginx/nginx.conf \
    --mount type=bind,source=/data/nginx/director.d,destination=/etc/nginx/director.d \
    --mount type=bind,source=/data/sites,destination=/data/sites,ro \
    --network director-sites \
    nginx:1.28.1-alpine

if service_exists director-nginx-static; then
    docker service rm director-nginx-static >/dev/null
fi

registry_cert_hash=$(sha256sum "$REGISTRY_CERT_PATH/localhost.crt" | awk '{print $1}')
ensure_service director-registry "$registry_cert_hash" \
    --replicas=1 \
    --mount type=bind,src=/data/registry,dst=/var/lib/registry \
    --mount type=bind,src="$REGISTRY_CERT_PATH",dst=/certs \
    --env REGISTRY_HTTP_ADDR=0.0.0.0:443 \
    --env REGISTRY_HTTP_TLS_CERTIFICATE=/certs/localhost.crt \
    --env REGISTRY_HTTP_TLS_KEY=/certs/localhost.key \
    --env REGISTRY_STORAGE_DELETE_ENABLED=true \
    --publish published=4433,target=443,mode=host \
    --network director-sites \
    registry:2

ensure_service director-postgres v1 \
    --replicas=1 \
    --publish published=5433,target=5432,mode=host \
    --mount type=bind,source=/data/db/postgres,destination=/var/lib/postgresql \
    --env POSTGRES_USER=postgres \
    --env POSTGRES_PASSWORD=pwd \
    --network director-sites \
    postgres:18-alpine

ensure_service director-mysql v1 \
    --replicas=1 \
    --publish published=3307,target=3306,mode=host \
    --mount type=bind,source=/data/db/mysql,destination=/var/lib/mysql \
    --env MYSQL_ROOT_PASSWORD=pwd \
    --network director-sites \
    mariadb:11.8.5

# The four services now initialize concurrently while application dependencies
# and other project state are prepared below.

## Documentation repository
install -d -o vagrant -g vagrant /usr/local/www/director-docs
if [[ -d /usr/local/www/director-docs/.git ]]; then
    (cd /usr/local/www/director-docs && sudo -u vagrant git pull --ff-only)
else
    sudo -u vagrant git clone https://github.com/tjcsl/director4-docs.git /usr/local/www/director-docs
fi

## Shell server keys
SHELL_SERVER_KEYS_DIR=/etc/director-shell-keys
install -d -o vagrant -g vagrant "$SHELL_SERVER_KEYS_DIR"
sudo -u vagrant bash -c "mkdir -p '$SHELL_SERVER_KEYS_DIR/etc/ssh' && ssh-keygen -A -f '$SHELL_SERVER_KEYS_DIR'"

## Application setup
if [[ ! -e manager/director/settings/secret.py ]]; then
    cp manager/director/settings/secret.{sample,py}
fi
if [[ ! -e orchestrator/orchestrator/settings/secret.py ]]; then
    cp orchestrator/orchestrator/settings/secret.{sample,py}
fi
if [[ ! -e shell/shell/settings/secret.py ]]; then
    cp shell/shell/settings/secret.{sample,py}
fi

export PIPENV_DEFAULT_PYTHON=/usr/bin/python3.13
sudo -H -u vagrant ./scripts/install_dependencies.sh

# Ensure directorutil is on sys.path inside each Pipenv environment.
for dname in manager orchestrator router shell; do
    venv_path=$(cd "$dname" && sudo -H -u vagrant pipenv --venv)
    pyver=$("$venv_path/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    site_dir="$venv_path/lib/python$pyver/site-packages"
    pth_file="$site_dir/directorutil.pth"
    if [[ ! -f "$pth_file" ]] || ! grep -Fxq /home/vagrant/director/shared "$pth_file"; then
        echo /home/vagrant/director/shared | sudo -H -u vagrant tee "$pth_file" >/dev/null
    fi
done

if [[ ! -e "$SHELL_SERVER_KEYS_DIR/shell-signing-token-privkey.pem" ]]; then
    (cd manager; sudo -H -u vagrant pipenv run ../scripts/generate-rsa-key.py 4096 \
        "$SHELL_SERVER_KEYS_DIR/shell-signing-token-pubkey.pem" \
        "$SHELL_SERVER_KEYS_DIR/shell-signing-token-privkey.pem")
fi
if [[ ! -e "$SHELL_SERVER_KEYS_DIR/shell-encryption-token-privkey.pem" ]]; then
    (cd manager; sudo -H -u vagrant pipenv run ../scripts/generate-rsa-key.py 4096 \
        "$SHELL_SERVER_KEYS_DIR/shell-encryption-token-pubkey.pem" \
        "$SHELL_SERVER_KEYS_DIR/shell-encryption-token-privkey.pem")
fi

(cd manager; sudo -H -u vagrant pipenv run ./manage.py migrate)

wait_for_services() {
    local service_names=("$@")
    local deadline=$((SECONDS + 240))
    local all_ready
    local service_name
    local replicas

    while (( SECONDS < deadline )); do
        all_ready=1
        service_list=$(docker service ls --format '{{.Name}} {{.Replicas}}')
        for service_name in "${service_names[@]}"; do
            replicas=$(awk -v name="$service_name" '$1 == name {print $2}' <<<"$service_list")
            if [[ $replicas != 1/1 ]]; then
                all_ready=0
                break
            fi
        done
        (( all_ready )) && return 0
        sleep 1
    done

    echo "Docker services did not become ready before the provisioning timeout."
    for service_name in "${service_names[@]}"; do
        docker service ps --no-trunc "$service_name" || true
    done
    return 1
}

wait_for_services director-nginx director-registry director-postgres director-mysql

# Verify Registry TLS/readiness explicitly instead of forcing a second rollout.
curl --fail --silent --show-error \
    --cacert "$REGISTRY_CERT_PATH/localhost.crt" \
    --retry 30 --retry-connrefused --retry-delay 1 --max-time 3 \
    https://localhost:4433/v2/ >/dev/null
echo user | docker login localhost:4433 --username user --password-stdin

# Create or update the database-service entries after the services are ready.
(cd manager; sudo -H -u vagrant pipenv run ./manage.py shell -c "
from director.apps.sites.models import DatabaseHost

DatabaseHost.objects.filter(hostname='127.0.0.1', port__in=[5432, 3306]).delete()

databases = [
    {
        'hostname': 'director-postgres',
        'port': 5432,
        'dbms': 'postgres',
        'admin_hostname': 'localhost',
        'admin_port': 5433,
        'admin_username': 'postgres',
        'admin_password': 'pwd',
    },
    {
        'hostname': 'director-mysql',
        'port': 3306,
        'dbms': 'mysql',
        'admin_hostname': '127.0.0.1',
        'admin_port': 3307,
        'admin_username': 'root',
        'admin_password': 'pwd',
    },
]

for data in databases:
    database_host = DatabaseHost.objects.filter(hostname=data['hostname'], port=data['port'])
    if database_host.exists():
        assert database_host.count() == 1, 'Please delete duplicate DatabaseHosts'
        database_host.update(**data)
    else:
        DatabaseHost.objects.create(**data)
")
