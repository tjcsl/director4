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
sudo pip3 install pipenv fabric


## Helpful utilities
apt-get -y install htop


## Setup PostgreSQL
# Install it
apt-get -y install postgresql postgresql-contrib libpq-dev

# Create users and databases
run_sql() {
    sudo -u postgres psql -U postgres -d postgres -c "$@"
}
for name in 'manager'; do
    run_sql "CREATE DATABASE $name;" || echo "Database '$name' already exists"
    run_sql "CREATE USER $name PASSWORD 'pwd';" || echo "User '$name' already exists"
done

# Edit the config and restart
for line in "host sameuser all 127.0.0.1/32 password" "host sameuser all ::1/128 password"; do
    if [[ $'\n'"$(</etc/postgresql/10/main/pg_hba.conf)"$'\n' != *$'\n'"$line"$'\n'* ]]; then
        echo "$line" >>/etc/postgresql/10/main/pg_hba.conf
    fi
done
systemctl restart postgresql
systemctl enable postgresql


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
done


## Setup Nginx
apt-get -y install nginx-full
cp vagrant-config/nginx.conf /etc/nginx/nginx.conf
mkdir -p /etc/nginx/director.d/
systemctl restart nginx
systemctl enable nginx


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


# Add vagrant user to docker group
usermod -a -G docker vagrant


## Setup secret.py(s)
if [[ ! -e manager/director/settings/secret.py ]]; then
    cp manager/director/settings/secret.{sample,py}
fi
