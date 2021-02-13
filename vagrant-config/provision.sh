#!/bin/bash

# Based on https://github.com/tjcsl/ion/blob/4bc6fa6de88f9b0f4595093aaa25b894da5b50f1/config/provision_vagrant.sh

set -e

cd /home/vagrant/director

## Always show a colored prompt when possible
sed -i 's/^#\(force_color_prompt=yes\)/\1/' /home/vagrant/.bashrc

export DEBIAN_FRONTEND=noninteractive


## System upgrade
sudo apt-get update
sudo apt-get -y dist-upgrade


## Set timezone
timedatectl set-timezone America/New_York


## Dependencies
# Pip for obvious reasons, tmux and expect for the launch script, and krb5-user for kinit
apt-get -y install python3-pip tmux expect krb5-user
# Development files
apt-get -y install python3-dev libssl-dev libcrypto++-dev
sudo pip3 install pipenv fabric


## Helpful utilities
apt-get -y install htop


## Setup PostgreSQL
# Install it
apt-get -y install postgresql postgresql-contrib libpq-dev


## Setup Kerberos
cat <<EOF >/etc/krb5.conf
[realms]
    CSL.TJHSST.EDU = {
        admin_server = kdc1.tjhsst.edu
        kdc = kdc2.tjhsst.edu
    }

EOF

# Create users and databases
run_psql() {
    sudo -u postgres psql -U postgres -d postgres -c "$@"
}
for name in 'manager'; do
    run_psql "CREATE DATABASE $name;" || echo "Database '$name' already exists"
    run_psql "CREATE USER $name PASSWORD 'pwd';" || echo "User '$name' already exists"
done

run_psql "ALTER USER postgres WITH PASSWORD 'pwd';"

# Edit the config and restart
for line in "host sameuser all 127.0.0.1/32 password" "host sameuser all ::1/128 password"; do
    if [[ $'\n'"$(</etc/postgresql/12/main/pg_hba.conf)"$'\n' != *$'\n'"$line"$'\n'* ]]; then
        echo "$line" >>/etc/postgresql/12/main/pg_hba.conf
    fi
done
systemctl restart postgresql
systemctl enable postgresql

## Install MySQL system dependency
apt-get -y install default-libmysqlclient-dev

## Setup Redis
apt-get -y install redis
sed -i 's/^#\(bind 127.0.0.1 ::1\)$/\1/' /etc/redis/redis.conf
sed -i 's/^\(protected-mode\) no$/\1 yes/' /etc/redis/redis.conf
systemctl restart redis-server
systemctl enable redis-server


## Disable RabbitMQ
# Not needed any more
systemctl stop rabbitmq-server || true
systemctl disable rabbitmq-server || true


## Setup Docker
wget -q -O - 'https://download.docker.com/linux/ubuntu/gpg' | sudo apt-key add -
sed -i "s,^\(deb.*https://download.docker.com/linux/ubuntu.*stable\)$,#\1," /etc/apt/sources.list
echo "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" >/etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce
systemctl start docker
systemctl enable docker

# Copy daemon.json and subuid/gid mappings and restart Docker
cp vagrant-config/docker-daemon.json /etc/docker/daemon.json
echo -e "vagrant:$(id -u vagrant):1\nvagrant:100000:65536" >/etc/subuid
echo -e "vagrant:$(id -g vagrant):1\nvagrant:100000:65536" >/etc/subgid
systemctl restart docker

# Setup swarm and main network
if [[ "$(docker info)" != *'Swarm: active'* ]]; then
    docker swarm init
fi

if docker network ls | grep -vzq 'director-sites'; then
    docker network create --scope=swarm --driver=overlay --opt encrypted=true --attachable director-sites
fi

# Add vagrant user to docker group
usermod -a -G docker vagrant


## Create /data directories
for dir in /data /data/db; do
    mkdir -p "$dir"
    chown root:root "$dir"
done

for dir in /data/sites /data/images /data/db/postgres /data/db/mysql /data/registry /data/nginx /data/nginx/director.d; do
    mkdir -p "$dir"
    chown vagrant:vagrant "$dir"
done


## Setup Nginx
# Move old Nginx config files
if [ -d /etc/nginx/director.d ]; then
    mv /etc/nginx/director.d /data/nginx
fi

# Remove Nginx if installed
# We don't need it anymore
apt-get -y remove nginx-full

# Copy main Nginx config file
cp vagrant-config/nginx.conf /data/nginx/nginx.conf

# Set up Docker Swarm nginx service
docker service rm director-nginx || true
docker service create --replicas=1 \
    --publish published=80,target=80 \
    --mount type=bind,source=/data/nginx/nginx.conf,destination=/etc/nginx/nginx.conf \
    --mount type=bind,source=/data/nginx/director.d,destination=/etc/nginx/director.d \
    --mount type=bind,source=/data/sites,destination=/data/sites,ro \
    --network director-sites \
    --name director-nginx \
    nginx:latest

# Remove old "static Nginx" service
docker service rm director-nginx-static || true


## Prune system
docker system prune --force


## Set up registry
REGISTRY_SERVER_CERT_PATH=/etc/docker/certs.d/localhost:4433
REGISTRY_CERT_PATH=/etc/director-registry/certs
# Create self-signed certificates for registry
if ! [ -d "$REGISTRY_CERT_PATH" ]; then
    mkdir -p "$REGISTRY_CERT_PATH"
fi
if ! [ -f "$REGISTRY_CERT_PATH/localhost.key" ]; then
    openssl req \
        -newkey rsa:4096 -nodes -sha256 -keyout $REGISTRY_CERT_PATH/localhost.key \
        -x509 -days 3650 -out $REGISTRY_CERT_PATH/localhost.crt \
        -subj "/C=US/ST=DC/L=Washington/CN=localhost" \
        -addext subjectAltName=DNS:localhost
fi
chown -R vagrant:vagrant "$REGISTRY_CERT_PATH"

# Copy registry certs in place
mkdir -p "$REGISTRY_SERVER_CERT_PATH"
cp "$REGISTRY_CERT_PATH"/localhost.crt "$REGISTRY_SERVER_CERT_PATH"/ca.crt

# Set up Docker Registry service
docker service rm director-registry || true
docker service create --replicas=1 \
    --mount type=bind,src=/data/registry,dst=/var/lib/registry \
    --mount type=bind,src=$REGISTRY_CERT_PATH,dst=/certs \
    -e REGISTRY_HTTP_ADDR=0.0.0.0:443 \
    -e REGISTRY_HTTP_TLS_CERTIFICATE=/certs/localhost.crt \
    -e REGISTRY_HTTP_TLS_KEY=/certs/localhost.key \
    -e REGISTRY_STORAGE_DELETE_ENABLED=true \
    --publish published=4433,target=443 \
    --network director-sites \
    --name director-registry \
    registry:2

# For some reason, provisioning sometimes fails if we don't do this.
docker service update --force director-registry

# Log in
echo "user" | docker login localhost:4433 --username user --password-stdin


## Set up PostgreSQL service
docker service rm director-postgres || true
docker service create --replicas=1 \
    --publish published=5433,target=5432 \
    --mount type=bind,source=/data/db/postgres,destination=/var/lib/postgresql/data \
    --env=POSTGRES_USER=postgres \
    --env=POSTGRES_PASSWORD=pwd \
    --network director-sites \
    --name director-postgres \
    postgres:latest

## Set up MySQL service
docker service rm director-mysql || true
docker service create --replicas=1 \
    --publish published=3307,target=3306 \
    --mount type=bind,source=/data/db/mysql,destination=/var/lib/mysql \
    --env=MYSQL_ROOT_PASSWORD=pwd \
    --network director-sites \
    --name director-mysql \
    mariadb:latest

# Docs repo
mkdir -p /usr/local/www/director-docs
chown vagrant:vagrant /usr/local/www/director-docs
if [ -d /usr/local/www/director-docs/.git ]; then
    (cd /usr/local/www/director-docs && sudo -u vagrant git pull)
else
    sudo -u vagrant git clone https://github.com/tjcsl/director4-docs.git /usr/local/www/director-docs
fi

# Generate shell server keys
SHELL_SERVER_KEYS_DIR="/etc/director-shell-keys"
mkdir -p "$SHELL_SERVER_KEYS_DIR"
chown vagrant:vagrant "$SHELL_SERVER_KEYS_DIR"
sudo -u vagrant bash -c "mkdir -p \"$SHELL_SERVER_KEYS_DIR/etc/ssh\" && ssh-keygen -A -f \"$SHELL_SERVER_KEYS_DIR\""

## Application setup
# Setup secret.pys
if [[ ! -e manager/director/settings/secret.py ]]; then
    cp manager/director/settings/secret.{sample,py}
fi
if [[ ! -e orchestrator/orchestrator/settings/secret.py ]]; then
    cp orchestrator/orchestrator/settings/secret.{sample,py}
fi
if [[ ! -e shell/shell/settings/secret.py ]]; then
    cp shell/shell/settings/secret.{sample,py}
fi

sudo -H -u vagrant ./scripts/install_dependencies.sh

# Create RSA keys for shell server token encryption
if [[ ! -e /etc/director-shell-keys/shell-signing-token-privkey.pem ]]; then
    (cd manager; sudo -H -u vagrant pipenv run ../scripts/generate-rsa-key.py 4096 /etc/director-shell-keys/shell-signing-token-pubkey.pem /etc/director-shell-keys/shell-signing-token-privkey.pem)
fi
if [[ ! -e /etc/director-shell-keys/shell-encryption-token-privkey.pem ]]; then
    (cd manager; sudo -H -u vagrant pipenv run ../scripts/generate-rsa-key.py 4096 /etc/director-shell-keys/shell-encryption-token-pubkey.pem /etc/director-shell-keys/shell-encryption-token-privkey.pem)
fi

# Migrate database
(cd manager; sudo -H -u vagrant pipenv run ./manage.py migrate)

# Create/update localhost database entries
(cd manager; sudo -H -u vagrant pipenv run ./manage.py shell -c "
from director.apps.sites.models import DatabaseHost

remove_databases = [
    {'hostname': '127.0.0.1', 'port': 5432},
    {'hostname': '127.0.0.1', 'port': 3306},
]
for data in remove_databases:
    DatabaseHost.objects.filter(**data).delete()

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
    q = DatabaseHost.objects.filter(hostname=data['hostname'], port=data['port'])
    if q.exists():
        assert q.count() == 1, 'Please delete duplicate DatabaseHosts'
        q.update(**data)
    else:
        DatabaseHost.objects.create(**data)
")
