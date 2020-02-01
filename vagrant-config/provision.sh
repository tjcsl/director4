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
# Pip for obvious reasons, tmux and expect for the launch script
apt-get -y install python3-pip tmux expect
# Development files
apt-get -y install python3-dev libssl-dev libcrypto++-dev
sudo pip3 install pipenv fabric


## Helpful utilities
apt-get -y install htop


## Setup PostgreSQL
# Install it
apt-get -y install postgresql postgresql-contrib libpq-dev

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
    if [[ $'\n'"$(</etc/postgresql/10/main/pg_hba.conf)"$'\n' != *$'\n'"$line"$'\n'* ]]; then
        echo "$line" >>/etc/postgresql/10/main/pg_hba.conf
    fi
done
systemctl restart postgresql
systemctl enable postgresql


## Setup MySQL
# Install it
apt-get -y install mysql-server default-libmysqlclient-dev

# Create users
run_mysql() {
    echo "$*" | sudo mysql -u root
}
run_mysql "CREATE USER IF NOT EXISTS 'admin'@'%';"
run_mysql "SET PASSWORD FOR admin@'%' = PASSWORD('pwd');"
run_mysql "GRANT ALL PRIVILEGES ON *.* TO 'admin'@'%' WITH GRANT OPTION;"
run_mysql "FLUSH PRIVILEGES;"


## Setup Redis
apt-get -y install redis
sed -i 's/^#\(bind 127.0.0.1 ::1\)$/\1/' /etc/redis/redis.conf
sed -i 's/^\(protected-mode\) no$/\1 yes/' /etc/redis/redis.conf
systemctl restart redis-server
systemctl enable redis-server


## Setup RabbitMQ
apt-get -y install rabbitmq-server
systemctl start rabbitmq-server
systemctl enable rabbitmq-server
for vhost in 'manager'; do
    if [[ "$(rabbitmqctl list_vhosts)\n" != *$'\n'"$vhost"$'\n'* ]]; then
        rabbitmqctl add_vhost "$vhost"
    fi
    rabbitmqctl set_permissions -p "$vhost" guest '.*' '.*' '.*'
done



## Setup Docker
wget -q -O - 'https://download.docker.com/linux/ubuntu/gpg' | sudo apt-key add -
sed -i "s,^\(deb.*https://download.docker.com/linux/ubuntu.*stable\)$,#\1," /etc/apt/sources.list
echo "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" >/etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce
systemctl start docker
systemctl enable docker
if [[ "$(docker info)" != *'Swarm: active'* ]]; then
    docker swarm init
fi

if docker network ls | grep -vzq 'director-sites'; then
    docker network create --scope=swarm --driver=overlay --opt encrypted=true --attachable director-sites
fi

# Add vagrant user to docker group
usermod -a -G docker vagrant

## Setup Nginx
# We need Nginx installed to check the config, but we don't want it running
apt install -y nginx-full
systemctl disable --now nginx

# Copy config files
cp vagrant-config/nginx.conf /etc/nginx/nginx.conf
mkdir -p /etc/nginx/director.d/
chown vagrant:vagrant /etc/nginx/director.d/

# Setup Docker Swarm service
docker service rm director-nginx || true
docker service create --replicas=1 \
    --publish published=80,target=80 \
    --mount type=bind,source=/etc/nginx/nginx.conf,destination=/etc/nginx/nginx.conf \
    --mount type=bind,source=/etc/nginx/director.d,destination=/etc/nginx/director.d \
    --network director-sites \
    --name director-nginx \
    nginx:latest


## Setup secret.pys
if [[ ! -e manager/director/settings/secret.py ]]; then
    cp manager/director/settings/secret.{sample,py}
fi
if [[ ! -e orchestrator/orchestrator/settings/secret.py ]]; then
    cp orchestrator/orchestrator/settings/secret.{sample,py}
fi

# Migrate database
(cd manager; sudo -H -u vagrant pipenv run ./manage.py migrate)

# Create/update localhost entry
(cd manager; sudo -H -u vagrant pipenv run ./manage.py shell -c "
from director.apps.sites.models import DatabaseHost

databases = [
    {
        'hostname': '127.0.0.1',
        'port': 5432,
        'dbms': 'postgres',
        'admin_username': 'postgres',
        'admin_password': 'pwd',
    },
    {
        'hostname': '127.0.0.1',
        'port': 3306,
        'dbms': 'mysql',
        'admin_username': 'admin',
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
