#!/bin/bash

# Last Modified: 26 Mar, 2020

# This script conducts a FULL reset of the Vagrant environment
# It focuses on:
# - Removing Docker Swarm services
# - Removing Docker networks
# - Stopping Docker
# - Removing Docker Swarm
# - Removing /data
# - Drops PostgreSQL manager DB

set -e

if [[ "$(sudo dmidecode  -s system-product-name)" != "VirtualBox" ]]
then
    echo "Not in VirtualBox VM."
    echo "Terminating."
    exit 1
fi


echo "WARNING! This is a VERY dangerous command that deletes ALL data in this entire environment."
echo "This includes /data, Docker Swarm, & the PostgreSQL manager DB"

read -p "Are you sure you want to proceed?  " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "Terminating."
    exit 1
fi

echo "Removing Docker services"
docker service rm director-nginx || true
docker service rm director-registry || true
docker service rm director-postgres || true
docker service rm director-mysql || true

echo "Pruning networks"
docker network prune || true

echo
echo "Stopping Docker"
sudo systemctl stop docker || true

echo "Forcibly removing swarm"
sudo rm -rf /var/lib/docker/swarm || echo "Swarm directory deleted already."

echo "Removing /data"
sudo rm -rf /data || echo "/data directory deleted already."

echo "Dropping Manager Database"
for name in 'manager'; do
    sudo -u postgres psql -U postgres -d postgres -c "DROP DATABASE $name;" || echo "Database $name already does not exist."
done
